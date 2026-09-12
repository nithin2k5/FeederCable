import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import csv
import os

try:
    from PIL import Image, ImageTk
    _pil_ok = True
except ImportError:
    _pil_ok = False

import db

# ── Palette ──────────────────────────────────────────────────────────────────
# One place for the page's colors instead of the same hex values retyped into
# every widget. The teal/near-black family is the console's own; OK/NG match
# the greens and reds the Test Console uses for a verdict, so a FAIL reads the
# same here as it did on the machine.
BG        = "#081014"   # page ground
PANEL     = "#0b1620"   # tiles, entries, buttons
BORDER    = "#182c35"   # panel outlines
BORDER_HI = "#23404d"   # outlines that should read as a step brighter
TXT       = "#e8f1f4"
TXT_DIM   = "#6f8794"   # captions, hints, units
TEAL      = "#489fb5"   # the brand accent
OK        = "#3ddc84"
NG        = "#ff5f5f"
WARN      = "#ffb300"
ROW_A     = "#0c131a"   # table stripes
ROW_B     = "#091117"
ROW_FAIL  = "#1d0d10"   # a failed part's row, tinted so it is findable
SEL       = "#1a3340"

# Identity first, then the measured values, then the verdicts -- CAM1/CAM2
# alongside the electrical results and RESULT last, the same left-to-right
# order as Today's PASS Records on the Test Console.
COLS = ("SNO", "DATE", "TIME", "CUSTOMER NAME", "MODEL", "P/NUMBER", "P/NAME",
        "LOTNO", "ALC", "CHANNEL", "IR_VAL", "ACW_VAL", "CONTACT",
        "CAM1", "CAM2", "RESULT")
# Sized so all sixteen add up to ~1445px and RESULT is on screen without
# scrolling sideways on the machine's own display -- the verdict being the one
# column you must scroll to reach would defeat the ordering above. CUSTOMER
# NAME and P/NAME are the two that stretch, so a wider screen goes to the
# free-text fields rather than padding every number.
COL_W = {"SNO": 50, "DATE": 95, "TIME": 80, "CUSTOMER NAME": 125, "MODEL": 95,
         "P/NUMBER": 115, "P/NAME": 115, "LOTNO": 165, "ALC": 60, "CHANNEL": 75,
         "IR_VAL": 85, "ACW_VAL": 90, "CONTACT": 85, "CAM1": 65, "CAM2": 65,
         "RESULT": 80}

PREVIEW_W, PREVIEW_H = 230, 150  # fixed image box -- a predictable, centered thumbnail


def _valid_date(txt: str) -> bool:
    try:
        datetime.datetime.strptime(txt.strip(), "%Y-%m-%d")
        return True
    except (AttributeError, ValueError):
        return False


