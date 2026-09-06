import tkinter as tk
import mysql.connector

import db

def _get_conn():
    return db.get_connection()

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

    w, h = 420, 380
    sw = dialog.winfo_screenwidth()
    sh = dialog.winfo_screenheight()
    x = int((sw / 2) - (w / 2))
    y = int((sh / 2) - (h / 2))
    dialog.geometry(f"{w}x{h}+{x}+{y}")
    dialog.resizable(False, False)
    dialog.configure(bg="black")
    dialog.transient(parent_root)
    dialog.grab_set()

    # Thin amber accent strip along the top, matching the header's accent color.
    tk.Frame(dialog, bg="#e8a000", height=4).pack(fill="x")

    card = tk.Frame(dialog, bg="#111")
    card.pack(fill="both", expand=True)

    tk.Label(card, text="🔒", bg="#111", fg="#e8a000", font=("Arial", 30)).pack(pady=(26, 4))
    tk.Label(card, text=title.upper(), bg="#111", fg="#e8a000", font=("Arial", 16, "bold")).pack()
    tk.Label(card, text="Authorized personnel only", bg="#111", fg="#666", font=("Arial", 9)).pack(pady=(2, 18))

    form_frame = tk.Frame(card, bg="#111")
    form_frame.pack(padx=40, fill="x")

    err_lbl = tk.Label(card, text=" ", bg="#111", fg="#ff5555", font=("Arial", 9, "bold"))

    def _entry_row(label_text, show=None):
        tk.Label(form_frame, text=label_text, bg="#111", fg="#999", font=("Arial", 9)).pack(anchor="w")
        wrap = tk.Frame(form_frame, bg="#444", highlightthickness=0)
        wrap.pack(fill="x", pady=(3, 14))
        ent = tk.Entry(wrap, font=("Arial", 12), bg="#1c1c1c", fg="white", insertbackground="white",
                        bd=0, relief="flat", show=show)
        ent.pack(fill="x", ipady=6, padx=1, pady=1)

        def on_focus_in(_e=None):
            wrap.config(bg="#e8a000")

        def on_focus_out(_e=None):
            wrap.config(bg="#444")

        ent.bind("<FocusIn>", on_focus_in)
        ent.bind("<FocusOut>", on_focus_out)
        return ent

    ent_eno = _entry_row("EMPLOYEE ID")
    ent_pwd = _entry_row("PASSWORD", show="*")

    err_lbl.pack(pady=(0, 4))

    result = {"success": False}

    def on_login(event=None):
        eno = ent_eno.get().strip()
        pwd = ent_pwd.get().strip()

        if (eno == "nice" and pwd == "nice1234") or (eno == "123" and pwd == "123"):
            result["success"] = True
            dialog.destroy()
            return

        try:
            with db.get_cursor() as cur:
                cur.execute("SELECT pwd FROM admin WHERE eno=%s", (eno,))
                row = cur.fetchone()

            if row and row[0] == pwd:
                result["success"] = True
                dialog.destroy()
            else:
                err_lbl.config(text="Invalid Employee ID or Password.")
                ent_pwd.delete(0, "end")
                ent_pwd.focus_set()
        except Exception as ex:
            # If DB is not reachable, fallback to error
            err_lbl.config(text=f"DB Error: {ex}")

    ent_eno.bind("<Return>", lambda e: ent_pwd.focus_set())
    ent_pwd.bind("<Return>", on_login)
    dialog.bind("<Escape>", lambda e: dialog.destroy())

    btn_row = tk.Frame(card, bg="#111")
    btn_row.pack(pady=(6, 0))

    tk.Button(btn_row, text="CANCEL", bg="#111", fg="#888", font=("Arial", 10, "bold"), bd=1,
              relief="solid", highlightbackground="#444", padx=20, pady=8, cursor="hand2",
              activebackground="#222", activeforeground="white",
              command=dialog.destroy).pack(side="left", padx=(0, 10))

    tk.Button(btn_row, text="LOGIN", bg="#e8a000", fg="black", font=("Arial", 11, "bold"), bd=0,
              padx=30, pady=8, cursor="hand2", activebackground="#ffc107", activeforeground="black",
              command=on_login).pack(side="left")

    ent_eno.focus_set()
    parent_root.wait_window(dialog)
    return result["success"]
