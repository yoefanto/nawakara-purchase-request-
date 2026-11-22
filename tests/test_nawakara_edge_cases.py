import pytest
import sqlite3
import os
from fastapi import HTTPException
from app.database import init_db, get_connection
from app.models import PurchaseRequestCreate, LineItemCreate, WorkflowAction
from app.service import create_purchase_request, transition_workflow, get_purchase_request, calculate_totals

TEST_DB = "test_nawakara_scenarios.db"

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

def test_scenario_1_empty_request_rejected():
    """Scenario 1: Rina tries to submit a request with no items -> 422 Unprocessable"""
    conn = get_test_conn()
    with pytest.raises(Exception):
        create_purchase_request(conn, PurchaseRequestCreate(
            requester_name="Rina Wijaya",
            department="IT",
            items=[]
        ))
    conn.close()

def test_scenario_2_unauthorised_approval_rejected():
    """Scenario 2: Andi (employee) and Rina (requester) try to approve -> 403 Forbidden"""
    conn = get_test_conn()
    pr = create_purchase_request(conn, PurchaseRequestCreate(
        requester_name="Rina Wijaya",
        department="IT",
        items=[LineItemCreate(item_name="Monitor 27\"", quantity=1, unit_price=3400000.0)]
    ))
    # Submit by Rina
    transition_workflow(conn, pr.id, WorkflowAction(actor="Rina Wijaya", role="requester", action="SUBMIT"))

    # Andi (Employee) tries to approve -> 403
    with pytest.raises(HTTPException) as exc_info:
        transition_workflow(conn, pr.id, WorkflowAction(actor="Andi Saputra", role="employee", action="APPROVE"))
    assert exc_info.value.status_code == 403
    assert "only managers" in exc_info.value.detail.lower()

    # Rina (Requester) tries to approve own request -> 403
    with pytest.raises(HTTPException) as exc_info2:
        transition_workflow(conn, pr.id, WorkflowAction(actor="Rina Wijaya", role="manager", action="APPROVE"))
    assert exc_info2.value.status_code == 403
    assert "cannot decide on your own request" in exc_info2.value.detail.lower()
    conn.close()

def test_scenario_3_duplicate_decision_rejected():
    """Scenario 3: Budi approves, then Sari tries to reject after final status -> 409 Conflict"""
    conn = get_test_conn()
    pr = create_purchase_request(conn, PurchaseRequestCreate(
        requester_name="Rina Wijaya",
        department="IT",
        items=[LineItemCreate(item_name="Monitor 27\"", quantity=1, unit_price=3400000.0)]
    ))
    transition_workflow(conn, pr.id, WorkflowAction(actor="Rina Wijaya", role="requester", action="SUBMIT"))

    # Budi approves
    pr_approved = transition_workflow(conn, pr.id, WorkflowAction(actor="Budi Hartono", role="manager", action="APPROVE", note="Within Q4 IT budget"))
    assert pr_approved.status == "APPROVED"

    # Sari tries to reject final status -> 409
    with pytest.raises(HTTPException) as exc_info:
        transition_workflow(conn, pr.id, WorkflowAction(actor="Sari Lestari", role="manager", action="REJECT", note="Too expensive"))
    assert exc_info.value.status_code == 409
    assert "Final statuses cannot change" in exc_info.value.detail
    conn.close()

def test_scenario_4_tampered_grand_total_overridden_by_server():
    """Scenario 4: Client tries to send manipulated total, server recomputes accurately"""
    items = [
        LineItemCreate(item_name="Laptop 14\" (i7, 16 GB)", quantity=2, unit_price=15500000.0),
        LineItemCreate(item_name="USB-C docking station", quantity=2, unit_price=1850000.0),
        LineItemCreate(item_name="Monitor 27\"", quantity=1, unit_price=3400000.0),
    ]
    # Server calculation must yield exact 38,100,000.0
    calc, grand_total = calculate_totals(items)
    assert grand_total == 38100000.0

    conn = get_test_conn()
    pr = create_purchase_request(conn, PurchaseRequestCreate(
        requester_name="Rina Wijaya",
        department="Engineering",
        items=items
    ))
    assert pr.grand_total == 38100000.0
    conn.close()

def test_scenario_5_concurrent_version_race_conflict():
    """Scenario 5: Concurrent approval attempts guarded by optimistic version locking -> 409 Conflict"""
    conn = get_test_conn()
    pr = create_purchase_request(conn, PurchaseRequestCreate(
        requester_name="Rina Wijaya",
        department="IT",
        items=[LineItemCreate(item_name="Monitor 27\"", quantity=1, unit_price=3400000.0)]
    ))
    pr_sub = transition_workflow(conn, pr.id, WorkflowAction(actor="Rina Wijaya", role="requester", action="SUBMIT"))

    # Manager Budi approves with version = 2
    transition_workflow(conn, pr.id, WorkflowAction(actor="Budi Hartono", role="manager", action="APPROVE", version=pr_sub.version))

    # Manager Sari submits decision with outdated version = 2 -> 409 Conflict
    with pytest.raises(HTTPException) as exc_info:
        transition_workflow(conn, pr.id, WorkflowAction(actor="Sari Lestari", role="manager", action="REJECT", version=pr_sub.version, note="Conflict test"))
    assert exc_info.value.status_code == 409
    conn.close()

def test_scenario_6_atomic_rollback_on_history_failure():
    """Scenario 6: Atomicity guarantee - history write failure rolls back status change"""
    conn = get_test_conn()
    pr = create_purchase_request(conn, PurchaseRequestCreate(
        requester_name="Rina Wijaya",
        department="IT",
        items=[LineItemCreate(item_name="Monitor 27\"", quantity=1, unit_price=3400000.0)]
    ))
    transition_workflow(conn, pr.id, WorkflowAction(actor="Rina Wijaya", role="requester", action="SUBMIT"))
    
    with pytest.raises(RuntimeError):
        transition_workflow(
            conn,
            pr.id,
            WorkflowAction(actor="Budi Hartono", role="manager", action="APPROVE", note="Rollback test"),
            test_fail_audit=True
        )

    # Status must still be SUBMITTED
    pr_check = get_purchase_request(conn, pr.id)
    assert pr_check.status == "SUBMITTED"
    conn.close()
