from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class LineItemCreate(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=200, description="Item name or description")
    quantity: int = Field(..., gt=0, description="Quantity must be greater than zero")
    unit_price: float = Field(..., ge=0.0, description="Unit price must be non-negative")

    @field_validator("item_name")
    def clean_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Item name cannot be empty")
        return s

class LineItemResponse(BaseModel):
    id: int
    request_id: int
    item_name: str
    quantity: int
    unit_price: float
    line_total: float

class PurchaseRequestCreate(BaseModel):
    requester_name: str = Field(..., min_length=1, max_length=100)
    department: str = Field(..., min_length=1, max_length=100)
    items: List[LineItemCreate] = Field(..., min_length=1, description="At least one line item is required")

    @field_validator("requester_name", "department")
    def clean_fields(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty")
        return s

class PurchaseRequestUpdate(BaseModel):
    requester_name: Optional[str] = None
    department: Optional[str] = None
    items: Optional[List[LineItemCreate]] = None

class WorkflowAction(BaseModel):
    actor: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., description="Role of the actor: requester or approver/manager")
    action: str = Field(..., description="SUBMIT, APPROVE, or REJECT")
    version: Optional[int] = None
    note: Optional[str] = None

class SimulatorDecision(BaseModel):
    actor: str = Field("Manager", description="Name of manager/actor")
    version: Optional[int] = None
    comment: Optional[str] = None


class AuditLogResponse(BaseModel):
    id: int
    request_id: int
    actor: str
    action: str
    from_status: Optional[str]
    to_status: Optional[str]
    note: Optional[str]
    created_at: str

class PurchaseRequestResponse(BaseModel):
    id: int
    request_number: str
    requester_name: str
    department: str
    status: str
    grand_total: float
    version: int
    created_at: str
    updated_at: str
    items: List[LineItemResponse] = []
    audit_logs: List[AuditLogResponse] = []
