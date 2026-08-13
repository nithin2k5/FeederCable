import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("COM Settings")
    root.geometry("1350x860")
    root.configure(bg="black")
    
    style = ttk.Style()
    style.theme_use("clam")
    
    # --- Header ---
    header = tk.Frame(root, bg="black", height=45)
    header.pack(fill="x")
    header.pack_propagate(False)

    logo_box = tk.Frame(header, bg="white", padx=6, pady=3)
    logo_box.pack(side="left", padx=10, pady=6)
    tk.Label(logo_box, text="INFAC", fg="#c00000", bg="white", font=('Arial', 16, 'bold')).pack(side="left")
    tk.Label(logo_box, text=" 주식회사인팩", fg="black", bg="white", font=('Malgun Gothic', 9)).pack(side="left")

    tk.Label(header, text="COM Settings", fg="#e8a000", bg="black", font=('Arial', 15, 'bold')).pack(side="left", padx=25)
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
    content.pack(side="left", fill="both", expand=True, padx=(20, 20), pady=(20, 20))
    
    # Outer panel simulating the dialog
    panel = tk.Frame(content, bg="#12151b", bd=1, relief="solid", highlightbackground="#333", highlightthickness=1)
    panel.pack(fill="both", expand=True)

    # Title bar
    title_bar = tk.Frame(panel, bg="#12151b")
    title_bar.pack(fill="x", padx=20, pady=15)
    tk.Label(title_bar, text="COM Setting", bg="#12151b", fg="white", font=('Arial', 14)).pack(side="left")
    tk.Label(title_bar, text="✕", bg="#12151b", fg="#aaa", font=('Arial', 14), cursor="hand2").pack(side="right")
    
    # Separator
    tk.Frame(panel, bg="#333", height=1).pack(fill="x", padx=20)

    # Table Frame
    table_frame = tk.Frame(panel, bg="#12151b")
    table_frame.pack(fill="x", padx=20, pady=20)
    
    # Configure columns
    for i in range(6):
        table_frame.columnconfigure(i, weight=1 if i == 0 else 0)

    # Headers
    headers = ["Device", "COM Port", "", "Baud Rate", "Station ID", "Action"]
    for i, h in enumerate(headers):
        sticky = "w" if i == 0 else ""
        tk.Label(table_frame, text=h, bg="#12151b", fg="white", font=('Arial', 11)).grid(row=0, column=i, sticky=sticky, padx=15, pady=(0, 15))

    devices = [
        ("HIPOT", "COM 3", "9600", "-"),
        ("LCR METER", "COM 0", "9600", "-"),
        ("PLC", "COM 0", "9600", "01"),
        ("IO Controller Cable", "COM 5", "9600", "-"),
        ("Label Printer", "COM 6", "9600", "-"),
        ("Scanner", "COM 0", "9600", "-"),
    ]

    def mk_combo(parent, val):
        cb = ttk.Combobox(parent, values=[val], font=('Arial', 10), width=10, state="readonly")
        cb.current(0)
        return cb

    for r, (dev, port, baud, sid) in enumerate(devices, start=1):
        tk.Label(table_frame, text=dev, bg="#12151b", fg="white", font=('Arial', 11)).grid(row=r, column=0, sticky="w", padx=15, pady=10)
        
        # COM Port
        mk_combo(table_frame, port).grid(row=r, column=1, padx=15)
        
        # Hyphen
        tk.Label(table_frame, text="-", bg="#12151b", fg="white", font=('Arial', 11)).grid(row=r, column=2, padx=5)
        
        # Baud Rate
        mk_combo(table_frame, baud).grid(row=r, column=3, padx=15)
        
        # Station ID
        mk_combo(table_frame, sid).grid(row=r, column=4, padx=15)
        
        # TEST Button
        tk.Button(table_frame, text="TEST", bg="#e0e0e0", fg="black", font=('Arial', 10, 'bold'), width=10, bd=0).grid(row=r, column=5, padx=15)

    # Text Area
    text_frame = tk.Frame(panel, bg="#12151b", bd=1, relief="solid", highlightbackground="#333", highlightthickness=1)
    text_frame.pack(fill="both", expand=True, padx=20, pady=(10, 20))
    
    log_text = tk.Text(text_frame, bg="#12151b", fg="white", font=('Consolas', 11), bd=0)
    log_text.pack(fill="both", expand=True, padx=10, pady=10)
    log_text.insert("end", "!007F00\n")
    log_text.config(state="disabled")

    # Bottom button
    bottom_bar = tk.Frame(panel, bg="#12151b")
    bottom_bar.pack(fill="x", padx=20, pady=(0, 20))
    
    tk.Button(bottom_bar, text="Complete", bg="#e0e0e0", fg="black", font=('Arial', 11, 'bold'), width=15, bd=0, pady=5).pack(side="right")

    root.mainloop()

if __name__ == "__main__":
    main()
