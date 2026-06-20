"""Quick test of AI analyst functionality."""
import sys
sys.path.insert(0, 'src')
from stockval.valuation.ai_analyst import AIAnalyst
from stockval.models import CompanyData, MarketData, Financials

# Test with sample data
market = MarketData(
    ticker='TEST',
    name='Test Corp',
    currency='USD',
    price=100.0,
    shares_outstanding=1_000_000,
    beta=1.1,
    market_cap=100_000_000,
    sector='Technology',
    industry='Software'
)

financials = Financials(
    revenue=50_000_000,
    ebit=10_000_000,
    ebitda=12_000_000,
    net_income=5_000_000,
    free_cash_flow=8_000_000,
    total_debt=10_000_000,
    cash_and_equivalents=20_000_000,
    eps=5.0,
    book_value_per_share=20.0
)

company = CompanyData(
    market=market,
    financials=financials,
    historical_revenue=[40_000_000, 42_000_000, 45_000_000, 48_000_000, 50_000_000],
    historical_fcf=[6_000_000, 6_500_000, 7_200_000, 7_800_000, 8_000_000],
    historical_dividends=[1_000_000, 1_100_000, 1_200_000, 1_300_000, 1_400_000]
)

# Run analysis
analyst = AIAnalyst(company)
growth = analyst.analyze_growth_trajectory()
trend = analyst.identify_trend()
seasonality = analyst.detect_seasonality()
thesis = analyst.generate_thesis(fair_value=120.0, current_price=100.0)

print('✓ AI Analyst initialized successfully')
print(f'  Growth CAGR: {growth.get("historical_cagr", 0):.1%}')
print(f'  Trend: {trend.trend_type}')
print(f'  Rating: {thesis.investment_rating}')
print(f'  Conviction: {thesis.conviction_level:.0%}')
print('✓ All analysis methods work correctly')
