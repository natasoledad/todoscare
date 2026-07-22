"""Import every model module so Base.metadata is fully populated before
Alembic autogenerate or `Base.metadata.create_all` run — and so that
declared_attr FKs referencing tables in other modules (e.g. AuditMixin's
created_by -> users.id) resolve during mapper configuration."""

from app.models.base import Base  # noqa: F401
from app.models import (  # noqa: F401
    catalog,
    clinical,
    finance,
    identity,
    insurance,
    integrations,
    patient,
    scheduling,
    tenant,
    wallet,
)
