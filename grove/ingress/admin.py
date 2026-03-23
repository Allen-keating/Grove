"""Admin API for runtime module management."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header

from grove.core.module_registry import ModuleRegistry

logger = logging.getLogger(__name__)


def create_admin_router(registry: ModuleRegistry, admin_token: str) -> APIRouter:
    router = APIRouter(prefix="/admin", tags=["admin"])

    async def verify_token(authorization: Optional[str] = Header(None)):
        if not authorization or authorization != f"Bearer {admin_token}":
            raise HTTPException(status_code=401, detail="Invalid or missing admin token")

    @router.get("/modules", dependencies=[Depends(verify_token)])
    async def list_modules():
        return {"modules": registry.get_status()}

    @router.post("/modules/{name}/enable", dependencies=[Depends(verify_token)])
    async def enable_module(name: str):
        if name not in registry.names:
            raise HTTPException(status_code=404, detail=f"Unknown module: {name}")
        changed = await registry.enable(name)
        entry = registry.get(name)
        return {"name": name, "enabled": entry.enabled, "changed": changed}

    @router.post("/modules/{name}/disable", dependencies=[Depends(verify_token)])
    async def disable_module(name: str):
        if name not in registry.names:
            raise HTTPException(status_code=404, detail=f"Unknown module: {name}")
        changed = await registry.disable(name)
        entry = registry.get(name)
        return {"name": name, "enabled": entry.enabled, "changed": changed}

    return router
