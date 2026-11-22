import pytest
import sqlite3
import os
from fastapi import HTTPException
from app.database import init_db, get_connection
from app.models import PurchaseRequestCreate, LineItemCreate, WorkflowAction
from app.service import create_purchase_request, transition_workflow, get_purchase_request

TEST_DB = "test_transitions.db"

@pytest.fixture(autouse=True)
def setup_teardown_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def get_test_conn():
    return get_connection(TEST_DB)

def test_workflow_draft_to_approved():
    conn = get_test_conn()
    pr_data = PurchaseRequestCreate(
        requester_name="Yogi",
        department="Engineering",
        items=[LineItemCreate(item_name="Mechanical Keyboard", quantity=1, unit_price=1200000.0)]
    )
    pr = create_purchase_request(conn, pr_data)
    assert pr.status == "DRAFT"

    # Submit
    action_submit = WorkflowAction(actor="Yogi", role="requester", action="SUBMIT", note="Please review")
    pr_sub = transition_workflow(conn, pr.id, action_submit)
    assert pr_sub.status == "SUBMITTED"

    # Approve by Approver
    action_app = WorkflowAction(actor="Director", role="approver", action="APPROVE", note="Approved budget")
    pr_app = transition_workflow(conn, pr.id, action_app)
    assert pr_app.status == "APPROVED"
    assert len(pr_app.audit_logs) == 3
    conn.close()

def test_workflow_rejection_is_irreversible():
    conn = get_test_conn()
    pr_data = PurchaseRequestCreate(
        requester_name="Budi",
        department="Sales",
        items=[LineItemCreate(item_name="Standing Desk", quantity=1, unit_price=4500000.0)]
    )
    pr = create_purchase_request(conn, pr_data)
    
    # Submit
    transition_workflow(conn, pr.id, WorkflowAction(actor="Budi", role="requester", action="SUBMIT"))
    
    # Reject
    pr_rej = transition_workflow(
        conn, pr.id, WorkflowAction(actor="Manager", role="approver", action="REJECT", note="Budget exceeded")
    )
    assert pr_rej.status == "REJECTED"

    # Attempt to approve rejected request -> MUST fail
    with pytest.raises(HTTPException) as exc_info:
        transition_workflow(
            conn, pr.id, WorkflowAction(actor="Director", role="approver", action="APPROVE", note="Overriding reject")
        )
    assert exc_info.value.status_code == 400
    assert "irreversible" in exc_info.value.detail
    conn.close()

def test_requester_cannot_approve():
    conn = get_test_conn()
    pr = create_purchase_request(conn, PurchaseRequestCreate(
        requester_name="Alice",
        department="HR",
        items=[LineItemCreate(item_name="Office Supplies", quantity=5, unit_price=50000.0)]
    ))
    transition_workflow(conn, pr.id, WorkflowAction(actor="Alice", role="requester", action="SUBMIT"))

    # Requester attempting to approve their own request
    with pytest.raises(HTTPException) as exc_info:
        transition_workflow(conn, pr.id, WorkflowAction(actor="Alice", role="requester", action="APPROVE"))
    assert exc_info.value.status_code == 403
    conn.close()
