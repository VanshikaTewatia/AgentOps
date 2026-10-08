import uuid
from typing import List, Optional
from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin


class Service(Base, TimestampMixin):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="HEALTHY")  # HEALTHY, DEGRADED, DOWN
    owner_team: Mapped[str] = mapped_column(String(100), nullable=False)
    repository_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_info: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    incidents: Mapped[List["Incident"]] = relationship(
        "Incident", back_populates="service", cascade="all, delete-orphan"
    )
