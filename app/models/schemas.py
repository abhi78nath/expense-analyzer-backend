from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Transaction(BaseModel):
    date: str
    transaction_reference: str = Field(..., alias="transaction reference")
    ref_no_chq_no: str = Field(..., alias="ref.no/chq.no")
    credit: Optional[float] = None
    debit: Optional[float] = None
    balance: Optional[float] = None

    class Config:
        populate_by_name = True

class ParseResult(BaseModel):
    filename: str
    total_transactions: int
    transactions: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
