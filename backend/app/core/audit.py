from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.base import AuditMixin


def _soft_delete_before_flush(session: Session, flush_context, instances) -> None:
    """Turn every ORM delete of an AuditMixin row into a soft delete.

    Clinical and financial history must never disappear — deleting a row
    just stamps deleted_at and leaves it in place for audit/history queries.
    """
    for obj in list(session.deleted):
        if isinstance(obj, AuditMixin):
            session.expunge(obj)
            obj.deleted_at = datetime.now(timezone.utc)
            session.add(obj)


def register_soft_delete_listener() -> None:
    event.listen(Session, "before_flush", _soft_delete_before_flush)


register_soft_delete_listener()
