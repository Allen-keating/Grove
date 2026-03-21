# Grove Setup Guide

This guide walks you through creating the required GitHub App and Feishu/Lark App, populating your environment variables, editing the config files, and starting Grove for the first time.

---

## 1. Create a GitHub App

### 1.1 Register the App

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**.
2. Fill in:
   - **GitHub App name:** `Grove-PM` (or any name unique to your org)
   - **Homepage URL:** your repo URL
   - **Webhook URL:** `https://<your-domain>/webhook/github` (can be updated later)
   - **Webhook secret:** generate a random string and save it as `GITHUB_WEBHOOK_SECRET`
3. Set **Repository permissions**:

   | Permission | Level |
   |---|---|
   | Issues | Read & Write |
   | Pull requests | Read & Write |
   | Contents | Read & Write |
   | Projects | Read & Write |
   | Metadata | Read-only (required) |

4. Under **Subscribe to events**, check:
   - `Pull request`
   - `Push`
   - `Issues`
5. Set **Where can this GitHub App be installed?** → `Only on this account` (or `Any account` for public use).
6. Click **Create GitHub App**.

### 1.2 Generate a Private Key

On the App settings page, scroll to **Private keys** → **Generate a private key**. Save the downloaded `.pem` file somewhere safe (e.g., `/secrets/grove.pem`). Set `GITHUB_PRIVATE_KEY_PATH` to that path.

### 1.3 Install the App

1. On the App settings page, click **Install App**.
2. Select your organization or personal account and choose the repositories Grove should access.
3. After installation, note the **Installation ID** from the URL: `github.com/settings/installations/<ID>`. Set this as `GITHUB_INSTALLATION_ID`.

### 1.4 Note the App ID

Back on the App settings page, copy the **App ID** field. Set it as `GITHUB_APP_ID`.

---

## 2. Create a Feishu / Lark App

### 2.1 Create the App

1. Go to [https://open.feishu.cn/app](https://open.feishu.cn/app) (or [https://open.larksuite.com/app](https://open.larksuite.com/app) for Lark).
2. Click **Create custom app**.
3. Give it a name (e.g., `Grove`) and an optional description.
4. On the **Credentials & Basic Info** page, copy **App ID** → `LARK_APP_ID` and **App Secret** → `LARK_APP_SECRET`.

### 2.2 Enable Bot Capabilities

1. Go to **Features → Bot**.
2. Enable the bot. This lets Grove send and receive messages.

### 2.3 Set Permissions

Go to **Permissions & Scopes** and add:

| Scope | Purpose |
|---|---|
| `im:message:send_as_bot` | Send messages |
| `im:message` | Read messages |
| `im:chat` | Access group chats |
| `docx:document` | Create and edit documents |
| `drive:drive` | Access Lark Drive / Docs space |
| `contact:user.base:readonly` | Resolve user info |

### 2.4 Enable Event Subscriptions (WebSocket mode)

1. Go to **Event Subscriptions**.
2. Set **Subscription method** to **Long connection (WebSocket)**. This avoids the need for a public HTTPS callback URL during development.
3. Subscribe to these events:
   - `im.message.receive_v1` — incoming messages
   - `im.message.message_read_v1` — message read receipts (optional)
   - `card.action.trigger` — interactive card button clicks

### 2.5 Publish the App

Click **Version Management & Release → Create Version** then **Apply for release** (self-built apps in an org can be released internally without review).

### 2.6 Get Chat ID and Space ID

- **Chat ID (`chat_id`):** Add Grove's bot to your team group chat. Then call the Lark API `im.v1.chat.list` or inspect incoming webhook events — the `chat_id` field (e.g., `oc_xxxx`) appears in every message event.
- **Space ID (`space_id`):** Go to your Lark Docs space in the browser. The URL contains `/space/<ID>`.

---

## 3. Environment Variables

Copy `.env.example` to `.env` and fill in all values:

```bash
cp .env.example .env
```

```dotenv
# Lark / Feishu
LARK_APP_ID=cli_xxxxxxxxxxxx
LARK_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# GitHub App
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY_PATH=/secrets/grove.pem
GITHUB_INSTALLATION_ID=78901234
GITHUB_WEBHOOK_SECRET=my-random-secret

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

> All values in `.grove/config.yml` that use `${VAR}` syntax are resolved from these environment variables at startup.

---

## 4. Edit Config Files

### `.grove/config.yml`

```yaml
project:
  name: "My Product"        # displayed in reports and PRDs
  repo: "org/repo"          # GitHub repo in owner/name format
  language: "zh-CN"         # response language (zh-CN or en-US)

lark:
  app_id: "${LARK_APP_ID}"
  app_secret: "${LARK_APP_SECRET}"
  chat_id: "oc_xxxx"        # team group chat ID
  space_id: "spc_xxxx"      # Lark Docs space ID

github:
  app_id: "${GITHUB_APP_ID}"
  private_key_path: "${GITHUB_PRIVATE_KEY_PATH}"
  installation_id: "${GITHUB_INSTALLATION_ID}"
  webhook_secret: "${GITHUB_WEBHOOK_SECRET}"

llm:
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-sonnet-4-6"

persona:
  name: "Grove"
  tone: "professional but approachable"
  reminder_intensity: 3     # 1 (gentle) – 5 (persistent)
  proactive_messaging: true

work_hours:
  start: "09:00"
  end: "18:00"
  timezone: "Asia/Shanghai"
  workdays: [1, 2, 3, 4, 5] # Monday=1
```

### `.grove/team.yml`

```yaml
members:
  - github_id: "alice"
    lark_id: "ou_xxxxxxxxxxxxxxxx"
    name: "Alice"
    role: "engineer"          # engineer | lead | owner | designer | qa
    skills: ["backend", "api", "database"]
  - github_id: "bob"
    lark_id: "ou_yyyyyyyyyyyyyyyy"
    name: "Bob"
    role: "lead"
    skills: ["frontend", "ux", "mobile"]
```

---

## 5. Start Grove

### Docker Compose (recommended)

```bash
docker compose up -d
docker compose logs -f grove
```

### Local (development)

```bash
source .venv/bin/activate
export GROVE_DIR=.grove
uvicorn grove.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 6. Verify the Installation

### Health endpoint

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "ok", "lark": "connected", "scheduler": "running"}
```

### Send a test message

In your Lark group chat, mention Grove's bot:

```
@Grove 你好，介绍一下你自己
```

Grove should respond within a few seconds describing its capabilities.

### Check GitHub webhook delivery

In your GitHub App settings → **Advanced → Recent Deliveries**, you should see successful `200` responses for any push or PR event after startup.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `lark: "disconnected"` in health | Wrong `LARK_APP_ID` / `LARK_APP_SECRET` | Check `.env` values |
| `scheduler: "stopped"` | Startup exception — check logs | `docker compose logs grove` |
| GitHub API 401 | Private key path wrong or key expired | Check `GITHUB_PRIVATE_KEY_PATH` |
| No response to Lark messages | Bot not added to chat, or wrong `chat_id` | Add bot to group and update `chat_id` |
| LLM errors | `ANTHROPIC_API_KEY` invalid or quota exceeded | Check key at console.anthropic.com |
