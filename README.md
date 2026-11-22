# Enterprise Purchase Request System

> **Reference**: Nawakara Talent & Engineering Assessment · Ref. TA-PRS  
> **Status**: Verified & Tested (8 Automated Tests Passing)

A full-stack, enterprise-grade Purchase Request System featuring multi-item requisition, approval workflow state machine, server-side data integrity guarantees, role-based controls, and atomic transactional audit trails.

---

## 1. Architectural Overview & Rationale

```
+--------------------------------------------------------------+
|                  Web Client (HTML5 / Tailwind)               |
|  - Role Switcher (Requester / Approver)                     |
|  - Realtime Total Preview & Dynamic Line Items               |
|  - Approval Actions & Rollback Simulation Test               |
+------------------------------+-------------------------------+
                               | REST API (JSON)
+------------------------------v-------------------------------+
|                      FastAPI Application                     |
|  - Input Validation via Pydantic Schemas                      |
|  - Role-based Access & Policy Enforcement                    |
+------------------------------+-------------------------------+
                               |
+------------------------------v-------------------------------+
|                    Domain Service Layer                      |
|  - Server-side Calculation Engine (Line Total & Grand Total) |
|  - Finite State Machine Workflow Manager                     |
|  - Optimistic Concurrency Control (Version checks)          |
+------------------------------+-------------------------------+
                               | Atomic Transactions
+------------------------------v-------------------------------+
|                Relational Storage (SQLite3)                  |
|  - Tables: purchase_requests, line_items, audit_logs         |
|  - Referential Integrity (Foreign Keys Enabled)              |
|  - ACID Rollback Guarantee on Failure                        |
+--------------------------------------------------------------+
```

### Design Decisions & Trade-Offs

1. **FastAPI & Python 3.12**:
   - Chosen for strong type safety (Pydantic models), automatic schema validation, asynchronous performance, and clear separation of concerns.
2. **SQLite with Strict Foreign Keys**:
   - Zero-configuration relational database with full ACID compliance.
   - `PRAGMA foreign_keys = ON;` is enforced on every connection to maintain relational integrity between requests, line items, and audit logs.
3. **Server-Side Calculation Authority**:
   - Client-supplied line totals and grand totals are completely ignored. The backend recomputes each `line_total = round(quantity * unit_price, 2)` and aggregates `grand_total`.
4. **State Machine Irreversibility**:
   - Once a request reaches `APPROVED` or `REJECTED`, no further modifications or transitions are permitted. A rejected request cannot be approved.
5. **Transactional Audit Trail (Atomicity)**:
   - When a status transition occurs, the database transaction updates the request status and inserts the audit record together. If writing the audit record fails for any reason, the entire transaction is rolled back, preserving the previous status.

---

## 2. Relational Database Schema

### Table: `purchase_requests`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique ID |
| `request_number` | TEXT | UNIQUE NOT NULL | Formatted PR-YYYYMMDD-XXXX |
| `requester_name` | TEXT | NOT NULL | Name of requester |
| `department` | TEXT | NOT NULL | Department name |
| `status` | TEXT | CHECK IN ('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED') | Workflow status |
| `grand_total` | REAL | NOT NULL DEFAULT 0.0 | Calculated grand total |
| `version` | INTEGER | NOT NULL DEFAULT 1 | Optimistic lock counter |
| `created_at` | TEXT | NOT NULL | UTC timestamp (ISO 8601) |
| `updated_at` | TEXT | NOT NULL | UTC timestamp (ISO 8601) |

### Table: `line_items`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique ID |
| `request_id` | INTEGER | NOT NULL, FK -> purchase_requests(id) ON DELETE CASCADE | Parent PR ID |
| `item_name` | TEXT | NOT NULL | Item description |
| `quantity` | INTEGER | CHECK (quantity > 0) | Quantity requisitioned |
| `unit_price` | REAL | CHECK (unit_price >= 0) | Price per unit |
| `line_total` | REAL | NOT NULL | quantity * unit_price |

### Table: `audit_logs`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique ID |
| `request_id` | INTEGER | NOT NULL, FK -> purchase_requests(id) ON DELETE CASCADE | Parent PR ID |
| `actor` | TEXT | NOT NULL | Name of user performing action |
| `action` | TEXT | NOT NULL | Action performed (CREATE, SUBMIT, APPROVE, REJECT) |
| `from_status` | TEXT | NULLABLE | Previous status |
| `to_status` | TEXT | NOT NULL | New status |
| `note` | TEXT | NULLABLE | Reason or comments |
| `created_at` | TEXT | NOT NULL | UTC timestamp (ISO 8601) |

