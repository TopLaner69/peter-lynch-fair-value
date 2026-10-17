"""Fair value calculation using Peter Lynch's method.

Formulas:
  * Fair P/E = EPS growth rate (PEG = 1)
      Fair value = EPS × growth (%)
  * Dividend-adjusted version (Lynch, "One Up on Wall Street"):
      Fair value = EPS × (growth % + dividend yield %)
  * Lynch ratio = (growth % + dividend yield %) / P/E
      < 1  -> unattractive, ~1.5 -> OK, >= 2 -> very attractive
"""

import math
import re
from dataclasses import dataclass

# Lynch considered growth above ~25%/year unsustainable in the long run.
GROWTH_CAP = 25.0

# Validation limits: reject absurd values before they reach the database.
MAX_PRICE = 10_000_000
MIN_EPS = 0.0001
MAX_GROWTH = 100.0
MAX_COMPANY_LEN = 100
MAX_TICKER_LEN = 12
MAX_NOTES_LEN = 2000
TICKER_RE = re.compile(rf"[A-Za-z0-9.\-]{{0,{MAX_TICKER_LEN}}}")
CURRENCY_RE = re.compile(r"[A-Za-z]{3}")


@dataclass
class LynchInput:
    company: str
    price: float          # current share price
    eps: float            # trailing twelve months (TTM) EPS
    growth: float         # expected annual EPS growth, in %
    dividend: float = 0.0  # annual dividend per share
    ticker: str = ""
    currency: str = "USD"
    cap_growth: bool = True
    notes: str = ""


@dataclass
class LynchResult:
    growth_used: float
    dividend_yield: float
    pe: float
    peg: float
    lynch_ratio: float
    fair_value_basic: float
    fair_value: float      # main value (dividend-adjusted)
    upside_pct: float
    verdict: str
    warnings: list


def validate(inp: LynchInput) -> None:
    for name, value in (("Price", inp.price), ("EPS", inp.eps), ("Growth", inp.growth),
                        ("Dividend", inp.dividend)):
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} must be a valid number.")

    company = inp.company.strip()
    if not company:
        raise ValueError("Enter the company name.")
    if len(company) > MAX_COMPANY_LEN:
        raise ValueError(f"The company name can be at most {MAX_COMPANY_LEN} characters.")
    if not TICKER_RE.fullmatch(inp.ticker.strip()):
        raise ValueError("The ticker can only contain letters, digits, dots or hyphens "
                         f"(max. {MAX_TICKER_LEN} characters).")
    if not CURRENCY_RE.fullmatch(inp.currency.strip()):
        raise ValueError("The currency must be a 3-letter code (e.g. USD).")
    if len(inp.notes) > MAX_NOTES_LEN:
        raise ValueError(f"Notes can be at most {MAX_NOTES_LEN} characters.")

    if not 0 < inp.price <= MAX_PRICE:
        raise ValueError(f"The price must be between 0 and {MAX_PRICE:,.0f}.")
    if inp.eps <= 0:
        raise ValueError("Lynch's formula does not apply to zero or negative EPS "
                         "(the company is not profitable).")
    if inp.eps < MIN_EPS or inp.eps > inp.price:
        raise ValueError(f"EPS must be between {MIN_EPS} and the share price "
                         "(a P/E below 1 suggests a typing mistake).")
    if inp.growth <= 0:
        raise ValueError("Lynch's formula requires a positive growth rate.")
    if inp.growth > MAX_GROWTH:
        raise ValueError(f"Growth can be at most {MAX_GROWTH:g}% per year.")
    if inp.dividend < 0:
        raise ValueError("The dividend cannot be negative.")
    if inp.dividend >= inp.price:
        raise ValueError("The annual dividend must be lower than the share price.")


def calculate(inp: LynchInput) -> LynchResult:
    validate(inp)
    warnings = []

    growth_used = inp.growth
    if inp.cap_growth and inp.growth > GROWTH_CAP:
        growth_used = GROWTH_CAP
        warnings.append(f"Growth of {inp.growth:g}% was capped at {GROWTH_CAP:g}% "
                        "(Lynch considered higher growth rates unsustainable).")
    elif inp.growth > GROWTH_CAP:
        warnings.append(f"Growth of {inp.growth:g}% — above {GROWTH_CAP:g}% the result "
                        "may be too optimistic.")
    if growth_used < 5:
        warnings.append("Growth below 5%: Lynch called such companies 'slow growers'; "
                        "the formula is less relevant for them.")

    dividend_yield = inp.dividend / inp.price * 100
    pe = inp.price / inp.eps
    peg = pe / growth_used
    lynch_ratio = (growth_used + dividend_yield) / pe

    fair_value_basic = inp.eps * growth_used
    fair_value = inp.eps * (growth_used + dividend_yield)
    upside_pct = (fair_value / inp.price - 1) * 100
    results = (dividend_yield, pe, peg, lynch_ratio, fair_value_basic, fair_value, upside_pct)
    if not all(math.isfinite(x) for x in results):
        raise ValueError("The values entered lead to an invalid result; please check them.")

    return LynchResult(
        growth_used=growth_used,
        dividend_yield=dividend_yield,
        pe=pe,
        peg=peg,
        lynch_ratio=lynch_ratio,
        fair_value_basic=fair_value_basic,
        fair_value=fair_value,
        upside_pct=upside_pct,
        verdict=verdict(inp.price, fair_value),
        warnings=warnings,
    )


def verdict(price: float, fair_value: float) -> str:
    ratio = price / fair_value
    if ratio <= 0.7:
        return "Strongly undervalued"
    if ratio < 0.95:
        return "Undervalued"
    if ratio <= 1.05:
        return "Fairly valued"
    if ratio <= 1.3:
        return "Overvalued"
    return "Strongly overvalued"


def lynch_ratio_label(ratio: float) -> str:
    if ratio < 1:
        return "unattractive"
    if ratio < 1.5:
        return "acceptable"
    if ratio < 2:
        return "good"
    return "excellent"
