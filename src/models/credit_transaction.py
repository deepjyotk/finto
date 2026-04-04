"""Credit transaction model for tracking credit ledger."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.user import User


class CreditTransaction(Base):
    """Model for tracking all credit transactions (additions and deductions)."""

    __tablename__ = "credit_transactions"

    # Primary key
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign key to user
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("f_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Transaction details
    amount: Mapped[int] = mapped_column(nullable=False)  # Positive for add, negative for deduct
    transaction_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'addition', 'deduction', 'initial', 'refund'

    balance_before: Mapped[int] = mapped_column(nullable=False)
    balance_after: Mapped[int] = mapped_column(nullable=False)

    # LLM usage details (for deductions)
    model_name: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int | None] = mapped_column()
    output_tokens: Mapped[int | None] = mapped_column()
    usd_cost: Mapped[float | None] = mapped_column(Numeric(10, 6))
    request_id: Mapped[str | None] = mapped_column(String(255), index=True)

    # Optional description
    description: Mapped[str | None] = mapped_column(Text)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="credit_transactions")

    def __repr__(self) -> str:
        return (
            f"<CreditTransaction(id={self.id}, user_id={self.user_id}, "
            f"type={self.transaction_type}, amount={self.amount}, "
            f"balance_after={self.balance_after})>"
        )
