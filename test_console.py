import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("Feeder Cable Tester ver. V0.02.33.1")
    root.geometry("1280x800")
    root.configure(bg="black")

    style = ttk.Style()
    style.theme_use("clam")
    
    # Common colors
    bg_color = "black"
    fg_color = "white"
    
    style.configure("TLabelframe", background=bg_color, foreground=fg_color, bordercolor="white")
    style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color, font=('Arial', 10))
    style.configure("TLabel", background=bg_color, foreground=fg_color, font=('Arial', 9))
    style.configure("TButton", background="black", foreground=fg_color, font=('Arial', 9, 'bold'), bordercolor="white")
    
    # Treeview style
    style.configure("Treeview.Heading", background="white", foreground="black", font=('Arial', 9, 'bold'))
    style.configure("Treeview", background="white", foreground="black", fieldbackground="white", font=('Arial', 9), rowheight=25)
    
    # ------------------ TOP HEADER ------------------
    header_frame = tk.Frame(root, bg="black", height=40)
    header_frame.pack(side="top", fill="x")
    
    # INFAC logo box
    logo_frame = tk.Frame(header_frame, bg="white", padx=5, pady=2)
    logo_frame.pack(side="left", padx=10, pady=5)
    
    tk.Label(logo_frame, text="INFAC", fg="#c00000", bg="white", font=('Arial', 18, 'bold')).pack(side="left")
    tk.Label(logo_frame, text="주식회사인팩", fg="black", bg="white", font=('Malgun Gothic', 10)).pack(side="left", padx=(5,0))
    
    tk.Label(header_frame, text="Feeder Cable", fg="#ffaa00", bg="black", font=('Arial', 14, 'bold')).pack(side="left", padx=20)

    # ------------------ MAIN LAYOUT ------------------
    main_frame = tk.Frame(root, bg="black")
    main_frame.pack(fill="both", expand=True, padx=5, pady=5)
    
    # Left Sidebar (Buttons)
    left_sidebar = tk.Frame(main_frame, bg="black", width=80)
    left_sidebar.pack(side="left", fill="y", padx=(0, 5))
    
    def create_sidebar_btn(parent, text, bg="black", fg="white", height=2):
        return tk.Button(parent, text=text, bg=bg, fg=fg, font=('Arial', 9, 'bold'), height=height, width=8, relief="solid", bd=1, highlightbackground="white")
        
    create_sidebar_btn(left_sidebar, "USER").pack(pady=2)
    tk.Frame(left_sidebar, height=20, bg="black").pack() # Spacer
    create_sidebar_btn(left_sidebar, "START").pack(pady=2)
    create_sidebar_btn(left_sidebar, "STOP").pack(pady=2)
    tk.Frame(left_sidebar, height=20, bg="black").pack() # Spacer
    
    # The image shows empty space, then smaller buttons for LABEL, MASTER, TEST, RESULT, Form Loadi
    create_sidebar_btn(left_sidebar, "LABEL").pack(pady=2)
    create_sidebar_btn(left_sidebar, "MASTE\nR").pack(pady=2)
    create_sidebar_btn(left_sidebar, "TEST").pack(pady=2)
    create_sidebar_btn(left_sidebar, "RESULT").pack(pady=2)
    create_sidebar_btn(left_sidebar, "Form\nLoadi", bg="#4caf50", fg="black").pack(pady=2)

    # Right Content Area
    right_content = tk.Frame(main_frame, bg="black")
    right_content.pack(side="left", fill="both", expand=True)
    
    # --- Top Info Section ---
    top_info_frame = tk.Frame(right_content, bg="black")
    top_info_frame.pack(fill="x", pady=(0, 5))
    
    def create_entry(parent, width, val=""):
        e = tk.Entry(parent, width=width, bg="black", fg="white", font=('Arial', 10), insertbackground="white")
        e.insert(0, val)
        return e

    # 1. Product Info
    product_frame = ttk.LabelFrame(top_info_frame, text="Product Info")
    product_frame.grid(row=0, column=0, rowspan=2, padx=(0,2), pady=0, sticky="nsew")
    
    tk.Label(product_frame, text="Product No", bg="black", fg="white").grid(row=0, column=0, sticky="ew", padx=2, pady=2)
    create_entry(product_frame, 20, "96230-K6510").grid(row=0, column=1, columnspan=3, sticky="ew", padx=2)
    tk.Label(product_frame, bg="black", text="v", fg="black", width=2).grid(row=0, column=3, sticky="e", padx=2)
    
    tk.Label(product_frame, text="ProductNa", bg="black", fg="white").grid(row=1, column=0, sticky="ew", padx=2, pady=2)
    create_entry(product_frame, 15).grid(row=1, column=1, sticky="ew", padx=2)
    tk.Label(product_frame, text="FLOOR", bg="black", fg="white").grid(row=1, column=2, sticky="ew", padx=2)
    create_entry(product_frame, 8).grid(row=1, column=3, sticky="ew", padx=2)
    tk.Label(product_frame, text="Car", bg="black", fg="white").grid(row=1, column=4, sticky="ew", padx=2)
    create_entry(product_frame, 5, "AI3").grid(row=1, column=5, sticky="ew", padx=2)

    tk.Label(product_frame, text="ALC code", bg="black", fg="white").grid(row=2, column=0, sticky="ew", padx=2, pady=2)
    create_entry(product_frame, 6, "K65").grid(row=2, column=1, sticky="ew", padx=2)
    tk.Label(product_frame, text="LOT", bg="black", fg="white").grid(row=2, column=2, sticky="ew", padx=2)
    create_entry(product_frame, 5, "HL").grid(row=2, column=3, sticky="ew", padx=2)
    tk.Label(product_frame, text="Serial", bg="black", fg="white").grid(row=2, column=4, sticky="ew", padx=2)
    create_entry(product_frame, 6, "0062").grid(row=2, column=5, sticky="ew", padx=2)

    tk.Label(product_frame, text="Barcode Scan(ALC check)", bg="black", fg="white").grid(row=3, column=0, sticky="ew", padx=2, pady=5)
    create_entry(product_frame, 30).grid(row=3, column=1, columnspan=5, sticky="ew", padx=2)


    # 2. Assistant Info
    product_frame.columnconfigure(1, weight=1)
    product_frame.columnconfigure(3, weight=1)
    product_frame.columnconfigure(5, weight=1)
    assistant_frame = ttk.LabelFrame(top_info_frame, text="Assistant Info")
    assistant_frame.grid(row=0, column=1, padx=2, pady=0, sticky="nsew")
    
    top_asst = tk.Frame(assistant_frame, bg="black")
    top_asst.pack(fill="x", pady=2)
    tk.Checkbutton(top_asst, text="Label print", bg="#76ff03", fg="black", selectcolor="#76ff03", font=('Arial', 9, 'bold')).pack(side="left", padx=5)
    tk.Button(top_asst, text="Reprint", bg="black", fg="white", relief="solid", bd=1).pack(side="left", padx=5)
    
    mid_asst = tk.Frame(assistant_frame, bg="black")
    mid_asst.pack(fill="x", pady=2)
    tk.Label(mid_asst, text="Master", bg="black", fg="white").pack(side="left", padx=2)
    create_entry(mid_asst, 4, "1").pack(side="left", padx=2)
    tk.Label(mid_asst, text="JIG No", bg="black", fg="white").pack(side="left", padx=10)
    create_entry(mid_asst, 4, "6").pack(side="left", padx=2)
    
    bot_asst = tk.Frame(assistant_frame, bg="black")
    bot_asst.pack(fill="x", pady=2)
    tk.Checkbutton(bot_asst, text="NG Box", bg="#76ff03", fg="black", selectcolor="#76ff03", font=('Arial', 9, 'bold')).pack(side="left", padx=40)

    # 3. Method
    method_frame = ttk.LabelFrame(top_info_frame, text="Method")
    method_frame.grid(row=1, column=1, padx=2, pady=0, sticky="nsew")
    
    tk.Radiobutton(method_frame, text="Single", bg="#76ff03", fg="black", selectcolor="#76ff03", font=('Arial', 9, 'bold')).pack(side="left", padx=5, pady=5)
    tk.Button(method_frame, text="Retest", bg="black", fg="white", relief="solid", bd=1).pack(side="left", padx=5)
    tk.Label(method_frame, text="0 / 0", bg="black", fg="white").pack(side="left", padx=15)

    # 4. Worker Inspect & Count
    right_top_frame = tk.Frame(top_info_frame, bg="black")
    right_top_frame.grid(row=0, column=2, rowspan=2, padx=2, pady=0, sticky="nsew")
    
    worker_frame = ttk.LabelFrame(right_top_frame, text="Worker Inspect")
    worker_frame.columnconfigure(1, weight=1)
    worker_frame.columnconfigure(2, weight=1)
    worker_frame.pack(fill="x", pady=(0, 2))
    
    tk.Label(worker_frame, text="CLIENT", bg="black", fg="white").grid(row=0, column=1, padx=20)
    tk.Label(worker_frame, text="WORKER", bg="black", fg="white").grid(row=0, column=2, padx=20)
    tk.Label(worker_frame, text="Now", bg="black", fg="white").grid(row=1, column=0, padx=5)
    create_entry(worker_frame, 12, "2026-08-12").grid(row=1, column=1, padx=5, pady=2)
    create_entry(worker_frame, 10, "11:00:10").grid(row=1, column=2, padx=5, pady=2)
    
    count_frame = ttk.LabelFrame(right_top_frame, text="Count")
    count_frame.columnconfigure(1, weight=1)
    count_frame.columnconfigure(3, weight=1)
    count_frame.pack(fill="x")
    
    tk.Label(count_frame, text="Total", bg="black", fg="white").grid(row=0, column=0, padx=10, pady=2)
    create_entry(count_frame, 5, "64").grid(row=0, column=1, padx=5)
    tk.Label(count_frame, text="NG", bg="black", fg="white").grid(row=0, column=2, padx=10)
    e1 = create_entry(count_frame, 5, "2")
    e1.config(fg="red")
    e1.grid(row=0, column=3, padx=5)
    
    tk.Label(count_frame, text="OK", bg="black", fg="white").grid(row=1, column=0, padx=10, pady=2)
    e2 = create_entry(count_frame, 5, "62")
    e2.config(fg="#76ff03")
    e2.grid(row=1, column=1, padx=5)
    tk.Label(count_frame, text="NG", bg="black", fg="white").grid(row=1, column=2, padx=10)
    e3 = create_entry(count_frame, 5, "3.13")
    e3.config(fg="red")
    e3.grid(row=1, column=3, padx=5)
    
    top_info_frame.columnconfigure(0, weight=1)
    top_info_frame.columnconfigure(1, weight=1)
    top_info_frame.columnconfigure(2, weight=1)

    # --- Inspection Section ---
    inspect_frame = tk.Frame(right_content, bg="black")
    inspect_frame.pack(fill="x", pady=2)
    
    lbl_inspect = tk.Label(inspect_frame, text="Inspecti", bg="black", fg="white", font=('Arial', 12, 'bold'), anchor="w")
    lbl_inspect.pack(fill="x")
    
    inspect_mid = tk.Frame(inspect_frame, bg="black")
    inspect_mid.pack(fill="x")
    
    cols_insp = ("No", "Channel", "Type", "Freq(kHz/MHz)", "Volt(V)", "Sec(s)", "Min", "Max", "S")
    tree_insp = ttk.Treeview(inspect_mid, columns=cols_insp, show="headings", height=4)
    
    col_widths = [40, 70, 70, 100, 70, 70, 70, 70, 30]
    for i, col in enumerate(cols_insp):
        tree_insp.heading(col, text=col)
        tree_insp.column(col, width=col_widths[i], anchor="center")
    tree_insp.pack(side="left", fill="x", expand=True)
    
    tree_insp.tag_configure('cyan_row', background='#b2ebf2', foreground='black')
    tree_insp.tag_configure('white_row', background='white', foreground='black')
    
    tree_insp.insert("", "end", values=("1", "1", "Single", "", "", "", "", "", ""), tags=('white_row',))
    tree_insp.insert("", "end", values=("2", "1", "Single", "", "500", "1", "100", "9999", ""), tags=('cyan_row',))
    tree_insp.insert("", "end", values=("3", "1", "Single", "", "1000", "3", "0", "10", ""), tags=('white_row',))
    tree_insp.insert("", "end", values=("4", "1", "Single", "", "", "", "", "", ""), tags=('cyan_row',))

    # Test progress Info
    progress_frame = ttk.LabelFrame(inspect_mid, text="Test progress Info")
    progress_frame.pack(side="right", fill="y", padx=(5, 0))
    
    div_frame = tk.Frame(progress_frame, bg="#4caf50", padx=5, pady=5)
    div_frame.pack(fill="x", padx=2, pady=2)
    tk.Label(div_frame, text="Product Division", bg="#4caf50", fg="black", font=('Arial', 9)).pack(anchor="w")
    
    rd_frame = tk.Frame(div_frame, bg="#4caf50")
    rd_frame.pack(anchor="center", pady=5)
    
    tk.Radiobutton(rd_frame, text="Cable", bg="#4caf50", fg="black", selectcolor="white", value=1, font=('Arial', 10, 'bold')).pack(side="left", padx=5)
    tk.Radiobutton(rd_frame, text="Coil", bg="#4caf50", fg="white", selectcolor="black", value=2, font=('Arial', 10)).pack(side="left", padx=5)
    
    save_frame = tk.Frame(progress_frame, bg="black")
    save_frame.pack(fill="x", pady=2)
    tk.Label(save_frame, text="Saving test\nresults", bg="black", fg="white", font=('Arial', 11), justify="left").pack(side="left", padx=10, pady=5)
    
    test_time_frame = tk.Frame(save_frame, bg="black")
    test_time_frame.pack(side="right", padx=10)
    tk.Label(test_time_frame, text="Test", bg="black", fg="white").pack()
    tk.Label(test_time_frame, text="12.92 s", bg="black", fg="white", borderwidth=1, relief="solid", width=8, font=('Arial', 10)).pack()

    # --- Test Results Section ---
    test_res_frame = tk.Frame(right_content, bg="black")
    test_res_frame.pack(fill="both", expand=True, pady=2)
    
    lbl_test = tk.Label(test_res_frame, text="Test", bg="black", fg="white", font=('Arial', 12, 'bold'), anchor="w")
    lbl_test.pack(fill="x")
    
    test_mid = tk.Frame(test_res_frame, bg="black")
    test_mid.pack(fill="both", expand=True)
    
    cols_test = ("CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8", "CH9", "CH10", "Result")
    
    test_grid = tk.Frame(test_mid, bg="black")
    test_grid.pack(side="left", fill="both", expand=True)
    
    for i, col in enumerate(cols_test):
        tk.Label(test_grid, text=col, bg="white", fg="black", borderwidth=1, relief="solid", font=('Arial', 10), width=6).grid(row=0, column=i, sticky="nsew")
        
    for r, vals in enumerate([
        ("OK", "-", "-", "-", "-", "-", "-", "-", "-", "-", "PASS"),
        ("1297", "-", "-", "-", "-", "-", "-", "-", "-", "-", "PASS"),
        ("0.33", "-", "-", "-", "-", "-", "-", "-", "-", "-", "PASS"),
        ("OK", "-", "-", "-", "-", "-", "-", "-", "-", "-", "PASS")
    ]):
        for c, val in enumerate(vals):
            bg_c = "#aeea00" if c == 0 or c == 10 else "white"
            font_w = ('Arial', 10, 'bold') if c == 0 or c == 10 else ('Arial', 10)
            tk.Label(test_grid, text=val, bg=bg_c, fg="black", borderwidth=1, relief="solid", font=font_w).grid(row=r+1, column=c, sticky="nsew")
            
    for i in range(11):
        test_grid.columnconfigure(i, weight=1)
    for i in range(5):
        test_grid.rowconfigure(i, weight=1)

    # Big PASS Box
    pass_lbl = tk.Label(test_mid, text="PASS", bg="#1945d1", fg="white", font=('Arial', 60, 'bold'), width=6)
    pass_lbl.pack(side="right", fill="both", expand=True, padx=(5, 0))

    # --- Bottom Log & Status Section ---
    bottom_section = tk.Frame(right_content, bg="black", height=80)
    bottom_section.pack(fill="x", pady=2)
    bottom_section.pack_propagate(False)
    
    # Receive IO
    io_frame = ttk.LabelFrame(bottom_section, text="Receive IO Cable Data")
    io_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
    
    io_layout = tk.Frame(io_frame, bg="black")
    io_layout.columnconfigure(0, weight=1)
    io_layout.pack(fill="both", expand=True, padx=2, pady=2)
    
    left_io = tk.Frame(io_layout, bg="black")
    left_io.columnconfigure(1, weight=1)
    left_io.grid(row=0, column=0, rowspan=2, sticky="nsew")
    
    tk.Label(left_io, text="SP4", bg="black", fg="white", font=('Arial', 7), borderwidth=1, relief="solid", width=4).grid(row=0, column=0, pady=1)
    tk.Entry(left_io, bg="black", fg="white", font=('Arial', 7), borderwidth=1, relief="solid", width=15).grid(row=0, column=1, pady=1)
    
    tk.Label(left_io, text="SB8", bg="black", fg="white", font=('Arial', 7), borderwidth=1, relief="solid", width=4).grid(row=1, column=0, pady=1)
    tk.Entry(left_io, bg="black", fg="white", font=('Arial', 7), borderwidth=1, relief="solid", width=15).grid(row=1, column=1, pady=1)
    
    tk.Label(io_layout, text="MPU", bg="black", fg="white", font=('Arial', 8, 'bold')).grid(row=0, column=1, rowspan=2, padx=15)
    
    ch_top = tk.Frame(io_layout, bg="black")
    ch_top.grid(row=0, column=2, sticky="sw")
    ch_bot = tk.Frame(io_layout, bg="black")
    ch_bot.grid(row=1, column=2, sticky="nw")
    
    for i in range(1, 11):
        tk.Label(ch_top, text=f"CH{i}", bg="#222", fg="white", borderwidth=1, relief="solid", width=3, font=('Arial', 7)).pack(side="left")
        tk.Label(ch_bot, text=f"CH{i}", bg="#222", fg="white", borderwidth=1, relief="solid", width=3, font=('Arial', 7)).pack(side="left")
        
    out_frame = tk.Frame(io_layout, bg="black")
    out_frame.grid(row=0, column=3, rowspan=2, padx=10, sticky="nsew")
    
    tk.Label(out_frame, text="OUTPUT", bg="black", fg="white", font=('Arial', 8, 'bold')).pack()
    rev_frame = tk.Frame(out_frame, bg="black")
    rev_frame.pack()
    tk.Label(rev_frame, text="Rev", bg="black", fg="white", font=('Arial', 7)).pack(side="left")
    tk.Label(rev_frame, text="S1./\nCG6 C's", bg="black", fg="white", font=('Arial', 7), justify="left").pack(side="left", padx=5)

    # COM Status
    com_frame = ttk.LabelFrame(bottom_section, text="COM Status")
    com_frame.pack(side="left", fill="y", padx=5)
    
    tk.Label(com_frame, text="HOST", bg="#76ff03", fg="black", width=5, font=('Arial', 7, 'bold')).grid(row=0, column=0, padx=1, pady=1)
    tk.Label(com_frame, text="LCR", bg="#555", fg="white", width=5, font=('Arial', 7)).grid(row=0, column=1, padx=1, pady=1)
    tk.Label(com_frame, text="RELAY", bg="#555", fg="white", width=5, font=('Arial', 7)).grid(row=0, column=2, padx=1, pady=1)
    tk.Label(com_frame, text="IO", bg="#76ff03", fg="black", width=5, font=('Arial', 7, 'bold')).grid(row=1, column=0, padx=1, pady=1)
    tk.Label(com_frame, text="R/MPU", bg="#76ff03", fg="black", width=5, font=('Arial', 7, 'bold')).grid(row=1, column=1, padx=1, pady=1)
    tk.Label(com_frame, text="SCANNE", bg="#555", fg="white", width=6, font=('Arial', 7)).grid(row=1, column=2, padx=1, pady=1)

    # Log
    log_frame = ttk.LabelFrame(bottom_section, text="Log")
    log_frame.pack(side="left", fill="y", padx=(5, 0))
    log_text = tk.Text(log_frame, bg="black", fg="white", font=('Arial', 8), borderwidth=0, width=25)
    log_text.pack(fill="both", expand=True)
    log_text.insert("end", ")\n11:00:06.916> function\nname=Connect\n11:00:08.596> Quit\n(0)=Normal")

    root.mainloop()

if __name__ == "__main__":
    main()
