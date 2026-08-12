import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("Feeder Cable HMI")
    root.geometry("1100x700")
    root.configure(bg="#f0f0f0")

    # Styles for Treeview
    style = ttk.Style()
    # 'clam' theme allows changing Treeview header background colors easily
    style.theme_use("clam") 
    style.configure("Treeview.Heading", background="#2b7a78", foreground="#a8d5ba", font=('Arial', 9, 'bold'))
    style.configure("Treeview", font=('Arial', 9), rowheight=25)
    
    # ------------------ TOP SECTION ------------------
    top_frame = tk.Frame(root, bg="black", padx=10, pady=10)
    top_frame.pack(side="top", fill="x")

    def make_field(parent, row, col, text, val=""):
        tk.Label(parent, text=text, fg="#00ffff", bg="black", font=('Arial', 9)).grid(row=row, column=col, sticky="w", padx=2, pady=2)
        e = tk.Entry(parent, width=12, font=('Arial', 9, 'bold'))
        e.insert(0, val)
        e.grid(row=row, column=col+1, sticky="w", padx=2, pady=2)

    # 1. Product Info
    p1 = tk.Frame(top_frame, bg="black")
    p1.pack(side="left", fill="y", expand=True)
    tk.Label(p1, text="PRODUCT INFORMATION", fg="yellow", bg="black", font=('Arial', 9, 'bold')).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
    make_field(p1, 1, 0, "Customer", "HMI")
    make_field(p1, 2, 0, "Model", "QY")
    make_field(p1, 3, 0, "Part No.", "300")
    make_field(p1, 4, 0, "Part Name", "MAIN")
    make_field(p1, 5, 0, "ALC", "H12")
    make_field(p1, 6, 0, "# OF CHLS", "2")

    # 2. Scan Codes
    p2 = tk.Frame(top_frame, bg="black")
    p2.pack(side="left", fill="y", expand=True)
    tk.Label(p2, text="SCAN CODES", fg="yellow", bg="black", font=('Arial', 9, 'bold')).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
    make_field(p2, 1, 0, "Master Cable", "300")
    # Empty space
    tk.Label(p2, bg="black").grid(row=2, column=0)
    make_field(p2, 3, 0, "Master Jig", "300")
    tk.Label(p2, bg="black").grid(row=4, column=0)
    make_field(p2, 5, 0, "Employee Code", "200")

    # 3. Production Count
    p3 = tk.Frame(top_frame, bg="black")
    p3.pack(side="left", fill="y", expand=True)
    tk.Label(p3, text="PRODUCTION COUNT", fg="yellow", bg="black", font=('Arial', 9, 'bold')).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))
    make_field(p3, 1, 0, "Total", "")
    make_field(p3, 1, 2, "PASS", "")
    tk.Label(p3, bg="black").grid(row=2, column=0) # Spacer
    make_field(p3, 3, 0, "PPM", "")
    make_field(p3, 3, 2, "NG", "")
    tk.Label(p3, bg="black").grid(row=4, column=0) # Spacer
    make_field(p3, 5, 0, "UPH", "")
    make_field(p3, 5, 2, "Test (Sec)", "")
    make_field(p3, 6, 2, "V_Code", "H001")

    # 4. Comport Status
    p4 = tk.Frame(top_frame, bg="black")
    p4.pack(side="left", fill="y", expand=True)
    tk.Label(p4, text="COMPORT STATUS", fg="yellow", bg="black", font=('Arial', 9, 'bold')).pack(anchor="w", pady=(0, 5))
    tk.Button(p4, text="HIPOT", bg="#7fffd4", font=('Arial', 9, 'bold'), width=15).pack(pady=4)
    tk.Button(p4, text="LCR METER", bg="#7fffd4", font=('Arial', 9, 'bold'), width=15).pack(pady=4)
    tk.Button(p4, text="IO CONTROLLER", bg="#7fffd4", font=('Arial', 9, 'bold'), width=15).pack(pady=4)

    # 5. Function
    p5 = tk.Frame(top_frame, bg="black")
    p5.pack(side="left", fill="y", expand=True)
    tk.Label(p5, text="FUNCTION", fg="yellow", bg="black", font=('Arial', 9, 'bold')).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
    
    btn_opts = {"bg": "black", "fg": "white", "font": ('Arial', 8), "width": 12, "relief": "ridge"}
    tk.Button(p5, text="ADMIN", **btn_opts).grid(row=1, column=0, pady=3, padx=3)
    tk.Button(p5, text="SETTINGS", **btn_opts).grid(row=1, column=1, pady=3, padx=3)
    tk.Button(p5, text="REPORT", **btn_opts).grid(row=2, column=0, pady=3, padx=3)
    tk.Button(p5, text="NEW PART_NO", **btn_opts).grid(row=2, column=1, pady=3, padx=3)
    tk.Button(p5, text="LABEL PRINT", **btn_opts).grid(row=3, column=0, pady=3, padx=3)
    tk.Button(p5, text="COMPORT", **btn_opts).grid(row=3, column=1, pady=3, padx=3)
    tk.Button(p5, text="Help", bg="white", fg="black", font=('Arial', 10, 'bold')).grid(row=4, column=1, sticky="e", pady=(5,0))

    # ------------------ MIDDLE SECTION ------------------
    mid_frame = tk.Frame(root, bg="#f0f0f0")
    mid_frame.pack(side="top", fill="both", expand=True, padx=5, pady=5)
    
    left_mid = tk.Frame(mid_frame, bg="#f0f0f0")
    left_mid.pack(side="left", fill="both", expand=True, padx=(0, 5))
    
    right_mid = tk.Frame(mid_frame, bg="#f0f0f0")
    right_mid.pack(side="right", fill="both", expand=True)

    # TEST SPECIFICATION
    spec_lbl = tk.Label(left_mid, text="TEST SPECIFICATION", bg="#2b7a78", fg="#a8d5ba", font=('Arial', 10, 'bold'), anchor="w")
    spec_lbl.pack(fill="x")
    
    cols_spec = ("Function", "Channel", "Freq(kHz/MHz)", "Volt(V)", "Sec(S)", "Min", "Max")
    tree_spec = ttk.Treeview(left_mid, columns=cols_spec, show="headings", height=3)
    for col in cols_spec:
        tree_spec.heading(col, text=col)
        tree_spec.column(col, width=80, anchor="center")
    tree_spec.pack(fill="x")
    
    tree_spec.insert("", "end", values=("Insulation Test", "2", "200", "120", "1", "5", "10"))
    tree_spec.insert("", "end", values=("Withstand Test", "2", "200", "120", "1", "5", "10"))
    tree_spec.insert("", "end", values=("Contact Test", "2", "200", "120", "1", "5", "10"))

    # TEST RESULT
    res_lbl = tk.Label(left_mid, text="TEST RESULT", bg="#2b7a78", fg="#a8d5ba", font=('Arial', 10, 'bold'), anchor="w")
    res_lbl.pack(fill="x", pady=(10, 0))
    
    cols_res = ("Function", "CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "RESULT")
    tree_res = ttk.Treeview(left_mid, columns=cols_res, show="headings", height=3)
    for col in cols_res:
        tree_res.heading(col, text=col)
        tree_res.column(col, width=70, anchor="center")
    tree_res.pack(fill="x")
    
    # Simple row highlight since per-cell highlight in Treeview requires custom rendering
    tree_res.tag_configure('pass_row', background='#008000', foreground='white')
    
    tree_res.insert("", "end", values=("Insulation Test", "7", "7", "7", "", "", "", "PASS"), tags=('pass_row',))
    tree_res.insert("", "end", values=("Withstand Test", "8", "8", "8", "", "", "", "PASS"), tags=('pass_row',))
    tree_res.insert("", "end", values=("Contact Test", "9", "9", "9", "", "", "", "PASS"), tags=('pass_row',))

    # TEST DATA
    data_lbl = tk.Label(right_mid, text="TEST DATA", bg="#2b7a78", fg="#a8d5ba", font=('Arial', 10, 'bold'), anchor="w")
    data_lbl.pack(fill="x")
    
    cols_data = ("SNO", "LOTNO", "ALC", "TEST RESULT")
    tree_data = ttk.Treeview(right_mid, columns=cols_data, show="headings")
    for col in cols_data:
        tree_data.heading(col, text=col)
        tree_data.column(col, width=100, anchor="center")
    tree_data.pack(fill="both", expand=True)
    
    tree_data.tag_configure('selected', background='#0078d7', foreground='white')
    
    data = [
        ("14", "240308I1A2A14", "H12", "PASS"),
        ("13", "240308I1A2A13", "H12", "PASS"),
        ("12", "240308I1A2A12", "H12", "PASS"),
        ("11", "240308I1A2A11", "H12", "PASS"),
        ("10", "240308I1A2A10", "H12", "PASS"),
        ("9",  "240308I1A2A9",  "H12", "PASS"),
        ("8",  "240308I1A2A8",  "H12", "PASS"),
        ("7",  "240308I1A2A7",  "H12", "PASS"),
    ]
    
    for i, d in enumerate(data):
        if i == 0:
            tree_data.insert("", "end", values=d, tags=('selected',))
        else:
            tree_data.insert("", "end", values=d)

    # ------------------ BOTTOM SECTION ------------------
    bottom_frame = tk.Frame(root, height=180, bg="#f0f0f0")
    bottom_frame.pack(side="bottom", fill="x", padx=5, pady=5)
    
    bottom_frame.grid_propagate(False)
    bottom_frame.columnconfigure(0, weight=1)
    bottom_frame.columnconfigure(1, weight=1)
    bottom_frame.columnconfigure(2, weight=3)
    bottom_frame.rowconfigure(0, weight=1)
    
    # Image Box
    lbl_img = tk.Label(bottom_frame, text="Image of label", bg="white", borderwidth=2, relief="solid", font=('Arial', 14))
    lbl_img.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
    
    # Content Box
    content_frame = tk.Frame(bottom_frame, borderwidth=2, relief="solid", bg="white")
    content_frame.grid(row=0, column=1, sticky="nsew", padx=2)
    content_frame.rowconfigure(0, weight=1)
    content_frame.rowconfigure(1, weight=1)
    content_frame.columnconfigure(0, weight=1)
    
    tk.Label(content_frame, text="Label content text", bg="white", font=('Arial', 14)).grid(row=0, column=0, sticky="nsew")
    tk.Frame(content_frame, bg="black", height=2).grid(row=0, column=0, sticky="sew")
    tk.Label(content_frame, text="OK/NG", bg="white", font=('Arial', 14)).grid(row=1, column=0, sticky="nsew")
    
    # PASS Box
    lbl_pass = tk.Label(bottom_frame, text="PASS", bg="blue", fg="white", font=('Arial', 100, 'bold'))
    lbl_pass.grid(row=0, column=2, sticky="nsew", padx=(2, 0))

    root.mainloop()

if __name__ == "__main__":
    main()
