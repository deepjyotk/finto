"""
portfolio_risk.py

Requirements:
    pip install yfinance pandas numpy

Usage:
    from portfolio_risk import portfolio_volatility, max_drawdown

    tickers = ["AAPL","MSFT","TSLA"]
    weights = [0.4, 0.4, 0.2]   # must sum to 1 (or None for equal weights)
    vol = portfolio_volatility(tickers, weights, start="2022-01-01", end="2024-12-31", interval="1d")
    print("Annualized volatility:", vol)

    # Also compute max drawdown:
    prices, retrieved_tickers = download_prices(tickers, start="2022-01-01", end="2024-12-31", interval="1d")
    pfolio = (prices.ffill().bfill() * weights).sum(axis=1)
    print("Max drawdown:", max_drawdown(pfolio))
"""

from typing import List, Optional, Tuple
import numpy as np
import pandas as pd
import yfinance as yf
from math import sqrt


def download_prices(tickers: List[str],
                    start: Optional[str] = None,
                    end: Optional[str] = None,
                    interval: str = "1d") -> Tuple[pd.DataFrame, List[str]]:
    """
    Download adjusted close prices for tickers using yfinance.
    Returns tuple of (DataFrame indexed by date with columns=tickers, list of successfully retrieved tickers).
    """
    if not tickers:
        raise ValueError("tickers list cannot be empty")
    # Download per-ticker with fail-safe: skip any ticker that errors
    all_prices: List[pd.Series] = []
    for t in tickers:
        try:
            df = yf.download(t, start=start, end=end, interval=interval, progress=False, auto_adjust=False)
            if df is None or df.empty:
                # Skip empty responses
                print(f"Warning: No data returned for ticker '{t}'. Skipping.")
                continue
            # Prefer adjusted close; fallback to close
            if "Adj Close" in df.columns:
                series = df["Adj Close"]
            else:
                series = df["Close"]
            # Ensure we have a Series
            if isinstance(series, pd.DataFrame):
                series = series.squeeze()
            # Name the series by ticker for concat
            if not isinstance(series, pd.Series):
                series = pd.Series(series, name=t)
            else:
                series.name = t
            all_prices.append(series)
        except Exception as e:
            print(f"Error downloading '{t}': {e}. Skipping.")
            continue

    if not all_prices:
        # Return empty DataFrame to signal no data available
        return pd.DataFrame(), []
    prices = pd.concat(all_prices, axis=1)
    # Ensure columns are ordered as input tickers but only those retrieved
    retrieved = [str(s.name) for s in all_prices]
    prices = prices.reindex(columns=[t for t in tickers if t in retrieved])
    return prices, retrieved


def annualization_factor(interval: str) -> float:
    """
    Return sqrt of periods per year for annualizing std dev.
    interval: "1d", "1wk", "1mo"
    """
    if interval in ("1d", "1d"):
        return sqrt(252)   # trading days
    if interval in ("1wk", "1wk"):
        return sqrt(52)
    if interval in ("1mo", "1mo"):
        return sqrt(12)
    # fallback: assume daily
    return sqrt(252)


def normalize_weights(weights: Optional[List[float]], n: int) -> np.ndarray:
    """
    Return a numpy array of weights summing to 1.
    If weights is None -> equal weight.
    """
    if weights is None:
        w = np.repeat(1.0 / n, n)
        return w
    w = np.array(weights, dtype=float)
    if w.size != n:
        raise ValueError(f"weights length {w.size} doesn't match number of assets {n}")
    s = w.sum()
    if s == 0:
        raise ValueError("sum of weights cannot be zero")
    return w / s


def portfolio_volatility(tickers: List[str],
                         weights: Optional[List[float]] = None,
                         start: Optional[str] = None,
                         end: Optional[str] = None,
                         interval: str = "1d",
                         dropna: bool = True) -> Tuple[float, dict]:
    """
    Compute annualized portfolio volatility (std dev of returns).

    Returns:
        annualized_vol (float): e.g. 0.18 meaning 18% annual volatility
        details (dict): useful intermediate objects (for debugging / display):
            {
              "returns": pd.DataFrame,      # asset returns used
              "portfolio_returns": pd.Series,
              "annualization_factor": float
            }

    Notes:
    - Uses adjusted close prices (if available).
    - We compute percent change (log returns could be used alternatively).
    - Annualization assumes 252 trading days for daily data.
    """
    prices, retrieved_tickers = download_prices(tickers, start=start, end=end, interval=interval)
    if prices.empty:
        raise RuntimeError("No price data returned for the requested tickers/dates.")
    # forward/backward fill missing prices conservatively
    prices = prices.ffill().bfill()

    # Percent change returns
    rets = prices.pct_change().dropna(how="all")
    if dropna:
        rets = rets.dropna(axis=1, how="all")  # drop columns that remain NaN
    n_assets = rets.shape[1]
    if n_assets == 0:
        raise RuntimeError("After dropping NaNs, no asset returns remain.")

    # Align weights to actual retrieved tickers (some may have been dropped)
    if weights is not None:
        # create mapping from ticker->weight for input tickers
        input_map = {t.upper(): float(weights[i]) for i, t in enumerate(tickers)}
        # align to rets columns - only include weights for successfully retrieved tickers
        aligned_w = []
        for col in rets.columns:
            key = col.upper()
            if key in input_map:
                aligned_w.append(input_map[key])
            else:
                # if ticker missing from input mapping, assume zero weight
                aligned_w.append(0.0)
        # Normalize aligned weights to sum to 1
        w = normalize_weights(aligned_w, len(aligned_w))
    else:
        # Equal weights for all assets
        w = normalize_weights(None, n_assets)

    # Portfolio returns: weighted sum of asset returns for each period
    port_rets_array = rets.values.dot(w)
    port_rets = pd.Series(port_rets_array, index=rets.index)

    # daily volatility (or per-interval)
    vol_per_period = float(port_rets.std(ddof=1))  # sample std

    # annualize
    ann_factor = annualization_factor(interval)
    annualized_vol = float(vol_per_period * ann_factor)

    details = {
        "returns": rets,
        "portfolio_returns": port_rets,
        "annualization_factor": ann_factor,
        "weights_used": w,
        "prices": prices
    }
    return annualized_vol, details


