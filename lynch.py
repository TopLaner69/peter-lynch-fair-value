"""Calculul fair value după metoda lui Peter Lynch.

Formule folosite:
  * Fair P/E = rata de creștere a EPS (PEG = 1)
      Fair value = EPS × creștere (%)
  * Varianta ajustată cu dividend (Lynch, "One Up on Wall Street"):
      Fair value = EPS × (creștere % + randament dividend %)
  * Lynch ratio = (creștere % + randament dividend %) / P/E
      < 1  -> neatractivă, ~1.5 -> OK, >= 2 -> foarte atractivă
"""

import math
import re
from dataclasses import dataclass

# Lynch considera creșteri peste ~25%/an nesustenabile pe termen lung.
GROWTH_CAP = 25.0

# Limite de validare: resping valorile absurde înainte să ajungă în baza de date.
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
    price: float          # prețul curent al acțiunii
    eps: float            # EPS pe ultimele 12 luni (TTM)
    growth: float         # creșterea anuală estimată a EPS, în %
    dividend: float = 0.0  # dividend anual pe acțiune
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
    fair_value: float      # valoarea principală (ajustată cu dividend)
    upside_pct: float
    verdict: str
    warnings: list


def validate(inp: LynchInput) -> None:
    for name, value in (("Prețul", inp.price), ("EPS", inp.eps), ("Creșterea", inp.growth),
                        ("Dividendul", inp.dividend)):
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} trebuie să fie un număr valid.")

    company = inp.company.strip()
    if not company:
        raise ValueError("Introdu numele companiei.")
    if len(company) > MAX_COMPANY_LEN:
        raise ValueError(f"Numele companiei poate avea cel mult {MAX_COMPANY_LEN} caractere.")
    if not TICKER_RE.fullmatch(inp.ticker.strip()):
        raise ValueError("Ticker-ul poate conține doar litere, cifre, punct sau cratimă "
                         f"(max. {MAX_TICKER_LEN} caractere).")
    if not CURRENCY_RE.fullmatch(inp.currency.strip()):
        raise ValueError("Moneda trebuie să fie un cod de 3 litere (ex. USD).")
    if len(inp.notes) > MAX_NOTES_LEN:
        raise ValueError(f"Notele pot avea cel mult {MAX_NOTES_LEN} caractere.")

    if not 0 < inp.price <= MAX_PRICE:
        raise ValueError(f"Prețul trebuie să fie între 0 și {MAX_PRICE:,.0f}.")
    if inp.eps <= 0:
        raise ValueError("Formula lui Lynch nu se aplică pentru EPS negativ sau zero "
                         "(compania nu are profit).")
    if inp.eps < MIN_EPS or inp.eps > inp.price:
        raise ValueError(f"EPS trebuie să fie între {MIN_EPS} și prețul acțiunii "
                         "(un P/E sub 1 indică o greșeală de introducere).")
    if inp.growth <= 0:
        raise ValueError("Formula lui Lynch necesită o rată de creștere pozitivă.")
    if inp.growth > MAX_GROWTH:
        raise ValueError(f"Creșterea poate fi de cel mult {MAX_GROWTH:g}% pe an.")
    if inp.dividend < 0:
        raise ValueError("Dividendul nu poate fi negativ.")
    if inp.dividend >= inp.price:
        raise ValueError("Dividendul anual trebuie să fie mai mic decât prețul acțiunii.")


def calculate(inp: LynchInput) -> LynchResult:
    validate(inp)
    warnings = []

    growth_used = inp.growth
    if inp.cap_growth and inp.growth > GROWTH_CAP:
        growth_used = GROWTH_CAP
        warnings.append(f"Creșterea de {inp.growth:g}% a fost plafonată la {GROWTH_CAP:g}% "
                        "(Lynch considera creșterile mai mari nesustenabile).")
    elif inp.growth > GROWTH_CAP:
        warnings.append(f"Creștere de {inp.growth:g}% — peste {GROWTH_CAP:g}% rezultatul "
                        "poate fi prea optimist.")
    if growth_used < 5:
        warnings.append("Creștere sub 5%: Lynch numea astfel de companii 'slow growers'; "
                        "formula e mai puțin relevantă pentru ele.")

    dividend_yield = inp.dividend / inp.price * 100
    pe = inp.price / inp.eps
    peg = pe / growth_used
    lynch_ratio = (growth_used + dividend_yield) / pe

    fair_value_basic = inp.eps * growth_used
    fair_value = inp.eps * (growth_used + dividend_yield)
    upside_pct = (fair_value / inp.price - 1) * 100
    results = (dividend_yield, pe, peg, lynch_ratio, fair_value_basic, fair_value, upside_pct)
    if not all(math.isfinite(x) for x in results):
        raise ValueError("Datele introduse duc la un rezultat invalid; verifică valorile.")

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
        return "Puternic subevaluată"
    if ratio < 0.95:
        return "Subevaluată"
    if ratio <= 1.05:
        return "Evaluată corect"
    if ratio <= 1.3:
        return "Supraevaluată"
    return "Puternic supraevaluată"


def lynch_ratio_label(ratio: float) -> str:
    if ratio < 1:
        return "neatractivă"
    if ratio < 1.5:
        return "acceptabilă"
    if ratio < 2:
        return "bună"
    return "excelentă"
