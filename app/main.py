import os
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import sqlite3

from .database import get_connection, init_db
from .models import (
    PurchaseRequestCreate,
    PurchaseRequestUpdate,
    WorkflowAction,
    PurchaseRequestResponse,
)
from .service import (
    create_purchase_request,
    get_purchase_request,
    list_purchase_requests,
    update_draft_request,
    transition_workflow,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Enterprise Purchase Request System",
    description="Assessment Reference TA-PRS - Full-Stack Purchase Request System with line items, state workflow, and transactional audit trail.",
    version="1.0.0",
    lifespan=lifespan
)

def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

# API Endpoints
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "purchase-request-system"}

@app.get("/api/requests", response_model=List[PurchaseRequestResponse])
def get_requests(status: Optional[str] = Query(None), conn: sqlite3.Connection = Depends(get_db)):
    return list_purchase_requests(conn, status=status)

@app.get("/api/requests/{pr_id}", response_model=PurchaseRequestResponse)
def get_request_by_id(pr_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return get_purchase_request(conn, pr_id)

@app.post("/api/requests", response_model=PurchaseRequestResponse, status_code=201)
def create_request(data: PurchaseRequestCreate, conn: sqlite3.Connection = Depends(get_db)):
    return create_purchase_request(conn, data)

@app.put("/api/requests/{pr_id}", response_model=PurchaseRequestResponse)
def update_request(pr_id: int, data: PurchaseRequestUpdate, actor: str = Query("system"), conn: sqlite3.Connection = Depends(get_db)):
    return update_draft_request(conn, pr_id, data, actor=actor)

@app.post("/api/requests/{pr_id}/workflow", response_model=PurchaseRequestResponse)
def workflow_action(
    pr_id: int,
    action: WorkflowAction,
    test_fail_audit: bool = Query(False),
    conn: sqlite3.Connection = Depends(get_db)
):
    try:
        return transition_workflow(conn, pr_id, action, test_fail_audit=test_fail_audit)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount Static UI
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(static_dir, "index.html"))
