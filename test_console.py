import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
import threading
import datetime

# ─── DB connection (mirrors Function.cs) ─────────────────────────────────────
def get_connection():
    return mysql.connector.connect(
        host="localhost", database="fceol", user="root", password="root"
    )


def render(parent):
    style = ttk.Style()
    style.configure("TLabelframe",
                    background="black", foreground="white", bordercolor="#555")
    style.configure("TLabelframe.Label",
                    background="black", foreground="white", font=('Arial', 10))
    style.configure("Spec.Treeview.Heading",
                    background="#1a1a1a", foreground="white",
                    font=('Arial', 9, 'bold'), bordercolor="#555")
    style.configure("Spec.Treeview",
                    background="#0d0d0d", foreground="white",
                    fieldbackground="#0d0d0d", font=('Arial', 9), rowheight=26)
    style.configure("Hist.Treeview.Heading",
                    background="#111", foreground="white",
                    font=('Arial', 8, 'bold'))
    style.configure("Hist.Treeview",
                    background="#080808", foreground="#ccc",
                    fieldbackground="#080808", font=('Arial', 8), rowheight=22)
    style.map("Spec.Treeview", background=[('selected', '#1c3a5e')])
    style.map("Hist.Treeview", background=[('selected', '#1c3a5e')])

    # ── State ──────────────────────────────────────────────────────────────────
    state = {
        "pno": None,          # current part number
        "spec_data": {},      # {ch: {"IR":[...], "ACW":[...]}}
        "num_channels": 0,
        "test_running": False,
        "total": 0, "ok": 0, "ng": 0,
    }

    # ── Root layout ────────────────────────────────────────────────────────────
    content = tk.Frame(parent, bg="black")
    content.pack(fill="both", expand=True, padx=5, pady=2)
    content.rowconfigure(0, weight=1)
    content.rowconfigure(1, weight=0)
    content.columnconfigure(0, weight=1)

    upper = tk.Frame(content, bg="black")
    upper.grid(row=0, column=0, sticky="nsew")
    upper.columnconfigure(0, weight=1)
    upper.columnconfigure(1, weight=0)
    upper.rowconfigure(0, weight=1)

    left_area = tk.Frame(upper, bg="black")
    left_area.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

    right_panel = tk.Frame(upper, bg="black", width=210)
    right_panel.grid(row=0, column=1, sticky="nsew")
    right_panel.grid_propagate(False)
    right_panel.columnconfigure(0, weight=1)
    right_panel.rowconfigure(0, weight=1)
    right_panel.rowconfigure(1, weight=0)

    # ══════════════════════════════════════════════════════════════════════════
    # RIGHT PANEL — PASS/FAIL result + per-channel mini result
    # ══════════════════════════════════════════════════════════════════════════
    result_outer = tk.Frame(right_panel, bg="#333", padx=1, pady=1)
    result_outer.grid(row=0, column=0, sticky="nsew", pady=(0, 3))

    result_inner = tk.Frame(result_outer, bg="black")
    result_inner.pack(fill="both", expand=True)

    tk.Label(result_inner, text="TEST RESULT", bg="black", fg="#888",
             font=('Arial', 10, 'bold')).pack(fill="x", pady=(6, 2))

    result_lbl = tk.Label(result_inner, text="READY", bg="#1a1a1a", fg="#888",
                          font=('Arial', 36, 'bold'), anchor="center")
    result_lbl.pack(fill="both", expand=True, padx=4, pady=(2, 4))

    # Lot number display
    tk.Label(result_inner, text="LOT NO", bg="black", fg="#555",
             font=('Arial', 8)).pack(fill="x")
    lot_lbl = tk.Label(result_inner, text="—", bg="black", fg="#888",
                       font=('Consolas', 9), anchor="center")
    lot_lbl.pack(fill="x", padx=4, pady=(0, 6))

    # COM Status panel (below result)
    com_lf = ttk.LabelFrame(right_panel, text="COM Status")
    com_lf.grid(row=1, column=0, sticky="ew", pady=(0, 3))
    com_inner = tk.Frame(com_lf, bg="black", padx=4, pady=4)
    com_inner.pack(fill="both")

    com_devices = ["HiPot", "IO Ctrl", "Scanner", "Printer"]
    com_labels = {}
    for i, dev in enumerate(com_devices):
        r, c = divmod(i, 2)
        lbl = tk.Label(com_inner, text=dev, bg="#2a2a2a", fg="#666",
                       font=('Arial', 8), width=9, pady=3, bd=1, relief="solid")
        lbl.grid(row=r, column=c, padx=2, pady=2, sticky="ew")
        com_labels[dev] = lbl
        com_inner.columnconfigure(c, weight=1)

    def set_com_status(dev, connected):
        lbl = com_labels.get(dev)
        if lbl:
            lbl.config(bg="#1b5e20" if connected else "#3a3a3a",
                       fg="white"   if connected else "#666")

    # ══════════════════════════════════════════════════════════════════════════
    # LEFT AREA
    # ══════════════════════════════════════════════════════════════════════════

    # ── Row 1: Product Info + Count ───────────────────────────────────────────
    row1 = tk.Frame(left_area, bg="black")
    row1.pack(fill="x", pady=(0, 3))
    row1.columnconfigure(0, weight=3)
    row1.columnconfigure(1, weight=2)

    # ── Product Info ──────────────────────────────────────────────────────────
    pf = ttk.LabelFrame(row1, text="Product Info")
    pf.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    pi = tk.Frame(pf, bg="black", padx=8, pady=5)
    pi.pack(fill="both", expand=True)
    for col in range(8):
        pi.columnconfigure(col, weight=1 if col % 2 != 0 else 0)

    def mk_lbl(parent, text):
        return tk.Label(parent, text=text, bg="black", fg="#aaa",
                        font=('Arial', 9))

    def mk_entry(parent, w=16, editable=True, fg="white"):
        st = "normal" if editable else "readonly"
        e = tk.Entry(parent, bg="black" if editable else "#0d0d0d",
                     fg=fg, font=('Arial', 10),
                     insertbackground="white", bd=1, relief="solid",
                     width=w, highlightbackground="#555",
                     highlightcolor="#888", highlightthickness=1,
                     readonlybackground="#0d0d0d", state=st)
        return e

    # Row 0: Part Number (interactive) + EMP ID (interactive)
    mk_lbl(pi, "Part No").grid(row=0, column=0, sticky="w", pady=4)
    ent_pno = mk_entry(pi, w=20, editable=True)
    ent_pno.grid(row=0, column=1, columnspan=3, sticky="ew", padx=5)
    mk_lbl(pi, "EMP ID").grid(row=0, column=4, sticky="w", padx=(10, 4))
    ent_emp = mk_entry(pi, w=10, editable=True)
    ent_emp.grid(row=0, column=5, columnspan=3, sticky="ew", padx=5)

    # Row 1: Part Name + Customer
    mk_lbl(pi, "Part Name").grid(row=1, column=0, sticky="w", pady=4)
    ent_pname = mk_entry(pi, w=14, editable=False)
    ent_pname.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5)
    mk_lbl(pi, "Customer").grid(row=1, column=4, sticky="w", padx=(10, 4))
    ent_cust = mk_entry(pi, w=10, editable=False)
    ent_cust.grid(row=1, column=5, columnspan=3, sticky="ew", padx=5)

    # Row 2: Model + ALC + LOT
    mk_lbl(pi, "Model").grid(row=2, column=0, sticky="w", pady=4)
    ent_model = mk_entry(pi, w=10, editable=False)
    ent_model.grid(row=2, column=1, sticky="ew", padx=5)
    mk_lbl(pi, "ALC").grid(row=2, column=2, sticky="w", padx=(10, 4))
    ent_alc = mk_entry(pi, w=6, editable=False)
    ent_alc.grid(row=2, column=3, sticky="ew", padx=5)
    mk_lbl(pi, "LOT No").grid(row=2, column=4, sticky="w", padx=(10, 4))
    ent_lot = mk_entry(pi, w=14, editable=False)
    ent_lot.grid(row=2, column=5, columnspan=2, sticky="ew", padx=5)

    # ── Count Panel ───────────────────────────────────────────────────────────
    cf = ttk.LabelFrame(row1, text="Count")
    cf.grid(row=0, column=1, sticky="nsew")
    ci = tk.Frame(cf, bg="black", padx=8, pady=5)
    ci.pack(fill="both", expand=True)
    ci.columnconfigure(1, weight=1)
    ci.columnconfigure(3, weight=1)

    mk_lbl(ci, "Total").grid(row=0, column=0, sticky="w", pady=3)
    cnt_total = mk_entry(ci, w=6, editable=False)
    cnt_total.grid(row=0, column=1, sticky="ew", padx=5)
    mk_lbl(ci, "NG").grid(row=0, column=2, sticky="w", padx=5)
    cnt_ng = mk_entry(ci, w=6, editable=False, fg="#ff5555")
    cnt_ng.grid(row=0, column=3, sticky="ew", padx=5)

    mk_lbl(ci, "OK").grid(row=1, column=0, sticky="w", pady=3)
    cnt_ok = mk_entry(ci, w=6, editable=False, fg="#76ff03")
    cnt_ok.grid(row=1, column=1, sticky="ew", padx=5)
    mk_lbl(ci, "NG %").grid(row=1, column=2, sticky="w", padx=5)
    cnt_ng_pct = mk_entry(ci, w=6, editable=False, fg="#ff5555")
    cnt_ng_pct.grid(row=1, column=3, sticky="ew", padx=5)

    def update_counts():
        t = state["total"]
        o = state["ok"]
        n = state["ng"]
        pct = f"{(n/t*100):.1f}%" if t > 0 else "0.0%"
        for entry, val in [(cnt_total, str(t)), (cnt_ok, str(o)),
                           (cnt_ng, str(n)), (cnt_ng_pct, pct)]:
            entry.config(state="normal")
            entry.delete(0, "end")
            entry.insert(0, val)
            entry.config(state="readonly")

    # ── Row 2: Inspection Specification (from DB) ──────────────────────────────
    spec_header_frame = tk.Frame(left_area, bg="black")
    spec_header_frame.pack(fill="x", pady=(6, 2))
    tk.Label(spec_header_frame, text="Inspection Specification",
             bg="black", fg="white", font=('Arial', 10, 'bold')).pack(side="left")
    spec_status_lbl = tk.Label(spec_header_frame, text="[ No part loaded ]",
                                bg="black", fg="#555", font=('Arial', 9))
    spec_status_lbl.pack(side="left", padx=10)

    cols_spec = ("TEST", "CH", "APPLIED VOLTS (V)", "TEST TIME (S)", "MIN", "MAX")
    tree_spec = ttk.Treeview(left_area, columns=cols_spec,
                              show="headings", height=6, style="Spec.Treeview")
    spec_widths = {"TEST": 160, "CH": 45, "APPLIED VOLTS (V)": 130,
                   "TEST TIME (S)": 110, "MIN": 80, "MAX": 80}
    for col in cols_spec:
        tree_spec.heading(col, text=col)
        tree_spec.column(col, anchor="center", width=spec_widths.get(col, 90))

    tree_spec.tag_configure("ir",  background="#0d1a0d", foreground="#8bc34a")
    tree_spec.tag_configure("acw", background="#0d0d1a", foreground="#64b5f6")
    tree_spec.tag_configure("contact", background="#1a1a0d", foreground="#ffd54f")
    tree_spec.pack(fill="x")

    # ── Row 3: Testing (live results) ─────────────────────────────────────────
    tk.Label(left_area, text="Testing", bg="black", fg="white",
             font=('Arial', 10, 'bold')).pack(fill="x", pady=(10, 2))

    test_frame = tk.Frame(left_area, bg="black")
    test_frame.pack(fill="x")

    ch_header = ["TEST", "UNIT", "CH1", "CH2", "CH3", "CH4",
                 "CH5", "CH6", "CH7", "CH8", "CH9", "CH10", "RESULT"]
    for i in range(len(ch_header)):
        test_frame.columnconfigure(i, weight=1)

    # Header
    for i, h in enumerate(ch_header):
        tk.Label(test_frame, text=h, bg="#1a1a1a", fg="white",
                 font=('Arial', 8, 'bold'), bd=1, relief="solid",
                 pady=6).grid(row=0, column=i, sticky="nsew")

    # Result row labels (IR, ACW, Contact)
    result_rows = {}
    test_rows_def = [
        ("IR",      "Insulation (IR)", "MΩ"),
        ("ACW",     "Withstand (ACW)", "mA"),
        ("Contact", "Contact",         "—"),
    ]
    for r_idx, (key, name, unit) in enumerate(test_rows_def, start=1):
        tk.Label(test_frame, text=name, bg="#111", fg="white",
                 font=('Arial', 8), bd=1, relief="solid",
                 pady=6).grid(row=r_idx, column=0, sticky="nsew")
        tk.Label(test_frame, text=unit, bg="#111", fg="#ffcc00",
                 font=('Arial', 8, 'bold'), bd=1, relief="solid").grid(
                 row=r_idx, column=1, sticky="nsew")
        row_cells = []
        for ch_i in range(10):
            lbl = tk.Label(test_frame, text="—", bg="#0d0d0d", fg="#444",
                           font=('Arial', 8), bd=1, relief="solid", pady=6)
            lbl.grid(row=r_idx, column=2 + ch_i, sticky="nsew")
            row_cells.append(lbl)
        # Result cell
        res_lbl = tk.Label(test_frame, text="—", bg="#0d0d0d", fg="#444",
                           font=('Arial', 9, 'bold'), bd=1, relief="solid")
        res_lbl.grid(row=r_idx, column=12, sticky="nsew")
        result_rows[key] = {"cells": row_cells, "result": res_lbl}

    def reset_test_display():
        for key in result_rows:
            for cell in result_rows[key]["cells"]:
                cell.config(text="—", bg="#0d0d0d", fg="#444")
            result_rows[key]["result"].config(text="—", bg="#0d0d0d", fg="#444")
        result_lbl.config(text="READY", bg="#1a1a1a", fg="#888")
        lot_lbl.config(text="—")

    def set_cell(test_key, ch_idx, value, passed):
        """Update a single channel cell in the results grid."""
        if ch_idx >= len(result_rows[test_key]["cells"]):
            return
        bg = "#0a3300" if passed else "#330000"
        fg = "#76ff03" if passed else "#ff5555"
        result_rows[test_key]["cells"][ch_idx].config(text=value, bg=bg, fg=fg)

    def set_row_result(test_key, passed):
        bg = "#0a3300" if passed else "#330000"
        fg = "#76ff03" if passed else "#ff5555"
        text = "PASS" if passed else "FAIL"
        result_rows[test_key]["result"].config(text=text, bg=bg, fg=fg)

    # ── Scan banner ────────────────────────────────────────────────────────────
    scan_outer = tk.Frame(left_area, bg="#1b5e20", padx=2, pady=2)
    scan_outer.pack(fill="x", pady=(10, 4))
    scan_lbl = tk.Label(scan_outer,
                        text="Enter Part Number above and press ENTER to load specs",
                        bg="#001830", fg="#888",
                        font=('Arial', 12, 'bold'), pady=10)
    scan_lbl.pack(fill="both", expand=True)

    # Scan entry (shown after test)
    scan_entry_frame = tk.Frame(left_area, bg="black")
    scan_entry_frame.pack(fill="x", pady=(0, 4))
    scan_entry_frame.pack_forget()   # hidden initially

    ent_scan = mk_entry(scan_entry_frame, w=40, editable=True)
    ent_scan.pack(side="left", padx=5, pady=5)

    # ── Row 4: Test History ───────────────────────────────────────────────────
    tk.Label(left_area, text="Recent Test History",
             bg="black", fg="white", font=('Arial', 10, 'bold')).pack(
             fill="x", pady=(6, 2))

    hist_cols = ("DATE", "TIME", "PART NO", "LOT NO", "EMP", "RESULT")
    tree_hist = ttk.Treeview(left_area, columns=hist_cols,
                              show="headings", height=4, style="Hist.Treeview")
    hist_widths = {"DATE": 80, "TIME": 70, "PART NO": 120,
                   "LOT NO": 130, "EMP": 70, "RESULT": 70}
    for col in hist_cols:
        tree_hist.heading(col, text=col)
        tree_hist.column(col, anchor="center", width=hist_widths.get(col, 80))
    tree_hist.tag_configure("pass", foreground="#76ff03")
    tree_hist.tag_configure("fail", foreground="#ff5555")
    tree_hist.pack(fill="x")

    # ══════════════════════════════════════════════════════════════════════════
    # BOTTOM BAR — IO Channels + Log
    # ══════════════════════════════════════════════════════════════════════════
    bottom = tk.Frame(content, bg="black", height=110)
    bottom.grid(row=1, column=0, sticky="ew", pady=(4, 0))
    bottom.grid_propagate(False)
    bottom.columnconfigure(0, weight=4)
    bottom.columnconfigure(1, weight=3)
    bottom.rowconfigure(0, weight=1)

    # IO Cable Data
    io_lf = ttk.LabelFrame(bottom, text="IO Channel State")
    io_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    io_inner = tk.Frame(io_lf, bg="black", padx=5, pady=3)
    io_inner.pack(fill="both", expand=True)

    tk.Label(io_inner, text="INPUT", bg="black", fg="#888",
             font=('Arial', 8, 'bold')).pack(anchor="w")
    in_row = tk.Frame(io_inner, bg="black")
    in_row.pack(anchor="w", pady=(0, 4))
    io_in_labels = []
    for i in range(1, 11):
        lbl = tk.Label(in_row, text=f"CH{i}", bg="#0a1a0a", fg="#2e7d32",
                       font=('Arial', 7), bd=1, relief="solid", width=5)
        lbl.pack(side="left", padx=1)
        io_in_labels.append(lbl)

    tk.Label(io_inner, text="OUTPUT", bg="black", fg="#888",
             font=('Arial', 8, 'bold')).pack(anchor="w")
    out_row = tk.Frame(io_inner, bg="black")
    out_row.pack(anchor="w")
    io_out_labels = []
    for i in range(1, 11):
        lbl = tk.Label(out_row, text=f"CH{i}", bg="#0a1a0a", fg="#2e7d32",
                       font=('Arial', 7), bd=1, relief="solid", width=5)
        lbl.pack(side="left", padx=1)
        io_out_labels.append(lbl)

    def set_io_channel(io_list, ch_idx, active):
        if ch_idx < len(io_list):
            io_list[ch_idx].config(
                bg="#1b5e20" if active else "#0a1a0a",
                fg="#76ff03" if active else "#2e7d32")

    # Log
    log_lf = ttk.LabelFrame(bottom, text="Log")
    log_lf.grid(row=0, column=1, sticky="nsew")
    log_txt = tk.Text(log_lf, bg="black", fg="#aaa",
                      font=('Consolas', 8), bd=0, height=5)
    log_txt.pack(fill="both", expand=True, padx=4, pady=3)
    log_txt.config(state="disabled")

    def log(msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:12]
        log_txt.config(state="normal")
        log_txt.insert("end", f"{ts}  {msg}\n")
        log_txt.see("end")
        log_txt.config(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    # DB FUNCTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def load_specs(pno):
        """
        Load settingmaster + settingspec for a given part number.
        Populates the product info fields and the spec grid.
        Returns True on success.
        """
        try:
            conn = get_connection()
            cur = conn.cursor(dictionary=True)

            # Load master
            cur.execute("SELECT * FROM settingmaster WHERE pno=%s", (pno,))
            master = cur.fetchone()
            if not master:
                messagebox.showwarning("Not Found",
                                       f"Part number '{pno}' not found in settings.")
                cur.close(); conn.close()
                return False

            # Populate product info (read-only fields)
            def fill(entry, val):
                entry.config(state="normal")
                entry.delete(0, "end")
                entry.insert(0, val or "")
                entry.config(state="readonly")

            fill(ent_pname, master.get("pname", ""))
            fill(ent_cust,  master.get("cname", ""))
            fill(ent_model, master.get("model", ""))
            fill(ent_alc,   master.get("alc", ""))

            state["pno"]          = pno
            state["num_channels"] = int(master.get("channel", 1))

            # Load specs
            cur.execute(
                "SELECT testname, channel, appvol, testtime, min, max "
                "FROM settingspec WHERE pno=%s ORDER BY channel, testname",
                (pno,))
            rows = cur.fetchall()
            cur.close(); conn.close()

            # Clear and repopulate spec_data
            spec = {}
            for ch in range(1, state["num_channels"] + 1):
                spec[ch] = {"IR": None, "ACW": None}
            for r in rows:
                ch = int(r["channel"])
                tn = r["testname"]
                if ch in spec and tn in spec[ch]:
                    spec[ch][tn] = {
                        "appvol":   r["appvol"],
                        "testtime": r["testtime"],
                        "min":      r["min"],
                        "max":      r["max"],
                    }
            state["spec_data"] = spec

            # Render spec treeview
            tree_spec.delete(*tree_spec.get_children())
            for ch in range(1, state["num_channels"] + 1):
                for test_key, tag in [("IR", "ir"), ("ACW", "acw")]:
                    s = spec[ch].get(test_key) or {}
                    tree_spec.insert("", "end", tags=(tag,),
                                     values=(test_key, str(ch),
                                             s.get("appvol", "—"),
                                             s.get("testtime", "—"),
                                             s.get("min", "—"),
                                             s.get("max", "—")))
                tree_spec.insert("", "end", tags=("contact",),
                                 values=("Contact", str(ch), "—", "—", "—", "—"))

            spec_status_lbl.config(
                text=f"[ {state['num_channels']} channel(s) loaded ]",
                fg="#4caf50")
            log(f"Specs loaded for {pno} — {state['num_channels']} ch")
            return True

        except Exception as ex:
            messagebox.showerror("DB Error", str(ex))
            log(f"DB Error: {ex}")
            return False

    def load_history(pno=None):
        """Populate the recent test history treeview."""
        tree_hist.delete(*tree_hist.get_children())
        try:
            conn = get_connection()
            cur = conn.cursor()
            if pno:
                cur.execute(
                    "SELECT date, time, pno, lotno, empcode, result "
                    "FROM testmaster WHERE pno=%s ORDER BY id DESC LIMIT 20",
                    (pno,))
            else:
                cur.execute(
                    "SELECT date, time, pno, lotno, empcode, result "
                    "FROM testmaster ORDER BY id DESC LIMIT 20")
            for row in cur.fetchall():
                date, time_, pno_, lot, emp, res = row
                tag = "pass" if res == "PASS" else "fail"
                tree_hist.insert("", "end", tags=(tag,),
                                 values=(date, time_, pno_, lot, emp, res))
            cur.close(); conn.close()
        except Exception:
            pass   # silently skip if DB not available

    def generate_lot_number():
        """Generate lot number: pno + YYYYMMDD + HHMMSS"""
        now = datetime.datetime.now()
        pno = state["pno"] or "XX"
        return f"{pno}-{now.strftime('%Y%m%d%H%M%S')}"

    def save_result(lot_no, overall_result, ch_results):
        """
        Insert into testmaster and testresult.
        ch_results: {ch: {"ir_volts","ir_resistance","ir_current","ir_result",
                           "acw_volts","acw_current","acw_result","contact_result"}}
        """
        try:
            conn = get_connection()
            cur = conn.cursor()
            now = datetime.datetime.now()
            pno   = state["pno"]
            emp   = ent_emp.get().strip()

            cur.execute(
                "INSERT INTO testmaster "
                "(pno, pname, model, lotno, date, time, empcode, result, machine) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (pno,
                 ent_pname.get(),
                 ent_model.get(),
                 lot_no,
                 now.strftime("%Y-%m-%d"),
                 now.strftime("%H:%M:%S"),
                 emp,
                 overall_result,
                 "PB1"))

            for ch, data in ch_results.items():
                cur.execute(
                    "INSERT INTO testresult "
                    "(lotno, channel, ir_volts, ir_resistance, ir_current, ir_result, "
                    "acw_volts, acw_current, acw_result, contact_result) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (lot_no, str(ch),
                     data.get("ir_volts", ""),
                     data.get("ir_resistance", ""),
                     data.get("ir_current", ""),
                     data.get("ir_result", ""),
                     data.get("acw_volts", ""),
                     data.get("acw_current", ""),
                     data.get("acw_result", ""),
                     data.get("contact_result", "")))

            conn.commit()
            cur.close()
            conn.close()
            log(f"Saved {overall_result} → {lot_no}")
            return True
        except Exception as ex:
            log(f"Save error: {ex}")
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # TEST SIMULATION (hardware integration placeholder)
    # ══════════════════════════════════════════════════════════════════════════

    def run_test_sequence():
        """
        Simulated test sequence mirroring TestConsole.cs flow:
        IR Test → ACW Test → Contact Test → Save → Print prompt
        Replace the simulation blocks with real serial/SCPI calls.
        """
        if not state["pno"]:
            log("No part loaded. Enter a part number first.")
            return
        if not ent_emp.get().strip():
            log("Employee ID required.")
            messagebox.showwarning("Validation", "Enter Employee ID.")
            return
        if state["test_running"]:
            return

        state["test_running"] = True
        btn_start.config(state="disabled", bg="#555", text="TESTING…")
        reset_test_display()
        result_lbl.config(text="TESTING…", bg="#e65100", fg="white")
        scan_lbl.config(text="Test in progress…", bg="#001830", fg="#888")

        def _test():
            n_ch = state["num_channels"]
            spec = state["spec_data"]
            ch_results = {}
            overall = "PASS"

            log("── Test Started ──")

            # ── IR Test ────────────────────────────────────────────────────
            log("IR Test → Sending MANU:EDIT:MODE IR | FUNC:TEST ON | MEAS?")
            ir_all_pass = True
            for ch in range(1, n_ch + 1):
                s = spec.get(ch, {}).get("IR") or {}
                # TODO: Replace with real serial SCPI read
                # Simulated values
                volts = float(s.get("appvol", 500))
                ir_val = 350.0    # placeholder MΩ reading
                v_min = float(s.get("min", 100))
                v_max = float(s.get("max", 999))
                passed = v_min <= ir_val <= v_max
                if not passed:
                    ir_all_pass = False; overall = "FAIL"
                parent.after(0, lambda c=ch-1, v=f"{ir_val:.0f}", p=passed:
                             set_cell("IR", c, v, p))
                ch_results.setdefault(ch, {}).update({
                    "ir_volts": str(volts),
                    "ir_resistance": str(ir_val),
                    "ir_current": "0.01",
                    "ir_result": "PASS" if passed else "FAIL",
                })
            parent.after(0, lambda p=ir_all_pass: set_row_result("IR", p))
            log(f"IR: {'PASS' if ir_all_pass else 'FAIL'}")

            # ── ACW Test ───────────────────────────────────────────────────
            log("ACW Test → Sending MANU:EDIT:MODE ACW | FUNC:TEST ON | MEAS?")
            acw_all_pass = True
            for ch in range(1, n_ch + 1):
                s = spec.get(ch, {}).get("ACW") or {}
                # Simulated values
                acw_current = 0.5   # placeholder mA
                v_min = float(s.get("min", 0))
                v_max = float(s.get("max", 10))
                passed = v_min <= acw_current <= v_max
                if not passed:
                    acw_all_pass = False; overall = "FAIL"
                parent.after(0, lambda c=ch-1, v=f"{acw_current:.2f}", p=passed:
                             set_cell("ACW", c, v, p))
                ch_results.setdefault(ch, {}).update({
                    "acw_volts": s.get("appvol", "1000"),
                    "acw_current": str(acw_current),
                    "acw_result": "PASS" if passed else "FAIL",
                })
            parent.after(0, lambda p=acw_all_pass: set_row_result("ACW", p))
            log(f"ACW: {'PASS' if acw_all_pass else 'FAIL'}")

            # ── Contact Test ───────────────────────────────────────────────
            log("Contact Test → Checking IO continuity (#010000 / $016)")
            contact_pass = True   # TODO: Replace with real ADAM IO read
            for ch in range(1, n_ch + 1):
                passed = contact_pass
                parent.after(0, lambda c=ch-1, p=passed:
                             set_cell("Contact", c, "OK" if p else "NG", p))
                ch_results.setdefault(ch, {})["contact_result"] = "PASS" if passed else "FAIL"
            parent.after(0, lambda p=contact_pass: set_row_result("Contact", p))
            log(f"Contact: {'PASS' if contact_pass else 'FAIL'}")

            # ── Result + Save ──────────────────────────────────────────────
            lot_no = generate_lot_number()
            state["total"] += 1
            if overall == "PASS":
                state["ok"] += 1
                parent.after(0, lambda: result_lbl.config(
                    text="PASS", bg="#0d47a1", fg="white"))
                parent.after(0, lambda: scan_lbl.config(
                    text="✅  PASS — Scan the printed barcode label",
                    bg="#0a2200", fg="#76ff03"))
            else:
                state["ng"] += 1
                parent.after(0, lambda: result_lbl.config(
                    text="FAIL", bg="#b71c1c", fg="white"))
                parent.after(0, lambda: scan_lbl.config(
                    text="❌  FAIL — Check cable and retry",
                    bg="#220000", fg="#ff5555"))

            parent.after(0, lambda l=lot_no: lot_lbl.config(text=l))
            parent.after(0, lambda l=lot_no: ent_lot.config(
                state="normal") or ent_lot.delete(0, "end") or
                ent_lot.insert(0, l) or ent_lot.config(state="readonly"))

            save_result(lot_no, overall, ch_results)
            parent.after(0, update_counts)
            parent.after(0, lambda: load_history(state["pno"]))
            log(f"── Test Complete: {overall} ──")

            state["test_running"] = False
            parent.after(0, lambda: btn_start.config(
                state="normal",
                bg="#1b5e20" if overall == "PASS" else "#b71c1c",
                text="▶  START TEST"))

        threading.Thread(target=_test, daemon=True).start()

    # ── START button ──────────────────────────────────────────────────────────
    btn_start = tk.Button(
        left_area,
        text="▶  START TEST",
        bg="#1a1a1a", fg="#555",
        font=('Arial', 14, 'bold'),
        pady=10, bd=0, cursor="hand2",
        activebackground="#2e7d32", activeforeground="white",
        command=run_test_sequence)
    btn_start.pack(fill="x", pady=(6, 0))

    # ══════════════════════════════════════════════════════════════════════════
    # PART NUMBER ENTRY — on Enter key load specs
    # ══════════════════════════════════════════════════════════════════════════
    def on_pno_enter(event=None):
        pno = ent_pno.get().strip().upper()
        if not pno:
            return
        reset_test_display()
        tree_spec.delete(*tree_spec.get_children())
        ent_lot.config(state="normal")
        ent_lot.delete(0, "end")
        ent_lot.config(state="readonly")
        spec_status_lbl.config(text="[ Loading… ]", fg="#e8a000")
        ok = load_specs(pno)
        if ok:
            load_history(pno)
            btn_start.config(bg="#1b5e20", fg="white")
            scan_lbl.config(
                text=f"Part '{pno}' loaded — Press START TEST or wait for hardware trigger",
                bg="#001830", fg="#4caf50")
        else:
            btn_start.config(bg="#1a1a1a", fg="#555")

    ent_pno.bind("<Return>", on_pno_enter)

    # ══════════════════════════════════════════════════════════════════════════
    # INITIAL LOAD
    # ══════════════════════════════════════════════════════════════════════════
    load_history()
    log("System ready. Enter Part Number and press ENTER.")
    set_com_status("HiPot",   False)
    set_com_status("IO Ctrl", False)
    set_com_status("Scanner", False)
    set_com_status("Printer", False)
