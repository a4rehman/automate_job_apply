from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel

class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    event_type: str
    entity_type: str
    entity_id: Optional[int]
    details: Dict[str, Any]
    ip_address: str
    timestamp: datetime

    class Config:
        from_attributes = True
