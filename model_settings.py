import tkinter as tk
from tkinter import ttk

def render(parent):
    style = ttk.Style()
    
    # Common treeview style
    style.configure("Treeview.Heading", background="#111", foreground="white", font=('Arial', 9, 'bold'), bordercolor="#444")
    style.configure("Treeview", background="#0a0a0a", foreground="white", fieldbackground="#0a0a0a", font=('Arial', 9), rowheight=25)
    
    # Main Content
    content = tk.Frame(parent, bg="black")
    content.pack(fill="both", expand=True, padx=(5, 5))

    def mk_entry(parent, width=20):
        return tk.Entry(parent, bg="#111", fg="white", font=('Arial', 10), bd=1, relief="solid", highlightbackground="#444", highlightthickness=1, insertbackground="white", width=width)

    def mk_combo(parent, values, width=20):
        cb = ttk.Combobox(parent, values=values, font=('Arial', 10), width=width, state="readonly")
        if values: cb.current(0)
        return cb

    # --- Top Form Section ---
    top_frame = tk.Frame(content, bg="black", bd=1, relief="solid", highlightbackground="#444", highlightthickness=1)
    top_frame.pack(fill="x", pady=(0, 5))
    
    f1 = tk.Frame(top_frame, bg="black", padx=15, pady=10)
    f1.pack(side="left", fill="both", expand=True)
    f1.columnconfigure(1, weight=1)
    tk.Label(f1, text="MODEL NAME", bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky="w", pady=6)
    mk_entry(f1).grid(row=0, column=1, sticky="ew", padx=10)
    tk.Label(f1, text="PART NUMBER", bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky="w", pady=6)
    mk_entry(f1).grid(row=1, column=1, sticky="ew", padx=10)
    mk_combo(f1, ["- ( Select Barcode Type )"]).grid(row=2, column=0, columnspan=2, sticky="ew", pady=6, padx=(0, 10))
    mk_combo(f1, [""]).grid(row=3, column=0, columnspan=2, sticky="ew", pady=6, padx=(0, 10))

    f2 = tk.Frame(top_frame, bg="black", padx=15, pady=10)
    f2.pack(side="left", fill="both", expand=True)
    f2.columnconfigure(1, weight=1)
    for i, lbl in enumerate(["VENDOR CODE", "EO NUMBER", "SPECIAL DATA", "SUPPLIER SECTION"]):
        tk.Label(f2, text=lbl, bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=i, column=0, sticky="w", pady=6)
        mk_entry(f2).grid(row=i, column=1, sticky="ew", padx=10)

    f3 = tk.Frame(top_frame, bg="black", padx=15, pady=10)
    f3.pack(side="left", fill="both", expand=True)
    f3.columnconfigure(1, weight=1)
    tk.Label(f3, text="SCAN CODE", bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky="w", pady=6)
    mk_entry(f3).grid(row=0, column=1, sticky="ew", padx=10)
    tk.Label(f3, text="INITIAL ID", bg="black", fg="white", font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky="w", pady=6)
    mk_entry(f3).grid(row=1, column=1, sticky="ew", padx=10)
    
    tk.Label(f3, text="MONITOR SIZE", bg="black", fg="#4ba3e3", font=('Arial', 9, 'bold')).grid(row=2, column=1, sticky="w", padx=10, pady=(10, 0))
    sp = ttk.Spinbox(f3, from_=10.0, to=30.0, increment=0.1, font=('Arial', 10), width=10)
    sp.set("14.0")
    sp.grid(row=3, column=1, sticky="w", padx=10, pady=2)

    # --- Buttons Section ---
    btn_frame = tk.Frame(content, bg="black", bd=1, relief="solid", highlightbackground="#444", highlightthickness=1)
    btn_frame.pack(fill="x", pady=(0, 5))
    
    btn_inner = tk.Frame(btn_frame, bg="black", pady=10)
    btn_inner.pack(expand=True)
    
    def mk_btn(parent, text, bg_color):
        return tk.Button(parent, text=text, bg=bg_color, fg="white", font=('Arial', 12, 'bold'), width=15, bd=0, padx=10, pady=6, activebackground=bg_color, activeforeground="white", cursor="hand2")

    mk_btn(btn_inner, "➕ NEW", "#8b0000").pack(side="left", padx=10)
    mk_btn(btn_inner, "✏ EDIT", "#0033aa").pack(side="left", padx=10)
    mk_btn(btn_inner, "💾 SAVE", "#006600").pack(side="left", padx=10)
    mk_btn(btn_inner, "✖ CANCEL", "#4b0082").pack(side="left", padx=10)
    mk_btn(btn_inner, "🗑 DELETE", "#b8860b").pack(side="left", padx=10)

    # --- Middle Section (Table) ---
    mid_frame = tk.Frame(content, bg="black", bd=1, relief="solid", highlightbackground="#444", highlightthickness=1)
    mid_frame.pack(fill="x", pady=(0, 5))
    
    tab_bar = tk.Frame(mid_frame, bg="black", pady=5, padx=5)
    tab_bar.pack(fill="x")
    
    mode_combo = mk_combo(tab_bar, ["WIRE / CHANNEL #", "COMBINED"], width=25)
    mode_combo.pack(side="left", padx=(0, 10))

    # Default test data template for each channel
    default_test_data = [
        ("1", "Insulation Test", "Volts", "unchecked", "All/Single", "1", "", "500", "100", "999"),
        ("2", "With Stand (mA)", "mA", "unchecked", "All/Single", "3", "", "1000", "0", "10"),
        ("3", "Contact", "-", "unchecked", "All/Single", "-", "-", "-", "-", "-"),
    ]

    # Store per-channel data: { ch_index: [ [row_list], ... ] }
    channel_data = {}
    for ch in range(1, 11):
        channel_data[ch] = [list(row) for row in default_test_data]

    # Track current active channel and mode
    active_channel = {"current": 1}
    current_mode = {"value": "WIRE / CHANNEL #"}

    # Frame to hold channel tabs (shown/hidden based on mode)
    ch_tab_frame = tk.Frame(tab_bar, bg="black")
    ch_tab_frame.pack(side="left")

    # Channel tab labels
    ch_labels = []
    for i in range(1, 11):
        lbl = tk.Label(ch_tab_frame, text=f"CH#{i}", bg="#111", fg="white",
                       font=('Arial', 9, 'bold'), width=8, bd=1, relief="solid", cursor="hand2")
        lbl.pack(side="left", padx=1)
        ch_labels.append(lbl)

    # Table container
    table_frame = tk.Frame(mid_frame, bg="black")
    table_frame.pack(fill="x")

    headers = ["#", "TEST", "Unit", "SKIP", "TEST TYPE", "TEST TIME (SEC)", "Freq (kHz/MHz)", "Applied Volts (V)", "Result - Min", "Result - Max"]

    # Track current table widgets for reading back values
    current_widgets = {"entries": [], "checkboxes": [], "combos": []}

    style.configure("Dark.TCheckbutton", background="#0a0a0a")

    def save_current_data():
        """Save widget values back into channel_data."""
        if not current_widgets["entries"]:
            return
        if current_mode["value"] == "COMBINED":
            # Save to ALL channels
            row_values = []
            for r in range(len(current_widgets["entries"])):
                saved_row = list(channel_data[1][r])  # start from template
                if r < len(current_widgets["checkboxes"]):
                    saved_row[3] = "checked" if current_widgets["checkboxes"][r].get() else "unchecked"
                if r < len(current_widgets["combos"]):
                    saved_row[4] = current_widgets["combos"][r].get()
                entry_row = current_widgets["entries"][r]
                for e_idx, entry in enumerate(entry_row):
                    saved_row[5 + e_idx] = entry.get()
                row_values.append(saved_row)
            for ch in range(1, 11):
                channel_data[ch] = [list(row) for row in row_values]
        else:
            # Save to active channel only
            ch = active_channel["current"]
            data = channel_data[ch]
            for r, row in enumerate(data):
                if r < len(current_widgets["checkboxes"]):
                    row[3] = "checked" if current_widgets["checkboxes"][r].get() else "unchecked"
                if r < len(current_widgets["combos"]):
                    row[4] = current_widgets["combos"][r].get()
                entry_row = current_widgets["entries"][r] if r < len(current_widgets["entries"]) else []
                for e_idx, entry in enumerate(entry_row):
                    row[5 + e_idx] = entry.get()

    def render_table_from_data(data):
        """Render the table using the given data rows."""
        # Clear table frame
        for widget in table_frame.winfo_children():
            widget.destroy()

        # Reset widget trackers
        current_widgets["entries"] = []
        current_widgets["checkboxes"] = []
        current_widgets["combos"] = []

        # Render headers
        for i, h in enumerate(headers):
            table_frame.columnconfigure(i, weight=1)
            tk.Label(table_frame, text=h, bg="#111", fg="white", font=('Arial', 9, 'bold'),
                     bd=1, relief="solid", pady=6).grid(row=0, column=i, sticky="nsew")

        # Render rows
        for r, row in enumerate(data):
            idx, test_name, unit, skip_val, ttype, ttime, freq, volts, rmin, rmax = row

            tk.Label(table_frame, text=idx, bg="#0a0a0a", fg="white", font=('Arial', 9),
                     bd=1, relief="solid", pady=6).grid(row=r+1, column=0, sticky="nsew")
            tk.Label(table_frame, text=test_name, bg="#0a0a0a", fg="white", font=('Arial', 9),
                     bd=1, relief="solid").grid(row=r+1, column=1, sticky="nsew")
            tk.Label(table_frame, text=unit, bg="#0a0a0a", fg="#ffcc00", font=('Arial', 9, 'bold'),
                     bd=1, relief="solid").grid(row=r+1, column=2, sticky="nsew")

            # SKIP Checkbox
            cb_frame = tk.Frame(table_frame, bg="#0a0a0a", bd=1, relief="solid")
            cb_frame.grid(row=r+1, column=3, sticky="nsew")
            var = tk.BooleanVar(value=(skip_val == "checked"))
            tk.Checkbutton(cb_frame, variable=var, bg="#0a0a0a", activebackground="#0a0a0a",
                           selectcolor="#222").pack(expand=True)
            current_widgets["checkboxes"].append(var)

            # TEST TYPE Combobox
            combo_frame = tk.Frame(table_frame, bg="#0a0a0a", bd=1, relief="solid")
            combo_frame.grid(row=r+1, column=4, sticky="nsew")
            combo = ttk.Combobox(combo_frame, values=["All/Single", "Combined"], state="readonly",
                                 width=12, font=('Arial', 9))
            combo.set(ttype if ttype in ["All/Single", "Combined"] else "All/Single")
            combo.pack(expand=True, pady=4)
            current_widgets["combos"].append(combo)

            # Editable entry fields (TEST TIME, Freq, Volts, Min, Max)
            row_entries = []
            for c_idx, val in enumerate([ttime, freq, volts, rmin, rmax], start=5):
                entry = tk.Entry(table_frame, bg="#0a0a0a", fg="white", font=('Arial', 9),
                                 bd=1, relief="solid", justify="center", insertbackground="white")
                entry.insert(0, val)
                entry.grid(row=r+1, column=c_idx, sticky="nsew", ipady=4)
                row_entries.append(entry)
            current_widgets["entries"].append(row_entries)

    def switch_to_channel(ch):
        """Switch to a specific channel tab."""
        save_current_data()
        active_channel["current"] = ch

        # Update tab highlight
        for idx, lbl in enumerate(ch_labels):
            if idx + 1 == ch:
                lbl.config(bg="#e8a000", fg="black")
            else:
                lbl.config(bg="#111", fg="white")

        render_table_from_data(channel_data[ch])

    def switch_to_combined():
        """Switch to combined mode — edits apply to all channels."""
        save_current_data()

        # Highlight all tabs to indicate combined mode
        for lbl in ch_labels:
            lbl.config(bg="#e8a000", fg="black")

        # Show data from channel 1 as the shared view
        render_table_from_data(channel_data[1])

    def on_mode_change(event):
        """Handle combobox mode switching."""
        mode = mode_combo.get()
        current_mode["value"] = mode
        if mode == "COMBINED":
            switch_to_combined()
        else:
            switch_to_channel(active_channel["current"])

    mode_combo.bind("<<ComboboxSelected>>", on_mode_change)

    # Bind click events to channel tabs
    for i, lbl in enumerate(ch_labels):
        ch_num = i + 1
        lbl.bind("<Button-1>", lambda e, c=ch_num: on_tab_click(c))

    def on_tab_click(ch):
        """Handler for channel tab clicks."""
        if current_mode["value"] == "COMBINED":
            return  # Ignore tab clicks in combined mode
        switch_to_channel(ch)

    # Render initial channel
    switch_to_channel(1)

    # --- Bottom Section ---
    bot_frame = tk.Frame(content, bg="black", bd=1, relief="solid", highlightbackground="#444", highlightthickness=1)
    bot_frame.pack(fill="both", expand=True, pady=(0, 5))
    
    tk.Label(bot_frame, text="L I S T   O F   P A R T   N U M B E R S", bg="black", fg="white", font=('Arial', 11, 'bold'), pady=8).pack(fill="x")
    
    cols_bot = ("SL", "MODEL", "PART NUMBER", "ALC", "CH#")
    tree_bot = ttk.Treeview(bot_frame, columns=cols_bot, show="headings", height=8)
    for col in cols_bot:
        tree_bot.heading(col, text=col)
        tree_bot.column(col, anchor="center")
    tree_bot.pack(fill="both", expand=True)
    
    # Insert some empty rows to show grid lines
    for _ in range(8):
        tree_bot.insert("", "end", values=("", "", "", "", ""))


