# 模块热开关（Hot-Toggle）设计 Spec

**日期：** 2026-03-23
**状态：** Draft
**作者：** Allen + Claude

---

## 1. 概述

### 1.1 背景

Grove 当前支持在 `config.yml` 中通过 `modules.*` 布尔值控制模块启停，但只在启动时生效。用户需要在运行时动态开关模块，无需重启服务。

### 1.2 目标

部署后可通过 HTTP API 或飞书群命令热开关 Grove 的 7 个功能模块，状态持久化到独立文件，重启后保持。

### 1.3 核心决策

| 决策 | 结论 |
|------|------|
| 操作方式 | HTTP API + 飞书群命令 |
| 权限 | 仅 owner（API 用 Bearer token，飞书检查 authority） |
| 持久化 | `.grove/runtime/modules-state.yml`（启动时合并，runtime 优先于 config.yml） |
| disable 行为 | 只停止接收事件，模块实例和内部状态保留，查询方法仍可用 |

---

## 2. EventBus 改动

修改 `grove/core/event_bus.py`：

### 2.1 register() 增加 name 参数

```python
def register(self, module: Any, name: str | None = None) -> None:
```

- `name` 默认取 `type(module).__name__`（向后兼容）
- 新增 `_module_handlers: dict[str, list[tuple[str, Callable]]]` 记录 module_name → [(event_type, handler), ...]

### 2.2 新增 unregister()

```python
def unregister(self, name: str) -> bool:
```

- 从 `_handlers` 中移除该模块的所有 handler
- 从 `_module_handlers` 中删除该模块的记录
- 返回 True/False 表示是否有模块被移除

### 2.3 向后兼容

- 现有的 `register(module)` 调用不受影响
- 现有测试无需修改

---

## 3. ModuleRegistry

新建 `grove/core/module_registry.py`：

### 3.1 数据结构

```python
@dataclass
class ModuleEntry:
    name: str
    instance: Any
    enabled: bool
```

### 3.2 API

| 方法 | 说明 |
|------|------|
| `add(name, instance, enabled)` | 添加模块，enabled 时注册到 EventBus |
| `enable(name) -> bool` | 启用模块（幂等），注册 handler |
| `disable(name) -> bool` | 禁用模块（幂等），注销 handler |
| `get_status() -> list[dict]` | 返回所有模块 `[{name, enabled, type}]` |
| `get(name) -> ModuleEntry | None` | 获取单个模块信息 |

### 3.3 依赖警告

disable `member` 时如果 `task_breakdown` 启用 → 记 warning 日志（不阻止操作）。

---

## 4. Runtime 状态持久化

### 4.1 文件路径

`.grove/runtime/modules-state.yml`（加入 `.gitignore`）

### 4.2 文件格式

```yaml
# 由 Grove 运行时自动维护，不要手动编辑
modules:
  pr_review: false
  doc_sync: false
  # 只记录与 config.yml 不同的值
```

### 4.3 启动时合并逻辑

```
1. 读取 config.yml 的 modules.* → 初始值
2. 如果 .grove/runtime/modules-state.yml 存在 → 覆盖对应字段
3. 最终值传给 registry.add()
```

### 4.4 写入时机

每次 enable/disable 操作后立即写入。

---

## 5. Admin API

新建 `grove/ingress/admin.py`：

### 5.1 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/modules` | 列出所有模块及状态 |
| POST | `/admin/modules/{name}/enable` | 启用模块 |
| POST | `/admin/modules/{name}/disable` | 禁用模块 |

### 5.2 认证

- Bearer token：`Authorization: Bearer <config.admin_token>`
- `config.admin_token` 为空时，admin 路由不挂载（fail-closed）

### 5.3 响应格式

```json
// GET /admin/modules
{
  "modules": [
    {"name": "communication", "enabled": true, "type": "CommunicationModule"},
    {"name": "pr_review", "enabled": false, "type": "PRReviewModule"}
  ]
}

// POST /admin/modules/pr_review/disable
{"name": "pr_review", "enabled": false}
```

### 5.4 错误处理

- 未知模块名 → 404
- 无效 token → 401
- admin_token 未配置 → 路由不存在 → 404

---

## 6. 飞书命令

### 6.1 新增意图

在 `communication/intent_parser.py` 的 `Intent` 枚举新增：

- `TOGGLE_MODULE = "toggle_module"`
- `QUERY_MODULE_STATUS = "query_module_status"`

### 6.2 识别的消息

| 消息示例 | 意图 |
|---------|------|
| "@Grove 关闭 PR 审查" | toggle_module (disable pr_review) |
| "@Grove 开启每日巡检" | toggle_module (enable daily_report) |
| "@Grove 模块状态" | query_module_status |

### 6.3 处理流程

```
lark.message → 意图识别 → TOGGLE_MODULE
  → 权限检查：event.member.authority == "owner"？
  → 否 → 回复"模块开关需要 owner 权限，请联系 {owner_name}"
  → 是 → 解析模块名 + 操作（enable/disable）
       → 调用 registry.enable/disable
       → 写入 runtime state
       → 回复"已关闭「PR 审查」模块" 或 "已开启「每日巡检」模块"
```

### 6.4 模块名映射

飞书命令中的中文名 → config key 映射：

| 中文名 | config key |
|--------|-----------|
| 交互沟通 | communication |
| PRD 生成 | prd_generator |
| 任务拆解 | task_breakdown |
| 每日巡检 | daily_report |
| PR 审查 | pr_review |
| 文档同步 | doc_sync |
| 成员管理 | member |

由 LLM 意图识别自动解析，无需硬编码完整映射（但在 prompt 中提供映射表作为参考）。

---

## 7. Config 改动

`grove/config.py` 的 `GroveConfig` 增加：

```python
admin_token: str = ""  # 空 = admin API 不挂载
```

---

## 8. main.py 改动

### 8.1 模块实例化

所有 7 个模块无条件实例化（当前部分已是如此，扩展到全部）。

### 8.2 注册方式

```python
registry = ModuleRegistry(bus=event_bus)

# 合并 config.yml + runtime state 得到 enabled 值
effective_modules = merge_module_state(config.modules, storage)

registry.add("communication", communication, enabled=effective_modules["communication"])
registry.add("prd_generator", prd_generator, enabled=effective_modules["prd_generator"])
# ... 7 个模块
```

### 8.3 Admin 路由

```python
if config.admin_token:
    app.include_router(create_admin_router(registry, config.admin_token, storage))
```

---

## 9. 文件变更总览

| 文件 | 操作 | 说明 |
|------|------|------|
| `grove/core/event_bus.py` | 修改 | +name 参数 +_module_handlers +unregister() |
| `grove/core/module_registry.py` | 新建 | ModuleRegistry 类 |
| `grove/ingress/admin.py` | 新建 | Admin API 路由 |
| `grove/config.py` | 修改 | +admin_token 字段 |
| `grove/main.py` | 修改 | 用 registry 替代直接注册，合并 runtime state |
| `grove/modules/communication/intent_parser.py` | 修改 | +TOGGLE_MODULE +QUERY_MODULE_STATUS 意图 |
| `grove/modules/communication/handler.py` | 修改 | +处理 toggle/query 命令 |
| `grove/modules/communication/prompts.py` | 修改 | +模块开关意图识别 prompt |
| `.gitignore` | 修改 | +.grove/runtime/ |
| `tests/` | 新建/修改 | EventBus unregister + registry + admin API 测试 |
