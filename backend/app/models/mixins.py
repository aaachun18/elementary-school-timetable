from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """created_at / updated_at columns shared by every model. Each model still
    declares its own `id` primary key explicitly."""

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
