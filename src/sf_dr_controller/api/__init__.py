"""FastAPI Modular Control Plane API Package for Snowflake Multi-Cloud DR.

Organized into domain-specific modules:
- state.py: Thread-safe live Snowflake telemetry store and persistent connection manager.
- telemetry.py: /api/status, /api/kpi, /api/diagnostics, /api/ledger, /api/live-logs, /api/drills.
- workflows.py: /api/workflows/stream/{workflow_type} (SSE real-time streaming runner).
- actions.py: /api/actions/* (failover, failback, chaos, ingest, reconcile, probe-now, watchdog).
- onboarding.py: /api/onboarding/* (Zero-Touch credential verification & provisioning).
- reports.py: /api/reports/pdf/latest-migrations (Compliance certificate generation).
- webhooks.py: /api/webhooks/git-push (Git-Ops CI/CD automation hook).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .actions import router as actions_router
from .onboarding import get_onboarding_status
from .onboarding import router as onboarding_router
from .reports import download_audit_pdf_report
from .reports import router as reports_router
from .state import LiveSnowflakeState, _exec_dict, _open_sf_connection, get_git_metadata, state
from .telemetry import get_system_status
from .telemetry import router as telemetry_router
from .webhooks import router as webhooks_router
from .workflows import router as workflows_router
from .workloads import router as workloads_router

logger = logging.getLogger("sf_dr_controller.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    state.start_background_monitor()
    yield
    state.stop_background_monitor()


app = FastAPI(
    title="Snowflake Multi-Cloud DR Control Plane API",
    description="100% Live Snowflake Execution & GitHub-Actions-Style Streaming Telemetry",
    version="3.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def disable_browser_cache(request: Request, call_next):
    response: Response = await call_next(request)
    if not request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


# Include domain routers
app.include_router(telemetry_router)
app.include_router(workflows_router)
app.include_router(workloads_router)
app.include_router(actions_router)
app.include_router(onboarding_router)
app.include_router(reports_router)
app.include_router(webhooks_router)

# Serve Compiled React Static Files
DIST_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"API endpoint /{full_path} not found")
        target = DIST_DIR / full_path
        if target.exists() and target.is_file():
            return FileResponse(target)
        return FileResponse(
            DIST_DIR / "index.html",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )


__all__ = [
    "app",
    "state",
    "LiveSnowflakeState",
    "get_onboarding_status",
    "download_audit_pdf_report",
    "_open_sf_connection",
    "_exec_dict",
    "get_git_metadata",
    "get_system_status",
]
