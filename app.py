"""Peter Lynch Fair Value — aplicație desktop pentru macOS (Tkinter)."""

import os
import re
import subprocess
import tkinter as tk
import tkinter.font as tkfont
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from lynch import GROWTH_CAP, LynchInput, calculate, lynch_ratio_label
from storage import DB_PATH, Storage

CURRENCIES = ["USD", "EUR", "RON", "GBP", "CHF", "JPY", "CAD"]
NUMBER_RE = re.compile(r"-?\d+(\.\d+)?")

# Paleta portocaliu / alb
ORANGE = "#F26B1D"
ORANGE_DARK = "#D4560F"
ORANGE_SOFT = "#FFF1E6"
ORANGE_LINE = "#F8D3B8"
WHITE = "#FFFFFF"
PAGE = "#FFF8F2"
TEXT = "#2B2118"
MUTED = "#8C7B6E"
GREEN = "#1E8E4E"
GREEN_SOFT = "#E3F5EA"
RED = "#C8341F"
RED_SOFT = "#FBE6E2"

# Dimensiunea ferestrei pentru care fonturile au mărimea de bază.
DESIGN_W, DESIGN_H = 1180, 820
# Sub aceste lățimi (în pixeli) aranjarea se schimbă.
STACK_BELOW = 900        # formularul și rezultatul unul sub altul
FORM_ONE_COL_BELOW = 560  # câmpurile formularului pe o singură coloană
# Coloanele din istoric rămase vizibile, în funcție de lățime.
HISTORY_COLUMNS = [
    (1000, None),  # toate
    (800, ("created_at", "company", "ticker", "price", "growth", "fair_value",
           "upside_pct", "verdict")),
    (600, ("created_at", "company", "fair_value", "upside_pct", "verdict")),
    (0, ("company", "fair_value", "upside_pct")),
]


def parse_number(text: str, field: str, required: bool = True) -> float:
    text = text.strip().replace(" ", "").replace(",", ".").replace("%", "")
    if not text:
        if required:
            raise ValueError(f"Completează câmpul „{field}”.")
        return 0.0
    # Doar numere zecimale simple: respinge „nan”, „inf”, notația 1e999 și textele lungi.
    if len(text) > 20 or not NUMBER_RE.fullmatch(text):
        raise ValueError(f"„{field}” trebuie să fie un număr (ai scris: {text[:20]}).")
    return float(text)


