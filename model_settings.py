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

    style = ttk.Style()
    style.configure("Treeview.Heading",
                    background="#111", foreground="white",
                    font=('Arial', 9, 'bold'), bordercolor="#444")
    # Column headers otherwise brighten on mouse-over / press -- pin the
    # color so it stays flat in every state.
    style.map("Treeview.Heading", background=[("active", "#111"), ("pressed", "#111")],
              foreground=[("active", "white"), ("pressed", "white")])
    style.configure("Treeview",
                    background="#0a0a0a", foreground="white",
                    fieldbackground="#0a0a0a", font=('Arial', 9), rowheight=25)
    style.map("Treeview", background=[('selected', '#1c3a5e')])

    # ── State tracking ────────────────────────────────────────────────────────
    mode = {"value": "VIEW"}          # VIEW | NEW | EDIT
    selected_pno = {"value": None}    # currently selected part number

    # ── Widget factories ──────────────────────────────────────────────────────
    def mk_entry(parent, width=22, state="normal"):
        e = tk.Entry(parent, bg="#111", fg="white", font=('Arial', 10),
                     bd=1, relief="solid", highlightbackground="#444",
                     highlightthickness=1, insertbackground="white",
                     width=width, disabledbackground="#1a1a1a",
                     disabledforeground="#555", state=state)
        return e

    def mk_combo(parent, values, width=22, state="readonly"):
        cb = ttk.Combobox(parent, values=values, font=('Arial', 10),
                          width=width, state=state)
        if values:
            cb.current(0)
        return cb

    def mk_btn(parent, text, bg_color, cmd=None, width=13):
        return tk.Button(parent, text=text, bg=bg_color, fg="white",
                         font=('Arial', 11, 'bold'), width=width, bd=0,
                         padx=8, pady=6, activebackground=bg_color,
                         activeforeground="white", cursor="hand2",
                         command=cmd)

    # ─────────────────────────────────────────────────────────────────────────
    # ROOT CONTENT
    # ─────────────────────────────────────────────────────────────────────────
    content = tk.Frame(parent, bg="black")
    content.pack(fill="both", expand=True, padx=5, pady=5)

    # ─────────────────────────────────────────────────────────────────────────
    # TOP  — Master form (settingmaster fields)
    # ─────────────────────────────────────────────────────────────────────────
    top_frame = tk.Frame(content, bg="black", bd=1, relief="solid",
                         highlightbackground="#444", highlightthickness=1)
    top_frame.pack(fill="x", pady=(0, 5))

    # Column-1: Part No, Part Name, Customer Name, Model Name
    f1 = tk.Frame(top_frame, bg="black", padx=15, pady=10)
    f1.pack(side="left", fill="both", expand=True)
    f1.columnconfigure(1, weight=1)

    tk.Label(f1, text="PART NUMBER",   bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky="w", pady=5)
    tk.Label(f1, text="PART NAME",     bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky="w", pady=5)
    tk.Label(f1, text="CUSTOMER NAME", bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=2, column=0, sticky="w", pady=5)
    tk.Label(f1, text="MODEL NAME",    bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=3, column=0, sticky="w", pady=5)

    ent_pno   = mk_entry(f1); ent_pno.grid(row=0, column=1, sticky="ew", padx=10)
    ent_pname = mk_entry(f1); ent_pname.grid(row=1, column=1, sticky="ew", padx=10)
    ent_cname = mk_entry(f1); ent_cname.grid(row=2, column=1, sticky="ew", padx=10)
    ent_model = mk_entry(f1); ent_model.grid(row=3, column=1, sticky="ew", padx=10)

    # Column-2: Vendor Code, EO Number, ALC
    f2 = tk.Frame(top_frame, bg="black", padx=15, pady=10)
    f2.pack(side="left", fill="both", expand=True)
    f2.columnconfigure(1, weight=1)

    tk.Label(f2, text="VENDOR CODE", bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky="w", pady=5)
    tk.Label(f2, text="EO NUMBER",   bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky="w", pady=5)
    tk.Label(f2, text="ALC",         bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=2, column=0, sticky="w", pady=5)

    ent_vcode = mk_entry(f2); ent_vcode.grid(row=0, column=1, sticky="ew", padx=10)
    ent_eon   = mk_entry(f2); ent_eon.grid(row=1, column=1, sticky="ew", padx=10)
    ent_alc   = mk_entry(f2); ent_alc.grid(row=2, column=1, sticky="ew", padx=10)

    tk.Label(f2, text="TEST MODE", bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=3, column=0, sticky="w", pady=5)
    cb_testmode = mk_combo(f2, ["Combined", "Single"], width=20)
    cb_testmode.grid(row=3, column=1, sticky="ew", padx=10, pady=5)

    # Column-3: Channels, Label Template, Machine ID
    f3 = tk.Frame(top_frame, bg="black", padx=15, pady=10)
    f3.pack(side="left", fill="both", expand=True)
    f3.columnconfigure(1, weight=1)

    tk.Label(f3, text="CHANNELS",      bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky="w", pady=5)
    tk.Label(f3, text="LABEL TEMPLATE",bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky="w", pady=5)
    tk.Label(f3, text="MACHINE ID",    bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=2, column=0, sticky="w", pady=5)

    cb_channels = mk_combo(f3, [str(i) for i in range(1, 9)], width=20)
    cb_channels.grid(row=0, column=1, sticky="ew", padx=10, pady=5)

    # Label template: picked via a file-explorer dialog instead of a fixed list
    lbl_wrap = tk.Frame(f3, bg="black")
    lbl_wrap.grid(row=1, column=1, sticky="ew", padx=10, pady=5)
    lbl_wrap.columnconfigure(0, weight=1)

    cb_label = tk.Entry(lbl_wrap, bg="#111", fg="white", font=('Arial', 10),
                         bd=1, relief="solid", highlightbackground="#444",
                         highlightthickness=1, insertbackground="white",
                         disabledbackground="#1a1a1a", disabledforeground="#555",
                         readonlybackground="#111", state="readonly")
    cb_label.grid(row=0, column=0, sticky="ew")

    def _set_label_entry(val):
        prev_state = cb_label.cget("state")
        cb_label.config(state="normal")
        cb_label.delete(0, "end")
        cb_label.insert(0, val or "")
        cb_label.config(state=prev_state)

    def on_browse_label():
        base = os.path.dirname(os.path.abspath(__file__))
        path = filedialog.askopenfilename(
            title="Select Label Template",
            initialdir=base,
            filetypes=[("PRN Label Files", "*.prn"), ("All Files", "*.*")])
        if not path:
            return
        _set_label_entry(os.path.abspath(path))

    btn_browse_label = tk.Button(lbl_wrap, text="📁", bg="#333", fg="white",
                                  font=('Arial', 9), bd=0, width=3, cursor="hand2",
                                  command=on_browse_label)
    btn_browse_label.grid(row=0, column=1, padx=(4, 0))

    _set_label_entry("")

    cb_machine = mk_combo(f3, ["PB1", "PB2", "PB3", "PB4"], width=20)
    cb_machine.grid(row=2, column=1, sticky="ew", padx=10, pady=5)

    # ─────────────────────────────────────────────────────────────────────────
    # BUTTONS
    # ─────────────────────────────────────────────────────────────────────────
    btn_frame = tk.Frame(content, bg="black", bd=1, relief="solid",
                         highlightbackground="#444", highlightthickness=1)
    btn_frame.pack(fill="x", pady=(0, 5))
    btn_inner = tk.Frame(btn_frame, bg="black", pady=10)
    btn_inner.pack(expand=True)

    # Forward-declared buttons so CRUD functions can reference them
    btn_new    = mk_btn(btn_inner, "➕ NEW",      "#8b0000")
    btn_save   = mk_btn(btn_inner, "💾 SAVE",     "#006600")
    btn_update = mk_btn(btn_inner, "✏ UPDATE",    "#0033aa")
    btn_delete = mk_btn(btn_inner, "🗑 DELETE",   "#b8860b")
    btn_cancel = mk_btn(btn_inner, "✖ CANCEL",   "#4b0082")

    for b in (btn_new, btn_save, btn_update, btn_delete, btn_cancel):
        b.pack(side="left", padx=10)

    # ─────────────────────────────────────────────────────────────────────────
    # SPEC TABLE  — IR + ACW rows per channel (settingspec)
    # ─────────────────────────────────────────────────────────────────────────
    mid_frame = tk.Frame(content, bg="black", bd=1, relief="solid",
                         highlightbackground="#444", highlightthickness=1)
    mid_frame.pack(fill="x", pady=(0, 5))

    tab_bar = tk.Frame(mid_frame, bg="black", pady=5, padx=5)
    tab_bar.pack(fill="x")

    # Channel tab labels
    ch_tab_frame = tk.Frame(tab_bar, bg="black")
    ch_tab_frame.pack(side="left")
    ch_labels = []
    for i in range(1, 9):
        lbl = tk.Label(ch_tab_frame, text=f"CH#{i}", bg="#111", fg="white",
                       font=('Arial', 9, 'bold'), width=7, bd=1,
                       relief="solid", cursor="hand2")
        lbl.pack(side="left", padx=1)
        ch_labels.append(lbl)

    table_frame = tk.Frame(mid_frame, bg="black")
    table_frame.pack(fill="x", padx=5, pady=(0, 5))

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

    def render_spec_table(ch):
        """Redraw the spec entry table for the given channel."""
        for w in table_frame.winfo_children():
            w.destroy()
        spec_widgets.clear()

        for col_i, h in enumerate(spec_headers):
            table_frame.columnconfigure(col_i, weight=1)
            tk.Label(table_frame, text=h, bg="#111", fg="white",
                     font=('Arial', 9, 'bold'), bd=1, relief="solid",
                     pady=6).grid(row=0, column=col_i, sticky="nsew")

        for row_i, (test_name, row_color) in enumerate(
                [("IR", "#1a2a1a"), ("ACW", "#1a1a2a")], start=1):
            vals = spec_data[ch][test_name]
            tk.Label(table_frame, text=test_name, bg=row_color, fg="#ffcc00",
                     font=('Arial', 9, 'bold'), bd=1, relief="solid",
                     pady=6).grid(row=row_i, column=0, sticky="nsew")
            row_entries = []
            for col_i, val in enumerate(vals, start=1):
                e = tk.Entry(table_frame, bg=row_color, fg="white",
                             font=('Arial', 9), bd=1, relief="solid",
                             justify="center", insertbackground="white")
                e.insert(0, val)
                e.grid(row=row_i, column=col_i, sticky="nsew", ipady=5)
                row_entries.append(e)
            spec_widgets[test_name] = row_entries

    def switch_channel(ch):
        save_spec_ui()
        active_ch["value"] = ch
        for idx, lbl in enumerate(ch_labels):
            lbl.config(bg="#e8a000" if idx + 1 == ch else "#111",
                       fg="black"  if idx + 1 == ch else "white")
        render_spec_table(ch)

    for i, lbl in enumerate(ch_labels):
        lbl.bind("<Button-1>", lambda e, c=i+1: switch_channel(c))

    def update_channel_visibility(*args):
        try:
            num_ch = int(cb_channels.get())
        except ValueError:
            num_ch = 1
        for i, lbl in enumerate(ch_labels):
            if i < num_ch:
                lbl.pack(side="left", padx=1)
            else:
                lbl.pack_forget()
        if active_ch["value"] > num_ch:
            switch_channel(num_ch)

    cb_channels.bind("<<ComboboxSelected>>", update_channel_visibility)
    cb_channels.bind("<KeyRelease>", update_channel_visibility)

    switch_channel(1)   # initial render
    update_channel_visibility()

    # ─────────────────────────────────────────────────────────────────────────
    # BOTTOM  — Parts list (settingmaster)
    # ─────────────────────────────────────────────────────────────────────────
    bot_frame = tk.Frame(content, bg="black", bd=1, relief="solid",
                         highlightbackground="#444", highlightthickness=1)
    bot_frame.pack(fill="both", expand=True, pady=(0, 5))

    tk.Label(bot_frame, text="L I S T   O F   P A R T   N U M B E R S",
             bg="black", fg="white", font=('Arial', 11, 'bold'),
             pady=8).pack(fill="x")

    cols_bot = ("SL", "PART NUMBER", "PART NAME", "CUSTOMER", "MODEL", "ALC", "CH#", "MACHINE")
    tree_bot = ttk.Treeview(bot_frame, columns=cols_bot, show="headings", height=7)
    sb = ttk.Scrollbar(bot_frame, orient="vertical", command=tree_bot.yview)
    tree_bot.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    tree_bot.pack(fill="both", expand=True)

    col_widths = {"SL": 40, "PART NUMBER": 120, "PART NAME": 140,
                  "CUSTOMER": 120, "MODEL": 100, "ALC": 70, "CH#": 50, "MACHINE": 80}
    for col in cols_bot:
        tree_bot.heading(col, text=col)
        tree_bot.column(col, anchor="center", width=col_widths.get(col, 90))

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
        try:
            with db.get_cursor() as cur:
                cur.execute("SELECT pno, pname, cname, mname, alc, chsel, machine FROM settingmaster ORDER BY pno")
                for idx, row in enumerate(cur.fetchall(), start=1):
                    pno, pname, cname, model, alc, channel, machine = row
                    tree_bot.insert("", "end", iid=pno,
                                    values=(idx, pno, pname, cname, model, alc, channel, machine))
        except Exception as ex:
            # DB not available — silently skip
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
                    except ValueError:
                        continue
                    if ch in spec_data and testname in spec_data[ch]:
                        spec_data[ch][testname] = [appvol, testtime, vmin, vmax]
        except Exception:
            pass
        switch_channel(active_ch["value"])

    # ─────────────────────────────────────────────────────────────────────────
    # CRUD FUNCTIONS
    # ─────────────────────────────────────────────────────────────────────────
    def on_new():
        clear_form()
        lock_form(False)
        ent_pno.focus()
        mode["value"] = "NEW"
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
            mode["value"] = "VIEW"
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
            mode["value"] = "VIEW"
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
            mode["value"] = "VIEW"
            btn_update.config(state="disabled")
            btn_delete.config(state="disabled")
        except Exception as ex:
            messagebox.showerror("DB Error", str(ex))

    def on_cancel():
        clear_form()
        lock_form(True)
        mode["value"] = "VIEW"
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
                mode["value"] = "EDIT"
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
    lock_form(True)   # read-only until NEW or row selected
    btn_save.config(state="disabled")
    btn_update.config(state="disabled")
    btn_delete.config(state="disabled")
    refresh_parts_list()
