"""Inspect what data is available in yfinance ticker.info"""

import yfinance as yf
import json

# Test with a well-known stock
symbol = "AAPL"
print(f"Fetching info for {symbol}...")
print("=" * 80)

ticker = yf.Ticker(symbol)
info = ticker.info

# Print all available keys and their values
print(f"\nTotal keys available: {len(info.keys())}\n")

# Group keys by category for easier reading
financial_metrics = {}
growth_metrics = {}
valuation_metrics = {}
other_metrics = {}

for key, value in sorted(info.items()):
    # Categorize the metrics
    if any(word in key.lower() for word in ['growth', 'earning', 'revenue', 'profit']):
        growth_metrics[key] = value
    elif any(word in key.lower() for word in ['pe', 'pb', 'ps', 'ratio', 'peg', 'price', 'market', 'value']):
        valuation_metrics[key] = value
    elif any(word in key.lower() for word in ['debt', 'cash', 'asset', 'equity', 'margin', 'return']):
        financial_metrics[key] = value
    else:
        other_metrics[key] = value

def print_category(category_name, metrics_dict):
    print(f"\n{'='*80}")
    print(f"{category_name} ({len(metrics_dict)} items)")
    print(f"{'='*80}")
    for key, value in sorted(metrics_dict.items()):
        # Truncate long values
        value_str = str(value)
        if len(value_str) > 100:
            value_str = value_str[:100] + "..."
        print(f"  {key:40s} = {value_str}")

# Print categorized metrics
print_category("VALUATION METRICS", valuation_metrics)
print_category("GROWTH METRICS", growth_metrics)
print_category("FINANCIAL METRICS", financial_metrics)
print_category("OTHER METRICS", other_metrics)

# Also save to JSON file for detailed inspection
output_file = f"{symbol}_ticker_info.json"
with open(output_file, 'w') as f:
    json.dump(info, f, indent=2, default=str)

print(f"\n{'='*80}")
print(f"Full data saved to: {output_file}")
print(f"{'='*80}\n")

# Print some key metrics for quick reference
print("\nKEY METRICS FOR FILTERING:")
print("-" * 80)
print(f"PEG Ratio:                    {info.get('pegRatio')}")
print(f"Trailing PE:                  {info.get('trailingPE')}")
print(f"Forward PE:                   {info.get('forwardPE')}")
print(f"Price to Book:                {info.get('priceToBook')}")
print(f"Price to Sales (TTM):         {info.get('priceToSalesTrailing12Months')}")
print(f"Revenue Growth:               {info.get('revenueGrowth')}")
print(f"Earnings Growth:              {info.get('earningsGrowth')}")
print(f"Earnings Quarterly Growth:    {info.get('earningsQuarterlyGrowth')}")
print(f"Profit Margins:               {info.get('profitMargins')}")
print(f"Return on Equity:             {info.get('returnOnEquity')}")
print("-" * 80)
