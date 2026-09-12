from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog
from app.core.logging_config import logger

class AuditService:
    @staticmethod
    async def log_event(
        db: AsyncSession,
        event_type: str,
        user_id: Optional[int] = None,
        entity_type: str = "",
        entity_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: str = ""
    ) -> AuditLog:
        details_clean = details or {}
        audit = AuditLog(
            user_id=user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details_clean,
            ip_address=ip_address
        )
        db.add(audit)
        try:
            await db.commit()
            await db.refresh(audit)
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to record audit log: {e}")
        
        logger.info(f"[AUDIT] Event={event_type} User={user_id} Entity={entity_type}:{entity_id}")
        return audit

audit_service = AuditService()
