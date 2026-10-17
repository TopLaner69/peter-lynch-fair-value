import csv
import tempfile
import unittest
from pathlib import Path

from lynch import LynchInput, calculate
from storage import Storage


class CalculateTest(unittest.TestCase):
    def test_basic_no_dividend(self):
        res = calculate(LynchInput("Test", price=100, eps=5, growth=15))
        self.assertAlmostEqual(res.fair_value, 75)
        self.assertAlmostEqual(res.pe, 20)
        self.assertAlmostEqual(res.peg, 20 / 15)
        self.assertAlmostEqual(res.upside_pct, -25)
        self.assertEqual(res.verdict, "Puternic supraevaluată")

    def test_dividend_adjusted(self):
        res = calculate(LynchInput("Test", price=50, eps=4, growth=10, dividend=1.5))
        self.assertAlmostEqual(res.dividend_yield, 3)
        self.assertAlmostEqual(res.fair_value_basic, 40)
        self.assertAlmostEqual(res.fair_value, 52)
        self.assertAlmostEqual(res.lynch_ratio, 13 / 12.5)

    def test_growth_cap(self):
        res = calculate(LynchInput("Test", price=100, eps=2, growth=40))
        self.assertEqual(res.growth_used, 25)
        self.assertAlmostEqual(res.fair_value, 50)
        res = calculate(LynchInput("Test", price=100, eps=2, growth=40, cap_growth=False))
        self.assertAlmostEqual(res.fair_value, 80)

    def test_invalid(self):
        for kwargs in ({"price": 10, "eps": -1, "growth": 10},
                       {"price": 0, "eps": 1, "growth": 10},
                       {"price": 10, "eps": 1, "growth": 0}):
            with self.assertRaises(ValueError):
                calculate(LynchInput("Test", **kwargs))
        with self.assertRaises(ValueError):
            calculate(LynchInput("  ", price=10, eps=1, growth=10))

    def test_non_finite_rejected(self):
        nan, inf = float("nan"), float("inf")
        for kwargs in ({"price": nan, "eps": 1, "growth": 10},
                       {"price": 100, "eps": inf, "growth": 10},
                       {"price": 100, "eps": 1, "growth": nan},
                       {"price": 100, "eps": 1, "growth": 10, "dividend": inf}):
            with self.assertRaises(ValueError):
                calculate(LynchInput("Test", **kwargs))

    def test_limits(self):
        for kwargs in ({"price": 2e7, "eps": 1, "growth": 10},
                       {"price": 100, "eps": 150, "growth": 10},
                       {"price": 100, "eps": 1e-9, "growth": 10},
                       {"price": 100, "eps": 1, "growth": 150},
                       {"price": 100, "eps": 1, "growth": 10, "dividend": 100}):
            with self.assertRaises(ValueError):
                calculate(LynchInput("Test", **kwargs))

    def test_text_fields(self):
        base = {"price": 100, "eps": 5, "growth": 10}
        for kwargs in ({"company": "x" * 101}, {"ticker": "=CMD()"},
                       {"ticker": "A" * 13}, {"currency": "US$"}, {"notes": "n" * 2001}):
            args = {"company": "Test", **base, **kwargs}
            with self.assertRaises(ValueError):
                calculate(LynchInput(**args))
        calculate(LynchInput("Test", ticker="BRK.B", **base))


class ParseNumberTest(unittest.TestCase):
    def test_accepts_and_rejects(self):
        from app import parse_number
        self.assertEqual(parse_number("230,5", "x"), 230.5)
        self.assertEqual(parse_number(" 12 % ", "x"), 12)
        for bad in ("nan", "inf", "-inf", "1e999", "1" * 25, "12a", "0x10"):
            with self.assertRaises(ValueError):
                parse_number(bad, "x")


class StorageTest(unittest.TestCase):
    def test_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "data" / "x.db"
            Storage(db)
            self.assertEqual(db.stat().st_mode & 0o777, 0o600)
            self.assertEqual(db.parent.stat().st_mode & 0o777, 0o700)

    def test_csv_formula_injection(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Storage(Path(tmp) / "x.db")
            inp = LynchInput("=HYPERLINK(\"http://x\")", price=100, eps=5, growth=15,
                             notes="@SUM(1)")
            st.save(inp, calculate(inp))
            out = Path(tmp) / "out.csv"
            st.export_csv(out)
            with open(out, encoding="utf-8-sig", newline="") as f:
                row = list(csv.DictReader(f))[0]
            self.assertTrue(row["company"].startswith("'="))
            self.assertTrue(row["notes"].startswith("'@"))
            self.assertTrue(row["upside_pct"].startswith("-"))  # numerele rămân numere

    def test_save_list_export_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Storage(Path(tmp) / "x.db")
            inp = LynchInput("Apple Inc.", price=100, eps=5, growth=15, ticker="aapl")
            eval_id = st.save(inp, calculate(inp))
            rows = st.list("aapl")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["ticker"], "AAPL")
            self.assertTrue(rows[0]["created_at"])
            self.assertEqual(st.export_csv(Path(tmp) / "out.csv"), 1)
            st.delete(eval_id)
            self.assertEqual(st.list(), [])


if __name__ == "__main__":
    unittest.main()
