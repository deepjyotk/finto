# src/repositories/holding_repo.py
import pandas as pd
from sqlalchemy.orm import Session
from src.models.equity_holding import EquityHolding
from src.core.settings import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def get_portfolio_df_from_db(user_id: str) -> pd.DataFrame:
    """
    Fetch the user's portfolio as a DataFrame from the equity_holdings_in table using the ORM model.
    """
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        query = (
            session.query(
                EquityHolding.symbol.label("Symbol"),
                EquityHolding.isin.label("ISIN"),
                EquityHolding.sector.label("Sector"),
                EquityHolding.qty_available.label("Quantity Available"),
                EquityHolding.qty_discrepant.label("Quantity Discrepant"),
                EquityHolding.qty_long_term.label("Quantity Long Term"),
                EquityHolding.qty_pledged_margin.label("Quantity Pledged (Margin)"),
                EquityHolding.qty_pledged_loan.label("Quantity Pledged (Loan)"),
                EquityHolding.avg_price.label("Average Price"),
            )
            .filter(EquityHolding.user_id == user_id)
        )
        df = pd.read_sql(query.statement, engine)
    return df


print(get_portfolio_df_from_db("12e51f5c-5a84-4029-af62-b12c3e3f9144").head())  # Example usage