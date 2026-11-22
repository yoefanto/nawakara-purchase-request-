import sqlite3
from datetime import datetime, timezone
from typing import List, Tuple, Optional
from fastapi import HTTPException
from .models import (
    LineItemCreate,
    PurchaseRequestCreate,
    PurchaseRequestUpdate,
    WorkflowAction,
    PurchaseRequestResponse,
    LineItemResponse,
    AuditLogResponse,
)
from .database import transaction

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def calculate_totals(items: List[LineItemCreate]) -> Tuple[List[dict], float]:
    """Server-side calculation of line totals and grand total."""
    calculated_items = []
    grand_total = 0.0
    for item in items:
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail=f"Invalid quantity for {item.item_name}: must be > 0")
        if item.unit_price < 0:
            raise HTTPException(status_code=400, detail=f"Invalid unit price for {item.item_name}: must be >= 0")
        line_total = round(item.quantity * item.unit_price, 2)
        grand_total += line_total
        calculated_items.append({
            "item_name": item.item_name,
            "quantity": item.quantity,
            "unit_price": round(item.unit_price, 2),
            "line_total": line_total
        })
    return calculated_items, round(grand_total, 2)

def generate_request_number(conn: sqlite3.Connection) -> str:
    date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM purchase_requests WHERE request_number LIKE ?",
        (f"PR-{date_prefix}-%",)
    )
    count = cursor.fetchone()[0] + 1
    return f"PR-{date_prefix}-{count:04d}"

def create_purchase_request(conn: sqlite3.Connection, data: PurchaseRequestCreate) -> PurchaseRequestResponse:
    if not data.items:
        raise HTTPException(status_code=400, detail="Purchase request must contain at least one item")
    
    calc_items, grand_total = calculate_totals(data.items)
    now = utc_now_iso()

    with transaction(conn):
        req_number = generate_request_number(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO purchase_requests (
                request_number, requester_name, department, status, grand_total, version, created_at, updated_at
            ) VALUES (?, ?, ?, 'DRAFT', ?, 1, ?, ?)
            """,
            (req_number, data.requester_name, data.department, grand_total, now, now)
        )
        pr_id = cursor.lastrowid

        for item in calc_items:
            cursor.execute(
                """
                INSERT INTO line_items (request_id, item_name, quantity, unit_price, line_total)
                VALUES (?, ?, ?, ?, ?)
                """,
                (pr_id, item["item_name"], item["quantity"], item["unit_price"], item["line_total"])
            )

        cursor.execute(
            """
            INSERT INTO audit_logs (request_id, actor, action, from_status, to_status, note, created_at)
            VALUES (?, ?, 'CREATE_DRAFT', NULL, 'DRAFT', 'Purchase Request draft created', ?)
            """,
            (pr_id, data.requester_name, now)
        )

    return get_purchase_request(conn, pr_id)

def get_purchase_request(conn: sqlite3.Connection, pr_id: int) -> PurchaseRequestResponse:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM purchase_requests WHERE id = ?", (pr_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Purchase Request ID {pr_id} not found")

    cursor.execute("SELECT * FROM line_items WHERE request_id = ? ORDER BY id ASC", (pr_id,))
    item_rows = cursor.fetchall()
    items = [
        LineItemResponse(
            id=i["id"],
            request_id=i["request_id"],
            item_name=i["item_name"],
            quantity=i["quantity"],
            unit_price=i["unit_price"],
            line_total=i["line_total"]
        ) for i in item_rows
    ]

    cursor.execute("SELECT * FROM audit_logs WHERE request_id = ? ORDER BY id ASC", (pr_id,))
    audit_rows = cursor.fetchall()
    audit_logs = [
        AuditLogResponse(
            id=a["id"],
            request_id=a["request_id"],
            actor=a["actor"],
            action=a["action"],
            from_status=a["from_status"],
            to_status=a["to_status"],
            note=a["note"],
            created_at=a["created_at"]
        ) for a in audit_rows
    ]

    return PurchaseRequestResponse(
        id=row["id"],
        request_number=row["request_number"],
        requester_name=row["requester_name"],
        department=row["department"],
        status=row["status"],
        grand_total=row["grand_total"],
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        items=items,
        audit_logs=audit_logs
    )

def list_purchase_requests(conn: sqlite3.Connection, status: Optional[str] = None) -> List[PurchaseRequestResponse]:
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT id FROM purchase_requests WHERE status = ? ORDER BY id DESC", (status.upper(),))
    else:
        cursor.execute("SELECT id FROM purchase_requests ORDER BY id DESC")
    ids = [row["id"] for row in cursor.fetchall()]
    return [get_purchase_request(conn, pid) for pid in ids]

def update_draft_request(conn: sqlite3.Connection, pr_id: int, data: PurchaseRequestUpdate, actor: str) -> PurchaseRequestResponse:
    current = get_purchase_request(conn, pr_id)
    if current.status != "DRAFT":
        raise HTTPException(status_code=400, detail=f"Cannot edit request in '{current.status}' status. Only DRAFT can be modified.")

    now = utc_now_iso()
    new_requester = data.requester_name or current.requester_name
    new_department = data.department or current.department
    
    with transaction(conn):
        cursor = conn.cursor()
        grand_total = current.grand_total

        if data.items is not None:
            if not data.items:
                raise HTTPException(status_code=400, detail="Purchase request must have at least one line item")
            calc_items, grand_total = calculate_totals(data.items)
            cursor.execute("DELETE FROM line_items WHERE request_id = ?", (pr_id,))
            for item in calc_items:
                cursor.execute(
                    """
                    INSERT INTO line_items (request_id, item_name, quantity, unit_price, line_total)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (pr_id, item["item_name"], item["quantity"], item["unit_price"], item["line_total"])
                )

        cursor.execute(
            """
            UPDATE purchase_requests
            SET requester_name = ?, department = ?, grand_total = ?, version = version + 1, updated_at = ?
            WHERE id = ? AND version = ?
            """,
            (new_requester, new_department, grand_total, now, pr_id, current.version)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=409, detail="Conflict: Record was modified concurrently. Please refresh.")

        cursor.execute(
            """
            INSERT INTO audit_logs (request_id, actor, action, from_status, to_status, note, created_at)
            VALUES (?, ?, 'UPDATE_DRAFT', 'DRAFT', 'DRAFT', 'Draft items or details updated', ?)
            """,
            (pr_id, actor, now)
        )

    return get_purchase_request(conn, pr_id)

