import tkinter as tk
from tkinter import ttk, messagebox
import db

def _get_conn():
    return db.get_connection()

def render(parent):
    bg_color = "#000000"
    text_color = "white"
    
    style = ttk.Style()
    style.configure("Admin.Treeview.Heading", background="#1a1a1a", foreground="white", font=("Arial", 9, "bold"))
    style.configure("Admin.Treeview", background="#0d0d0d", foreground="white", fieldbackground="#0d0d0d", font=("Arial", 9), rowheight=26)
    style.map("Admin.Treeview", background=[("selected", "#1c3a5e")])

    content = tk.Frame(parent, bg=bg_color)
    content.pack(fill="both", expand=True, padx=20, pady=20)
    
    tk.Label(content, text="ADMIN USER MANAGEMENT", fg="#e8a000", bg=bg_color, font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 20))
    
    # Form Frame
    form_frame = tk.Frame(content, bg="#111", bd=1, relief="solid", highlightbackground="#444", highlightthickness=1, padx=20, pady=20)
    form_frame.pack(fill="x", pady=(0, 20))
    
    def _lbl(parent_frame, txt):
        return tk.Label(parent_frame, text=txt, bg="#111", fg="#aaa", font=("Arial", 10))
    def _ent(parent_frame, is_password=False):
        return tk.Entry(parent_frame, font=("Arial", 11), bg="#222", fg="white", insertbackground="white", bd=1, relief="solid", show="*" if is_password else "")

    _lbl(form_frame, "Employee ID (ENO)").grid(row=0, column=0, sticky="w", pady=10, padx=(0,10))
    ent_eno = _ent(form_frame)
    ent_eno.grid(row=0, column=1, sticky="ew", padx=(0, 30))
    
    _lbl(form_frame, "Employee Name").grid(row=0, column=2, sticky="w", pady=10, padx=(0,10))
    ent_ename = _ent(form_frame)
    ent_ename.grid(row=0, column=3, sticky="ew")

    _lbl(form_frame, "Password").grid(row=1, column=0, sticky="w", pady=10, padx=(0,10))
    ent_pwd = _ent(form_frame, is_password=True)
    ent_pwd.grid(row=1, column=1, sticky="ew", padx=(0, 30))

    _lbl(form_frame, "Designation").grid(row=1, column=2, sticky="w", pady=10, padx=(0,10))
    ent_desig = _ent(form_frame)
    ent_desig.grid(row=1, column=3, sticky="ew")

    _lbl(form_frame, "Department").grid(row=2, column=0, sticky="w", pady=10, padx=(0,10))
    ent_dept = _ent(form_frame)
    ent_dept.grid(row=2, column=1, sticky="ew", padx=(0, 30))

    for i in range(4): form_frame.columnconfigure(i, weight=1)

    # Buttons
    btn_frame = tk.Frame(content, bg=bg_color)
    btn_frame.pack(fill="x", pady=(0, 20))
    
    def load_users():
        tree.delete(*tree.get_children())
        try:
            with db.get_cursor() as cur:
                cur.execute("SELECT eno, ename, desig, dept FROM admin")
                for row in cur.fetchall():
                    tree.insert("", "end", values=row)
        except Exception as ex:
            messagebox.showerror("DB Error", f"Failed to load users: {ex}")

    def on_tree_select(event):
        selected = tree.selection()
        if not selected: return
        item = tree.item(selected[0])
        eno = item["values"][0]
        try:
            with db.get_cursor() as cur:
                cur.execute("SELECT eno, ename, pwd, desig, dept FROM admin WHERE eno=%s", (str(eno),))
                row = cur.fetchone()
            if row:
                for e in [ent_eno, ent_ename, ent_pwd, ent_desig, ent_dept]: e.delete(0, "end")
                ent_eno.insert(0, row[0]); ent_ename.insert(0, row[1])
                ent_pwd.insert(0, row[2]); ent_desig.insert(0, row[3]); ent_dept.insert(0, row[4])
        except Exception as ex:
            messagebox.showerror("DB Error", str(ex))

    def on_save():
        eno = ent_eno.get().strip(); ename = ent_ename.get().strip(); pwd = ent_pwd.get().strip()
        desig = ent_desig.get().strip(); dept = ent_dept.get().strip()
        if not eno or not pwd:
            messagebox.showwarning("Validation", "Employee ID and Password are required.")
            return
        try:
            with db.get_cursor(commit=True) as cur:
                cur.execute("SELECT eno FROM admin WHERE eno=%s", (eno,))
                exists = cur.fetchone()
                if exists:
                    cur.execute("UPDATE admin SET ename=%s, pwd=%s, desig=%s, dept=%s WHERE eno=%s", (ename, pwd, desig, dept, eno))
                else:
                    cur.execute("INSERT INTO admin (eno, ename, pwd, desig, dept) VALUES (%s, %s, %s, %s, %s)", (eno, ename, pwd, desig, dept))
            messagebox.showinfo("Success", "User saved successfully.")
            load_users()
            on_clear()
        except Exception as ex:
            messagebox.showerror("Error", str(ex))

    def on_delete():
        eno = ent_eno.get().strip()
        if not eno: return
        if messagebox.askyesno("Confirm", f"Delete user '{eno}'?"):
            try:
                with db.get_cursor(commit=True) as cur:
                    cur.execute("DELETE FROM admin WHERE eno=%s", (eno,))
                messagebox.showinfo("Success", "User deleted.")
                load_users()
                on_clear()
            except Exception as ex:
                messagebox.showerror("Error", str(ex))

    def on_clear():
        for e in [ent_eno, ent_ename, ent_pwd, ent_desig, ent_dept]: e.delete(0, "end")
        ent_eno.focus_set()

    tk.Button(btn_frame, text="Save / Update", bg="#1b5e20", fg="white", font=("Arial", 11, "bold"), bd=0, padx=20, pady=8, cursor="hand2", command=on_save).pack(side="left", padx=(0, 10))
    tk.Button(btn_frame, text="Delete", bg="#b71c1c", fg="white", font=("Arial", 11, "bold"), bd=0, padx=20, pady=8, cursor="hand2", command=on_delete).pack(side="left", padx=(0, 10))
    tk.Button(btn_frame, text="Clear", bg="#333", fg="white", font=("Arial", 11, "bold"), bd=0, padx=20, pady=8, cursor="hand2", command=on_clear).pack(side="left")

    # Treeview
    tree_frame = tk.Frame(content, bg="#111", bd=1, relief="solid", highlightbackground="#444", highlightthickness=1)
    tree_frame.pack(fill="both", expand=True)
    
    cols = ("Employee ID", "Name", "Designation", "Department")
    tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="Admin.Treeview")
    for col in cols: tree.heading(col, text=col); tree.column(col, anchor="center")
    tree.pack(fill="both", expand=True, padx=2, pady=2)
    tree.bind("<<TreeviewSelect>>", on_tree_select)
    
    load_users()
