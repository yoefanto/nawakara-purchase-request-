import sqlite3
from app.database import init_db, get_connection
from app.models import PurchaseRequestCreate, LineItemCreate, WorkflowAction
from app.service import create_purchase_request, transition_workflow

def seed():
    init_db("purchase_requests.db")
    conn = get_connection("purchase_requests.db")
    
    # Check if already seeded
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM purchase_requests")
    if cursor.fetchone()[0] > 0:
        print("Database already contains records. Skipping seed.")
        conn.close()
        return

    # Seed 1: PR-2026-0042 in DRAFT status (Exact Nawakara Simulator Sample)
    pr1 = create_purchase_request(conn, PurchaseRequestCreate(
        requester_name="Rina Wijaya",
        department="Information Technology",
        items=[
            LineItemCreate(item_name="Laptop 14\" (i7, 16 GB)", quantity=2, unit_price=15500000.0),
            LineItemCreate(item_name="USB-C docking station", quantity=2, unit_price=1850000.0),
            LineItemCreate(item_name="Monitor 27\"", quantity=1, unit_price=3400000.0),
        ]
    ))
    cursor.execute("UPDATE purchase_requests SET request_number = 'PR-2026-0042' WHERE id = ?", (pr1.id,))
    conn.commit()
    print("Seeded PR 1 (DRAFT): PR-2026-0042 by Rina Wijaya - Grand Total:", pr1.grand_total)

    # Seed 2: Submitted PR awaiting Manager approval
    pr2 = create_purchase_request(conn, PurchaseRequestCreate(
        requester_name="Andi Saputra",
        department="Operations",
        items=[
            LineItemCreate(item_name="Ergonomic Workstation Desk", quantity=4, unit_price=4200000.0),
            LineItemCreate(item_name="High-back Mesh Chair", quantity=4, unit_price=1750000.0)
        ]
    ))
    transition_workflow(conn, pr2.id, WorkflowAction(actor="Andi Saputra", role="requester", action="SUBMIT", note="Office expansion equipment request"))
    print("Seeded PR 2 (SUBMITTED):", pr2.request_number, "by Andi Saputra - Grand Total:", pr2.grand_total)

    conn.close()

if __name__ == "__main__":
    seed()
