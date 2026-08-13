import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("Feeder Cable Tester ver. V0.02.33.1")
    root.geometry("1350x860")
    root.configure(bg="black")
    root.resizable(True, True)

    style = ttk.Style()
    style.theme_use("clam")

    bg = "black"
    style.configure("TLabelframe", background=bg, foreground="white", bordercolor="#555")
    style.configure("TLabelframe.Label", background=bg, foreground="white", font=('Arial', 10))
    style.configure("Treeview.Heading", background="#d0d0d0", foreground="black", font=('Arial', 9, 'bold'))
    style.configure("Treeview", background="white", foreground="black", fieldbackground="white", font=('Arial', 9), rowheight=28)

    # ==================== HEADER ====================
    header = tk.Frame(root, bg="black", height=45)
    header.pack(fill="x")
    header.pack_propagate(False)

    logo_box = tk.Frame(header, bg="white", padx=6, pady=3)
    logo_box.pack(side="left", padx=10, pady=6)
    tk.Label(logo_box, text="INFAC", fg="#c00000", bg="white", font=('Arial', 16, 'bold')).pack(side="left")
    tk.Label(logo_box, text=" 주식회사인팩", fg="black", bg="white", font=('Malgun Gothic', 9)).pack(side="left")

    tk.Label(header, text="Feeder Cable", fg="#e8a000", bg="black", font=('Arial', 15, 'bold')).pack(side="left", padx=25)
    tk.Label(header, text="15/07/2025  15:05:07", fg="white", bg="black", font=('Arial', 10)).pack(side="right", padx=15)

    # ==================== BODY ====================
    body = tk.Frame(root, bg="black")
    body.pack(fill="both", expand=True)

    # --- Sidebar ---
    sidebar_w = 90
    sidebar = tk.Frame(body, bg="black", width=sidebar_w)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    sidebar_buttons = [
        ("👤", "Admin"),
        ("⚙", "Settings"),
        ("⚖", "Comparator"),
        ("📋", "Test Data"),
        ("🔧", "COM Setting"),
    ]
    for icon, text in sidebar_buttons:
        f = tk.Frame(sidebar, bg="#111", bd=1, relief="solid", highlightbackground="#444", highlightthickness=1)
        f.pack(fill="x", padx=4, pady=3)
        tk.Label(f, text=icon, bg="#111", fg="white", font=('Arial', 18)).pack(pady=(6, 0))
        tk.Label(f, text=text, bg="#111", fg="white", font=('Arial', 8)).pack(pady=(0, 6))

    # --- Main content area ---
    content = tk.Frame(body, bg="black")
    content.pack(side="left", fill="both", expand=True, padx=(5, 0))

    # Use grid: row0 = upper (left_area + right_panels), row1 = bottom bar
    content.rowconfigure(0, weight=1)
    content.rowconfigure(1, weight=0)
    content.columnconfigure(0, weight=1)

    upper = tk.Frame(content, bg="black")
    upper.grid(row=0, column=0, sticky="nsew")

    # Upper: left_area (Product/Inspect/Test/Scan) + right_panels (Cam1/Cam2/Result)
    upper.columnconfigure(0, weight=1)
    upper.columnconfigure(1, weight=0)  # fixed width right
    upper.rowconfigure(0, weight=1)

    left_area = tk.Frame(upper, bg="black")
    left_area.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

    right_panels = tk.Frame(upper, bg="black", width=220)
    right_panels.grid(row=0, column=1, sticky="nsew")
    right_panels.grid_propagate(False)
    right_panels.columnconfigure(0, weight=1)
    right_panels.rowconfigure(0, weight=3)
    right_panels.rowconfigure(1, weight=3)
    right_panels.rowconfigure(2, weight=2)

    # ==================== RIGHT PANELS ====================
    def make_cam_panel(parent, title):
        outer = tk.Frame(parent, bg="#555", padx=1, pady=1)
        inner = tk.Frame(outer, bg="black")
        inner.pack(fill="both", expand=True)
        tk.Label(inner, text=title, bg="black", fg="white", font=('Arial', 11, 'bold'), anchor="center").pack(fill="x", pady=(5, 0))
        content_lbl = tk.Label(inner, text="Image / result", bg="#d8d8d8", fg="#555", font=('Arial', 13), anchor="center")
        content_lbl.pack(fill="both", expand=True, padx=3, pady=(3, 3))
        return outer

    cam1 = make_cam_panel(right_panels, "Cam 1")
    cam1.grid(row=0, column=0, sticky="nsew", pady=(0, 3))

    cam2 = make_cam_panel(right_panels, "Cam 2")
    cam2.grid(row=1, column=0, sticky="nsew", pady=3)

    # Test Result panel
    tr_outer = tk.Frame(right_panels, bg="#555", padx=1, pady=1)
    tr_outer.grid(row=2, column=0, sticky="nsew", pady=(3, 0))
    tr_inner = tk.Frame(tr_outer, bg="black")
    tr_inner.pack(fill="both", expand=True)
    tk.Label(tr_inner, text="Test Result", bg="black", fg="white", font=('Arial', 11, 'bold'), anchor="center").pack(fill="x", pady=(5, 0))
    tk.Label(tr_inner, text="PASS", bg="#1945d1", fg="white", font=('Arial', 55, 'bold'), anchor="center").pack(fill="both", expand=True, padx=3, pady=(3, 3))

    # ==================== LEFT AREA ====================
    # --- Row 1: Product Info + Count/Method ---
    row1 = tk.Frame(left_area, bg="black")
    row1.pack(fill="x", pady=(0, 3))
    row1.columnconfigure(0, weight=3)
    row1.columnconfigure(1, weight=2)

    def mk_entry(parent, val="", fg_c="white", w=10):
        e = tk.Entry(parent, bg="black", fg=fg_c, font=('Arial', 11), insertbackground="white",
                     bd=1, relief="solid", width=w,
                     highlightbackground="#888", highlightcolor="#aaa", highlightthickness=1)
        if val:
            e.insert(0, val)
        return e

    # Product Info
    pf = ttk.LabelFrame(row1, text="Product Info")
    pf.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 5))
    pi = tk.Frame(pf, bg="black", padx=8, pady=5)
    pi.pack(fill="both", expand=True)
    for i in range(8):
        pi.columnconfigure(i, weight=1 if i % 2 != 0 else 0)

    # Row 0
    tk.Label(pi, text="Product No", bg="black", fg="white", font=('Arial', 10)).grid(row=0, column=0, sticky="w", pady=4)
    mk_entry(pi, "96220 06250", w=20).grid(row=0, column=1, columnspan=5, sticky="ew", padx=5)
    tk.Label(pi, text="EMP ID", bg="black", fg="white", font=('Arial', 10)).grid(row=0, column=6, sticky="w", padx=(10, 5))
    mk_entry(pi, "", w=8).grid(row=0, column=7, sticky="ew", padx=(0, 5))

    # Row 1
    tk.Label(pi, text="ProductNa", bg="black", fg="white", font=('Arial', 10)).grid(row=1, column=0, sticky="w", pady=4)
    mk_entry(pi, "SP2I", w=12).grid(row=1, column=1, columnspan=3, sticky="ew", padx=5)
    tk.Label(pi, text="Car", bg="black", fg="white", font=('Arial', 10)).grid(row=1, column=4, sticky="w", padx=(10, 5))
    mk_entry(pi, "MAI", w=6).grid(row=1, column=5, sticky="ew", padx=5)

    # Row 2
    tk.Label(pi, text="ALC code", bg="black", fg="white", font=('Arial', 10)).grid(row=2, column=0, sticky="w", pady=4)
    mk_entry(pi, "P96", w=5).grid(row=2, column=1, sticky="ew", padx=5)
    tk.Label(pi, text="LOT", bg="black", fg="white", font=('Arial', 10)).grid(row=2, column=2, sticky="w", padx=(10, 5))
    mk_entry(pi, "", w=5).grid(row=2, column=3, sticky="ew", padx=5)
    tk.Label(pi, text="PCI", bg="black", fg="white", font=('Arial', 10)).grid(row=2, column=4, sticky="w", padx=(10, 5))
    mk_entry(pi, "", w=5).grid(row=2, column=5, sticky="ew", padx=5)
    tk.Label(pi, text="Serial", bg="black", fg="white", font=('Arial', 10)).grid(row=2, column=6, sticky="w", padx=(10, 5))
    mk_entry(pi, "0229", w=6).grid(row=2, column=7, sticky="ew", padx=(0, 5))

    # Count
    cf = ttk.LabelFrame(row1, text="Count")
    cf.grid(row=0, column=1, sticky="nsew", pady=(0, 2))
    ci = tk.Frame(cf, bg="black", padx=8, pady=5)
    ci.pack(fill="both", expand=True)
    ci.columnconfigure(1, weight=1)
    ci.columnconfigure(3, weight=1)

    tk.Label(ci, text="Total", bg="black", fg="white", font=('Arial', 10)).grid(row=0, column=0, sticky="w", pady=3)
    mk_entry(ci, "235", w=6).grid(row=0, column=1, sticky="ew", padx=5)
    tk.Label(ci, text="NG", bg="black", fg="white", font=('Arial', 10)).grid(row=0, column=2, sticky="w", padx=5)
    mk_entry(ci, "6", fg_c="#ff3333", w=6).grid(row=0, column=3, sticky="ew", padx=5)

    tk.Label(ci, text="OK", bg="black", fg="white", font=('Arial', 10)).grid(row=1, column=0, sticky="w", pady=3)
    mk_entry(ci, "229", fg_c="#76ff03", w=6).grid(row=1, column=1, sticky="ew", padx=5)
    tk.Label(ci, text="NG", bg="black", fg="white", font=('Arial', 10)).grid(row=1, column=2, sticky="w", padx=5)
    mk_entry(ci, "2.55", fg_c="#ff3333", w=6).grid(row=1, column=3, sticky="ew", padx=5)

    # Method
    mf = ttk.LabelFrame(row1, text="Method")
    mf.grid(row=1, column=1, sticky="nsew", pady=(2, 0))
    mi = tk.Frame(mf, bg="black", padx=8, pady=8)
    mi.pack(fill="both", expand=True)
    mi.columnconfigure(0, weight=1)
    mi.columnconfigure(1, weight=1)
    mi.columnconfigure(2, weight=1)

    tk.Label(mi, text="Combined", bg="#333", fg="white", font=('Arial', 10), bd=1, relief="solid", padx=10, pady=4).grid(row=0, column=0, sticky="ew", padx=2)
    tk.Label(mi, text="Individual", bg="#388e3c", fg="white", font=('Arial', 10), bd=1, relief="solid", padx=10, pady=4).grid(row=0, column=1, sticky="ew", padx=2)
    tk.Label(mi, text="Rework", bg="#388e3c", fg="white", font=('Arial', 10), bd=1, relief="solid", padx=10, pady=4).grid(row=0, column=2, sticky="ew", padx=2)

    # --- Row 2: Inspection Specification ---
    tk.Label(left_area, text="Inspection Specification", bg="black", fg="white", font=('Arial', 11), anchor="w").pack(fill="x", pady=(8, 2))

    cols_insp = ("TEST", "unit", "No", "Channel", "Type", "Freq (kHz/MHz)", "Volt (V)", "Sec (s)", "Min", "Max", "Std")
    tree_insp = ttk.Treeview(left_area, columns=cols_insp, show="headings", height=5)
    col_w = [110, 50, 50, 80, 70, 120, 80, 70, 70, 70, 50]
    for i, col in enumerate(cols_insp):
        tree_insp.heading(col, text=col)
        tree_insp.column(col, width=col_w[i], anchor="center")
    tree_insp.pack(fill="x")

    tree_insp.tag_configure('normal', background='white', foreground='black')
    tree_insp.tag_configure('selected', background='#b0d8b0', foreground='black')

    tree_insp.insert("", "end", values=("Insulation Test", "Volts", "1", "3", "All", "", "500", "1", "100", "", ""), tags=('normal',))
    tree_insp.insert("", "end", values=("With Stand(mA)", "mA", "2", "3", "All", "", "1000", "3", "0", "10", ""), tags=('normal',))
    tree_insp.insert("", "end", values=("Contact", "-", "3", "3", "Single", "", "", "", "", "", ""), tags=('selected',))

    # --- Row 3: Testing ---
    tk.Label(left_area, text="Testing", bg="black", fg="white", font=('Arial', 11), anchor="w").pack(fill="x", pady=(10, 2))

    test_frame = tk.Frame(left_area, bg="black")
    test_frame.pack(fill="x")

    ch_labels = ["TEST", "unit", "CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8", "CH9", "CH10", "Result"]
    for i in range(13):
        test_frame.columnconfigure(i, weight=1)

    # Header row
    for i, h in enumerate(ch_labels):
        tk.Label(test_frame, text=h, bg="#d0d0d0", fg="black", font=('Arial', 9, 'bold'), bd=1, relief="solid", pady=8).grid(row=0, column=i, sticky="nsew")

    test_data = [
        (["Insulation Test", "Volts", "3253", "3253", "3253", "-", "-", "-", "-", "-", "-", "-", "PASS"]),
        (["With Stand(mA)", "mA", "0.82", "0.82", "0.82", "-", "-", "-", "-", "-", "-", "-", "PASS"]),
        (["Contact", "-", "OK", "OK", "OK", "-", "-", "-", "-", "-", "-", "-", "PASS"]),
    ]
    for r, row_data in enumerate(test_data):
        for c, val in enumerate(row_data):
            if 1 < c < 5:
                bg_c = "#aeea00"
            elif c == 12:
                bg_c = "#aeea00"
            else:
                bg_c = "white"
            tk.Label(test_frame, text=val, bg=bg_c, fg="black", font=('Arial', 9), bd=1, relief="solid", pady=8).grid(row=r+1, column=c, sticky="nsew")

    # --- Row 4: Scan label banner ---
    scan_outer = tk.Frame(left_area, bg="#4caf50", padx=2, pady=2)
    scan_outer.pack(fill="x", pady=(12, 8))
    tk.Label(scan_outer, text="Scan the printed label & PASS Display", bg="#001830", fg="white", font=('Arial', 16, 'bold'), pady=12).pack(fill="both", expand=True)

    # ==================== BOTTOM BAR ====================
    bottom = tk.Frame(content, bg="black", height=120)
    bottom.grid(row=1, column=0, sticky="ew", pady=(5, 0))
    bottom.grid_propagate(False)
    bottom.columnconfigure(0, weight=4)
    bottom.columnconfigure(1, weight=2)
    bottom.columnconfigure(2, weight=3)
    bottom.rowconfigure(0, weight=1)

    # IO Cable Data
    io_lf = ttk.LabelFrame(bottom, text="Receive IO Cable Data")
    io_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
    io_inner = tk.Frame(io_lf, bg="black", padx=5, pady=3)
    io_inner.pack(fill="both", expand=True)

    tk.Label(io_inner, text="INPUT", bg="black", fg="white", font=('Arial', 9, 'bold')).pack(anchor="w")
    in_row = tk.Frame(io_inner, bg="black")
    in_row.pack(anchor="w", pady=(0, 5))
    for i in range(1, 11):
        tk.Label(in_row, text=f"CH{i}", bg="#002200", fg="#4caf50", font=('Arial', 7), bd=1, relief="solid", width=4).pack(side="left", padx=1)

    out_row_lbl = tk.Frame(io_inner, bg="black")
    out_row_lbl.pack(fill="x")
    tk.Label(out_row_lbl, text="OUTPUT", bg="black", fg="white", font=('Arial', 9, 'bold')).pack(side="left")
    tk.Label(out_row_lbl, text="CS", bg="black", fg="white", font=('Arial', 9, 'bold')).pack(side="right", padx=10)

    out_row = tk.Frame(io_inner, bg="black")
    out_row.pack(fill="x")
    out_ch = tk.Frame(out_row, bg="black")
    out_ch.pack(side="left")
    for i in range(1, 11):
        tk.Label(out_ch, text=f"CH{i}", bg="#002200", fg="#4caf50", font=('Arial', 7), bd=1, relief="solid", width=4).pack(side="left", padx=1)
    cs_canvas = tk.Canvas(out_row, width=35, height=14, bg="black", highlightthickness=0)
    cs_canvas.pack(side="right", padx=10)
    cs_canvas.create_oval(2, 1, 14, 13, fill="#4caf50", outline="#4caf50")
    cs_canvas.create_oval(20, 1, 32, 13, fill="#4caf50", outline="#4caf50")

    # COM Status
    com_lf = ttk.LabelFrame(bottom, text="COM Status")
    com_lf.grid(row=0, column=1, sticky="nsew", padx=3)
    com_inner = tk.Frame(com_lf, bg="black", padx=5, pady=5)
    com_inner.pack(expand=True)

    com_data = [
        [("PROT", True), ("LCR", False), ("Rever", False)],
        [("IO", True), ("Printer", True), ("Scanner", True)],
    ]
    for r, row_items in enumerate(com_data):
        for c, (txt, on) in enumerate(row_items):
            bg_c = "#4caf50" if on else "#3a3a3a"
            fg_c = "black" if on else "white"
            tk.Label(com_inner, text=txt, bg=bg_c, fg=fg_c, font=('Arial', 9), width=8, pady=2).grid(row=r, column=c, padx=2, pady=2)

    # Log
    log_lf = ttk.LabelFrame(bottom, text="Log")
    log_lf.grid(row=0, column=2, sticky="nsew", padx=(3, 0))
    log_txt = tk.Text(log_lf, bg="black", fg="#bbb", font=('Consolas', 9), bd=0, width=35, height=4)
    log_txt.pack(fill="both", expand=True, padx=5, pady=3)
    log_txt.insert("end", "15:05:07.305> function name=Connect\n")
    log_txt.insert("end", "15:05:10.264> Quit\n")
    log_txt.insert("end", "(0)=Normal\n")
    log_txt.config(state="disabled")

    root.mainloop()

if __name__ == "__main__":
    main()
