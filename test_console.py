import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("Feeder Cable Tester")
    root.geometry("1280x800")
    root.configure(bg="#2d2d2d")

    # Styles
    style = ttk.Style()
    style.theme_use("clam")
    
    # Common colors
    bg_color = "#1e1e1e"
    fg_color = "#e0e0e0"
    border_color = "#555555"

    style.configure("TFrame", background=bg_color)
    style.configure("TLabelframe", background=bg_color, foreground=fg_color, bordercolor=border_color)
    style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color, font=('Arial', 9))
    style.configure("TLabel", background=bg_color, foreground=fg_color, font=('Arial', 9))
    style.configure("TButton", background="#333333", foreground=fg_color, font=('Arial', 9, 'bold'))
    
    # Treeview style
    style.configure("Treeview.Heading", background="#444444", foreground="white", font=('Arial', 9, 'bold'))
    style.configure("Treeview", background="#eeeeee", foreground="black", fieldbackground="#eeeeee", font=('Arial', 9), rowheight=25)
    
    # ------------------ TOP HEADER ------------------
    header_frame = tk.Frame(root, bg="#2a3b4c", height=40)
    header_frame.pack(side="top", fill="x")
    header_frame.pack_propagate(False)
    
    lbl_title_infac1 = tk.Label(header_frame, text="INFAC", fg="red", bg="#2a3b4c", font=('Arial', 14, 'bold'))
    lbl_title_infac1.pack(side="left", padx=(10, 0), pady=5)
    lbl_title_infac2 = tk.Label(header_frame, text="주식회사인팩", fg="white", bg="#2a3b4c", font=('Arial', 10))
    lbl_title_infac2.pack(side="left", padx=(0, 20), pady=5)
    
    lbl_title_cable = tk.Label(header_frame, text="Feeder Cable", fg="#ffaa00", bg="#2a3b4c", font=('Arial', 12, 'bold'))
    lbl_title_cable.pack(side="left", padx=20)

    # ------------------ MAIN LAYOUT ------------------
    main_frame = tk.Frame(root, bg=bg_color)
    main_frame.pack(fill="both", expand=True, padx=5, pady=5)
    
    # Left Sidebar (Buttons)
    left_sidebar = tk.Frame(main_frame, bg=bg_color, width=80)
    left_sidebar.pack(side="left", fill="y", padx=(0, 5))
    
    btn_opts = {"bg": "#333333", "fg": "white", "font": ('Arial', 9, 'bold'), "height": 2, "width": 8, "relief": "ridge", "bd": 2}
    
    tk.Button(left_sidebar, text="USER", **btn_opts).pack(pady=2)
    tk.Frame(left_sidebar, height=50, bg=bg_color).pack() # Spacer
    tk.Button(left_sidebar, text="START", bg="#333333", fg="cyan", font=('Arial', 9, 'bold'), height=2, width=8, relief="ridge", bd=2).pack(pady=2)
    tk.Button(left_sidebar, text="STOP", bg="#333333", fg="white", font=('Arial', 9, 'bold'), height=2, width=8, relief="ridge", bd=2).pack(pady=2)
    tk.Frame(left_sidebar, height=20, bg=bg_color).pack() # Spacer
    tk.Button(left_sidebar, text="LABEL", **btn_opts).pack(pady=2)
    tk.Button(left_sidebar, text="MASTE\nR", **btn_opts).pack(pady=2)
    tk.Button(left_sidebar, text="TEST", **btn_opts).pack(pady=2)
    tk.Button(left_sidebar, text="RESULT", **btn_opts).pack(pady=2)
    tk.Button(left_sidebar, text="Form\nLoadi", bg="#4caf50", fg="black", font=('Arial', 9, 'bold'), height=2, width=8, relief="ridge", bd=2).pack(pady=2)

    # Right Content Area
    right_content = tk.Frame(main_frame, bg=bg_color)
    right_content.pack(side="left", fill="both", expand=True)
    
    # --- Top Info Section ---
    top_info_frame = tk.Frame(right_content, bg=bg_color)
    top_info_frame.pack(fill="x", pady=(0, 5))
    
    # 1. Product Info
    product_frame = ttk.LabelFrame(top_info_frame, text="Product Info")
    product_frame.grid(row=0, column=0, rowspan=2, padx=2, pady=2, sticky="nsew")
    
    ttk.Label(product_frame, text="Product No").grid(row=0, column=0, sticky="w", padx=5, pady=2)
    tk.Entry(product_frame, width=20, bg="#555", fg="white").grid(row=0, column=1, columnspan=3, sticky="w", padx=5)
    
    ttk.Label(product_frame, text="ProductNa").grid(row=1, column=0, sticky="w", padx=5, pady=2)
    tk.Entry(product_frame, width=15, bg="#555", fg="white").grid(row=1, column=1, sticky="w", padx=5)
    ttk.Label(product_frame, text="Car").grid(row=1, column=2, sticky="w", padx=5)
    tk.Entry(product_frame, width=6, bg="#555", fg="white").grid(row=1, column=3, sticky="w", padx=5)

    ttk.Label(product_frame, text="ALC code").grid(row=2, column=0, sticky="w", padx=5, pady=2)
    tk.Entry(product_frame, width=6, bg="#555", fg="white").grid(row=2, column=1, sticky="w", padx=5)
    ttk.Label(product_frame, text="LOT").grid(row=2, column=2, sticky="w", padx=5)
    
    alc_frame = tk.Frame(product_frame, bg=bg_color)
    alc_frame.grid(row=2, column=1, columnspan=3, sticky="w", padx=5)
    tk.Entry(alc_frame, width=5, bg="#555", fg="white").pack(side="left") 
    ttk.Label(alc_frame, text=" LOT ").pack(side="left")
    tk.Entry(alc_frame, width=5, bg="#555", fg="white").pack(side="left") 
    ttk.Label(alc_frame, text=" Serial ").pack(side="left")
    tk.Entry(alc_frame, width=6, bg="#555", fg="white").pack(side="left")

    ttk.Label(product_frame, text="Barcode Scan(ALC check)").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    tk.Entry(product_frame, width=25, bg="#555", fg="white").grid(row=3, column=1, columnspan=3, sticky="w", padx=5)


    # 2. Assistant Info
    assistant_frame = ttk.LabelFrame(top_info_frame, text="Assistant Info")
    assistant_frame.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
    
    ttk.Label(assistant_frame, text="Label print", background="#8bc34a", foreground="black").grid(row=0, column=0, padx=5, pady=5)
    ttk.Button(assistant_frame, text="Reprint").grid(row=0, column=1, padx=5)
    
    tk.Label(assistant_frame, text="Master", bg=bg_color, fg=fg_color).grid(row=1, column=0, sticky="e")
    tk.Entry(assistant_frame, width=4, bg="#555", fg="white").grid(row=1, column=1, sticky="w")
    tk.Label(assistant_frame, text="JIG No", bg=bg_color, fg=fg_color).grid(row=1, column=2, sticky="e")
    tk.Entry(assistant_frame, width=4, bg="#555", fg="white").grid(row=1, column=3, sticky="w")
    
    tk.Checkbutton(assistant_frame, text="NG Box", bg="#8bc34a", fg="black", selectcolor="#8bc34a").grid(row=2, column=0, columnspan=2, pady=5)

    # 3. Method
    method_frame = ttk.LabelFrame(top_info_frame, text="Method")
    method_frame.grid(row=1, column=1, padx=2, pady=2, sticky="nsew")
    
    tk.Radiobutton(method_frame, text="Single", bg=bg_color, fg="#8bc34a", selectcolor=bg_color).grid(row=0, column=0, padx=5, pady=5)
    tk.Radiobutton(method_frame, text="Retest", bg=bg_color, fg=fg_color, selectcolor=bg_color).grid(row=0, column=1, padx=5, pady=5)
    tk.Label(method_frame, text="0 / 0", bg=bg_color, fg=fg_color).grid(row=0, column=2, padx=5)

    # 4. Worker Inspect & Count
    right_top_frame = tk.Frame(top_info_frame, bg=bg_color)
    right_top_frame.grid(row=0, column=2, rowspan=2, padx=2, pady=2, sticky="nsew")
    
    worker_frame = ttk.LabelFrame(right_top_frame, text="Worker Inspect")
    worker_frame.pack(fill="x", pady=(0, 2))
    
    tk.Label(worker_frame, text="CLIENT", bg=bg_color, fg=fg_color).grid(row=0, column=1, padx=10)
    tk.Label(worker_frame, text="WORKER", bg=bg_color, fg=fg_color).grid(row=0, column=2, padx=10)
    tk.Label(worker_frame, text="Now", bg=bg_color, fg=fg_color).grid(row=1, column=0, padx=5)
    tk.Label(worker_frame, text="2026-08-12", bg=bg_color, fg=fg_color).grid(row=1, column=1)
    tk.Label(worker_frame, text="11:00:10", bg=bg_color, fg=fg_color).grid(row=1, column=2)
    
    count_frame = ttk.LabelFrame(right_top_frame, text="Count")
    count_frame.pack(fill="x")
    
    tk.Label(count_frame, text="Total", bg=bg_color, fg=fg_color).grid(row=0, column=0, padx=5, pady=2)
    tk.Label(count_frame, text="64", bg=bg_color, fg="cyan").grid(row=0, column=1, padx=15)
    tk.Label(count_frame, text="NG", bg=bg_color, fg=fg_color).grid(row=0, column=2, padx=5)
    tk.Label(count_frame, text="2", bg=bg_color, fg="red").grid(row=0, column=3, padx=15)
    
    tk.Label(count_frame, text="OK", bg=bg_color, fg=fg_color).grid(row=1, column=0, padx=5, pady=2)
    tk.Label(count_frame, text="62", bg=bg_color, fg="#8bc34a").grid(row=1, column=1, padx=15)
    tk.Label(count_frame, text="NG", bg=bg_color, fg=fg_color).grid(row=1, column=2, padx=5)
    tk.Label(count_frame, text="3.13", bg=bg_color, fg="red").grid(row=1, column=3, padx=15)

    top_info_frame.columnconfigure(0, weight=2)
    top_info_frame.columnconfigure(1, weight=1)
    top_info_frame.columnconfigure(2, weight=1)

    # --- Inspection Section ---
    inspect_frame = tk.Frame(right_content, bg=bg_color)
    inspect_frame.pack(fill="x", pady=5)
    
    lbl_inspect = tk.Label(inspect_frame, text="Inspecti", bg="#333", fg="white", font=('Arial', 10, 'bold'), anchor="w")
    lbl_inspect.pack(fill="x")
    
    inspect_mid = tk.Frame(inspect_frame, bg=bg_color)
    inspect_mid.pack(fill="x")
    
    cols_insp = ("No", "Channel", "Type", "Freq(kHz/MHz)", "Volt(V)", "Sec(s)", "Min", "Max", "S")
    tree_insp = ttk.Treeview(inspect_mid, columns=cols_insp, show="headings", height=5)
    
    col_widths = [30, 60, 60, 100, 60, 50, 50, 50, 30]
    for i, col in enumerate(cols_insp):
        tree_insp.heading(col, text=col)
        tree_insp.column(col, width=col_widths[i], anchor="center")
    tree_insp.pack(side="left", fill="x", expand=True)
    
    tree_insp.tag_configure('green_row', background='#b2dfdb', foreground='black')
    
    tree_insp.insert("", "end", values=("1", "1", "Single", "", "", "", "", "", ""))
    tree_insp.insert("", "end", values=("2", "1", "Single", "", "500", "1", "100", "9999", ""), tags=('green_row',))
    tree_insp.insert("", "end", values=("3", "1", "Single", "", "1000", "3", "0", "10", ""), tags=('green_row',))
    tree_insp.insert("", "end", values=("4", "1", "Single", "", "", "", "", "", ""), tags=('green_row',))

    # Test progress Info
    progress_frame = ttk.LabelFrame(inspect_mid, text="Test progress Info")
    progress_frame.pack(side="right", fill="y", padx=(5, 0))
    
    div_frame = tk.Frame(progress_frame, bg="#8bc34a", padx=5, pady=5)
    div_frame.pack(fill="x", padx=2, pady=2)
    tk.Label(div_frame, text="Product Division", bg="#8bc34a", fg="black", font=('Arial', 9, 'bold')).pack(anchor="w")
    tk.Radiobutton(div_frame, text="Cable", bg="#8bc34a", fg="black", selectcolor="#8bc34a", value=1).pack(side="left")
    tk.Radiobutton(div_frame, text="Coil", bg="#8bc34a", fg="black", selectcolor="#8bc34a", value=2).pack(side="left")
    
    save_frame = tk.Frame(progress_frame, bg=bg_color)
    save_frame.pack(fill="x", pady=5)
    tk.Button(save_frame, text="Saving test\nresults", bg="#333", fg="white", font=('Arial', 9, 'bold'), width=12).pack(side="left", padx=5)
    
    test_time_frame = tk.Frame(save_frame, bg=bg_color)
    test_time_frame.pack(side="left", padx=5)
    tk.Label(test_time_frame, text="Test", bg=bg_color, fg=fg_color).pack()
    tk.Label(test_time_frame, text="12.92 s", bg="#222", fg="white", borderwidth=1, relief="sunken", width=8).pack()


    # --- Test Results Section ---
    test_res_frame = tk.Frame(right_content, bg=bg_color)
    test_res_frame.pack(fill="both", expand=True, pady=5)
    
    lbl_test = tk.Label(test_res_frame, text="Test", bg="#333", fg="white", font=('Arial', 10, 'bold'), anchor="w")
    lbl_test.pack(fill="x")
    
    test_mid = tk.Frame(test_res_frame, bg=bg_color)
    test_mid.pack(fill="both", expand=True)
    
    cols_test = ("CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8", "CH9", "CH10", "Resul")
    tree_test = ttk.Treeview(test_mid, columns=cols_test, show="headings", height=8)
    for col in cols_test:
        tree_test.heading(col, text=col)
        tree_test.column(col, width=45, anchor="center")
    tree_test.pack(side="left", fill="both", expand=True)
    
    tree_test.tag_configure('normal', background='#eeeeee', foreground='black')
    
    tree_test.insert("", "end", values=("OK", "-", "-", "-", "-", "-", "-", "-", "-", "-", "PASS"), tags=('normal',))
    tree_test.insert("", "end", values=("1297", "-", "-", "-", "-", "-", "-", "-", "-", "-", "PASS"), tags=('normal',))
    tree_test.insert("", "end", values=("0.33", "-", "-", "-", "-", "-", "-", "-", "-", "-", "PASS"), tags=('normal',))
    tree_test.insert("", "end", values=("OK", "-", "-", "-", "-", "-", "-", "-", "-", "-", "PASS"), tags=('normal',))

    # Big PASS Box
    pass_lbl = tk.Label(test_mid, text="PASS", bg="#1945d1", fg="white", font=('Arial', 48, 'bold'), width=8)
    pass_lbl.pack(side="right", fill="both", expand=True, padx=(5, 0))

    # --- Bottom Log & Status Section ---
    bottom_section = tk.Frame(right_content, bg=bg_color, height=100)
    bottom_section.pack(fill="x", pady=5)
    bottom_section.pack_propagate(False)
    
    # Receive IO
    io_frame = ttk.LabelFrame(bottom_section, text="Receive IO Cable Data")
    io_frame.pack(side="left", fill="y", padx=(0, 5))
    
    io_top = tk.Frame(io_frame, bg=bg_color)
    io_top.pack(fill="x")
    tk.Label(io_top, text="STA", bg=bg_color, fg=fg_color).pack(side="left")
    tk.Entry(io_top, width=5, bg="#333", fg="white").pack(side="left", padx=2)
    tk.Label(io_top, text="Con", bg=bg_color, fg=fg_color).pack(side="left", padx=2)
    tk.Entry(io_top, width=5, bg="#333", fg="white").pack(side="left", padx=2)
    tk.Label(io_top, text="INPU", bg=bg_color, fg=fg_color).pack(side="left", padx=10)
    tk.Label(io_top, text="OUTPUT", bg=bg_color, fg=fg_color).pack(side="right", padx=10)
    
    io_channels = tk.Frame(io_frame, bg=bg_color)
    io_channels.pack(fill="x", pady=2)
    for i in range(1, 10):
        tk.Label(io_channels, text=f"CH{i}", bg="#222", fg="#888", borderwidth=1, relief="solid", width=3, font=('Arial', 7)).pack(side="left", padx=1)
        
    # COM Status
    com_frame = ttk.LabelFrame(bottom_section, text="COM Status")
    com_frame.pack(side="left", fill="y", padx=5)
    
    tk.Label(com_frame, text="HIPOT", bg="#8bc34a", fg="black", width=6).grid(row=0, column=0, padx=2, pady=2)
    tk.Label(com_frame, text="LCR", bg="#555", fg="white", width=6).grid(row=0, column=1, padx=2, pady=2)
    tk.Label(com_frame, text="Rever", bg="#555", fg="white", width=6).grid(row=0, column=2, padx=2, pady=2)
    tk.Label(com_frame, text="IO", bg="#8bc34a", fg="black", width=6).grid(row=1, column=0, padx=2, pady=2)
    tk.Label(com_frame, text="Printe", bg="#8bc34a", fg="black", width=6).grid(row=1, column=1, padx=2, pady=2)
    tk.Label(com_frame, text="Scane", bg="#555", fg="white", width=6).grid(row=1, column=2, padx=2, pady=2)

    # Log
    log_frame = ttk.LabelFrame(bottom_section, text="Log")
    log_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))
    log_text = tk.Text(log_frame, bg="#222", fg="white", height=4, font=('Arial', 8))
    log_text.pack(fill="both", expand=True)
    log_text.insert("end", ")\n11:00:06.916> function\nname=Connect\n11:00:08.596> Quit\n(0)=Normal")

    root.mainloop()

if __name__ == "__main__":
    main()
