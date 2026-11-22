import pytest
import sqlite3
import os
from app.database import init_db, get_connection
from app.models import PurchaseRequestCreate, LineItemCreate, WorkflowAction
from app.service import create_purchase_request, transition_workflow, get_purchase_request

TEST_DB = "test_atomicity.db"

@pytest.fixture(autouse=True)
def setup_teardown_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_atomic_rollback_on_audit_failure():
    """
    Test atomicity: When writing the audit trail fails, the entire transaction
    must be rolled back. The status MUST NOT change to APPROVED.
    """
    conn = get_connection(TEST_DB)
    pr = create_purchase_request(conn, PurchaseRequestCreate(
        requester_name="Citra",
        department="Finance",
        items=[LineItemCreate(item_name="Enterprise Cloud License", quantity=1, unit_price=25000000.0)]
    ))
    
    # Transition to SUBMITTED
    transition_workflow(conn, pr.id, WorkflowAction(actor="Citra", role="requester", action="SUBMIT"))
    current = get_purchase_request(conn, pr.id)
    assert current.status == "SUBMITTED"
    initial_version = current.version
    initial_audit_count = len(current.audit_logs)

    # Attempt to approve with simulated audit failure
    with pytest.raises(RuntimeError) as exc_info:
        transition_workflow(
            conn,
            pr.id,
            WorkflowAction(actor="CFO", role="approver", action="APPROVE", note="Budget OK"),
            test_fail_audit=True
        )
    assert "SIMULATED_AUDIT_FAILURE" in str(exc_info.value)

    # Verify rollback in database: status must STILL be SUBMITTED, version unchanged, no partial audit log
    pr_after_failure = get_purchase_request(conn, pr.id)
    assert pr_after_failure.status == "SUBMITTED"
    assert pr_after_failure.version == initial_version
    assert len(pr_after_failure.audit_logs) == initial_audit_count
    conn.close()
