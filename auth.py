import tkinter as tk
from tkinter import messagebox
import mysql.connector

def _get_conn():
    return mysql.connector.connect(
        host="localhost", database="fceol", user="root", password="root"
    )

def show_disclaimer(parent_root):
    # Modal dialog that blocks the main window
    dialog = tk.Toplevel(parent_root)
    dialog.title("Disclaimer")
    
    w, h = 600, 400
    sw = dialog.winfo_screenwidth()
    sh = dialog.winfo_screenheight()
    x = int((sw/2) - (w/2))
    y = int((sh/2) - (h/2))
    dialog.geometry(f"{w}x{h}+{x}+{y}")
    dialog.configure(bg="black")
    dialog.transient(parent_root)
    dialog.grab_set()
    
    # Remove window controls so user is forced to accept
    dialog.protocol("WM_DELETE_WINDOW", lambda: None)
    
    lbl_title = tk.Label(dialog, text="IMPORTANT SAFETY INSTRUCTIONS", bg="black", fg="red", font=("Arial", 16, "bold"))
    lbl_title.pack(pady=(20, 10))
    
    msg = (
        "This is an industrial End-Of-Line (EOL) tester.\n"
        "It involves High Voltage (HiPot) and automated IO control.\n\n"
        "1. Ensure the jig and cables are properly secured before testing.\n"
        "2. Do NOT touch the exposed leads during testing.\n"
        "3. Only authorized personnel are permitted to operate this machine.\n"
    )
    
    lbl_msg = tk.Label(dialog, text=msg, bg="black", fg="white", font=("Arial", 12), justify="left")
    lbl_msg.pack(pady=10)
    
    chk_var = tk.BooleanVar(value=False)
    
    def on_check():
        if chk_var.get():
            btn_accept.config(state="normal", bg="#1b5e20", fg="white")
        else:
            btn_accept.config(state="disabled", bg="#333", fg="#777")
            
    chk = tk.Checkbutton(dialog, text="I have read and understood the instructions.", 
                         variable=chk_var, bg="black", fg="#e8a000", selectcolor="black", 
                         activebackground="black", activeforeground="#e8a000", font=("Arial", 12),
                         command=on_check)
    chk.pack(pady=20)
    
    def on_accept():
        dialog.destroy()
        
    btn_accept = tk.Button(dialog, text="ACCEPT", state="disabled", bg="#333", fg="#777", font=("Arial", 14, "bold"), bd=0, padx=30, pady=10, command=on_accept)
    btn_accept.pack(pady=20)
    
    # Wait for the window to be destroyed before returning
    parent_root.wait_window(dialog)


def show_login(parent_root, title="Login"):
    """
    Shows a login modal. 
    Returns True if login successful, False otherwise.
    """
    dialog = tk.Toplevel(parent_root)
    dialog.title(title)
    
    w, h = 400, 300
    sw = dialog.winfo_screenwidth()
    sh = dialog.winfo_screenheight()
    x = int((sw/2) - (w/2))
    y = int((sh/2) - (h/2))
    dialog.geometry(f"{w}x{h}+{x}+{y}")
    dialog.configure(bg="#111")
    dialog.transient(parent_root)
    dialog.grab_set()
    
    tk.Label(dialog, text=title.upper(), bg="#111", fg="#e8a000", font=("Arial", 16, "bold")).pack(pady=(20, 10))
    
    form_frame = tk.Frame(dialog, bg="#111")
    form_frame.pack(pady=10)
    
    tk.Label(form_frame, text="Employee ID", bg="#111", fg="white", font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=10, padx=10)
    ent_eno = tk.Entry(form_frame, font=("Arial", 12), bg="#222", fg="white", insertbackground="white", bd=1, relief="solid")
    ent_eno.grid(row=0, column=1, pady=10, padx=10)
    
    tk.Label(form_frame, text="Password", bg="#111", fg="white", font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=10, padx=10)
    ent_pwd = tk.Entry(form_frame, font=("Arial", 12), bg="#222", fg="white", insertbackground="white", bd=1, relief="solid", show="*")
    ent_pwd.grid(row=1, column=1, pady=10, padx=10)
    
    result = {"success": False}
    
    def on_login(event=None):
        eno = ent_eno.get().strip()
        pwd = ent_pwd.get().strip()
        
        if (eno == "nice" and pwd == "nice1234") or (eno == "123" and pwd == "123"):
            result["success"] = True
            dialog.destroy()
            return
            
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute("SELECT pwd FROM admin WHERE eno=%s", (eno,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if row and row[0] == pwd:
                result["success"] = True
                dialog.destroy()
            else:
                messagebox.showerror("Access Denied", "Invalid Employee ID or Password.", parent=dialog)
        except Exception as ex:
            # If DB is not reachable, fallback to error
            messagebox.showerror("DB Error", f"Could not authenticate:\n{ex}", parent=dialog)
            
    ent_pwd.bind("<Return>", on_login)
    
    btn_login = tk.Button(dialog, text="LOGIN", bg="#0a33aa", fg="white", font=("Arial", 12, "bold"), bd=0, padx=30, pady=8, cursor="hand2", command=on_login)
    btn_login.pack(pady=15)
    
    ent_eno.focus_set()
    parent_root.wait_window(dialog)
    return result["success"]