---

## 3. Workflow State Transitions

```
[ New PR ] ---> DRAFT
                  |
                  | [SUBMIT] (Requester or Approver)
                  v
              SUBMITTED
             /         \
 [APPROVE]  /           \  [REJECT]
(Approver) /             \ (Approver)
          v               v
      APPROVED         REJECTED
      (Final)          (Final)
```

- **DRAFT**: Requisition details and line items can be edited or deleted.
- **SUBMITTED**: Locked against edits. Only approvers can review and make a decision.
- **APPROVED**: Final state. Locked.
- **REJECTED**: Final state. Rejection reason required in audit trail. Irreversible.

---

## 4. Edge Cases & Concurrency Handling

1. **Negative or Zero Values**:
   - Handled at Pydantic layer (`quantity > 0`, `unit_price >= 0`) and reinforced with SQLite table CHECK constraints.
2. **Double Approval / Concurrent Review**:
   - Guarded by optimistic concurrency control (`UPDATE ... WHERE id = ? AND version = ?`). If two approvers attempt to approve simultaneously, only the first succeeds; the second receives HTTP 409 Conflict.
3. **Audit Failure Rollback**:
   - Wrapped in atomic transaction block. The UI provides a "Simulate Rollback Failure" button to test and demonstrate this rollback live.
4. **Resubmission Assumption**:
   - In accordance with enterprise audit standards, a `REJECTED` request is permanently archived. To resubmit, a user creates a new PR referencing previous context if necessary.

---

## 5. API Reference & Endpoints

FastAPI generates automatic, interactive OpenAPI documentation. When the server is running, you can explore and test all endpoints interactively at:
- **Interactive Swagger UI**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`

### REST Endpoints Summary

Sistem menyediakan dual-route mapping: rute standar REST API (`/api/requests/...`) dan rute simulator resmi asesmen Nawakara (`/requests/...`):

| Method | Endpoint | Description | Status Code | Role / Rule |
|---|---|---|---|---|
| `GET` | `/requests` atau `/api/requests` | List all purchase requests | `200` | Public / Filterable by `?status=` |
| `GET` | `/requests/{id}` atau `/api/requests/{id}` | Get detail request with items & audit history | `200` / `404` | Public |
| `POST` | `/api/requests` | Create new purchase request (DRAFT) | `201` / `422` | Requester |
| `PUT` | `/requests/{id}` atau `/api/requests/{id}` | Update draft details & line items | `200` / `409` | Allowed only in `DRAFT` status |
| `POST` | `/requests/{id}/submit` | Submit draft for approval review | `200` / `409` / `422` | Requester (requires >= 1 valid item) |
| `POST` | `/requests/{id}/approve` | Approve submitted purchase request | `200` / `403` / `409` | Manager only (requester cannot self-approve) |
| `POST` | `/requests/{id}/reject` | Reject purchase request (final, irreversible) | `200` / `403` / `409` / `422` | Manager only (requires comment/reason) |

#### Standard HTTP Response Codes Handled
- `200 OK`: Aksi berhasil dieksekusi dengan subtotal dan grand total dihitung ulang oleh server.
- `403 Forbidden`: Pemohon mencoba menyetujui request milik sendiri, atau user non-manajer mencoba approve/reject.
- `409 Conflict`: Request sudah bukan Draft saat di-submit, atau request sudah Approved/Rejected (status final), atau terjadi version mismatch concurrency.
- `422 Unprocessable Entity`: Daftar item kosong, nilai kuantitas <= 0, harga < 0, atau alasan penolakan kosong saat reject.
- `500 Internal Server Error`: Kegagalan penulisan audit log yang memicu rollback transaksi database secara atomik.

---

## 6. Running the Application

### Prerequisites
- Python 3.10+ (Tested on Python 3.12)

### Installation
```bash
pip install -r requirements.txt
```

### Start Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser at `http://localhost:8000` to access the interactive web interface.  
Swagger API documentation is available at `http://localhost:8000/docs`.

### Running Automated Tests
```bash
pytest -v
```
All 8 automated test suites verify calculations, workflow transitions, role gates, and atomic rollback guarantees.
