import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("Feeder Cable Tester")
    root.geometry("1280x800")
    
    # Colors to match the image
    bg_color = "#080c14"
    fg_color = "white"
    border_color = "#3a4150"
    
    root.configure(bg=bg_color)
    
    style = ttk.Style()
    style.theme_use("clam")
    
    # Configure styles
    style.configure("TLabelframe", background=bg_color, foreground="white", bordercolor=border_color)
    style.configure("TLabelframe.Label", background=bg_color, foreground="white", font=('Arial', 10))
    style.configure("Treeview.Heading", background="#f0f0f0", foreground="black", font=('Arial', 9, 'bold'))
    style.configure("Treeview", background="#f0f0f0", foreground="black", fieldbackground="#f0f0f0", font=('Arial', 9), rowheight=25)
    
    # ---- TOP HEADER ----
    header_frame = tk.Frame(root, bg="black", height=40)
    header_frame.pack(side="top", fill="x")
    
    # INFAC logo box
    logo_frame = tk.Frame(header_frame, bg="white", padx=5, pady=2)
    logo_frame.pack(side="left", padx=10, pady=5)
    tk.Label(logo_frame, text="INFAC", fg="#c00000", bg="white", font=('Arial', 18, 'bold')).pack(side="left")
    tk.Label(logo_frame, text="주식회사인팩", fg="black", bg="white", font=('Malgun Gothic', 10)).pack(side="left", padx=(5,0))
    
    tk.Label(header_frame, text="Feeder Cable", fg="#ffaa00", bg="black", font=('Arial', 14, 'bold')).pack(side="left", padx=20)
    tk.Label(header_frame, text="15/07/2025 15:05:07", fg="white", bg="black", font=('Arial', 10)).pack(side="right", padx=20)
    
    # ---- MAIN LAYOUT ----
    main_frame = tk.Frame(root, bg=bg_color)
    main_frame.pack(fill="both", expand=True, padx=5, pady=5)
    
    # ---- SIDEBAR ----
    sidebar = tk.Frame(main_frame, bg="black", width=80)
    sidebar.pack(side="left", fill="y", padx=(0, 5))
    
    def create_sidebar_btn(parent, text, icon_placeholder=None):
        f = tk.Frame(parent, bg="black", bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1)
        f.pack(fill="x", pady=2, padx=2)
        if icon_placeholder:
            tk.Label(f, text=icon_placeholder, fg="white", bg="black", font=('Arial', 16)).pack(pady=(5,0))
        tk.Label(f, text=text, fg="white", bg="black", font=('Arial', 9)).pack(pady=(0,5))
        
        # Hover effect
        def on_enter(e):
            f.config(bg="#333")
            for child in f.winfo_children(): child.config(bg="#333")
        def on_leave(e):
            f.config(bg="black")
            for child in f.winfo_children(): child.config(bg="black")
            
        f.bind("<Enter>", on_enter)
        f.bind("<Leave>", on_leave)
        for child in f.winfo_children():
            child.bind("<Enter>", on_enter)
            child.bind("<Leave>", on_leave)
            
    create_sidebar_btn(sidebar, "Admin", "👤")
    create_sidebar_btn(sidebar, "Settings", "⚙")
    create_sidebar_btn(sidebar, "Comparator", "⚖")
    create_sidebar_btn(sidebar, "Test Data", "📄")
    create_sidebar_btn(sidebar, "COM Setting", "🔌")
    
    # ---- CONTENT COLUMNS ----
    content_area = tk.Frame(main_frame, bg=bg_color)
    content_area.pack(side="left", fill="both", expand=True)
    
    content_area.columnconfigure(0, weight=4) # Left large column
    content_area.columnconfigure(1, weight=1) # Right smaller column
    content_area.rowconfigure(0, weight=1)
    
    left_col = tk.Frame(content_area, bg=bg_color)
    left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
    
    right_col = tk.Frame(content_area, bg=bg_color)
    right_col.grid(row=0, column=1, sticky="nsew")
    
    def create_entry(parent, val="", fg="white", bg="black", font_size=12):
        e = tk.Entry(parent, bg=bg, fg=fg, font=('Arial', font_size), insertbackground="white", bd=1, relief="solid")
        e.insert(0, val)
        return e

    # ---- LEFT COLUMN ----
    
    # 1. Top Info Section
    top_info_frame = tk.Frame(left_col, bg=bg_color)
    top_info_frame.pack(fill="x", pady=(0, 5))
    top_info_frame.columnconfigure(0, weight=2)
    top_info_frame.columnconfigure(1, weight=1)
    
    # Product Info
    product_frame = ttk.LabelFrame(top_info_frame, text="Product Info")
    product_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 5))
    
    pf_inner = tk.Frame(product_frame, bg=bg_color, padx=5, pady=5)
    pf_inner.pack(fill="both", expand=True)
    pf_inner.columnconfigure(1, weight=1)
    pf_inner.columnconfigure(3, weight=1)
    
    tk.Label(pf_inner, text="Product No", bg=bg_color, fg="white", font=('Arial', 10)).grid(row=0, column=0, sticky="w", pady=5)
    create_entry(pf_inner, "96220 06250").grid(row=0, column=1, sticky="ew", padx=5)
    tk.Label(pf_inner, text="EMP ID", bg=bg_color, fg="white", font=('Arial', 10)).grid(row=0, column=2, sticky="w", padx=10)
    create_entry(pf_inner, "").grid(row=0, column=3, sticky="ew", padx=5)
    
    tk.Label(pf_inner, text="ProductNa", bg=bg_color, fg="white", font=('Arial', 10)).grid(row=1, column=0, sticky="w", pady=5)
    create_entry(pf_inner, "SP2I").grid(row=1, column=1, sticky="ew", padx=5)
    tk.Label(pf_inner, text="Car", bg=bg_color, fg="white", font=('Arial', 10)).grid(row=1, column=2, sticky="w", padx=10)
    create_entry(pf_inner, "MAI").grid(row=1, column=3, sticky="ew", padx=5)
    
    row2_f = tk.Frame(pf_inner, bg=bg_color)
    row2_f.grid(row=2, column=0, columnspan=4, sticky="ew", pady=5)
    for i in range(8):
        row2_f.columnconfigure(i, weight=1 if i%2!=0 else 0)
        
    tk.Label(row2_f, text="ALC code", bg=bg_color, fg="white", font=('Arial', 10)).grid(row=0, column=0, sticky="w")
    create_entry(row2_f, "P96").grid(row=0, column=1, sticky="ew", padx=(5,10))
    tk.Label(row2_f, text="LOT", bg=bg_color, fg="white", font=('Arial', 10)).grid(row=0, column=2, sticky="w")
    create_entry(row2_f, "").grid(row=0, column=3, sticky="ew", padx=(5,10))
    tk.Label(row2_f, text="PCI", bg=bg_color, fg="white", font=('Arial', 10)).grid(row=0, column=4, sticky="w")
    create_entry(row2_f, "").grid(row=0, column=5, sticky="ew", padx=(5,10))
    tk.Label(row2_f, text="Serial", bg=bg_color, fg="white", font=('Arial', 10)).grid(row=0, column=6, sticky="w")
    create_entry(row2_f, "0229").grid(row=0, column=7, sticky="ew", padx=(5,0))
    
    # Count
    count_frame = ttk.LabelFrame(top_info_frame, text="Count")
    count_frame.grid(row=0, column=1, sticky="nsew", pady=(0, 2))
    cf_inner = tk.Frame(count_frame, bg=bg_color, padx=5, pady=5)
    cf_inner.pack(fill="both", expand=True)
    cf_inner.columnconfigure(1, weight=1)
    cf_inner.columnconfigure(3, weight=1)
    
    tk.Label(cf_inner, text="Total", bg=bg_color, fg="white", font=('Arial', 10)).grid(row=0, column=0, sticky="w", pady=2)
    create_entry(cf_inner, "235").grid(row=0, column=1, sticky="ew", padx=5)
    tk.Label(cf_inner, text="NG", bg=bg_color, fg="white", font=('Arial', 10)).grid(row=0, column=2, sticky="w", padx=5)
    create_entry(cf_inner, "6", fg="#ff4444").grid(row=0, column=3, sticky="ew")
    
    tk.Label(cf_inner, text="OK", bg=bg_color, fg="white", font=('Arial', 10)).grid(row=1, column=0, sticky="w", pady=2)
    create_entry(cf_inner, "229", fg="#76ff03").grid(row=1, column=1, sticky="ew", padx=5)
    tk.Label(cf_inner, text="NG", bg=bg_color, fg="white", font=('Arial', 10)).grid(row=1, column=2, sticky="w", padx=5)
    create_entry(cf_inner, "2.55", fg="#ff4444").grid(row=1, column=3, sticky="ew")

    # Method
    method_frame = ttk.LabelFrame(top_info_frame, text="Method")
    method_frame.grid(row=1, column=1, sticky="nsew", pady=(2, 0))
    mf_inner = tk.Frame(method_frame, bg=bg_color, padx=5, pady=5)
    mf_inner.pack(fill="both", expand=True)
    
    tk.Label(mf_inner, text="Combined", bg="#222", fg="white", font=('Arial', 10), relief="solid", bd=1).pack(side="left", expand=True, fill="both", padx=2)
    tk.Label(mf_inner, text="Individual", bg="#388e3c", fg="white", font=('Arial', 10), relief="solid", bd=1).pack(side="left", expand=True, fill="both", padx=2)
    tk.Label(mf_inner, text="Rework", bg="#388e3c", fg="white", font=('Arial', 10), relief="solid", bd=1).pack(side="left", expand=True, fill="both", padx=2)

    # 2. Inspection Spec
    insp_label = tk.Label(left_col, text="Inspection Specification", bg=bg_color, fg="white", font=('Arial', 11), anchor="w")
    insp_label.pack(fill="x", pady=(5,0))
    
    cols_insp = ("No", "Channel", "Type", "Freq (kHz/MHz)", "Volt (V)", "Sec (s)", "Min", "Max", "Std")
    tree_insp = ttk.Treeview(left_col, columns=cols_insp, show="headings", height=4)
    for col in cols_insp:
        tree_insp.heading(col, text=col)
        tree_insp.column(col, width=80, anchor="center")
    tree_insp.pack(fill="x")
    
    tree_insp.tag_configure('grey', background='#f0f0f0')
    tree_insp.tag_configure('blue', background='#1945d1', foreground='white')
    
    tree_insp.insert("", "end", values=("1", "3", "All", "", "500", "1", "100", "", ""), tags=('grey',))
    tree_insp.insert("", "end", values=("2", "3", "All", "", "1000", "3", "0", "10", ""), tags=('grey',))
    tree_insp.insert("", "end", values=("3", "3", "Single", "", "", "", "", "", ""), tags=('blue',))
    
    # 3. Testing
    test_label = tk.Label(left_col, text="Testing", bg=bg_color, fg="white", font=('Arial', 11), anchor="w")
    test_label.pack(fill="x", pady=(10,0))
    
    test_grid = tk.Frame(left_col, bg=bg_color)
    test_grid.pack(fill="x")
    
    cols_test = ("CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8", "CH9", "CH10", "Result")
    
    for i, col in enumerate(cols_test):
        tk.Label(test_grid, text=col, bg="#f0f0f0", fg="black", bd=1, relief="solid", font=('Arial', 10, 'bold'), width=8).grid(row=0, column=i, sticky="nsew")
        test_grid.columnconfigure(i, weight=1)
        
    for r, vals in enumerate([
        ("3253", "3253", "3253", "-", "-", "-", "-", "-", "-", "-", "PASS"),
        ("0.82", "0.82", "0.82", "-", "-", "-", "-", "-", "-", "-", "PASS"),
        ("OK", "OK", "OK", "-", "-", "-", "-", "-", "-", "-", "PASS")
    ]):
        for c, val in enumerate(vals):
            bg_c = "#aeea00" if c < 3 or c == 10 else "#f0f0f0"
            tk.Label(test_grid, text=val, bg=bg_c, fg="black", bd=1, relief="solid", font=('Arial', 10)).grid(row=r+1, column=c, sticky="nsew")
            
    # 4. Scan Label Display
    scan_frame = tk.Frame(left_col, bg="#001835", bd=1, relief="solid", highlightbackground="#1945d1", highlightthickness=1)
    scan_frame.pack(fill="x", pady=15)
    tk.Label(scan_frame, text="Scan the printed label & PASS Display", fg="white", bg="#001835", font=('Arial', 16, 'bold'), pady=15).pack()

    # 5. Bottom Section
    bottom_frame = tk.Frame(left_col, bg=bg_color)
    bottom_frame.pack(fill="x")
    bottom_frame.columnconfigure(0, weight=4)
    bottom_frame.columnconfigure(1, weight=2)
    bottom_frame.columnconfigure(2, weight=3)
    
    # IO Cable Data
    io_frame = ttk.LabelFrame(bottom_frame, text="Receive IO Cable Data")
    io_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
    io_inner = tk.Frame(io_frame, bg=bg_color, padx=5, pady=5)
    io_inner.pack(fill="both", expand=True)
    
    io_inner.columnconfigure(1, weight=1)
    
    tk.Label(io_inner, text="INPUT", bg=bg_color, fg="white", font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky="w", columnspan=2)
    in_box = tk.Frame(io_inner, bg=bg_color)
    in_box.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))
    for i in range(1, 11):
        tk.Label(in_box, text=f"CH{i}", bg="#001000", fg="#4caf50", bd=1, relief="solid", highlightbackground="#4caf50", font=('Arial', 8), width=3).pack(side="left", padx=1)
        
    tk.Label(io_inner, text="OUTPUT", bg=bg_color, fg="white", font=('Arial', 9, 'bold')).grid(row=2, column=0, sticky="w")
    tk.Label(io_inner, text="CS", bg=bg_color, fg="white", font=('Arial', 9, 'bold')).grid(row=2, column=1, sticky="e", padx=10)
    
    out_box = tk.Frame(io_inner, bg=bg_color)
    out_box.grid(row=3, column=0, sticky="w")
    for i in range(1, 11):
        tk.Label(out_box, text=f"CH{i}", bg="#001000", fg="#4caf50", bd=1, relief="solid", highlightbackground="#4caf50", font=('Arial', 8), width=3).pack(side="left", padx=1)
        
    cs_box = tk.Frame(io_inner, bg=bg_color)
    cs_box.grid(row=3, column=1, sticky="e", padx=10)
    canvas = tk.Canvas(cs_box, width=40, height=20, bg=bg_color, highlightthickness=0)
    canvas.pack()
    canvas.create_oval(2, 4, 14, 16, fill="#4caf50", outline="#4caf50")
    canvas.create_oval(20, 4, 32, 16, fill="#4caf50", outline="#4caf50")

    # COM Status
    com_frame = ttk.LabelFrame(bottom_frame, text="COM Status")
    com_frame.grid(row=0, column=1, sticky="nsew", padx=5)
    com_inner = tk.Frame(com_frame, bg=bg_color, padx=5, pady=5)
    com_inner.pack(expand=True)
    
    def mk_com_lbl(parent, text, on=True):
        bg = "#4caf50" if on else "#3a4150"
        fg = "white" if not on else "black"
        return tk.Label(parent, text=text, bg=bg, fg=fg, width=8, font=('Arial', 9))
        
    mk_com_lbl(com_inner, "PROT", True).grid(row=0, column=0, padx=2, pady=3)
    mk_com_lbl(com_inner, "LCR", False).grid(row=0, column=1, padx=2, pady=3)
    mk_com_lbl(com_inner, "Rever", False).grid(row=0, column=2, padx=2, pady=3)
    mk_com_lbl(com_inner, "IO", True).grid(row=1, column=0, padx=2, pady=3)
    mk_com_lbl(com_inner, "Printer", True).grid(row=1, column=1, padx=2, pady=3)
    mk_com_lbl(com_inner, "Scanner", True).grid(row=1, column=2, padx=2, pady=3)

    # Log
    log_frame = ttk.LabelFrame(bottom_frame, text="Log")
    log_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
    log_text = tk.Text(log_frame, bg=bg_color, fg="#aaa", font=('Consolas', 10), borderwidth=0, width=30, height=5)
    log_text.pack(fill="both", expand=True, padx=5, pady=5)
    log_text.insert("end", "15:05:07.305> function name=Connect\n")
    log_text.insert("end", "15:05:10.264> Quit\n")
    log_text.insert("end", "(0)=Normal\n")
    log_text.config(state="disabled")

    # ---- RIGHT COLUMN ----
    right_col.rowconfigure(0, weight=2)
    right_col.rowconfigure(1, weight=2)
    right_col.rowconfigure(2, weight=1)
    
    def create_right_panel(parent, title, content_bg, content_fg, content_text, font_size, is_bold=False):
        outer = tk.Frame(parent, bg="#7a7a7a", padx=1, pady=1) # border
        inner = tk.Frame(outer, bg="black")
        inner.pack(fill="both", expand=True)
        tk.Label(inner, text=title, bg="black", fg="white", font=('Arial', 11)).pack(pady=4)
        font_weight = 'bold' if is_bold else 'normal'
        tk.Label(inner, text=content_text, bg=content_bg, fg=content_fg, font=('Arial', font_size, font_weight)).pack(fill="both", expand=True)
        return outer
        
    cam1_frame = create_right_panel(right_col, "Cam 1", "#e0e0e0", "black", "Image / result", 14)
    cam1_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
    
    cam2_frame = create_right_panel(right_col, "Cam 2", "#e0e0e0", "black", "Image / result", 14)
    cam2_frame.grid(row=1, column=0, sticky="nsew", pady=5)
    
    res_frame = create_right_panel(right_col, "Test Result", "#1945d1", "white", "PASS", 60, True)
    res_frame.grid(row=2, column=0, sticky="nsew", pady=(5, 0))

    root.mainloop()

if __name__ == "__main__":
    main()
