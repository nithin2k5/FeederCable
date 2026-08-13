import tkinter as tk
from tkinter import ttk

def render(parent):
    style = ttk.Style()
    
    # Main Content
    content = tk.Frame(parent, bg="black")
    content.pack(fill="both", expand=True, padx=(20, 20), pady=(20, 20))
    
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

    # Bottom buttons
    bottom_bar = tk.Frame(panel, bg="#12151b")
    bottom_bar.pack(side="bottom", fill="x", padx=20, pady=(0, 20))
    
    tk.Button(bottom_bar, text="Complete", bg="#e0e0e0", fg="black", font=('Arial', 11, 'bold'), width=12, bd=0, pady=5, cursor="hand2").pack(side="right", padx=(5, 0))
    tk.Button(bottom_bar, text="Update", bg="#2196f3", fg="white", font=('Arial', 11, 'bold'), width=12, bd=0, pady=5, cursor="hand2").pack(side="right", padx=5)
    tk.Button(bottom_bar, text="Save", bg="#4caf50", fg="white", font=('Arial', 11, 'bold'), width=12, bd=0, pady=5, cursor="hand2").pack(side="right", padx=5)

    # Text Area
    text_frame = tk.Frame(panel, bg="#12151b", bd=1, relief="solid", highlightbackground="#333", highlightthickness=1)
    text_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(10, 20))
    
    log_text = tk.Text(text_frame, bg="#12151b", fg="white", font=('Consolas', 11), bd=0, height=8)
    log_text.pack(fill="both", expand=True, padx=10, pady=10)
    log_text.insert("end", "!007F00\n")
    log_text.config(state="disabled")