def fmt(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Peter Lynch Fair Value")
        width = min(DESIGN_W, self.winfo_screenwidth() - 80)
        height = min(DESIGN_H, self.winfo_screenheight() - 120)
        self.geometry(f"{width}x{height}")
        self.minsize(480, 520)
        self.configure(bg=PAGE)

        self._setup_style()
        self.storage = Storage()
        self.last = None  # (LynchInput, LynchResult) după ultimul calcul
        self.scale = None
        self.eval_mode = None
        self.form_cols = None
        self.history_level = None

        self._build_header()
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=20, pady=(14, 20))
        self.eval_tab = ttk.Frame(notebook, style="Page.TFrame", padding=(0, 14, 0, 0))
        self.history_tab = ttk.Frame(notebook, style="Page.TFrame", padding=(0, 14, 0, 0))
        notebook.add(self.eval_tab, text="Evaluare nouă")
        notebook.add(self.history_tab, text="Istoric evaluări")
        self.notebook = notebook

        self._build_scroll_area()
        self._build_eval_tab()
        self._build_history_tab()
        self.refresh_history()

        self._resize_job = None
        self.bind("<Configure>", self._on_configure)
        self.bind_all("<MouseWheel>", self._on_wheel)
        try:  # Tk 9: scroll fin pe trackpad
            self.bind_all("<TouchpadScroll>", self._on_touchpad)
        except tk.TclError:
            pass
        self.update_idletasks()
        self._apply_responsive()

    def report_callback_exception(self, exc, val, tb):
        # O eroare neprevăzută e afișată, nu ignorată în tăcere.
        traceback.print_exception(exc, val, tb)
        messagebox.showerror("Eroare neașteptată",
                             f"Operația nu a putut fi finalizată.\n\n{exc.__name__}: {val}",
                             parent=self)

    # ---------- Stil ----------
    def _setup_style(self):
        family = tkfont.nametofont("TkDefaultFont").actual()["family"]
        # Fonturi denumite: schimbarea mărimii lor actualizează toate widget-urile.
        self.font_sizes = {
            "base": (13, "normal"), "small": (11, "normal"), "label": (12, "bold"),
            "title": (20, "bold"), "subtitle": (12, "normal"), "section": (15, "bold"),
            "big": (34, "bold"), "value": (14, "bold"), "tile": (20, "bold"),
            "verdict": (14, "bold"),
        }
        self.f = {name: tkfont.Font(self, family=family, size=size, weight=weight)
                  for name, (size, weight) in self.font_sizes.items()}
        # Culori pentru widget-urile clasice Tk (listă dropdown, câmp text).
        self.option_add("*TCombobox*Listbox.background", WHITE)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ORANGE)
        self.option_add("*TCombobox*Listbox.selectForeground", WHITE)

        s = ttk.Style(self)
        s.theme_use("clam")  # tema „aqua” ignoră culorile personalizate
        s.configure(".", background=WHITE, foreground=TEXT, font=self.f["base"],
                    bordercolor=ORANGE_LINE, focuscolor=ORANGE)

        s.configure("Page.TFrame", background=PAGE)
        s.configure("Card.TFrame", background=WHITE, relief="solid", borderwidth=1,
                    bordercolor=ORANGE_LINE)
        s.configure("Plain.TFrame", background=WHITE)
        s.configure("Tile.TFrame", background=ORANGE_SOFT)
        s.configure("Header.TFrame", background=ORANGE)

        s.configure("TLabel", background=WHITE, foreground=TEXT)
        s.configure("Page.TLabel", background=PAGE)
        s.configure("Muted.TLabel", foreground=MUTED, font=self.f["small"])
        s.configure("Field.TLabel", font=self.f["label"])
        s.configure("Section.TLabel", font=self.f["section"], foreground=ORANGE_DARK)
        s.configure("Big.TLabel", font=self.f["big"], foreground=ORANGE)
        s.configure("Value.TLabel", font=self.f["value"])
        s.configure("TileTitle.TLabel", background=ORANGE_SOFT, foreground=MUTED,
                    font=self.f["small"])
        s.configure("TileValue.TLabel", background=ORANGE_SOFT, font=self.f["tile"])
        s.configure("HeaderTitle.TLabel", background=ORANGE, foreground=WHITE,
                    font=self.f["title"])
        s.configure("HeaderSub.TLabel", background=ORANGE, foreground="#FFE3D0",
                    font=self.f["subtitle"])
        s.configure("Warn.TLabel", foreground=ORANGE_DARK, font=self.f["small"])

        s.configure("TEntry", fieldbackground=WHITE, foreground=TEXT, padding=7,
                    bordercolor=ORANGE_LINE, lightcolor=ORANGE_LINE, darkcolor=ORANGE_LINE,
                    insertcolor=TEXT)
        s.map("TEntry", bordercolor=[("focus", ORANGE)], lightcolor=[("focus", ORANGE)],
              darkcolor=[("focus", ORANGE)])
        s.configure("TCombobox", fieldbackground=WHITE, background=WHITE, foreground=TEXT,
                    arrowcolor=ORANGE, padding=5, bordercolor=ORANGE_LINE,
                    lightcolor=ORANGE_LINE, darkcolor=ORANGE_LINE)
        s.map("TCombobox", fieldbackground=[("readonly", WHITE)],
              selectbackground=[("readonly", WHITE)], selectforeground=[("readonly", TEXT)],
              bordercolor=[("focus", ORANGE)])

        s.configure("TCheckbutton", background=WHITE, foreground=TEXT,
                    indicatorbackground=WHITE, indicatorforeground=WHITE,
                    indicatormargin=(0, 0, 8, 0))
        s.map("TCheckbutton", background=[("active", WHITE)],
              indicatorbackground=[("selected", ORANGE), ("active", ORANGE_SOFT)])

        s.configure("Accent.TButton", background=ORANGE, foreground=WHITE, borderwidth=0,
                    padding=(18, 9), font=self.f["label"], bordercolor=ORANGE,
                    lightcolor=ORANGE, darkcolor=ORANGE)
        s.map("Accent.TButton",
              background=[("disabled", ORANGE_LINE), ("pressed", ORANGE_DARK),
                          ("active", ORANGE_DARK)],
              foreground=[("disabled", WHITE)],
              lightcolor=[("active", ORANGE_DARK)], darkcolor=[("active", ORANGE_DARK)])
        s.configure("Ghost.TButton", background=WHITE, foreground=ORANGE_DARK, padding=(16, 8),
                    font=self.f["label"], bordercolor=ORANGE, lightcolor=WHITE,
                    darkcolor=WHITE)
        s.map("Ghost.TButton",
              background=[("disabled", WHITE), ("pressed", ORANGE_SOFT), ("active", ORANGE_SOFT)],
              foreground=[("disabled", ORANGE_LINE)], bordercolor=[("disabled", ORANGE_LINE)],
              lightcolor=[("active", ORANGE_SOFT)], darkcolor=[("active", ORANGE_SOFT)])

        s.configure("TNotebook", background=PAGE, borderwidth=0, tabmargins=(0, 0, 0, 0))
        s.configure("TNotebook.Tab", background=ORANGE_SOFT, foreground=ORANGE_DARK,
                    padding=(22, 9), font=self.f["label"], borderwidth=0,
                    bordercolor=PAGE, lightcolor=ORANGE_SOFT)
        s.map("TNotebook.Tab", background=[("selected", ORANGE), ("active", ORANGE_LINE)],
              foreground=[("selected", WHITE)], lightcolor=[("selected", ORANGE)],
              expand=[("selected", (0, 0, 0, 0))])

        s.configure("Treeview", background=WHITE, fieldbackground=WHITE, foreground=TEXT,
                    rowheight=30, borderwidth=0, font=self.f["base"])
        s.map("Treeview", background=[("selected", ORANGE)], foreground=[("selected", WHITE)])
        s.configure("Treeview.Heading", background=ORANGE, foreground=WHITE,
                    font=self.f["label"], padding=(6, 7), borderwidth=0,
                    bordercolor=ORANGE, lightcolor=ORANGE, darkcolor=ORANGE)
        s.map("Treeview.Heading", background=[("active", ORANGE_DARK)])
        s.configure("Vertical.TScrollbar", background=ORANGE_SOFT, troughcolor=WHITE,
                    bordercolor=WHITE, arrowcolor=ORANGE, lightcolor=ORANGE_SOFT,
                    darkcolor=ORANGE_SOFT)

    def _build_header(self):
        header = ttk.Frame(self, style="Header.TFrame", padding=(24, 16))
        header.pack(fill="x")
        ttk.Label(header, text="Peter Lynch Fair Value", style="HeaderTitle.TLabel").pack(
            anchor="w")
        self.header_sub = ttk.Label(
            header, text="Valoarea corectă a unei acțiuni: P/E corect = rata de creștere "
                         "a profitului (PEG = 1)", style="HeaderSub.TLabel")
        self.header_sub.pack(anchor="w")

    def _build_scroll_area(self):
        """Tab-ul de evaluare derulează vertical când conținutul nu încape."""
        tab = self.eval_tab
        self.canvas = tk.Canvas(tab, bg=PAGE, highlightthickness=0, borderwidth=0)
        self.vscroll = ttk.Scrollbar(tab, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.eval_body = ttk.Frame(self.canvas, style="Page.TFrame")
        self.body_window = self.canvas.create_window(0, 0, window=self.eval_body, anchor="nw")
        self.canvas.bind("<Configure>", lambda _e: self._fit_body())
        self.eval_body.bind("<Configure>", lambda _e: self._fit_body())

    def _fit_body(self):
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        need = self.eval_body.winfo_reqheight()
        # Conținutul umple cel puțin înălțimea vizibilă, ca să se întindă cardurile.
        self.canvas.itemconfigure(self.body_window, width=cw, height=max(need, ch))
        self.canvas.configure(scrollregion=(0, 0, cw, max(need, ch)))
        overflow = need > ch + 1
        if overflow and not self.vscroll.winfo_ismapped():
            self.vscroll.pack(side="right", fill="y", before=self.canvas)
        elif not overflow and self.vscroll.winfo_ismapped():
            self.vscroll.pack_forget()
            self.canvas.yview_moveto(0)

    def _scroll_eval(self, units):
        if self.notebook.select() == str(self.eval_tab) and self.vscroll.winfo_ismapped():
            self.canvas.yview_scroll(units, "units")

    def _on_wheel(self, event):
        if event.widget is self.notes or str(event.widget).startswith(str(self.tree)):
            return
        delta = event.delta
        self._scroll_eval(int(-delta / 120) if abs(delta) >= 120 else -delta)

    def _on_touchpad(self, event):
        if event.widget is self.notes:
            return
        try:
            _dx, dy = self.tk.splitlist(self.tk.call("tk::PreciseScrollDeltas", event.delta))
        except tk.TclError:
            return
        dy = float(dy)
        if dy:
            self._scroll_eval(-1 if dy > 0 else 1)

    # ---------- Responsive ----------
    def _on_configure(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(60, self._apply_responsive)

    def _apply_responsive(self):
        self._resize_job = None
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50:
            return
        # Fonturile urmează mărimea ferestrei, în pași de 5%, între 80% și 115%.
        scale = min(w / DESIGN_W, h / DESIGN_H)
        scale = round(max(0.8, min(1.15, scale)) * 20) / 20
        if scale != self.scale:
            self.scale = scale
            for name, (size, _weight) in self.font_sizes.items():
                self.f[name].configure(size=max(9, round(size * scale)))
            ttk.Style(self).configure("Treeview", rowheight=round(30 * scale))

        self._layout_eval(w)
        self._layout_history(w)
        self.header_sub.configure(wraplength=max(200, w - 60))
        self.update_idletasks()
        self._update_wraps()
        self._fit_body()

    def _layout_eval(self, w):
        mode = "stack" if w < STACK_BELOW else "side"
        if mode != self.eval_mode:
            self.eval_mode = mode
            body = self.eval_body
            if mode == "side":
                body.columnconfigure(0, weight=2, minsize=0, uniform="")
                body.columnconfigure(1, weight=3)
                body.rowconfigure(0, weight=1)
                body.rowconfigure(1, weight=0)
                self.form_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16), pady=0)
                self.results_card.grid(row=0, column=1, sticky="nsew")
            else:
                body.columnconfigure(0, weight=1)
                body.columnconfigure(1, weight=0)
                body.rowconfigure(0, weight=0)
                body.rowconfigure(1, weight=1)
                self.form_card.grid(row=0, column=0, columnspan=1, sticky="nsew",
                                    padx=0, pady=(0, 16))
                self.results_card.grid(row=1, column=0, sticky="nsew")
        cols = 1 if w < FORM_ONE_COL_BELOW else 2
        if cols != self.form_cols:
            self.form_cols = cols
            self._layout_form(cols)

    def _layout_form(self, cols):
        row = 1
        for widget, r2, c2, span2, pady in self.form_items:
            if cols == 2:
                padx = (0, 0) if span2 == 2 else ((0, 6) if c2 == 0 else (6, 0))
                widget.grid(row=r2, column=c2, columnspan=span2, padx=padx, pady=pady)
            else:
                widget.grid(row=row, column=0, columnspan=2, padx=0, pady=pady)
                row += 1

    def _update_wraps(self):
        rw = self.results_card.winfo_width() - 44
        if rw > 50:
            self.warn_label.configure(wraplength=rw)
            self.explain_label.configure(wraplength=rw)
            for label in self.row_labels:
                label.configure(wraplength=max(120, int(rw * 0.62)))
            # Verdictul trece sub valoare când nu mai încape alături.
            narrow = rw < self.fair_label.winfo_reqwidth() + self.verdict_label.winfo_reqwidth() + 20
            if narrow:
                self.verdict_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
                self.fair_caption.grid(row=4, column=0, columnspan=2, sticky="w")
            else:
                self.verdict_label.grid(row=2, column=1, columnspan=1, sticky="e", pady=0)
                self.fair_caption.grid(row=3, column=0, columnspan=2, sticky="w")

    def _layout_history(self, w):
        level = next(i for i, (min_w, _cols) in enumerate(HISTORY_COLUMNS) if w >= min_w)
        if level == self.history_level:
            return
        self.history_level = level
        cols = HISTORY_COLUMNS[level][1]
        self.tree.configure(displaycolumns=cols if cols else "#all")
        if w < 760:
            self.search_hint.pack_forget()
            self.finder_btn.pack_forget()
            self.finder_btn.pack(side="left", pady=(8, 0), in_=self.bottom2)
            self.bottom2.pack(fill="x")
        else:
            self.search_hint.pack(side="right", padx=8, after=self.search_entry)
            self.finder_btn.pack_forget()
            self.bottom2.pack_forget()
            self.finder_btn.pack(side="right", in_=self.bottom)

    def _card(self, parent, title):
        card = ttk.Frame(parent, style="Card.TFrame", padding=20)
        ttk.Label(card, text=title, style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        return card

    # ---------- Tab: evaluare ----------
    def _build_eval_tab(self):
        body = self.eval_body

        form = self._card(body, "Date companie")
        self.form_card = form
        form.columnconfigure(0, weight=1, uniform="formcol")
        form.columnconfigure(1, weight=1, uniform="formcol")

        self.vars = {
            "company": tk.StringVar(),
            "ticker": tk.StringVar(),
            "currency": tk.StringVar(value="USD"),
            "price": tk.StringVar(),
            "eps": tk.StringVar(),
            "growth": tk.StringVar(),
            "dividend": tk.StringVar(),
        }
        self.cap_var = tk.BooleanVar(value=True)
        # (widget, rând, coloană, colspan, pady) pentru aranjarea pe două coloane;
        # pe o coloană se păstrează aceeași ordine.
        self.form_items = []

        def place(widget, row, col, span=1, pady=5, sticky="we"):
            widget.grid(sticky=sticky)
            self.form_items.append((widget, row, col, span, pady))

        def field(row, col, key, label, hint, colspan=1):
            box = ttk.Frame(form, style="Plain.TFrame")
            top = ttk.Frame(box, style="Plain.TFrame")
            top.pack(fill="x")
            ttk.Label(top, text=label, style="Field.TLabel").pack(side="left")
            ttk.Label(top, text=hint, style="Muted.TLabel").pack(side="right")
            entry = ttk.Entry(box, textvariable=self.vars[key], font=self.f["base"], width=8)
            entry.pack(fill="x", pady=(3, 0))
            place(box, row, col, colspan)
            return entry

        field(1, 0, "company", "Nume companie *", "ex. Apple Inc.", colspan=2).focus_set()
        field(2, 0, "ticker", "Ticker", "opțional")

        cur_box = ttk.Frame(form, style="Plain.TFrame")
        ttk.Label(cur_box, text="Monedă", style="Field.TLabel").pack(anchor="w")
        ttk.Combobox(cur_box, textvariable=self.vars["currency"], values=CURRENCIES,
                     font=self.f["base"], width=6, state="readonly").pack(fill="x", pady=(3, 0))
        place(cur_box, 2, 1)

        field(3, 0, "price", "Preț curent *", "bursă")
        field(3, 1, "eps", "EPS (TTM) *", "12 luni")
        field(4, 0, "growth", "Creștere EPS % *", "3–5 ani")
        field(4, 1, "dividend", "Dividend / acț.", "anual")

        place(ttk.Checkbutton(form, text=f"Plafonează creșterea la {GROWTH_CAP:g}% (recomandat)",
                              variable=self.cap_var), 5, 0, 2, (10, 4), sticky="w")
        place(ttk.Label(form, text="Note", style="Field.TLabel"), 6, 0, 2, (8, 3), sticky="w")
        self.notes = tk.Text(form, height=3, width=20, wrap="word", font=self.f["base"], bg=WHITE,
                             fg=TEXT, insertbackground=TEXT, relief="flat",
                             highlightthickness=1, highlightbackground=ORANGE_LINE,
                             highlightcolor=ORANGE, padx=8, pady=6,
                             selectbackground=ORANGE_SOFT, selectforeground=TEXT)
        place(self.notes, 7, 0, 2, 0)

        buttons = ttk.Frame(form, style="Plain.TFrame")
        ttk.Button(buttons, text="Calculează", style="Accent.TButton",
                   command=self.on_calculate).pack(side="left")
        self.save_btn = ttk.Button(buttons, text="Salvează", style="Ghost.TButton",
                                   command=self.on_save, state="disabled")
        self.save_btn.pack(side="left", padx=8)
        ttk.Button(buttons, text="Golește", style="Ghost.TButton",
                   command=self.on_reset).pack(side="right")
        place(buttons, 8, 0, 2, (18, 0))
        place(ttk.Label(form, text="Enter = calculează  ·  ⌘S = salvează", style="Muted.TLabel"),
              9, 0, 2, (10, 0), sticky="w")

        self.bind("<Return>", lambda e: None if e.widget is self.notes else self.on_calculate())
        self.bind("<Command-s>", lambda _e: self.on_save())

        # Rezultate
        results = self._card(body, "Rezultat")
        self.results_card = results
        results.columnconfigure(0, weight=1)
        results.columnconfigure(1, weight=1)

        self.company_label = ttk.Label(results, text="Completează datele și apasă Calculează",
                                       style="Muted.TLabel")
        self.company_label.grid(row=1, column=0, columnspan=2, sticky="w")
        self.fair_label = ttk.Label(results, text="—", style="Big.TLabel")
        self.fair_label.grid(row=2, column=0, sticky="w")
        self.verdict_label = tk.Label(results, text="", font=self.f["verdict"], bg=WHITE,
                                      padx=14, pady=6)
        self.verdict_label.grid(row=2, column=1, sticky="e")
        self.fair_caption = ttk.Label(results, text="Fair value (Peter Lynch)",
                                      style="Muted.TLabel")
        self.fair_caption.grid(row=3, column=0, columnspan=2, sticky="w")

        tiles = ttk.Frame(results, style="Plain.TFrame")
        tiles.grid(row=5, column=0, columnspan=2, sticky="we", pady=(14, 8))
        self.tiles = {}
        for i, (key, title) in enumerate([("upside", "Potențial"), ("peg", "PEG"),
                                          ("lynch", "Lynch ratio")]):
            tiles.columnconfigure(i, weight=1, uniform="tile")
            tile = ttk.Frame(tiles, style="Tile.TFrame", padding=(12, 10))
            tile.grid(row=0, column=i, sticky="nsew",
                      padx=(0 if i == 0 else 4, 0 if i == 2 else 4))
            ttk.Label(tile, text=title, style="TileTitle.TLabel").pack(anchor="w")
            value = ttk.Label(tile, text="—", style="TileValue.TLabel")
            value.pack(anchor="w")
            note = ttk.Label(tile, text="", style="TileTitle.TLabel")
            note.pack(anchor="w")
            self.tiles[key] = (value, note)

        self.result_rows = {}
        self.row_labels = []
        rows = [
            ("price", "Preț curent"),
            ("basic", "Fair value fără dividend (EPS × creștere)"),
            ("pe", "P/E curent"),
            ("fair_pe", "P/E corect (creștere + randament dividend)"),
            ("growth", "Creștere folosită în calcul"),
            ("yield", "Randament dividend"),
        ]
        for i, (key, label) in enumerate(rows, start=5):
            ttk.Separator(results).grid(row=i * 2, column=0, columnspan=2, sticky="we")
            name = ttk.Label(results, text=label, justify="left")
            name.grid(row=i * 2 + 1, column=0, sticky="w", pady=4)
            self.row_labels.append(name)
            value = ttk.Label(results, text="—", style="Value.TLabel")
            value.grid(row=i * 2 + 1, column=1, sticky="e", pady=4)
            self.result_rows[key] = value

        self.warn_label = ttk.Label(results, text="", style="Warn.TLabel", wraplength=500,
                                    justify="left")
        self.warn_label.grid(row=40, column=0, columnspan=2, sticky="w", pady=(12, 0))
        results.rowconfigure(41, weight=1)
        explain = ("Lynch ratio = (creștere + randament dividend) / P/E: sub 1 neatractivă, "
                   "1.5 acceptabilă, peste 2 excelentă.")
        self.explain_label = ttk.Label(results, text=explain, style="Muted.TLabel",
                                       wraplength=500, justify="left")
        self.explain_label.grid(row=42, column=0, columnspan=2, sticky="sw", pady=(8, 0))

    def read_form(self) -> LynchInput:
        v = self.vars
        return LynchInput(
            company=v["company"].get(),
            ticker=v["ticker"].get(),
            currency=v["currency"].get() or "USD",
            price=parse_number(v["price"].get(), "Preț curent"),
            eps=parse_number(v["eps"].get(), "EPS"),
            growth=parse_number(v["growth"].get(), "Creștere EPS"),
            dividend=parse_number(v["dividend"].get(), "Dividend", required=False),
            cap_growth=self.cap_var.get(),
            notes=self.notes.get("1.0", "end").strip(),
        )

    def on_calculate(self):
        try:
            inp = self.read_form()
            res = calculate(inp)
        except ValueError as e:
            messagebox.showerror("Date invalide", str(e), parent=self)
            return
        self.last = (inp, res)
        self.show_result(inp, res)
        self.save_btn.config(state="normal", style="Accent.TButton")

    def show_result(self, inp, res):
        cur = inp.currency
        up = res.upside_pct >= 0
        name = inp.company.strip() + (f" ({inp.ticker.strip().upper()})" if inp.ticker.strip()
                                      else "")
        self.company_label.config(text=name)
        self.fair_label.config(text=f"{fmt(res.fair_value)} {cur}")
        self.verdict_label.config(text=res.verdict, fg=GREEN if up else RED,
                                  bg=GREEN_SOFT if up else RED_SOFT)

        value, note = self.tiles["upside"]
        value.config(text=f"{res.upside_pct:+.1f}%", foreground=GREEN if up else RED)
        note.config(text="față de prețul curent")
        value, note = self.tiles["peg"]
        value.config(text=fmt(res.peg), foreground=GREEN if res.peg <= 1 else RED)
        note.config(text="ideal ≤ 1")
        value, note = self.tiles["lynch"]
        value.config(text=f"{res.lynch_ratio:.2f}",
                     foreground=GREEN if res.lynch_ratio >= 1.5 else
                     (ORANGE_DARK if res.lynch_ratio >= 1 else RED))
        note.config(text=lynch_ratio_label(res.lynch_ratio))

        r = self.result_rows
        r["price"].config(text=f"{fmt(inp.price)} {cur}")
        r["basic"].config(text=f"{fmt(res.fair_value_basic)} {cur}")
        r["pe"].config(text=fmt(res.pe))
        r["fair_pe"].config(text=fmt(res.growth_used + res.dividend_yield))
        r["growth"].config(text=f"{res.growth_used:g}%")
        r["yield"].config(text=f"{res.dividend_yield:.2f}%")
        self.warn_label.config(text="\n".join("⚠ " + w for w in res.warnings))

    def on_save(self):
        if not self.last:
            return
        # Recalculăm din formular, ca să nu salvăm date modificate după calcul.
        try:
            inp = self.read_form()
            res = calculate(inp)
        except ValueError as e:
            messagebox.showerror("Date invalide", str(e), parent=self)
            return
        self.show_result(inp, res)
        self.storage.save(inp, res)
        self.refresh_history()
        self.save_btn.config(state="disabled", style="Ghost.TButton")
        messagebox.showinfo("Salvat", f"Evaluarea pentru {inp.company.strip()} a fost salvată.",
                            parent=self)

    def on_reset(self):
        for key, var in self.vars.items():
            var.set("USD" if key == "currency" else "")
        self.cap_var.set(True)
        self.notes.delete("1.0", "end")
        self.last = None
        self.save_btn.config(state="disabled", style="Ghost.TButton")
        self.company_label.config(text="Completează datele și apasă Calculează")
        self.fair_label.config(text="—")
        self.verdict_label.config(text="", bg=WHITE)
        for value, note in self.tiles.values():
            value.config(text="—", foreground=TEXT)
            note.config(text="")
        for label in self.result_rows.values():
            label.config(text="—")
        self.warn_label.config(text="")

    # ---------- Tab: istoric ----------
    def _build_history_tab(self):
        tab = self.history_tab
        card = ttk.Frame(tab, style="Card.TFrame", padding=20)
        card.pack(fill="both", expand=True)

        top = ttk.Frame(card, style="Plain.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Evaluări salvate", style="Section.TLabel").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_history())
        self.search_entry = ttk.Entry(top, textvariable=self.search_var, width=18,
                                      font=self.f["base"])
        self.search_entry.pack(side="right", padx=(12, 0))
        self.search_hint = ttk.Label(top, text="Caută companie / ticker", style="Muted.TLabel")
        self.search_hint.pack(side="right", padx=8)

        cols = [
            ("created_at", "Data", 150), ("company", "Companie", 170), ("ticker", "Ticker", 70),
            ("price", "Preț", 100), ("eps", "EPS", 65), ("growth", "Creștere %", 90),
            ("fair_value", "Fair value", 110), ("upside_pct", "Potențial", 85),
            ("lynch_ratio", "Lynch", 65), ("verdict", "Verdict", 170),
        ]
        frame = ttk.Frame(card, style="Plain.TFrame")
        frame.pack(fill="both", expand=True, pady=14)
        self.tree = ttk.Treeview(frame, columns=[c[0] for c in cols], show="headings",
                                 selectmode="browse")
        for key, title, width in cols:
            self.tree.heading(key, text=title)
            anchor = "w" if key in ("created_at", "company", "ticker", "verdict") else "e"
            self.tree.column(key, width=width, minwidth=50, anchor=anchor, stretch=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.tag_configure("odd", background=ORANGE_SOFT)
        self.tree.tag_configure("up", foreground=GREEN)
        self.tree.tag_configure("down", foreground=RED)
        self.tree.bind("<Double-1>", lambda _e: self.on_load())

        self.bottom = ttk.Frame(card, style="Plain.TFrame")
        self.bottom.pack(fill="x")
        ttk.Button(self.bottom, text="Reevaluează", style="Accent.TButton",
                   command=self.on_load).pack(side="left")
        ttk.Button(self.bottom, text="Șterge", style="Ghost.TButton",
                   command=self.on_delete).pack(side="left", padx=8)
        ttk.Button(self.bottom, text="Exportă CSV…", style="Ghost.TButton",
                   command=self.on_export).pack(side="left")
        # Pe ferestre înguste butonul Finder trece pe al doilea rând.
        self.bottom2 = ttk.Frame(card, style="Plain.TFrame")
        self.finder_btn = ttk.Button(card, text="Arată baza de date în Finder",
                                     style="Ghost.TButton",
                                     command=lambda: subprocess.run(["open", "-R", str(DB_PATH)]))
        self.finder_btn.pack(side="right", in_=self.bottom)

    def refresh_history(self):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.storage.list(self.search_var.get())):
            cur = r["currency"] or ""
            tags = ["up" if r["upside_pct"] >= 0 else "down"]
            if i % 2:
                tags.append("odd")
            self.tree.insert("", "end", iid=str(r["id"]), tags=tags,
                             values=(
                                 r["created_at"], r["company"], r["ticker"],
                                 f"{fmt(r['price'])} {cur}", fmt(r["eps"]),
                                 f"{r['growth']:g}", f"{fmt(r['fair_value'])} {cur}",
                                 f"{r['upside_pct']:+.1f}%", f"{r['lynch_ratio']:.2f}",
                                 r["verdict"],
                             ))

    def selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Selectează", "Selectează mai întâi o evaluare din listă.",
                                parent=self)
            return None
        return int(sel[0])

    def on_load(self):
        eval_id = self.selected_id()
        if eval_id is None:
            return
        r = self.storage.get(eval_id)
        self.on_reset()
        self.vars["company"].set(r["company"])
        self.vars["ticker"].set(r["ticker"] or "")
        self.vars["currency"].set(r["currency"] or "USD")
        self.vars["price"].set(f"{r['price']:g}")
        self.vars["eps"].set(f"{r['eps']:g}")
        self.vars["growth"].set(f"{r['growth']:g}")
        self.vars["dividend"].set(f"{r['dividend']:g}")
        self.cap_var.set(r["growth_used"] < r["growth"] or r["growth"] <= GROWTH_CAP)
        self.notes.insert("1.0", r["notes"] or "")
        self.notebook.select(self.eval_tab)
        self.on_calculate()

    def on_delete(self):
        eval_id = self.selected_id()
        if eval_id is None:
            return
        r = self.storage.get(eval_id)
        if messagebox.askyesno("Șterge evaluarea",
                               f"Ștergi evaluarea pentru {r['company']} din {r['created_at']}?",
                               parent=self):
            self.storage.delete(eval_id)
            self.refresh_history()

    def on_export(self):
        dest = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv", initialfile="evaluari_lynch.csv",
            filetypes=[("CSV", "*.csv")])
        if not dest:
            return
        count = self.storage.export_csv(Path(dest), self.search_var.get())
        messagebox.showinfo("Export", f"Am exportat {count} evaluări în:\n{dest}", parent=self)


if __name__ == "__main__":
    os.umask(0o077)  # fișierele create de aplicație sunt accesibile doar utilizatorului
    App().mainloop()
