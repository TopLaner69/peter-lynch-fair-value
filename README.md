# Peter Lynch Fair Value

A macOS desktop app (Python + Tkinter) that calculates a stock's fair value using
Peter Lynch's formula and saves every valuation together with the date it was made.

## Installation

On a Mac with [Homebrew](https://brew.sh):

```bash
brew install python@3.14 python-tk@3.14
```

Then, from the cloned folder:

```bash
./install.sh
```

The script creates a build environment, runs the tests, builds the app and installs it
in /Applications. Run it again after pulling new changes to update the app.

## Getting started

Once built and installed, the app lives in **/Applications/Peter Lynch Fair Value.app**:
open it from Launchpad or Spotlight (⌘Space → "Peter Lynch"). To keep it in the Dock,
right-click its icon while it is running → Options → Keep in Dock.

The app bundles its own Python, so it does not depend on Homebrew.

For development you can run it straight from the source: double-click `start.command`, or

```bash
/opt/homebrew/bin/python3.14 app.py
```

## Rebuilding the .app manually

`./install.sh` does all of this for you; these are the equivalent manual steps.

```bash
python3.14 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-build.txt
```

```bash
rm -rf build dist && .venv/bin/python setup.py py2app && ditto "dist/Peter Lynch Fair Value.app" "/Applications/Peter Lynch Fair Value.app"
```

## What you enter

| Field | Where to find it |
|---|---|
| Company name | required |
| Ticker, currency | optional |
| Current price | the stock's market price |
| EPS (TTM) | net earnings per share over the last 12 months |
| Annual EPS growth (%) | expected earnings growth over the next 3–5 years |
| Annual dividend / share | 0 if it pays no dividend |

Decimals can be written with a dot or a comma (`230.5` or `230,5`).

## Formulas

- **Fair value** = EPS × (growth % + dividend yield %)
  (without a dividend: EPS × growth %, i.e. fair P/E = growth rate, PEG = 1)
- **PEG** = P/E ÷ growth
- **Lynch ratio** = (growth % + dividend yield %) ÷ P/E — below 1 unattractive,
  ~1.5 OK, above 2 excellent
- Growth can be capped at 25% (Lynch considered higher growth rates unsustainable).
- The formula does not apply to unprofitable companies (EPS ≤ 0) or companies with no growth.

## Data

Valuations are stored in
`~/Library/Application Support/Peter Lynch Fair Value/valuations.db` (SQLite), outside
the app, so they survive reinstalls. The "Show database in Finder" button in the
"Valuation history" tab opens that folder. From the same tab you can search, reload a
valuation to re-evaluate it, delete it, or export to CSV (Excel/Numbers).

## Security

- No network access and no telemetry; SSL/OpenSSL and network modules are excluded from the bundle.
- Parameterized SQL queries; the database has `600` permissions (its folder `700`).
- Input is validated: plain decimal numbers only (no `nan`/`inf`), sensible limits,
  maximum text lengths, currency picked from a list.
- CSV export neutralizes text that Excel/Numbers would interpret as a formula.
- Build dependencies have pinned versions and hashes (`requirements-build.txt`).
- The app bundles its own Python: rebuild it every few months to pick up security
  updates for Python, SQLite and Tk.
- For personal use the ad-hoc signature is enough; distribution requires a Developer ID
  signature and Apple notarization.

## Tests

```bash
/opt/homebrew/bin/python3.14 -m unittest test_lynch
```