def max_drawdown(price_series: pd.Series) -> float:
    """
    Compute maximum drawdown for a price series.
    Returns positive float like 0.25 for 25% drawdown.
    """
    if price_series.empty:
        return 0.0
    roll_max = price_series.cummax()
    drawdown = (price_series - roll_max) / roll_max
    max_dd = drawdown.min()  # negative
    return float(abs(max_dd))


def max_drawdown_asset(tickers: Optional[List[str]] = None,
                       prices: Optional[pd.DataFrame] = None,
                       weights: Optional[List[float]] = None,
                       start: Optional[str] = None,
                       end: Optional[str] = None,
                       interval: str = "1d") -> List[dict]:
    """
    Calculate drawdown for each ticker and return sorted list by drawdown magnitude.

    Parameters:
        tickers: List of ticker symbols to download. Required if prices is None.
        prices: DataFrame of price levels, columns=tickers. If provided, tickers/start/end/interval are ignored.
        weights: Optional weights (aligned to columns). If provided, will scale each asset's price
                 before computing drawdown to reflect portfolio exposure.
        start: Start date for download (if prices not provided).
        end: End date for download (if prices not provided).
        interval: Price interval for download (if prices not provided).

    Returns:
        List of dicts, each containing:
            {
                'ticker': str,
                'max_drawdown': float,
                'peak_date': pd.Timestamp,
                'trough_date': pd.Timestamp
            }
        Sorted by max_drawdown (descending).

    Notes:
    - Drawdown is computed as (price - rolling max) / rolling max over time.
    - If weights provided, each column is multiplied by its weight before drawdown.
    - If prices is None, will download prices for the given tickers.
    """
    retrieved_tickers: List[str] = []
    
    if prices is None:
        if tickers is None or len(tickers) == 0:
            raise ValueError("Either prices or tickers must be provided")
        prices, retrieved_tickers = download_prices(tickers, start=start, end=end, interval=interval)
        if prices.empty:
            return []
    else:
        retrieved_tickers = [str(col) for col in prices.columns]

    df = prices.copy()
    df = df.ffill().bfill()

    if weights is not None:
        if len(weights) != df.shape[1]:
            raise ValueError("weights length must match number of tickers in prices")
        w = np.array(weights, dtype=float)
        df = df * w

    results = []

    for t in df.columns:
        s = df[t].dropna()
        if s.empty:
            continue
        roll_max = s.cummax()
        dd = (s - roll_max) / roll_max  # negative or zero
        min_dd = dd.min()
        abs_dd = abs(min_dd)
        
        if abs_dd > 0:  # Only include stocks with actual drawdown
            trough_idx = dd.idxmin()
            # peak is the last time the running max equals the peak before trough
            # find peak level up to trough
            s_up_to = s.loc[:trough_idx]
            roll_up_to = s_up_to.cummax()
            peak_idx = pd.Series(roll_up_to == roll_up_to.max()).idxmax()
            
            results.append({
                'ticker': str(t),
                'max_drawdown': float(abs_dd),
                'peak_date': pd.Timestamp(peak_idx),
                'trough_date': pd.Timestamp(trough_idx)
            })

    # Sort by max_drawdown descending
    results.sort(key=lambda x: x['max_drawdown'], reverse=True)
    return results


# ---------------------------
# Example / CLI usage block
# ---------------------------
if __name__ == "__main__":
    # quick demo
    tickers = ["AAPL", "MSFT", "TSLA"]
    weights = [0.4, 0.4, 0.2]  # must sum to 1 (or None)
    vol, details = portfolio_volatility(tickers, weights, start="2023-01-01", end=None, interval="1d")
    print(f"Annualized volatility for {tickers} = {vol:.2%}")
    p_rets = details["portfolio_returns"]
    # build portfolio price series (for drawdown)
    prices = details["prices"]
    # use weights used (aligned) to make portfolio price-level series
    port_price = (prices * details["weights_used"]).sum(axis=1)
    dd = max_drawdown(port_price)
    print(f"Max drawdown (historical) = {dd:.2%}")
    # Identify the single stock with worst drawdown (weighted)
    drawdown_results = max_drawdown_asset(prices=prices, weights=details["weights_used"])
    if drawdown_results:
        print("\nDrawdown Analysis (sorted by severity):")
        for result in drawdown_results:
            print(f"  {result['ticker']}: {result['max_drawdown']:.2%} (from {result['peak_date'].date()} to {result['trough_date'].date()})")
    else:
        print("No drawdown data available")
