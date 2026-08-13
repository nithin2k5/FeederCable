import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("Model Settings")
    root.geometry("1350x860")
    root.configure(bg="black")
    
    style = ttk.Style()
    style.theme_use("clam")
    
    # Common treeview style
    style.configure("Treeview.Heading", background="#111", foreground="white", font=('Arial', 9, 'bold'), bordercolor="#444")
    style.configure("Treeview", background="#0a0a0a", foreground="white", fieldbackground="#0a0a0a", font=('Arial', 9), rowheight=25)
    
    # --- Header ---
    header = tk.Frame(root, bg="black", height=45)
    header.pack(fill="x")
    header.pack_propagate(False)

    logo_box = tk.Frame(header, bg="white", padx=6, pady=3)
    logo_box.pack(side="left", padx=10, pady=6)
    tk.Label(logo_box, text="INFAC", fg="#c00000", bg="white", font=('Arial', 16, 'bold')).pack(side="left")
    tk.Label(logo_box, text=" 주식회사인팩", fg="black", bg="white", font=('Malgun Gothic', 9)).pack(side="left")

    tk.Label(header, text="Model Settings", fg="#e8a000", bg="black", font=('Arial', 15, 'bold')).pack(side="left", padx=25)
    tk.Label(header, text="15/07/2025  15:05:07", fg="white", bg="black", font=('Arial', 10)).pack(side="right", padx=15)

    # --- Body ---
    body = tk.Frame(root, bg="black")
    body.pack(fill="both", expand=True)

    # Sidebar
    sidebar_w = 90
    sidebar = tk.Frame(body, bg="black", width=sidebar_w)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    sidebar_buttons = [
        ("👤", "Admin", "test_console.py"),
        ("⚙", "Settings", "model_settings.py"),
        ("⚖", "Comparator", ""),
        ("📋", "Test Data", "data_console.py"),
        ("🔧", "COM Setting", "comport_settings.py"),
    ]
    
    import subprocess
    import sys
    import os
    
    def on_btn_click(script):
        if script and os.path.exists(script):
            subprocess.Popen([sys.executable, script])
            root.destroy()
            
    for icon, text, script in sidebar_buttons:
        f = tk.Frame(sidebar, bg="#111", bd=1, relief="solid", highlightbackground="#444", highlightthickness=1, cursor="hand2" if script else "arrow")
        f.pack(fill="x", padx=4, pady=3)
        lbl_icon = tk.Label(f, text=icon, bg="#111", fg="white", font=('Arial', 18), cursor="hand2" if script else "arrow")
        lbl_icon.pack(pady=(6, 0))
        lbl_text = tk.Label(f, text=text, bg="#111", fg="white", font=('Arial', 8), cursor="hand2" if script else "arrow")
        lbl_text.pack(pady=(0, 6))
        
        if script:
            f.bind("<Button-1>", lambda e, s=script: on_btn_click(s))
            lbl_icon.bind("<Button-1>", lambda e, s=script: on_btn_click(s))
            lbl_text.bind("<Button-1>", lambda e, s=script: on_btn_click(s))

    # Main Content
    content = tk.Frame(body, bg="black")
    content.pack(side="left", fill="both", expand=True, padx=(5, 5))

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
    
    mk_combo(tab_bar, ["WIRE / CHANNEL #"], width=25).pack(side="left", padx=(0, 10))
    
    for i in range(1, 11):
        bg_c = "#111" if i > 1 else "#222"
        tk.Label(tab_bar, text=f"CH#{i}", bg=bg_c, fg="white", font=('Arial', 9, 'bold'), width=8, bd=1, relief="solid").pack(side="left", padx=1)

    table_frame = tk.Frame(mid_frame, bg="black")
    table_frame.pack(fill="x")
    
    headers = ["#", "TEST", "Unit", "SKIP", "TEST TYPE", "TEST TIME (SEC)", "Freq (kHz/MHz)", "Applied Volts (V)", "Result - Min", "Result - Max", "REF", "Offset"]
    for i, h in enumerate(headers):
        table_frame.columnconfigure(i, weight=1)
        tk.Label(table_frame, text=h, bg="#111", fg="white", font=('Arial', 9, 'bold'), bd=1, relief="solid", pady=6).grid(row=0, column=i, sticky="nsew")

    test_data = [
        ("1", "Insulation Test", "Volts", "All/Single", "1", "", "500", "100", "999", "0", "0"),
        ("2", "With Stand (mA)", "mA", "All/Single", "3", "", "1000", "0", "10", "0", "0"),
        ("3", "Contact", "-", "All/Single", "-", "-", "-", "-", "-", "-", "-"),
        ("4", "Resistance", "Ω", "All/Single", "-", "-", "-", "-", "-", "-", "-"),
    ]
    
    style.configure("Dark.TCheckbutton", background="#0a0a0a")
    
    for r, row in enumerate(test_data):
        idx, test_name, unit, ttype, ttime, freq, volts, rmin, rmax, ref, offset = row
        
        tk.Label(table_frame, text=idx, bg="#0a0a0a", fg="white", font=('Arial', 9), bd=1, relief="solid", pady=6).grid(row=r+1, column=0, sticky="nsew")
        tk.Label(table_frame, text=test_name, bg="#0a0a0a", fg="white", font=('Arial', 9), bd=1, relief="solid").grid(row=r+1, column=1, sticky="nsew")
        tk.Label(table_frame, text=unit, bg="#0a0a0a", fg="#ffcc00", font=('Arial', 9, 'bold'), bd=1, relief="solid").grid(row=r+1, column=2, sticky="nsew")
        
        cb_frame = tk.Frame(table_frame, bg="#0a0a0a", bd=1, relief="solid")
        cb_frame.grid(row=r+1, column=3, sticky="nsew")
        # Custom checkbox look
        tk.Label(cb_frame, text="☐", bg="#0a0a0a", fg="#4ba3e3", font=('Arial', 14)).pack(expand=True)
        
        for c_idx, val in enumerate([ttype, ttime, freq, volts, rmin, rmax, ref, offset], start=4):
            tk.Label(table_frame, text=val, bg="#0a0a0a", fg="white", font=('Arial', 9), bd=1, relief="solid").grid(row=r+1, column=c_idx, sticky="nsew")

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

    root.mainloop()

if __name__ == "__main__":
    main()
