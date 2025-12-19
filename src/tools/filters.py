import yfinance as yf


def growth_filter(symbols):
    """
    Filter stocks based on growth criteria.

    Growth criteria (any of the following):
    - Revenue growth > 8% AND Earnings growth > 10%
    - Earnings growth > 20% (high growth)
    - Revenue growth > 15% (high revenue growth)
    """
    growth_stocks = []

    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            info = ticker.info

            # Get growth metrics
            revenue_growth = info.get("revenueGrowth") or 0
            earnings_growth = info.get("earningsGrowth") or 0

            print(f"\n{sym}:")
            print(f"  Revenue Growth: {revenue_growth:.1%}")
            print(f"  Earnings Growth: {earnings_growth:.1%}")

            # Multiple paths to qualify as growth stock
            balanced_growth = revenue_growth > 0.08 and earnings_growth > 0.10
            high_earnings_growth = earnings_growth > 0.20
            high_revenue_growth = revenue_growth > 0.15

            if balanced_growth or high_earnings_growth or high_revenue_growth:
                growth_stocks.append(sym)
                print("  ✓ PASSED")
                if balanced_growth:
                    print("    - Balanced growth (Rev > 8%, Earn > 10%)")
                if high_earnings_growth:
                    print("    - High earnings growth (> 20%)")
                if high_revenue_growth:
                    print("    - High revenue growth (> 15%)")
            else:
                print("  ✗ FAILED: Growth criteria not met")

        except Exception as e:
            print(f"✗ Error fetching {sym}: {e}")
            continue

    return growth_stocks


def value_filter(symbols):
    """
    Filter stocks based on value criteria.

    Value criteria (must meet at least one):
    - Trailing P/E < 20 AND (Price to Book < 5 OR Price to Sales < 3)
    - Price to Book < 2.5 (deeply undervalued)
    - Forward P/E < 15 (expected value)
    """
    value_stocks = []

    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            info = ticker.info

            # Get valuation metrics
            trailing_pe = info.get("trailingPE")
            forward_pe = info.get("forwardPE")
            price_to_book = info.get("priceToBook")
            price_to_sales = info.get("priceToSalesTrailing12Months")

            print(f"\n{sym}:")
            print(f"  Trailing PE: {trailing_pe:.2f}" if trailing_pe else "  Trailing PE: N/A")
            print(f"  Forward PE: {forward_pe:.2f}" if forward_pe else "  Forward PE: N/A")
            print(
                f"  Price to Book: {price_to_book:.2f}" if price_to_book else "  Price to Book: N/A"
            )
            print(
                f"  Price to Sales: {price_to_sales:.2f}"
                if price_to_sales
                else "  Price to Sales: N/A"
            )

            # Multiple paths to qualify as value stock
            reasonable_pe_with_low_multiple = (
                trailing_pe is not None
                and trailing_pe < 20
                and (
                    (price_to_book is not None and price_to_book < 5)
                    or (price_to_sales is not None and price_to_sales < 3)
                )
            )
            deep_book_value = price_to_book is not None and price_to_book < 2.5
            attractive_forward_pe = forward_pe is not None and forward_pe < 15

            if reasonable_pe_with_low_multiple or deep_book_value or attractive_forward_pe:
                value_stocks.append(sym)
                print("  ✓ PASSED")
                if reasonable_pe_with_low_multiple:
                    print("    - Reasonable PE with low multiples")
                if deep_book_value:
                    print("    - Deep book value (P/B < 2.5)")
                if attractive_forward_pe:
                    print("    - Attractive forward PE (< 15)")
            else:
                print("  ✗ FAILED: Value criteria not met")

        except Exception as e:
            print(f"✗ Error fetching {sym}: {e}")
            continue

    return value_stocks


if __name__ == "__main__":
    symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "JPM", "KO", "WMT", "XOM"]

    print("\n" + "=" * 60)
    print("GROWTH FILTER")
    print("=" * 60)
    growth = growth_filter(symbols)
    print(f"\n{'=' * 60}")
    print(f"Growth Stocks Found: {growth}")
    print(f"{'=' * 60}")

    print("\n" + "=" * 60)
    print("VALUE FILTER")
    print("=" * 60)
    value = value_filter(symbols)
    print(f"\n{'=' * 60}")
    print(f"Value Stocks Found: {value}")
    print(f"{'=' * 60}")
