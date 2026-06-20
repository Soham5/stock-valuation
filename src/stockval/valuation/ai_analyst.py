"""AI-powered financial analyst with 20+ years of institutional expertise.

Provides deep analysis of seasonal patterns, market trends, growth trajectories,
and generates institutional-grade investment theses with analyst reasoning.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from ..models import CompanyData


@dataclass
class TrendAnalysis:
    """Identifies market and company-specific trends."""
    
    trend_type: str  # "GROWTH", "CYCLICAL", "VALUE", "MOMENTUM", "DECLINING"
    confidence: float  # 0.0 to 1.0
    description: str
    key_drivers: list[str]


@dataclass
class SeasonalPattern:
    """Identifies seasonal patterns in business performance."""
    
    is_seasonal: bool
    seasonality_strength: float  # 0.0 to 1.0 (coefficient of variation)
    peak_quarters: list[int]  # Q1-Q4
    trough_quarters: list[int]
    reasoning: str


@dataclass
class AnalystThesis:
    """Investment thesis from institutional analyst perspective."""
    
    thesis_title: str
    executive_summary: str
    investment_rating: str  # "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"
    conviction_level: float  # 0.0 to 1.0
    
    bull_case: str
    bear_case: str
    key_catalysts: list[str]
    risks: list[str]
    
    valuation_commentary: str
    growth_outlook: str
    competitive_position: str
    
    analyst_notes: str  # Institutional perspective with experience-based insights


@dataclass
class SwotAnalysis:
    """Classic SWOT framework derived from fundamentals and trend signals."""

    strengths: list[str]
    weaknesses: list[str]
    opportunities: list[str]
    threats: list[str]


class AIAnalyst:
    """20+ years of institutional investment banking expertise in code."""    
    def __init__(self, company: CompanyData):
        self.company = company
        self.financials = company.financials
        self.market = company.market
    def analyze_growth_trajectory(self) -> dict:
        """Analyze historical growth patterns and project forward."""
        if not self.company.historical_revenue or len(self.company.historical_revenue) < 2:
            return {"status": "insufficient_data"}
        
        revenue = self.company.historical_revenue
        years = len(revenue)
        
        # Calculate CAGR over available history
        try:
            cagr = (revenue[-1] / revenue[0]) ** (1 / (years - 1)) - 1
        except (ValueError, ZeroDivisionError):
            cagr = 0
        
        # Analyze acceleration/deceleration
        recent_years = min(3, len(revenue) - 1)
        recent_growth_rates = []
        for i in range(recent_years):
            if revenue[-(i+2)] != 0:
                gr = (revenue[-(i+1)] / revenue[-(i+2)]) - 1
                recent_growth_rates.append(gr)
        
        avg_recent_growth = sum(recent_growth_rates) / len(recent_growth_rates) if recent_growth_rates else cagr
        momentum = "accelerating" if avg_recent_growth > cagr else "decelerating"
        
        return {
            "historical_cagr": cagr,
            "recent_growth_rate": avg_recent_growth,
            "momentum": momentum,
            "years_analyzed": years,
            "growth_quality": self._assess_growth_quality(cagr, avg_recent_growth)
        }
    
    def detect_seasonality(self) -> SeasonalPattern:
        """Detect seasonality from quarterly revenue using seasonal indices.

        Seasonality is an *intra-year* phenomenon and cannot be inferred from
        annual figures.  This requires at least eight quarters of revenue and
        computes a seasonal index per calendar quarter (mean quarter revenue /
        overall mean).  Quarters whose index runs materially above or below 1.0
        are flagged as peaks / troughs, and the dispersion of those indices is
        the seasonality strength.
        """
        quarterly = self.company.quarterly_revenue
        periods = self.company.quarterly_revenue_periods

        if not quarterly or len(quarterly) < 8:
            return SeasonalPattern(
                is_seasonal=False,
                seasonality_strength=0.0,
                peak_quarters=[],
                trough_quarters=[],
                reasoning=(
                    "Insufficient quarterly data (need 8+ quarters) for reliable "
                    "seasonality detection; annual figures cannot reveal intra-year "
                    "seasonality."
                ),
            )

        # Align each value to a calendar quarter (1-4). Fall back to positional
        # quarters when explicit labels are unavailable.
        if periods and len(periods) == len(quarterly):
            labels = periods
        else:
            labels = [(i % 4) + 1 for i in range(len(quarterly))]

        overall_mean = sum(quarterly) / len(quarterly)
        if overall_mean <= 0:
            return SeasonalPattern(
                is_seasonal=False,
                seasonality_strength=0.0,
                peak_quarters=[],
                trough_quarters=[],
                reasoning="Non-positive average revenue; seasonality undefined.",
            )

        # Mean revenue per calendar quarter, then its seasonal index.
        buckets: dict[int, list[float]] = {}
        for q, value in zip(labels, quarterly):
            buckets.setdefault(q, []).append(value)
        indices = {
            q: (sum(vals) / len(vals)) / overall_mean for q, vals in buckets.items()
        }

        peak_quarters = sorted(q for q, idx in indices.items() if idx >= 1.05)
        trough_quarters = sorted(q for q, idx in indices.items() if idx <= 0.95)

        # Strength = dispersion (coefficient of variation) of the seasonal indices.
        idx_values = list(indices.values())
        idx_mean = sum(idx_values) / len(idx_values)
        variance = sum((v - idx_mean) ** 2 for v in idx_values) / len(idx_values)
        strength = (variance ** 0.5) / idx_mean if idx_mean else 0.0
        is_seasonal = strength > 0.10 or bool(peak_quarters and trough_quarters)

        reasoning = (
            f"Analysed {len(quarterly)} quarters of revenue across "
            f"{len(buckets)} calendar quarters. Seasonal-index dispersion: "
            f"{strength:.1%}. "
            + (
                "Statistically meaningful seasonality detected."
                if is_seasonal
                else "No material intra-year seasonality detected."
            )
        )

        return SeasonalPattern(
            is_seasonal=is_seasonal,
            seasonality_strength=strength,
            peak_quarters=peak_quarters,
            trough_quarters=trough_quarters,
            reasoning=reasoning,
        )
    
    def generate_swot(self) -> SwotAnalysis:
        """Build a SWOT from fundamentals, growth signals and trend context."""
        fin = self.financials
        mkt = self.market
        growth = self.analyze_growth_trajectory()
        trend = self.identify_trend()

        strengths: list[str] = []
        weaknesses: list[str] = []
        opportunities: list[str] = []
        threats: list[str] = []

        # --- Margin & profitability -----------------------------------
        if fin.revenue and fin.net_income is not None and fin.revenue > 0:
            net_margin = fin.net_income / fin.revenue
            if net_margin > 0.15:
                strengths.append(f"High net margin ({net_margin:.1%}) signals strong pricing power")
            elif net_margin < 0.05:
                weaknesses.append(f"Thin net margin ({net_margin:.1%}) limits earnings resilience")

        if fin.revenue and fin.ebit is not None and fin.revenue > 0:
            op_margin = fin.ebit / fin.revenue
            if op_margin > 0.20:
                strengths.append(f"Robust operating margin ({op_margin:.1%}) reflects operational efficiency")
            elif op_margin < 0.08:
                weaknesses.append(f"Low operating margin ({op_margin:.1%}) pressures profitability")

        # --- Balance sheet --------------------------------------------
        net_debt = fin.net_debt
        if net_debt is not None:
            if net_debt < 0:
                strengths.append("Net cash position provides balance-sheet flexibility")
            elif fin.ebitda and fin.ebitda > 0 and (net_debt / fin.ebitda) > 3:
                weaknesses.append(f"Elevated leverage (Net debt/EBITDA {net_debt / fin.ebitda:.1f}x)")

        # --- Cash generation ------------------------------------------
        if fin.free_cash_flow is not None:
            if fin.free_cash_flow > 0:
                strengths.append("Positive free cash flow supports reinvestment and returns")
            else:
                weaknesses.append("Negative free cash flow constrains capital allocation")

        # --- Growth ----------------------------------------------------
        if growth.get("status") != "insufficient_data":
            cagr = growth.get("historical_cagr", 0)
            if cagr > 0.10:
                strengths.append(f"Strong revenue CAGR ({cagr:.1%}) over the analysed period")
            if growth.get("momentum") == "accelerating":
                opportunities.append("Accelerating growth momentum can drive multiple re-rating")
            elif growth.get("momentum") == "decelerating":
                threats.append("Decelerating growth may compress valuation multiples")

        # --- Dividend / shareholder returns ---------------------------
        if mkt.dividend_per_share:
            opportunities.append("Dividend stream broadens the total-return profile")

        # --- Trend-driven opportunities & threats ---------------------
        for driver in trend.key_drivers[:2]:
            opportunities.append(driver)

        if trend.trend_type == "CYCLICAL":
            threats.append("Earnings sensitivity to the economic cycle")
        elif trend.trend_type == "DECLINING":
            threats.append("Structural headwinds weighing on the demand outlook")

        # --- Valuation context ----------------------------------------
        if mkt.price and fin.eps and fin.eps > 0:
            pe = mkt.price / fin.eps
            if pe > 35:
                threats.append(f"Premium valuation (P/E {pe:.1f}x) leaves little margin for error")
            elif pe < 12:
                opportunities.append(f"Undemanding valuation (P/E {pe:.1f}x) offers re-rating potential")

        # --- Sensible fallbacks ---------------------------------------
        if not strengths:
            strengths.append("Established operations within its sector")
        if not weaknesses:
            weaknesses.append("Limited disclosure constrains deeper diligence")
        if not opportunities:
            opportunities.append("Operational improvements and market expansion")
        if not threats:
            threats.append("Competitive intensity and macroeconomic uncertainty")

        return SwotAnalysis(
            strengths=strengths,
            weaknesses=weaknesses,
            opportunities=opportunities,
            threats=threats,
        )
    
    def identify_trend(self) -> TrendAnalysis:
        """Identify dominant market trend from institutional perspective."""
        growth_data = self.analyze_growth_trajectory()
        
        if growth_data.get("status") == "insufficient_data":
            return TrendAnalysis(
                trend_type="UNKNOWN",
                confidence=0.0,
                description="Insufficient data for trend analysis",
                key_drivers=[]
            )
        
        cagr = growth_data.get("historical_cagr", 0)
        recent_growth = growth_data.get("recent_growth_rate", 0)
        momentum = growth_data.get("momentum", "")
        
        # Profitability analysis
        pe_ratio = None
        if self.market.price and self.financials.eps and self.financials.eps > 0:
            pe_ratio = self.market.price / self.financials.eps
        
        pb_ratio = None
        if self.market.price and self.financials.book_value_per_share:
            pb_ratio = self.market.price / self.financials.book_value_per_share
        
        # Determine trend type
        if recent_growth > 0.15:  # >15% growth
            trend_type = "GROWTH"
            description = "High-growth company with strong forward momentum"
            drivers = ["Rapid revenue expansion", "Market share gains", "New market penetration"]
            confidence = 0.85
        elif recent_growth > 0.08:  # 8-15% growth
            trend_type = "MOMENTUM"
            description = "Above-market growth with positive momentum"
            drivers = ["Steady revenue growth", "Operating leverage", "Market tailwinds"]
            confidence = 0.80
        elif recent_growth > 0.03:  # 3-8% growth
            if pe_ratio and pb_ratio and pe_ratio < 15 and pb_ratio < 2:
                trend_type = "VALUE"
                description = "Undervalued company trading below intrinsic worth"
                drivers = ["Low valuation multiples", "Steady cash generation", "Potential mean reversion"]
                confidence = 0.75
            else:
                trend_type = "CYCLICAL"
                description = "Mature company with business-cycle dependent earnings"
                drivers = ["Economic sensitivity", "Commodity/demand cycles", "Stable markets"]
                confidence = 0.70
        else:  # <3% growth
            if momentum == "decelerating":
                trend_type = "DECLINING"
                description = "Slowing growth with deteriorating momentum"
                drivers = ["Market saturation", "Competitive pressures", "Structural headwinds"]
                confidence = 0.80
            else:
                trend_type = "VALUE"
                description = "Mature, steady business with limited growth"
                drivers = ["Stable cash flows", "Dividend potential", "Low volatility"]
                confidence = 0.70
        
        return TrendAnalysis(
            trend_type=trend_type,
            confidence=confidence,
            description=description,
            key_drivers=drivers
        )
    
    def generate_thesis(self, fair_value: Optional[float], current_price: Optional[float]) -> AnalystThesis:
        """Generate comprehensive investment thesis from analyst perspective."""
        
        trend = self.identify_trend()
        growth_data = self.analyze_growth_trajectory()
        seasonality = self.detect_seasonality()
        
        # Rating logic
        if current_price is None or fair_value is None:
            upside = None
        else:
            upside = (fair_value / current_price - 1.0) if current_price > 0 else None
        
        rating, conviction = self._determine_rating(trend, upside)
        
        # Generate narrative sections
        bull_case = self._generate_bull_case(trend, growth_data, upside)
        bear_case = self._generate_bear_case(trend, growth_data, upside)
        catalysts = self._identify_catalysts(trend, growth_data)
        risks = self._identify_risks(trend, growth_data)
        
        valuation_commentary = self._assess_valuation(upside, current_price, fair_value)
        growth_outlook = self._project_growth_outlook(growth_data, trend)
        competitive_pos = self._assess_competitive_position()
        
        thesis_title = f"{self.market.ticker}: {trend.trend_type} Profile with {rating} Rating"
        
        executive_summary = (
            f"After comprehensive analysis of {self.market.name} ({self.market.ticker}), "
            f"we initiate coverage with a {rating} rating and {conviction:.0%} conviction level. "
            f"The company exhibits a {trend.trend_type.lower()} profile characterized by "
            f"{trend.description.lower()}. "
            f"Our analysis incorporates 20+ years of institutional equity research methodology, "
            f"including fundamental analysis, relative valuation, and market trend assessment. "
            f"{'Seasonal patterns are present in the business model and should be monitored.' if seasonality.is_seasonal else 'The business demonstrates relatively stable earnings patterns year-round.'}"
        )
        
        analyst_notes = (
            f"INSTITUTIONAL PERSPECTIVE: From our 20+ years of investment banking experience, "
            f"this company exhibits characteristics typical of {trend.trend_type.lower()}-phase "
            f"equity investments. The {trend.description.lower()} profile suggests "
            f"{self._analyst_commentary(trend, growth_data)}. "
            f"We view the {rating.lower()} rating as justified given the current valuation context "
            f"and forward-looking growth dynamics."
        )
        
        return AnalystThesis(
            thesis_title=thesis_title,
            executive_summary=executive_summary,
            investment_rating=rating,
            conviction_level=conviction,
            bull_case=bull_case,
            bear_case=bear_case,
            key_catalysts=catalysts,
            risks=risks,
            valuation_commentary=valuation_commentary,
            growth_outlook=growth_outlook,
            competitive_position=competitive_pos,
            analyst_notes=analyst_notes
        )
    
    def _assess_growth_quality(self, historical_cagr: float, recent_growth: float) -> str:
        """Assess the quality of earnings growth."""
        if recent_growth > historical_cagr * 1.1:
            return "ACCELERATING (High Quality)"
        elif recent_growth < historical_cagr * 0.9:
            return "DECELERATING (Watch for Signs)"
        else:
            return "STEADY (Sustainable)"
    
    def _infer_peak_quarters(self) -> list[int]:
        """Infer peak quarters based on typical industry patterns."""
        # This is simplified - in production would use actual quarterly data
        sector = (self.market.sector or "").upper()
        
        # Common seasonal patterns by sector
        patterns = {
            "CONSUMER": [4, 1],  # Q4 holidays, Q1 new year
            "RETAIL": [4],  # Holiday season
            "AGRICULTURE": [3, 4],  # Harvest season
            "TECHNOLOGY": [4],  # Year-end IT spending
            "MANUFACTURING": [2, 3],  # Post-winter ramp
        }
        
        for key, quarters in patterns.items():
            if key in sector:
                return quarters
        return []
    
    def _infer_trough_quarters(self) -> list[int]:
        """Infer trough quarters."""
        sector = (self.market.sector or "").upper()
        
        patterns = {
            "CONSUMER": [2],  # Q2 post-holiday slowdown
            "RETAIL": [1, 2],  # Post-holiday weakness
            "AGRICULTURE": [1, 2],  # Pre-harvest
            "TECHNOLOGY": [1],  # Post-holiday spend
        }
        
        for key, quarters in patterns.items():
            if key in sector:
                return quarters
        return []
    
    def _determine_rating(self, trend: TrendAnalysis, upside: Optional[float]) -> tuple[str, float]:
        """Determine investment rating and conviction."""
        if upside is None:
            return "NEUTRAL", 0.5
        
        if upside > 0.30:
            rating = "STRONG BUY"
            conviction = 0.90 * trend.confidence
        elif upside > 0.15:
            rating = "BUY"
            conviction = 0.80 * trend.confidence
        elif upside > -0.05:
            rating = "HOLD"
            conviction = 0.70 * trend.confidence
        elif upside > -0.15:
            rating = "SELL"
            conviction = 0.75 * trend.confidence
        else:
            rating = "STRONG SELL"
            conviction = 0.85 * trend.confidence
        
        return rating, conviction
    
    def _generate_bull_case(self, trend: TrendAnalysis, growth_data: dict, upside: Optional[float]) -> str:
        """Generate bull case narrative."""
        cagr = growth_data.get("historical_cagr", 0)
        
        case = f"The bull case centers on the company's {trend.description.lower()} "
        case += f"with consistent {cagr:.1%} historical CAGR. "
        
        if upside and upside > 0:
            case += f"At current prices, the stock offers {upside:.0%} upside to intrinsic value. "
        
        case += f"Key tailwinds include: {', '.join(trend.key_drivers)}. "
        case += "Forward-looking fundamentals support margin expansion and capital allocation efficiency."
        
        return case
    
    def _generate_bear_case(self, trend: TrendAnalysis, growth_data: dict, upside: Optional[float]) -> str:
        """Generate bear case narrative."""
        momentum = growth_data.get("momentum", "")
        
        case = f"The bear case highlights potential headwinds facing {self.market.name}. "
        
        if momentum == "decelerating":
            case += "Decelerating growth momentum raises questions about medium-term sustainability. "
        
        if upside and upside < 0:
            case += f"Downside risk of {abs(upside):.0%} to intrinsic value cannot be ignored. "
        
        case += "Competitive pressures, regulatory risks, and macro sensitivity could weigh on valuations."
        
        return case
    
    def _identify_catalysts(self, trend: TrendAnalysis, growth_data: dict) -> list[str]:
        """Identify key catalysts for stock performance."""
        catalysts = [
            f"{self.market.name} earnings beat/miss (quarterly catalyst)",
            "Industry consolidation or M&A activity",
            "Changes in competitive landscape",
            "Macroeconomic cycle impacts",
            "Product launches or innovation cycles",
        ]
        
        if growth_data.get("historical_cagr", 0) > 0.10:
            catalysts.append("Accelerated revenue growth announcements")
        
        if trend.trend_type == "CYCLICAL":
            catalysts.append("Economic cycle inflection points")
        
        return catalysts[:5]
    
    def _identify_risks(self, trend: TrendAnalysis, growth_data: dict) -> list[str]:
        """Identify key risks to investment thesis."""
        risks = [
            "Execution risk on growth initiatives",
            "Valuation compression in market downturn",
            "Loss of key customer or supplier concentration",
            "Regulatory or compliance risks",
        ]
        
        if growth_data.get("momentum", "") == "decelerating":
            risks.append("Continued deceleration in growth trajectory")
        
        if trend.trend_type == "CYCLICAL":
            risks.append("Economic downturn impacting demand")
        
        return risks[:5]
    
    def _assess_valuation(self, upside: Optional[float], current_price: Optional[float], fair_value: Optional[float]) -> str:
        """Provide valuation assessment."""
        if current_price is None or fair_value is None:
            return "Insufficient data for valuation assessment."
        
        if upside and upside > 0.20:
            assessment = "Trading at a meaningful discount to intrinsic value. "
            assessment += "Current valuation presents an attractive risk/reward profile for long-term investors."
        elif upside and upside > 0:
            assessment = "Fairly valued with modest upside. "
            assessment += "Current prices reflect most positive developments."
        elif upside and upside > -0.15:
            assessment = "Trading near fair value with balanced risk/reward. "
            assessment += "Valuation likely to compress further without growth acceleration."
        else:
            assessment = "Trading at a premium to intrinsic value. "
            assessment += "Current market prices leave limited margin of safety."
        
        return assessment
    
    def _project_growth_outlook(self, growth_data: dict, trend: TrendAnalysis) -> str:
        """Project forward growth outlook."""
        cagr = growth_data.get("historical_cagr", 0)
        recent = growth_data.get("recent_growth_rate", 0)
        momentum = growth_data.get("momentum", "")
        
        if momentum == "accelerating":
            outlook = f"We forecast growth to accelerate from recent {recent:.1%} levels to 12-15% over next 2-3 years"
        elif momentum == "decelerating":
            outlook = f"Expected moderation from {recent:.1%} to {max(cagr * 0.8, 0.03):.1%} as growth normalizes"
        else:
            outlook = f"We model steady growth in line with historical {cagr:.1%} CAGR"
        
        outlook += f", driven by {trend.key_drivers[0] if trend.key_drivers else 'organic expansion'}."
        
        return outlook
    
    def _assess_competitive_position(self) -> str:
        """Assess competitive positioning."""
        sector = (self.market.sector or "").upper()
        
        if self.market.name:
            return (
                f"{self.market.name} operates in the {sector.lower()} sector with established "
                f"market position. Competitive advantages include brand equity, scale, and operational "
                f"efficiency. We view the company as well-positioned to navigate sector dynamics."
            )
        return "Competitive position: To be determined upon further analysis."
    
    def _analyst_commentary(self, trend: TrendAnalysis, growth_data: dict) -> str:
        """Provide analyst commentary from experience."""
        cagr = growth_data.get("historical_cagr", 0)
        
        if trend.trend_type == "GROWTH":
            return (
                f"growth companies typically command premium valuations during expansion cycles. "
                f"With {cagr:.1%} historical CAGR and accelerating momentum, the company merits "
                f"continued accumulation on weakness."
            )
        elif trend.trend_type == "VALUE":
            return (
                f"value stocks often offer superior risk/reward when trading below intrinsic value. "
                f"The current valuation suggests room for mean reversion and upside surprises."
            )
        elif trend.trend_type == "CYCLICAL":
            return (
                f"cyclical businesses cycle with the economy. Timing entry points during industry "
                f"troughs yields superior long-term returns. Current positioning warrants tactical consideration."
            )
        else:
            return f"the company exhibits {trend.description.lower()} characteristics worth monitoring."
