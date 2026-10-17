# Peter Lynch Fair Value

Aplicație desktop pentru macOS (Python + Tkinter) care calculează valoarea corectă
(fair value) a unei acțiuni după formula lui Peter Lynch și salvează fiecare evaluare,
cu data la care a fost făcută.

## Pornire

Aplicația e instalată în **/Applications/Peter Lynch Fair Value.app**: o găsești în
Launchpad sau Spotlight (⌘Space → „Peter Lynch”). Ca s-o ții în Dock, după ce o pornești
dă click-dreapta pe iconiță → Opțiuni → Păstrează în Dock.

Aplicația conține propriul Python, deci nu depinde de Homebrew.

Pentru dezvoltare o poți rula direct din cod: dublu-click pe `start.command` sau

```bash
/opt/homebrew/bin/python3.14 app.py
```

## Reconstruire .app (după modificări în cod)

```bash
python3.14 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-build.txt
```

```bash
rm -rf build dist && .venv/bin/python setup.py py2app && ditto "dist/Peter Lynch Fair Value.app" "/Applications/Peter Lynch Fair Value.app"
```

## Ce introduci

| Câmp | De unde îl iei |
|---|---|
| Nume companie | obligatoriu |
| Ticker, monedă | opțional |
| Preț curent | prețul acțiunii pe bursă |
| EPS (TTM) | profitul net pe acțiune pe ultimele 12 luni |
| Creștere anuală EPS (%) | estimarea creșterii profitului pe următorii 3–5 ani |
| Dividend anual / acțiune | 0 dacă nu plătește dividend |

Numerele se pot scrie și cu virgulă (`230,5`).

## Formule

- **Fair value** = EPS × (creștere % + randament dividend %)
  (fără dividend: EPS × creștere %, adică P/E corect = rata de creștere, PEG = 1)
- **PEG** = P/E ÷ creștere
- **Lynch ratio** = (creștere % + randament dividend %) ÷ P/E — sub 1 neatractivă,
  ~1.5 OK, peste 2 excelentă
- Creșterea poate fi plafonată la 25% (Lynch considera creșterile mai mari nesustenabile).
- Formula nu se aplică pentru companii fără profit (EPS ≤ 0) sau fără creștere.

## Date

Evaluările sunt stocate în
`~/Library/Application Support/Peter Lynch Fair Value/evaluari.db` (SQLite), în afara
aplicației, ca să rămână după reinstalare. Butonul „Arată baza de date în Finder” din
tab-ul „Istoric evaluări” deschide folderul. Tot de acolo poți căuta, reîncărca o evaluare
pentru reevaluare, șterge sau exporta în CSV (Excel/Numbers).

## Securitate

- Fără rețea și fără telemetrie; din pachet sunt excluse SSL/OpenSSL și modulele de rețea.
- Interogări SQL parametrizate; baza de date are permisiuni `600` (folderul `700`).
- Datele introduse sunt validate: doar numere zecimale simple (fără `nan`/`inf`), limite
  rezonabile, lungimi maxime pentru texte, monedă aleasă din listă.
- Exportul CSV neutralizează textele care ar fi interpretate ca formule în Excel/Numbers.
- Dependențele de build au versiuni și hash-uri fixate (`requirements-build.txt`).
- Aplicația include propriul Python: reconstruiește-o la câteva luni ca să primească
  actualizările de securitate pentru Python, SQLite și Tk.
- Pentru uz personal, semnătura ad-hoc e suficientă; pentru distribuire e nevoie de
  semnătură Developer ID și notarizare Apple.

## Teste

```bash
/opt/homebrew/bin/python3.14 -m unittest test_lynch
```
