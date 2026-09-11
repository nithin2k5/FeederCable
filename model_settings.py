import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import mysql.connector

import db


def render(parent):
    try:
        db.widen_column("settingmaster", "lblsel", "VARCHAR(500)")
    except Exception:
        pass  # DB may be unreachable right now -- don't block the page for it

    # ── Palette ───────────────────────────────────────────────────────────────
    # One set of colours for the whole page. The old form mixed five saturated
    # button fills with unlabelled panels, so nothing read as more or less
    # important than anything else.
    BG, PANEL, HEADER = "#000000", "#0d0d0d", "#161616"
    LINE, FIELD = "#2b2b2b", "#111111"
    TXT, TXT_DIM, ACCENT = "#e8e8e8", "#8a8a8a", "#e8a000"
    BTN_OFF_BG, BTN_OFF_FG = "#1a1a1a", "#555555"

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    # Scoped to this page. The old code configured the bare "Treeview" style,
    # which is global -- every other page's table inherited whatever this one
    # asked for, and whichever page rendered last won the argument.
    style.configure("Model.Treeview.Heading", background=HEADER, foreground=TXT,
                    font=('Arial', 9, 'bold'), bordercolor=LINE, relief="flat")
    style.map("Model.Treeview.Heading",
              background=[("active", HEADER), ("pressed", HEADER)],
              foreground=[("active", TXT), ("pressed", TXT)])
    style.configure("Model.Treeview", background=PANEL, foreground=TXT,
                    fieldbackground=PANEL, font=('Arial', 9), rowheight=26,
                    bordercolor=LINE)
    style.map("Model.Treeview", background=[('selected', '#1c3a5e')],
              foreground=[('selected', 'white')])

    # ── State tracking ────────────────────────────────────────────────────────
    mode = {"value": "VIEW"}          # VIEW | NEW | EDIT
    selected_pno = {"value": None}    # currently selected part number

    # ── Widget factories ──────────────────────────────────────────────────────
    def mk_entry(parent, width=12, state="normal"):
        e = tk.Entry(parent, bg=FIELD, fg=TXT, font=('Arial', 10),
                     bd=0, relief="flat", highlightbackground=LINE,
                     highlightcolor=ACCENT, highlightthickness=1,
                     insertbackground="white", width=width,
                     disabledbackground="#151515", disabledforeground="#4a4a4a",
                     readonlybackground=FIELD, state=state)
        return e

    def mk_combo(parent, values, width=12, state="readonly"):
        cb = ttk.Combobox(parent, values=values, font=('Arial', 10),
                          width=width, state=state)
        if values:
            cb.current(0)
        return cb

    def mk_btn(parent, text, fill, hover, width=11, fg="white"):
        """An action button that also looks disabled when it is disabled.

        tk.Button keeps its fill colour at state="disabled" and only greys the
        text, which left DELETE sitting there in full gold with unreadable
        lettering. The CRUD code below turns buttons on and off with a plain
        config(state=...), so rather than rewrite all of that, the colour swap
        is folded into config itself.
        """
        b = tk.Button(parent, text=text, bg=fill, fg=fg,
                      font=('Arial', 10, 'bold'), width=width, bd=0,
                      padx=10, pady=7, activebackground=hover,
                      activeforeground=fg, cursor="hand2",
                      disabledforeground=BTN_OFF_FG)
        _orig = tk.Button.configure

        def _cfg(cnf=None, **kw):
            if "state" in kw:
                on = kw["state"] == "normal"
                kw["bg"] = fill if on else BTN_OFF_BG
                kw["fg"] = fg if on else BTN_OFF_FG
                kw["cursor"] = "hand2" if on else "arrow"
            return _orig(b, cnf, **kw)
        b.configure = _cfg
        b.config = _cfg

        def _enter(_e):
            if str(b["state"]) == "normal":
                _orig(b, bg=hover)

        def _leave(_e):
            if str(b["state"]) == "normal":
                _orig(b, bg=fill)
        b.bind("<Enter>", _enter)
        b.bind("<Leave>", _leave)
        return b

    def section(parent, title):
        """A titled panel: caption bar above a bordered body.

        The page used to be four unlabelled boxes stacked on black. A caption
        is the cheapest thing that says what a region is for, and it gives the
        row count and the active channel somewhere to live.
        """
        outer = tk.Frame(parent, bg=LINE, padx=1, pady=1)
        bar = tk.Frame(outer, bg=HEADER)
        bar.pack(fill="x")
        tk.Label(bar, text=title, bg=HEADER, fg=TXT, font=('Arial', 10, 'bold'),
                 padx=12, pady=7).pack(side="left")
        note = tk.Label(bar, text="", bg=HEADER, fg=TXT_DIM, font=('Arial', 9))
        note.pack(side="right", padx=12)
        body = tk.Frame(outer, bg=PANEL)
        body.pack(fill="both", expand=True)
        return outer, body, note

    # ─────────────────────────────────────────────────────────────────────────
    # ROOT CONTENT
    # ─────────────────────────────────────────────────────────────────────────
    content = tk.Frame(parent, bg=BG)
    content.pack(fill="both", expand=True, padx=8, pady=8)

    # ── Page header, with the form's mode on the right ───────────────────────
    head = tk.Frame(content, bg=BG)
    head.pack(fill="x", pady=(0, 8))
    tk.Label(head, text="Model Settings", bg=BG, fg=TXT,
             font=('Arial', 15, 'bold')).pack(side="left")
    tk.Label(head, text="Part master and per-channel test specifications",
             bg=BG, fg=TXT_DIM, font=('Arial', 9)).pack(side="left", padx=(12, 0), pady=(7, 0))
    mode_chip = tk.Label(head, text="VIEW", bg="#1a1a1a", fg=TXT_DIM,
                         font=('Arial', 9, 'bold'), padx=14, pady=5,
                         bd=1, relief="solid")
    mode_chip.pack(side="right")

    _MODE_LOOK = {"VIEW": ("#1a1a1a", TXT_DIM, "VIEW — read only"),
                  "NEW":  ("#1b5e20", "white", "NEW — entering a part"),
                  "EDIT": ("#0d47a1", "white", "EDIT — changing a saved part")}

    def set_mode(val):
        """Single place the form's mode is recorded and shown.

        Whether the fields were live used to be invisible -- the form looked
        the same read-only as it did mid-entry.
        """
        mode["value"] = val
        bg, fg, text = _MODE_LOOK.get(val, _MODE_LOOK["VIEW"])
        try:
            mode_chip.config(text=text, bg=bg, fg=fg)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # PART MASTER  — settingmaster fields
    # ─────────────────────────────────────────────────────────────────────────
    form_outer, form, _form_note = section(content, "Part Master")
    form_outer.pack(fill="x", pady=(0, 6))

    # Three equal columns. "uniform" is what keeps them equal: without it the
    # column holding the longest label quietly took more width than the rest.
    fcols = []
    for c in range(3):
        form.columnconfigure(c, weight=1, uniform="formcol")
        f = tk.Frame(form, bg=PANEL, padx=14, pady=10)
        f.grid(row=0, column=c, sticky="nsew")
        f.columnconfigure(1, weight=1)
        fcols.append(f)
    f1, f2, f3 = fcols

    def field(frame, row, text):
        tk.Label(frame, text=text, bg=PANEL, fg=TXT_DIM, font=('Arial', 9, 'bold'),
                 anchor="w").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 12))

    for _r, _t in enumerate(("PART NUMBER", "PART NAME", "CUSTOMER NAME", "MODEL NAME")):
        field(f1, _r, _t)
    ent_pno   = mk_entry(f1); ent_pno.grid(row=0, column=1, sticky="ew", pady=6)
    ent_pname = mk_entry(f1); ent_pname.grid(row=1, column=1, sticky="ew", pady=6)
    ent_cname = mk_entry(f1); ent_cname.grid(row=2, column=1, sticky="ew", pady=6)
    ent_model = mk_entry(f1); ent_model.grid(row=3, column=1, sticky="ew", pady=6)

    for _r, _t in enumerate(("VENDOR CODE", "EO NUMBER", "ALC", "TEST MODE")):
        field(f2, _r, _t)
    ent_vcode = mk_entry(f2); ent_vcode.grid(row=0, column=1, sticky="ew", pady=6)
    ent_eon   = mk_entry(f2); ent_eon.grid(row=1, column=1, sticky="ew", pady=6)
    ent_alc   = mk_entry(f2); ent_alc.grid(row=2, column=1, sticky="ew", pady=6)
    cb_testmode = mk_combo(f2, ["Combined", "Single"])
    cb_testmode.grid(row=3, column=1, sticky="ew", pady=6)

    for _r, _t in enumerate(("CHANNELS", "LABEL TEMPLATE", "MACHINE ID")):
        field(f3, _r, _t)
    cb_channels = mk_combo(f3, [str(i) for i in range(1, 9)])
    cb_channels.grid(row=0, column=1, sticky="ew", pady=6)

    # Label template: picked via a file-explorer dialog instead of a fixed list
    lbl_wrap = tk.Frame(f3, bg=PANEL)
    lbl_wrap.grid(row=1, column=1, sticky="ew", pady=6)
    lbl_wrap.columnconfigure(0, weight=1)

    cb_label = tk.Entry(lbl_wrap, bg=FIELD, fg=TXT, font=('Arial', 10),
                        bd=0, relief="flat", highlightbackground=LINE,
                        highlightcolor=ACCENT, highlightthickness=1,
                        insertbackground="white", width=12,
                        disabledbackground="#151515", disabledforeground="#4a4a4a",
                        readonlybackground=FIELD, state="readonly")
    cb_label.grid(row=0, column=0, sticky="ew")

    def _set_label_entry(val):
        prev_state = cb_label.cget("state")
        cb_label.config(state="normal")
        cb_label.delete(0, "end")
        cb_label.insert(0, val or "")
        cb_label.config(state=prev_state)
        # The stored path is longer than the box, and Tk shows its head. Show
        # the tail instead: the file name is the half that says which template
        # this is.
        try:
            cb_label.xview_moveto(1.0)
        except Exception:
            pass

    def on_browse_label():
        base = os.path.dirname(os.path.abspath(__file__))
        path = filedialog.askopenfilename(
            title="Select Label Template",
            initialdir=base,
            filetypes=[("PRN Label Files", "*.prn"), ("All Files", "*.*")])
        if not path:
            return
        _set_label_entry(os.path.abspath(path))

    btn_browse_label = tk.Button(lbl_wrap, text="Browse", bg="#2a2a2a", fg=TXT,
                                 font=('Arial', 9), bd=0, padx=10, pady=3,
                                 activebackground="#3a3a3a", activeforeground=TXT,
                                 cursor="hand2", command=on_browse_label)
    btn_browse_label.grid(row=0, column=1, padx=(6, 0))

    _set_label_entry("")

    cb_machine = mk_combo(f3, ["PB1", "PB2", "PB3", "PB4"])
    cb_machine.grid(row=2, column=1, sticky="ew", pady=6)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST SPECIFICATION  — IR + ACW rows per channel (settingspec)
    # ─────────────────────────────────────────────────────────────────────────
    spec_outer, spec_body, spec_note = section(content, "Test Specification")
    spec_outer.pack(fill="x", pady=(0, 6))

    tab_bar = tk.Frame(spec_body, bg=PANEL, pady=8, padx=10)
    tab_bar.pack(fill="x")

    tk.Label(tab_bar, text="CHANNEL", bg=PANEL, fg=TXT_DIM,
             font=('Arial', 9, 'bold')).pack(side="left", padx=(0, 10))

    # Channel tabs
    ch_tab_frame = tk.Frame(tab_bar, bg=PANEL)
    ch_tab_frame.pack(side="left")
    ch_labels = []
    for i in range(1, 9):
        lbl = tk.Label(ch_tab_frame, text=str(i), bg="#1a1a1a", fg=TXT_DIM,
                       font=('Arial', 10, 'bold'), width=4, pady=5,
                       bd=0, cursor="hand2")
        lbl.pack(side="left", padx=(0, 3))
        ch_labels.append(lbl)

    table_frame = tk.Frame(spec_body, bg=LINE)
    table_frame.pack(fill="x", padx=10, pady=(0, 10))

    spec_headers = ["TEST", "APPLIED VOLTS (V)", "TEST TIME (SEC)", "SPEC MIN", "SPEC MAX"]

    # Per-channel spec data: {ch: {"IR": [appvol, testtime, min, max], "ACW": [...]}}
    spec_data = {}
    for ch in range(1, 9):
        spec_data[ch] = {
            "IR":  ["", "", "", ""],
            "ACW": ["", "", "", ""],
        }

    active_ch = {"value": 1}
    spec_widgets = {}   # {test_name: [entry_appvol, entry_time, entry_min, entry_max]}

    def save_spec_ui():
        """Write current UI entry values back to spec_data for the active channel."""
        ch = active_ch["value"]
        for test_name, entries in spec_widgets.items():
            spec_data[ch][test_name] = [e.get() for e in entries]

    # The unit belongs on the row, not in the operator's head.
    _SPEC_ROWS = [("IR", "Insulation   (MΩ)", "#8bc34a"),
                  ("ACW", "Withstand   (mA)", "#64b5f6")]

    def render_spec_table(ch):
        """Redraw the spec entry table for the given channel."""
        for w in table_frame.winfo_children():
            w.destroy()
        spec_widgets.clear()

        for col_i, h in enumerate(spec_headers):
            table_frame.columnconfigure(col_i, weight=0 if col_i == 0 else 1)
            tk.Label(table_frame, text=h, bg=HEADER, fg=TXT,
                     font=('Arial', 9, 'bold'), pady=7,
                     width=22 if col_i == 0 else 0).grid(
                row=0, column=col_i, sticky="nsew", padx=1, pady=1)

        for row_i, (test_name, pretty, accent) in enumerate(_SPEC_ROWS, start=1):
            vals = spec_data[ch][test_name]
            tk.Label(table_frame, text=pretty, bg="#131313", fg=accent,
                     font=('Arial', 9, 'bold'), pady=7, anchor="w", padx=12).grid(
                row=row_i, column=0, sticky="nsew", padx=1, pady=1)
            row_entries = []
            for col_i, val in enumerate(vals, start=1):
                e = tk.Entry(table_frame, bg=FIELD, fg=TXT,
                             font=('Arial', 10), bd=0, relief="flat",
                             justify="center", insertbackground="white",
                             highlightbackground=LINE, highlightcolor=accent,
                             highlightthickness=1)
                e.insert(0, val)
                e.grid(row=row_i, column=col_i, sticky="nsew", ipady=5, padx=1, pady=1)
                row_entries.append(e)
            spec_widgets[test_name] = row_entries

    def _note_channel():
        try:
            spec_note.config(text=f"Editing channel {active_ch['value']} of {cb_channels.get()}")
        except Exception:
            pass

    def switch_channel(ch):
        save_spec_ui()
        active_ch["value"] = ch
        for idx, lbl in enumerate(ch_labels):
            on = idx + 1 == ch
            lbl.config(bg=ACCENT if on else "#1a1a1a", fg="black" if on else TXT_DIM)
        render_spec_table(ch)
        _note_channel()

    for i, lbl in enumerate(ch_labels):
        lbl.bind("<Button-1>", lambda e, c=i+1: switch_channel(c))

    def update_channel_visibility(*args):
        try:
            num_ch = int(cb_channels.get())
        except ValueError:
            num_ch = 1
        for i, lbl in enumerate(ch_labels):
            if i < num_ch:
                lbl.pack(side="left", padx=(0, 3))
            else:
                lbl.pack_forget()
        if active_ch["value"] > num_ch:
            switch_channel(num_ch)
        else:
            _note_channel()

    cb_channels.bind("<<ComboboxSelected>>", update_channel_visibility)
    cb_channels.bind("<KeyRelease>", update_channel_visibility)

    switch_channel(1)   # initial render
    update_channel_visibility()

    # ─────────────────────────────────────────────────────────────────────────
    # ACTION BAR
    # ─────────────────────────────────────────────────────────────────────────
    # Destructive on the left, away from where the hand finishes; the two that
    # commit work sit on the right. The old bar centred five equally loud
    # colours, so DELETE looked exactly as inviting as SAVE.
    act_outer = tk.Frame(content, bg=LINE, padx=1, pady=1)
    act_outer.pack(side="bottom", fill="x")
    act = tk.Frame(act_outer, bg=PANEL, padx=10, pady=8)
    act.pack(fill="x")

    btn_new    = mk_btn(act, "NEW",    "#2a2a2a", "#3a3a3a", fg=ACCENT)
    btn_delete = mk_btn(act, "DELETE", "#8e1c1c", "#b71c1c")
    btn_save   = mk_btn(act, "SAVE",   "#1b5e20", "#2e7d32")
    btn_update = mk_btn(act, "UPDATE", "#0d47a1", "#1565c0")
    btn_cancel = mk_btn(act, "CANCEL", "#2a2a2a", "#3a3a3a")

    btn_new.pack(side="left")
    btn_delete.pack(side="left", padx=(8, 0))
    btn_save.pack(side="right")
    btn_update.pack(side="right", padx=(0, 8))
    btn_cancel.pack(side="right", padx=(0, 8))

    # ─────────────────────────────────────────────────────────────────────────
    # SAVED PARTS  — settingmaster list
    # ─────────────────────────────────────────────────────────────────────────
    list_outer, list_body, list_note = section(content, "Saved Parts")
    list_outer.pack(fill="both", expand=True, pady=(0, 6))

    cols_bot = ("SL", "PART NUMBER", "PART NAME", "CUSTOMER", "MODEL", "ALC", "CH#", "MACHINE")
    tree_wrap = tk.Frame(list_body, bg=PANEL)
    tree_wrap.pack(fill="both", expand=True, padx=1, pady=1)
    tree_bot = ttk.Treeview(tree_wrap, columns=cols_bot, show="headings",
                            style="Model.Treeview")
    sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree_bot.yview)
    tree_bot.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    tree_bot.pack(fill="both", expand=True)
    # Banded rows: eight near-identical part numbers in one column are hard to
    # track across to the machine column without them.
    tree_bot.tag_configure("odd", background="#0f0f0f")
    tree_bot.tag_configure("even", background="#141414")

    col_widths = {"SL": 50, "PART NUMBER": 150, "PART NAME": 170,
                  "CUSTOMER": 140, "MODEL": 120, "ALC": 80, "CH#": 60, "MACHINE": 90}
    for col in cols_bot:
        tree_bot.heading(col, text=col)
        tree_bot.column(col, anchor="center", width=col_widths.get(col, 90),
                        stretch=(col in ("PART NAME", "CUSTOMER", "MODEL")))


    # ─────────────────────────────────────────────────────────────────────────
    # HELPER FUNCTIONS
    # ─────────────────────────────────────────────────────────────────────────
    def clear_form():
        """Clear all form fields and reset spec data."""
        for e in (ent_pno, ent_pname, ent_cname, ent_model,
                  ent_vcode, ent_eon, ent_alc):
            e.config(state="normal")
            e.delete(0, "end")
        cb_channels.current(0)
        _set_label_entry("")
        cb_machine.current(0)
        cb_testmode.current(0)
        selected_pno["value"] = None
        update_channel_visibility()
        # Reset spec data
        for ch in range(1, 9):
            spec_data[ch] = {
                "IR":  ["", "", "", ""],
                "ACW": ["", "", "", ""],
            }
        switch_channel(1)

    def lock_form(locked=True):
        """Disable/enable form fields."""
        st = "disabled" if locked else "normal"
        for e in (ent_pno, ent_pname, ent_cname, ent_model,
                  ent_vcode, ent_eon, ent_alc):
            e.config(state=st)
        cb_state = "disabled" if locked else "readonly"
        for cb in (cb_channels, cb_label, cb_machine, cb_testmode):
            cb.config(state=cb_state)
        btn_browse_label.config(state=st)

    def set_form(row_dict):
        """Populate form fields from a dict."""
        lock_form(False)
        fields = [
            (ent_pno,   row_dict.get("pno", "")),
            (ent_pname, row_dict.get("pname", "")),
            (ent_cname, row_dict.get("cname", "")),
            (ent_model, row_dict.get("mname", "")),
            (ent_vcode, row_dict.get("vendorcode", "")),
            (ent_eon,   row_dict.get("eocode", "")),
            (ent_alc,   row_dict.get("alc", "")),
        ]
        for entry, val in fields:
            entry.delete(0, "end")
            entry.insert(0, val or "")

        ch_val = str(row_dict.get("chsel", "1"))
        ch_list = [str(i) for i in range(1, 9)]
        cb_channels.config(values=ch_list)
        cb_channels.set(ch_val if ch_val in ch_list else "1")

        _set_label_entry(row_dict.get("lblsel", ""))

        mach_val = row_dict.get("machine", "PB1")
        if mach_val in list(cb_machine["values"]):
            cb_machine.set(mach_val)

        tmode_val = row_dict.get("testmode", "Combined")
        if tmode_val in list(cb_testmode["values"]):
            cb_testmode.set(tmode_val)
        
        update_channel_visibility()

    def refresh_parts_list():
        """Reload the bottom treeview from settingmaster."""
        tree_bot.delete(*tree_bot.get_children())
        count = 0
        try:
            with db.get_cursor() as cur:
                cur.execute("SELECT pno, pname, cname, mname, alc, chsel, machine FROM settingmaster ORDER BY pno")
                for idx, row in enumerate(cur.fetchall(), start=1):
                    pno, pname, cname, model, alc, channel, machine = row
                    tree_bot.insert("", "end", iid=pno,
                                    tags=("odd" if idx % 2 else "even",),
                                    values=(idx, pno, pname, cname, model, alc, channel, machine))
                    count = idx
        except Exception as ex:
            # DB not available — silently skip
            pass
        # The caption carries the count, so an empty list reads as "no parts
        # saved" rather than as a table that failed to load.
        try:
            list_note.config(text=f"{count} part{'' if count == 1 else 's'}")
        except Exception:
            pass

    def load_specs_from_db(pno):
        """Load settingspec rows into spec_data for all channels."""
        for ch in range(1, 9):
            spec_data[ch] = {
                "IR":  ["", "", "", ""],
                "ACW": ["", "", "", ""],
            }
        try:
            with db.get_cursor() as cur:
                cur.execute(
                    "SELECT testname, chsel, appvol, testtime, min, max "
                    "FROM settingspec WHERE pno=%s", (pno,))
                for row in cur.fetchall():
                    testname, ch_str, appvol, testtime, vmin, vmax = row
                    try:
                        ch = int(ch_str)
                    except (TypeError, ValueError):
                        continue
                    if ch not in spec_data:
                        continue
                    # Rows written by the legacy Settings form store testname
                    # as "Insulation Test(MΩ)" / "Withstand Test(mA)" instead
                    # of "IR"/"ACW" -- normalize both spellings so specs saved
                    # by either tool load correctly.
                    tn = str(testname or "").strip().lower()
                    if tn == "ir" or "insulation" in tn:
                        key = "IR"
                    elif tn == "acw" or "withstand" in tn:
                        key = "ACW"
                    else:
                        continue
                    spec_data[ch][key] = [appvol, testtime, vmin, vmax]
        except Exception:
            pass
        # Redraw directly -- switch_channel() would call save_spec_ui() first,
        # which copies whatever is still showing in the (stale/blank) entry
        # widgets back into spec_data for the active channel, clobbering the
        # values just loaded from the DB before they ever get displayed.
        render_spec_table(active_ch["value"])

    # ─────────────────────────────────────────────────────────────────────────
    # CRUD FUNCTIONS
    # ─────────────────────────────────────────────────────────────────────────
    def on_new():
        clear_form()
        lock_form(False)
        ent_pno.focus()
        set_mode("NEW")
        btn_save.config(state="normal")
        btn_update.config(state="disabled")
        btn_delete.config(state="disabled")

    def validate_channel_data():
        num_channels = int(cb_channels.get())
        for ch in range(1, num_channels + 1):
            for test_name in ("IR", "ACW"):
                vals = spec_data[ch][test_name]
                if any(str(v).strip() == "" for v in vals):
                    messagebox.showwarning("Validation", f"Please fill all {test_name} values for CH#{ch}.")
                    return False
        return True

    def on_save():
        pno = ent_pno.get().strip().upper()
        if not pno:
            messagebox.showwarning("Validation", "PART NUMBER is required.")
            return
        save_spec_ui()   # capture current channel spec before saving
        if not validate_channel_data():
            return
        try:
            with db.get_cursor(commit=True) as cur:
                # Insert settingmaster
                cur.execute(
                    "INSERT INTO settingmaster (pno, pname, cname, mname, vendorcode, eocode, alc, chsel, lblsel, machine, testmode) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (pno, ent_pname.get().strip(), ent_cname.get().strip(),
                     ent_model.get().strip(), ent_vcode.get().strip(),
                     ent_eon.get().strip(), ent_alc.get().strip(),
                     cb_channels.get(), cb_label.get(), cb_machine.get(),
                     cb_testmode.get()))

                # Insert settingspec for each channel and test type
                num_channels = int(cb_channels.get())
                for ch in range(1, num_channels + 1):
                    for test_name in ("IR", "ACW"):
                        vals = spec_data[ch][test_name]
                        cur.execute(
                            "INSERT INTO settingspec (pno, testname, chsel, appvol, testtime, min, max) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (pno, test_name, str(ch), vals[0], vals[1], vals[2], vals[3]))

            messagebox.showinfo("Success", f"Part '{pno}' saved successfully.")
            set_mode("VIEW")
            refresh_parts_list()
            lock_form(True)
        except mysql.connector.IntegrityError:
            messagebox.showerror("Error", f"Part number '{pno}' already exists.")
        except Exception as ex:
            messagebox.showerror("DB Error", str(ex))

    def on_update():
        pno = selected_pno["value"]
        if not pno:
            messagebox.showwarning("Validation", "Select a part first.")
            return
        save_spec_ui()
        if not validate_channel_data():
            return
        try:
            with db.get_cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE settingmaster SET pname=%s, cname=%s, mname=%s, vendorcode=%s, "
                    "eocode=%s, alc=%s, chsel=%s, lblsel=%s, machine=%s, testmode=%s WHERE pno=%s",
                    (ent_pname.get().strip(), ent_cname.get().strip(),
                     ent_model.get().strip(), ent_vcode.get().strip(),
                     ent_eon.get().strip(), ent_alc.get().strip(),
                     cb_channels.get(), cb_label.get(), cb_machine.get(),
                     cb_testmode.get(), pno))

                # Delete old specs and re-insert
                cur.execute("DELETE FROM settingspec WHERE pno=%s", (pno,))
                num_channels = int(cb_channels.get())
                for ch in range(1, num_channels + 1):
                    for test_name in ("IR", "ACW"):
                        vals = spec_data[ch][test_name]
                        cur.execute(
                            "INSERT INTO settingspec (pno, testname, chsel, appvol, testtime, min, max) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (pno, test_name, str(ch), vals[0], vals[1], vals[2], vals[3]))

            messagebox.showinfo("Success", f"Part '{pno}' updated.")
            set_mode("VIEW")
            refresh_parts_list()
            lock_form(True)
        except Exception as ex:
            messagebox.showerror("DB Error", str(ex))

    def on_delete():
        pno = selected_pno["value"]
        if not pno:
            messagebox.showwarning("Validation", "Select a part to delete.")
            return
        if not messagebox.askyesno("Confirm", f"Delete part '{pno}' and all its specs?"):
            return
        try:
            with db.get_cursor(commit=True) as cur:
                cur.execute("DELETE FROM settingspec WHERE pno=%s", (pno,))
                cur.execute("DELETE FROM settingmaster WHERE pno=%s", (pno,))
            messagebox.showinfo("Deleted", f"Part '{pno}' deleted.")
            clear_form()
            lock_form(True)
            refresh_parts_list()
            set_mode("VIEW")
            btn_update.config(state="disabled")
            btn_delete.config(state="disabled")
        except Exception as ex:
            messagebox.showerror("DB Error", str(ex))

    def on_cancel():
        clear_form()
        lock_form(True)
        set_mode("VIEW")
        btn_save.config(state="disabled")
        btn_update.config(state="disabled")
        btn_delete.config(state="disabled")

    def on_tree_select(event):
        """Row click in parts list → load into form (RETRIEVE)."""
        sel = tree_bot.selection()
        if not sel:
            return
        pno = sel[0]   # iid is pno
        selected_pno["value"] = pno
        try:
            with db.get_dict_cursor() as cur:
                cur.execute("SELECT * FROM settingmaster WHERE pno=%s", (pno,))
                row = cur.fetchone()
            if row:
                set_form(row)
                load_specs_from_db(pno)
                set_mode("EDIT")
                btn_save.config(state="disabled")
                btn_update.config(state="normal")
                btn_delete.config(state="normal")
        except Exception as ex:
            messagebox.showerror("DB Error", str(ex))

    # Wire up buttons
    btn_new.config(command=on_new)
    btn_save.config(command=on_save)
    btn_update.config(command=on_update)
    btn_delete.config(command=on_delete)
    btn_cancel.config(command=on_cancel)
    tree_bot.bind("<<TreeviewSelect>>", on_tree_select)

    # ─────────────────────────────────────────────────────────────────────────
    # Initial state
    # ─────────────────────────────────────────────────────────────────────────
    set_mode("VIEW")
    lock_form(True)   # read-only until NEW or row selected
    btn_save.config(state="disabled")
    btn_update.config(state="disabled")
    btn_delete.config(state="disabled")
    refresh_parts_list()
