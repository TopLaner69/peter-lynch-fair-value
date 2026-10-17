"""Stocarea evaluărilor într-o bază de date SQLite locală."""

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from lynch import LynchInput, LynchResult

# În afara aplicației, ca datele să rămână și după reinstalarea/actualizarea ei.
DATA_DIR = Path.home() / "Library" / "Application Support" / "Peter Lynch Fair Value"
DB_PATH = DATA_DIR / "evaluari.db"

COLUMNS = [
    "id", "created_at", "company", "ticker", "currency", "price", "eps", "growth",
    "growth_used", "dividend", "dividend_yield", "pe", "peg", "lynch_ratio",
    "fair_value_basic", "fair_value", "upside_pct", "verdict", "notes",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TEXT NOT NULL,
    company          TEXT NOT NULL,
    ticker           TEXT,
    currency         TEXT,
    price            REAL NOT NULL,
    eps              REAL NOT NULL,
    growth           REAL NOT NULL,
    growth_used      REAL NOT NULL,
    dividend         REAL NOT NULL,
    dividend_yield   REAL NOT NULL,
    pe               REAL NOT NULL,
    peg              REAL NOT NULL,
    lynch_ratio      REAL NOT NULL,
    fair_value_basic REAL NOT NULL,
    fair_value       REAL NOT NULL,
    upside_pct       REAL NOT NULL,
    verdict          TEXT NOT NULL,
    notes            TEXT
);
CREATE INDEX IF NOT EXISTS idx_company ON evaluations(company);
"""


# Caractere cu care Excel/Numbers încep o formulă (OWASP: CSV injection).
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value):
    """Textul care ar fi interpretat ca formulă primește un apostrof în față."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


class Storage:
    def __init__(self, path: Path = DB_PATH):
        # Doar utilizatorul curent poate citi sau modifica datele.
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        path.touch(mode=0o600, exist_ok=True)
        path.chmod(0o600)  # SQLite creează fișierele jurnal cu aceleași permisiuni
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def save(self, inp: LynchInput, res: LynchResult) -> int:
        row = {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "company": inp.company.strip(),
            "ticker": inp.ticker.strip().upper(),
            "currency": inp.currency.strip().upper(),
            "price": inp.price,
            "eps": inp.eps,
            "growth": inp.growth,
            "growth_used": res.growth_used,
            "dividend": inp.dividend,
            "dividend_yield": res.dividend_yield,
            "pe": res.pe,
            "peg": res.peg,
            "lynch_ratio": res.lynch_ratio,
            "fair_value_basic": res.fair_value_basic,
            "fair_value": res.fair_value,
            "upside_pct": res.upside_pct,
            "verdict": res.verdict,
            "notes": inp.notes.strip(),
        }
        keys = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        with self.conn:
            cur = self.conn.execute(
                f"INSERT INTO evaluations ({keys}) VALUES ({marks})", list(row.values()))
        return cur.lastrowid

    def list(self, search: str = "") -> list[sqlite3.Row]:
        like = f"%{search.strip()}%"
        return self.conn.execute(
            "SELECT * FROM evaluations WHERE company LIKE ? OR ticker LIKE ? "
            "ORDER BY created_at DESC, id DESC", (like, like)).fetchall()

    def get(self, eval_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM evaluations WHERE id = ?", (eval_id,)).fetchone()

    def delete(self, eval_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM evaluations WHERE id = ?", (eval_id,))

    def export_csv(self, dest: Path, search: str = "") -> int:
        rows = self.list(search)
        with open(dest, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(COLUMNS)
            for r in rows:
                writer.writerow([csv_safe(r[c]) for c in COLUMNS])
        return len(rows)
