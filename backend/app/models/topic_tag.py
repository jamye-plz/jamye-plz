"""TopicTag model — AI and user tags for a topic."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.topic import Topic


class TopicTag(Base):
    __tablename__ = "topic_tags"
    __table_args__ = (UniqueConstraint("topic_id", "tag", name="uq_topic_tags_topic_tag"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id"))
    tag: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(8))  # ai | user
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # relationships
    topic: Mapped["Topic"] = relationship("Topic", back_populates="tags", lazy="noload")
