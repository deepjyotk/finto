from .dividend_form import DividendForm
from .economic_sensitivity_form import EconomicSensitivityForm
from .growth_form import GrowthForm
from .investment_style_form import InvestmentStyleForm
from .market_cap_form import (
    DEFAULT_LARGE_CAP_MIN_USD,
    DEFAULT_MID_CAP_MAX_USD,
    DEFAULT_MID_CAP_MIN_USD,
    DEFAULT_SMALL_CAP_MAX_USD,
    MarketCapForm,
    MarketCapSegment,
    resolved_market_cap_bounds,
)
from .ownership_form import OwnershipForm
from .sector_form import SectorForm
from .value_form import ValueForm
from .volatility_risk_form import VolatilityRiskForm


SCREENER_CATEGORY_FORMS = {
    "market_cap": MarketCapForm,
    "growth": GrowthForm,
    "value": ValueForm,
    "dividend": DividendForm,
    "sector": SectorForm,
    "economic_sensitivity": EconomicSensitivityForm,
    "ownership": OwnershipForm,
    "investment_style": InvestmentStyleForm,
    "volatility_risk": VolatilityRiskForm,
}


__all__ = [
    "DEFAULT_LARGE_CAP_MIN_USD",
    "DEFAULT_MID_CAP_MAX_USD",
    "DEFAULT_MID_CAP_MIN_USD",
    "DEFAULT_SMALL_CAP_MAX_USD",
    "MarketCapForm",
    "MarketCapSegment",
    "resolved_market_cap_bounds",
    "GrowthForm",
    "ValueForm",
    "DividendForm",
    "SectorForm",
    "EconomicSensitivityForm",
    "OwnershipForm",
    "InvestmentStyleForm",
    "VolatilityRiskForm",
    "SCREENER_CATEGORY_FORMS",
]
