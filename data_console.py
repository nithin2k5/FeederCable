import tkinter as tk
from tkinter import ttk

def render(parent):
    bg_color = "#081014" # Dark cyan-tinted background from image
    border_color = "#182c35" # slightly lighter cyan/teal for borders
    text_color = "white"
    teal_text = "#489fb5" # cyan/teal color for INFAC INDIA
    
    style = ttk.Style()
    
    # Custom styles
    style.configure("Treeview.Heading", background="#0a1920", foreground=text_color, font=('Arial', 9, 'bold'), bordercolor=border_color, lightcolor=border_color, darkcolor=border_color)
    style.configure("Treeview", background="#0c131a", foreground=text_color, fieldbackground="#0c131a", font=('Arial', 9), rowheight=28, bordercolor=border_color)
    style.map("Treeview", background=[('selected', '#1a3340')])
    
    style.configure("TCombobox", fieldbackground="#111", background="#111", foreground="white", bordercolor=border_color)

    # --- Main Content ---
    content = tk.Frame(parent, bg=bg_color, bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1)
    content.pack(fill="both", expand=True, padx=5, pady=5)
    
    # --- Top Header ---
    header = tk.Frame(content, bg=bg_color, height=80, bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1)
    header.pack(fill="x", padx=10, pady=(10, 5))
    header.pack_propagate(False)
    
    # INFAC INDIA logo box
    logo_frame = tk.Frame(header, bg=bg_color, bd=1, relief="solid", highlightbackground=teal_text, highlightthickness=1, padx=15, pady=5)
    logo_frame.pack(side="left", padx=20, pady=10)
    
    logo_top = tk.Frame(logo_frame, bg=bg_color)
    logo_top.pack()
    tk.Label(logo_top, text="IN", fg="red", bg=bg_color, font=('Arial', 18, 'bold')).pack(side="left")
    tk.Label(logo_top, text="FAC", fg=teal_text, bg=bg_color, font=('Arial', 18, 'bold')).pack(side="left")
    tk.Label(logo_frame, text="INDIA", fg=teal_text, bg=bg_color, font=('Arial', 10, 'bold')).pack()

    # Title
    tk.Label(header, text="TEST DATA CONSOLE", fg="white", bg=bg_color, font=('Arial', 24, 'bold')).pack(side="left", expand=True, padx=(0, 100))

    # --- Filter Bar ---
    filter_bar = tk.Frame(content, bg=bg_color, bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1)
    filter_bar.pack(fill="x", padx=10, pady=5)
    
    filter_inner = tk.Frame(filter_bar, bg=bg_color, pady=15)
    filter_inner.pack(expand=True) # Center it

    def mk_lbl(parent, txt):
        return tk.Label(parent, text=txt, bg=bg_color, fg="white", font=('Arial', 9, 'bold'))
        
    def mk_combo(parent, val, w=15):
        cb = ttk.Combobox(parent, values=[val], font=('Arial', 10), width=w, state="readonly")
        cb.current(0)
        return cb

    # Part Number
    mk_lbl(filter_inner, "PART NUMBER :").grid(row=0, column=0, sticky="e", padx=(0, 10))
    mk_combo(filter_inner, "", 20).grid(row=0, column=1, sticky="w", padx=(0, 30))
    
    # Dates
    mk_lbl(filter_inner, "START DATE :").grid(row=0, column=2, sticky="e", padx=(0, 10), pady=5)
    mk_combo(filter_inner, "01 February 2024", 18).grid(row=0, column=3, sticky="w", padx=(0, 30), pady=5)
    
    mk_lbl(filter_inner, "END DATE :").grid(row=1, column=2, sticky="e", padx=(0, 10), pady=5)
    mk_combo(filter_inner, "08 February 2024", 18).grid(row=1, column=3, sticky="w", padx=(0, 30), pady=5)
    
    # Result
    mk_lbl(filter_inner, "RESULT :").grid(row=0, column=4, sticky="e", padx=(0, 10))
    mk_combo(filter_inner, "", 15).grid(row=0, column=5, sticky="w", padx=(0, 30))
    
    # Buttons
    btn_frame = tk.Frame(filter_inner, bg=bg_color)
    btn_frame.grid(row=0, column=6, rowspan=2, padx=10)
    
    search_btn = tk.Button(btn_frame, text="🔍 Search", bg="#0a2a30", fg="white", font=('Arial', 10, 'bold'), bd=1, relief="solid", highlightbackground=teal_text, highlightthickness=1, padx=15, pady=5, cursor="hand2")
    search_btn.pack(side="left", padx=10)
    
    export_btn = tk.Button(btn_frame, text="📄 ExportToExcel", bg="#0a2a30", fg="white", font=('Arial', 10, 'bold'), bd=1, relief="solid", highlightbackground=teal_text, highlightthickness=1, padx=15, pady=5, cursor="hand2")
    export_btn.pack(side="left", padx=10)
    
    # --- Table Area ---
    table_outer = tk.Frame(content, bg=bg_color, bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1)
    table_outer.pack(fill="both", expand=True, padx=10, pady=(5, 10))
    
    cols = ("SNO", "DATE", "TIME", "CUSTOMER NAME", "MODEL", "P/NUMBER", "P/NAME", "LOTNO", "ALC", "TEST NAME", "CH1", "CH2", "CH3", "CH4")
    tree = ttk.Treeview(table_outer, columns=cols, show="headings")
    
    # Horizontal scrollbar
    hsb = ttk.Scrollbar(table_outer, orient="horizontal", command=tree.xview)
    tree.configure(xscrollcommand=hsb.set)
    hsb.pack(side="bottom", fill="x")
    tree.pack(side="top", fill="both", expand=True)
    
    col_widths = {
        "SNO": 50,
        "DATE": 80,
        "TIME": 80,
        "CUSTOMER NAME": 120,
        "MODEL": 80,
        "P/NUMBER": 80,
        "P/NAME": 80,
        "LOTNO": 80,
        "ALC": 60,
        "TEST NAME": 100,
        "CH1": 50, "CH2": 50, "CH3": 50, "CH4": 50
    }
    
    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, width=col_widths.get(col, 80), anchor="center")


