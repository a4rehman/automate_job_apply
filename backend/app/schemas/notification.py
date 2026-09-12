from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    level: str
    link: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
