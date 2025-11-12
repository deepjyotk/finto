"""Holdings service - pure class for business logic, no FastAPI imports"""

from uuid import UUID

from src.api.schemas.holdings import HoldingsRequestSchema, HoldingsResponseSchema
from src.models.equity_holding import EquityHolding
from src.repositories.holdings_repo import HoldingsRepository


class HoldingsService:
    """Service layer for holdings operations"""

    def __init__(self, repo: HoldingsRepository):
        """
        Initialize HoldingsService.

        Args:
            repo: HoldingsRepository instance for data access
        """
        self.repo = repo

    async def save_user_holding(
        self, holding_schema: HoldingsRequestSchema, user_id: UUID
    ) -> HoldingsResponseSchema:
        """
        Save a new equity holding for a user.

        This is the use-case boundary - handles the full holding creation transaction.

        Args:
            holding_schema: Holdings data to save
            user_id: UUID of the user

        Returns:
            HoldingsResponseSchema with the created holding
        """
        # Create holding
        holding = await self.repo.add(
            user_id=user_id,
            broker_id=holding_schema.broker_id,
            symbol=holding_schema.symbol,
            isin=holding_schema.isin,
            sector=holding_schema.sector,
            qty_available=holding_schema.qty_available,
            qty_discrepant=holding_schema.qty_discrepant,
            qty_long_term=holding_schema.qty_long_term,
            qty_pledged_margin=holding_schema.qty_pledged_margin,
            qty_pledged_loan=holding_schema.qty_pledged_loan,
            avg_price=holding_schema.avg_price,
            prev_close_price=holding_schema.prev_close_price,
            unrealized_pnl=holding_schema.unrealized_pnl,
            unrealized_pnl_pct=holding_schema.unrealized_pnl_pct,
        )

        # Commit at the use-case boundary
        await self.repo.session.commit()

        return HoldingsResponseSchema.model_validate(holding)

    async def save_user_holdings(
        self, holdings_list: list[HoldingsRequestSchema], user_id: UUID
    ) -> int:
        """
        Save multiple equity holdings for a user (bulk insert).

        This is the use-case boundary - handles the full bulk holding creation transaction.

        Args:
            holdings_list: List of holdings data to save
            user_id: UUID of the user

        Returns:
            Number of holdings created
        """
        # Create list of EquityHolding objects
        holdings = [
            EquityHolding(
                user_id=user_id,
                broker_id=holding.broker_id,
                symbol=holding.symbol,
                isin=holding.isin,
                sector=holding.sector,
                qty_available=holding.qty_available,
                qty_discrepant=holding.qty_discrepant,
                qty_long_term=holding.qty_long_term,
                qty_pledged_margin=holding.qty_pledged_margin,
                qty_pledged_loan=holding.qty_pledged_loan,
                avg_price=holding.avg_price,
                prev_close_price=holding.prev_close_price,
                unrealized_pnl=holding.unrealized_pnl,
                unrealized_pnl_pct=holding.unrealized_pnl_pct,
            )
            for holding in holdings_list
        ]

        # Bulk insert all holdings
        await self.repo.add_all(holdings)

        # Commit at the use-case boundary
        await self.repo.session.commit()

        return len(holdings)