def render(parent):
    # Every style here is namespaced. The page used to configure the bare
    # "Treeview"/"TCombobox", which are the defaults every other page's plain
    # widgets inherit -- so opening the report restyled tables elsewhere in the
    # app and left them that way for the rest of the session.
    style = ttk.Style()
    # Same theme the rest of the app asks for. The native Windows theme ignores
    # most colour options on Combobox and Treeview, so without this the filter
    # dropdowns render as light-on-light when the page is opened standalone.
    try: style.theme_use("clam")
    except Exception: pass
    style.configure("Report.Treeview.Heading", background="#0a1920", foreground=TXT,
                    font=("Arial", 10, "bold"), relief="flat",
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
    # Headings otherwise brighten on hover/press (the theme's built-in states);
    # pin them so a column header stays flat while being clicked to sort.
    style.map("Report.Treeview.Heading",
              background=[("active", "#0e2530"), ("pressed", "#0e2530")],
              foreground=[("active", TEAL), ("pressed", TEAL)])
    style.configure("Report.Treeview", background=ROW_A, foreground=TXT,
                    fieldbackground=ROW_A, font=("Consolas", 10), rowheight=29,
                    bordercolor=BORDER)
    style.map("Report.Treeview", background=[("selected", SEL)],
              foreground=[("selected", TXT)])
    style.configure("Report.TCombobox", fieldbackground=PANEL, background=PANEL,
                    foreground=TXT, arrowcolor=TEAL, bordercolor=BORDER)
    style.map("Report.TCombobox",
              fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TXT)],
              selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", TXT)])

    content = tk.Frame(parent, bg=BG, bd=1, relief="solid",
                       highlightbackground=BORDER, highlightthickness=1)
    content.pack(fill="both", expand=True, padx=5, pady=5)

    # ── Header: brand, page name, and the numbers that summarise the search ──
    header = tk.Frame(content, bg=BG, height=86, bd=1, relief="solid",
                      highlightbackground=BORDER, highlightthickness=1)
    header.pack(fill="x", padx=10, pady=(10, 5))
    header.pack_propagate(False)

    logo_frame = tk.Frame(header, bg=BG, bd=1, relief="solid",
                          highlightbackground=TEAL, highlightthickness=1, padx=14, pady=4)
    logo_frame.pack(side="left", padx=(16, 18), pady=10)
    logo_top = tk.Frame(logo_frame, bg=BG); logo_top.pack()
    tk.Label(logo_top, text="IN", fg="red", bg=BG, font=("Arial", 17, "bold")).pack(side="left")
    tk.Label(logo_top, text="FAC", fg=TEAL, bg=BG, font=("Arial", 17, "bold")).pack(side="left")
    tk.Label(logo_frame, text="INDIA", fg=TEAL, bg=BG, font=("Arial", 10, "bold")).pack()

    title_box = tk.Frame(header, bg=BG); title_box.pack(side="left", pady=10)
    tk.Label(title_box, text="REPORT", fg=TXT, bg=BG,
             font=("Arial", 24, "bold")).pack(anchor="w")
    tk.Label(title_box, text="TEST HISTORY  ·  ALL PARTS  ·  ALL SHIFTS", fg=TXT_DIM, bg=BG,
             font=("Arial", 8, "bold")).pack(anchor="w")

    # Stat tiles, right-aligned. Packed right-to-left so they read
    # TOTAL · PASS · FAIL · NG% left-to-right on screen.
    stats_box = tk.Frame(header, bg=BG)
    stats_box.pack(side="right", padx=(0, 16), pady=10)

    def _stat_tile(caption, color):
        box = tk.Frame(stats_box, bg=PANEL, bd=1, relief="solid",
                       highlightbackground=BORDER_HI, highlightthickness=1,
                       padx=16, pady=5)
        box.pack(side="right", padx=(8, 0))
        val = tk.Label(box, text="—", bg=PANEL, fg=color, font=("Consolas", 17, "bold"))
        val.pack()
        tk.Label(box, text=caption, bg=PANEL, fg=TXT_DIM, font=("Arial", 8, "bold")).pack()
        return val

    st_ngpct = _stat_tile("NG %", WARN)
    st_fail  = _stat_tile("FAIL", NG)
    st_pass  = _stat_tile("PASS", OK)
    st_total = _stat_tile("PARTS", TXT)

    # ── Filter bar: the query on the left, the judged frame on the right ─────
    filter_bar = tk.Frame(content, bg=BG, bd=1, relief="solid",
                          highlightbackground=BORDER, highlightthickness=1)
    filter_bar.pack(fill="x", padx=10, pady=5)

    filter_inner = tk.Frame(filter_bar, bg=BG, padx=14, pady=10)
    filter_inner.pack(side="left")

    def mk_cap(parent, txt):
        return tk.Label(parent, text=txt, bg=BG, fg=TXT_DIM, font=("Arial", 9, "bold"))

    def mk_entry(parent, w=16):
        return tk.Entry(parent, font=("Consolas", 11), width=w, bg=PANEL, fg=TXT,
                        insertbackground=TEAL, bd=1, relief="solid",
                        highlightbackground=BORDER, highlightcolor=TEAL, highlightthickness=1)

    try:
        with db.get_cursor() as cur:
            cur.execute("SELECT DISTINCT pno FROM testmaster ORDER BY pno")
            pno_list = ["ALL"] + [r[0] for r in cur.fetchall()]
    except Exception:
        pno_list = ["ALL"]

    # Caption above field, two fields per column -- the captions used to sit to
    # the left of every box, so the four labels and four boxes made eight
    # ragged columns across the bar.
    mk_cap(filter_inner, "PART NUMBER").grid(row=0, column=0, sticky="w", padx=(0, 18))
    cb_pno = ttk.Combobox(filter_inner, values=pno_list, font=("Consolas", 11), width=16,
                          state="readonly", style="Report.TCombobox")
    cb_pno.current(0)
    cb_pno.grid(row=1, column=0, sticky="w", padx=(0, 18), pady=(1, 8))

    mk_cap(filter_inner, "RESULT").grid(row=0, column=1, sticky="w", padx=(0, 18))
    cb_result = ttk.Combobox(filter_inner, values=["ALL", "PASS", "FAIL"], font=("Consolas", 11),
                             width=10, state="readonly", style="Report.TCombobox")
    cb_result.current(0)
    cb_result.grid(row=1, column=1, sticky="w", padx=(0, 18), pady=(1, 8))

    mk_cap(filter_inner, "START DATE").grid(row=0, column=2, sticky="w", padx=(0, 10))
    ent_start = mk_entry(filter_inner, 13)
    ent_start.grid(row=1, column=2, sticky="w", padx=(0, 10), pady=(1, 8))

    mk_cap(filter_inner, "END DATE").grid(row=0, column=3, sticky="w", padx=(0, 18))
    ent_end = mk_entry(filter_inner, 13)
    ent_end.grid(row=1, column=3, sticky="w", padx=(0, 18), pady=(1, 8))

    def _fill_dates(start: datetime.date, end: datetime.date):
        for ent, val in ((ent_start, start), (ent_end, end)):
            ent.delete(0, "end"); ent.insert(0, val.strftime("%Y-%m-%d"))

    _fill_dates(datetime.date.today() - datetime.timedelta(days=7), datetime.date.today())

    # Quick ranges -- typing two ISO dates by hand to answer "how did today go"
    # was the most common thing this page asked for.
    chip_row = tk.Frame(filter_inner, bg=BG)
    chip_row.grid(row=2, column=0, columnspan=4, sticky="w")
    tk.Label(chip_row, text="QUICK", bg=BG, fg=TXT_DIM, font=("Arial", 8, "bold")).pack(side="left", padx=(0, 8))

    def _range_chip(text, fn):
        b = tk.Label(chip_row, text=text, bg=PANEL, fg=TEAL, font=("Arial", 9, "bold"),
                     bd=1, relief="solid", padx=10, pady=2, cursor="hand2")
        b.pack(side="left", padx=(0, 6))
        b.bind("<Button-1>", lambda e: (fn(), _do_search()))
        b.bind("<Enter>", lambda e: b.config(bg="#122a33"))
        b.bind("<Leave>", lambda e: b.config(bg=PANEL))
        return b

    _today = datetime.date.today
    _range_chip("TODAY",      lambda: _fill_dates(_today(), _today()))
    _range_chip("7 DAYS",     lambda: _fill_dates(_today() - datetime.timedelta(days=6), _today()))
    _range_chip("30 DAYS",    lambda: _fill_dates(_today() - datetime.timedelta(days=29), _today()))
    _range_chip("THIS MONTH", lambda: _fill_dates(_today().replace(day=1), _today()))

    btn_frame = tk.Frame(filter_inner, bg=BG)
    btn_frame.grid(row=0, column=4, rowspan=3, padx=(24, 0))

    def mk_button(text, cmd, accent=TEAL):
        b = tk.Button(btn_frame, text=text, bg=PANEL, fg=TXT, font=("Arial", 11, "bold"),
                      bd=1, relief="solid", highlightbackground=accent, highlightthickness=1,
                      padx=16, pady=6, cursor="hand2", activebackground="#122a33",
                      activeforeground=accent, command=cmd)
        b.pack(fill="x", pady=4)
        return b

    # Vision image preview -- the frame that was judged, match box already drawn
    # on it by test_console at PASS-with-vision-OK time, for the selected row.
    tk.Frame(filter_bar, bg=BORDER, width=1).pack(side="left", fill="y", pady=8)
    preview_outer = tk.Frame(filter_bar, bg=BG, width=252)
    preview_outer.pack(side="left", fill="y", padx=10, pady=8)
    preview_outer.pack_propagate(False)
    tk.Label(preview_outer, text="VISION FRAME", bg=BG, fg=TXT_DIM,
             font=("Arial", 8, "bold")).pack(anchor="w")
    img_box = tk.Frame(preview_outer, bg="#05080a", width=PREVIEW_W, height=PREVIEW_H,
                       bd=1, relief="solid", highlightbackground=BORDER, highlightthickness=1)
    img_box.pack(pady=(2, 0))
    img_box.pack_propagate(False)
    preview_img_lbl = tk.Label(img_box, bg="#05080a", fg=TXT_DIM, font=("Arial", 10, "bold"),
                               text="Select a row", wraplength=PREVIEW_W - 16, justify="center")
    preview_img_lbl.pack(fill="both", expand=True)
    preview_lot_lbl = tk.Label(preview_outer, bg=BG, fg=TXT_DIM, font=("Consolas", 9),
                               wraplength=PREVIEW_W, justify="center", anchor="center")
    preview_lot_lbl.pack(fill="x", pady=(3, 0))

    # ── Status bar, packed before the table so it stays pinned to the bottom ──
    status_bar = tk.Frame(content, bg=BG, bd=1, relief="solid",
                         highlightbackground=BORDER, highlightthickness=1)
    status_bar.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
    status_lbl = tk.Label(status_bar, text="", bg=BG, fg=TXT_DIM,
                          font=("Consolas", 9), anchor="w", padx=10, pady=4)
    status_lbl.pack(side="left")
    tk.Label(status_bar, text="click a column header to sort  ·  select a row for its vision frame",
             bg=BG, fg="#3f5662", font=("Arial", 8), anchor="e", padx=10).pack(side="right")

    # ── Table ────────────────────────────────────────────────────────────────
    table_outer = tk.Frame(content, bg=BG, bd=1, relief="solid",
                           highlightbackground=BORDER, highlightthickness=1)
    table_outer.pack(fill="both", expand=True, padx=10, pady=(5, 5))

    tree = ttk.Treeview(table_outer, columns=COLS, show="headings", style="Report.Treeview")
    hsb = ttk.Scrollbar(table_outer, orient="horizontal", command=tree.xview)
    vsb = ttk.Scrollbar(table_outer, orient="vertical", command=tree.yview)
    tree.configure(xscrollcommand=hsb.set, yscrollcommand=vsb.set)
    hsb.pack(side="bottom", fill="x")
    vsb.pack(side="right", fill="y")
    tree.pack(side="top", fill="both", expand=True)

    tree.tag_configure("even", background=ROW_A, foreground=TXT)
    tree.tag_configure("odd", background=ROW_B, foreground=TXT)
    # Only failures are tinted. Colouring passes green too would light up the
    # whole table on a good day and leave the one row that matters no louder
    # than its neighbours.
    tree.tag_configure("fail", background=ROW_FAIL, foreground="#ff9a9a")
    tree.tag_configure("empty", background=ROW_A, foreground=TXT_DIM)

    row_images = {}                 # tree item id -> visionimg path from the DB (or "")
    preview_photo = {"img": None}   # keep a reference so Tk doesn't collect it
    sort_state = {"col": None, "desc": False}

    def _show_preview(path, lot_no=""):
        preview_lot_lbl.config(text=f"LOT {lot_no}" if lot_no else "")
        if not path:
            preview_photo["img"] = None
            msg = "No vision image for this record" if lot_no else "Select a row"
            preview_img_lbl.config(image="", text=msg, fg=TXT_DIM)
            return
        if not _pil_ok:
            preview_photo["img"] = None
            preview_img_lbl.config(image="", text="Pillow not installed — can't preview images", fg=WARN)
            return
        if not os.path.exists(path):
            preview_photo["img"] = None
            preview_img_lbl.config(image="", text=f"Image file missing:\n{os.path.basename(path)}", fg=NG)
            return
        try:
            img = Image.open(path)
            # Fit inside the fixed box (a few px of margin) and never larger, so
            # it always lands centered and whole rather than clipped.
            img.thumbnail((PREVIEW_W - 10, PREVIEW_H - 10), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            preview_photo["img"] = photo
            preview_img_lbl.config(image=photo, text="")
        except Exception as ex:
            preview_photo["img"] = None
            preview_img_lbl.config(image="", text=f"Couldn't open image:\n{ex}", fg=NG)

    def _on_row_select(event=None):
        sel = tree.selection()
        if not sel:
            _show_preview("")
            return
        iid = sel[0]
        _show_preview(row_images.get(iid, ""), tree.set(iid, "LOTNO"))

    tree.bind("<<TreeviewSelect>>", _on_row_select)

    def _restripe():
        """Re-tag every visible row. Called after a load and after a sort --
        the stripes follow screen position, not insertion order, so sorting
        without this leaves them interleaved."""
        for pos, iid in enumerate(tree.get_children("")):
            if str(tree.set(iid, "RESULT")).upper() == "FAIL":
                tree.item(iid, tags=("fail",))
            else:
                tree.item(iid, tags=("odd" if pos % 2 else "even",))

    def _sort_by(col):
        items = list(tree.get_children(""))
        if not items or "empty" in tree.item(items[0], "tags"):
            return
        desc = not sort_state["desc"] if sort_state["col"] == col else False

        def key(iid):
            raw = str(tree.set(iid, col)).strip()
            # Numbers sort as numbers and group ahead of text, so an empty
            # IR_VAL does not land in the middle of the readings.
            try:
                return (0, float(raw.replace(",", "")), "")
            except ValueError:
                return (1, 0.0, raw.lower())

        for pos, iid in enumerate(sorted(items, key=key, reverse=desc)):
            tree.move(iid, "", pos)
        sort_state.update(col=col, desc=desc)
        for c in COLS:
            arrow = ("  ▼" if desc else "  ▲") if c == col else ""
            tree.heading(c, text=c + arrow)
        _restripe()

    for col in COLS:
        tree.heading(col, text=col, command=lambda c=col: _sort_by(c))
        tree.column(col, width=COL_W.get(col, 80), anchor="center",
                    stretch=(col in ("CUSTOMER NAME", "P/NAME")))

    def _set_stats(parts: dict):
        total = len(parts)
        failed = sum(1 for v in parts.values() if str(v).upper() == "FAIL")
        passed = total - failed
        st_total.config(text=str(total) if total else "—")
        st_pass.config(text=str(passed) if total else "—")
        st_fail.config(text=str(failed) if total else "—")
        st_ngpct.config(text=f"{failed / total * 100:.1f}" if total else "—")

    def _do_search():
        start, end = ent_start.get().strip(), ent_end.get().strip()
        if not (_valid_date(start) and _valid_date(end)):
            messagebox.showwarning("Date", "Dates must be written as YYYY-MM-DD.")
            return
        if start > end:
            messagebox.showwarning("Date", "The start date is after the end date.")
            return

        tree.delete(*tree.get_children())
        row_images.clear()
        _show_preview("")
        sort_state.update(col=None, desc=False)
        for c in COLS:
            tree.heading(c, text=c)

        pno, res = cb_pno.get(), cb_result.get()
        # One row per channel, not per part: testresult holds a row for each
        # channel of a run, so the stat tiles count distinct (part, lot) pairs
        # instead of rows -- otherwise an 8-channel part counts as eight parts.
        parts = {}
        try:
            with db.get_cursor() as cur:
                query = """
                    SELECT m.date, m.time,
                           (SELECT cname FROM settingmaster s WHERE s.pno=m.pno LIMIT 1) AS cname,
                           m.model, m.pno, m.pname, m.lotno, m.alc,
                           r.channel, r.ir_resistance, r.acw_current, r.contact_result,
                           m.cam1result, m.cam2result, m.result, m.visionimg
                    FROM testmaster m
                    LEFT JOIN testresult r ON m.lotno = r.lotno AND m.pno = r.pno
                    WHERE m.date >= %s AND m.date <= %s
                """
                params = [start, end]
                if pno != "ALL": query += " AND m.pno = %s"; params.append(pno)
                if res != "ALL": query += " AND m.result = %s"; params.append(res)
                query += " ORDER BY m.date DESC, m.time DESC, m.lotno, r.channel"

                cur.execute(query, tuple(params))
                for idx, row in enumerate(cur.fetchall(), start=1):
                    (date, time_, cname, model, r_pno, pname, lotno, alc,
                     channel, ir_val, acw_val, contact, cam1, cam2, result, vimg) = row
                    iid = tree.insert("", "end", values=(
                        idx, date, time_, cname or "", model, r_pno, pname, lotno, alc,
                        channel or "", ir_val or "", acw_val or "", contact or "",
                        # A blank camera verdict means vision was off or the part
                        # has no model -- "—" says that, where "" reads as a bug.
                        cam1 or "—", cam2 or "—", result))
                    row_images[iid] = vimg or ""
                    parts[(r_pno, lotno)] = result
        except Exception as ex:
            messagebox.showerror("DB Error", f"Failed to search: {ex}")
            status_lbl.config(text="search failed", fg=NG)
            return

        _restripe()
        _set_stats(parts)
        rows = len(tree.get_children())
        if not rows:
            tree.insert("", "end", values=("", "", "", "", "", "",
                                           "no records for this filter", "",
                                           "", "", "", "", "", "", "", ""),
                        tags=("empty",))
        filters = f"part {pno}" + ("" if res == "ALL" else f"  ·  {res} only")
        status_lbl.config(text=f"{rows} rows  ·  {len(parts)} parts  ·  {start} → {end}  ·  {filters}",
                          fg=TXT_DIM)

    def _do_export():
        rows = [tree.item(c)["values"] for c in tree.get_children()
                if "empty" not in tree.item(c, "tags")]
        if not rows:
            messagebox.showinfo("Export", "No data to export.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=f"report_{ent_start.get().strip()}_to_{ent_end.get().strip()}.csv",
            title="Save Report")
        if not filepath:
            return
        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(COLS)
                writer.writerows(rows)
            messagebox.showinfo("Export", f"{len(rows)} rows exported to\n{filepath}")
        except Exception as ex:
            messagebox.showerror("Export Error", f"Failed to export: {ex}")

    mk_button("🔍  SEARCH", _do_search)
    mk_button("📄  EXPORT CSV", _do_export)

    # ENTER anywhere in the filter bar runs the search, and changing either
    # dropdown re-runs it -- the page is read by picking a filter, so making
    # the operator then find the button was a step for nothing.
    for widget in (ent_start, ent_end):
        widget.bind("<Return>", lambda e: _do_search())
    cb_pno.bind("<<ComboboxSelected>>", lambda e: _do_search())
    cb_result.bind("<<ComboboxSelected>>", lambda e: _do_search())

    _do_search()  # initial load