def transition_workflow(
    conn: sqlite3.Connection,
    pr_id: int,
    action_data: WorkflowAction,
    test_fail_audit: bool = False
) -> PurchaseRequestResponse:
    """
    Executes state machine transitions with transactional atomicity.
    If audit log write fails, transaction rolls back.
    """
    current = get_purchase_request(conn, pr_id)
    action = action_data.action.upper()
    role = action_data.role.lower()
    
    # State transition rules
    allowed_transitions = {
        "DRAFT": {"SUBMIT": "SUBMITTED"},
        "SUBMITTED": {"APPROVE": "APPROVED", "REJECT": "REJECTED"},
        "APPROVED": {},
        "REJECTED": {},
    }

    if current.status in ("APPROVED", "REJECTED"):
        raise HTTPException(
            status_code=409,
            detail=f"Conflict: request is already {current.status}. Final statuses cannot change."
        )

    next_status = allowed_transitions.get(current.status, {}).get(action)
    if not next_status:
        raise HTTPException(
            status_code=409,
            detail=f"Conflict: request is in {current.status}. Cannot perform '{action}'."
        )

    # Concurrency version check
    if action_data.version is not None and action_data.version != current.version:
        raise HTTPException(
            status_code=409,
            detail=f"Conflict: request changed (expected v{action_data.version}, current v{current.version}, status {current.status}). Reload and try again."
        )

    # Business rule validations
    if action == "SUBMIT":
        if not current.items:
            raise HTTPException(
                status_code=422,
                detail="Unprocessable: a request needs at least one item before it can be submitted."
            )
    elif action in ("APPROVE", "REJECT"):
        if role not in ("approver", "manager"):
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: only managers can {action.lower()} requests."
            )
        if action_data.actor.lower() == current.requester_name.lower():
            raise HTTPException(
                status_code=403,
                detail="Forbidden: you cannot decide on your own request."
            )
        if action == "REJECT" and (not action_data.note or not action_data.note.strip()):
            raise HTTPException(
                status_code=422,
                detail="Unprocessable: a rejection reason is required."
            )

    now = utc_now_iso()

    with transaction(conn):
        cursor = conn.cursor()
        
        # Optimistic concurrency check
        cursor.execute(
            """
            UPDATE purchase_requests
            SET status = ?, version = version + 1, updated_at = ?
            WHERE id = ? AND version = ?
            """,
            (next_status, now, pr_id, current.version)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=409, detail="Concurrency conflict: Request was already updated by another transaction.")

        # Simulate intentional audit failure for atomicity tests
        if test_fail_audit:
            raise RuntimeError("SIMULATED_AUDIT_FAILURE: Testing rollback atomicity.")

        cursor.execute(
            """
            INSERT INTO audit_logs (request_id, actor, action, from_status, to_status, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (pr_id, action_data.actor, action, current.status, next_status, action_data.note or f"Status changed to {next_status}", now)
        )

    return get_purchase_request(conn, pr_id)
