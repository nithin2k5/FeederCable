import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import mysql.connector
import datetime
import csv
import os

import db

def _get_conn():
    return db.get_connection()

def render(parent):
    bg_color = "#081014" 
    border_color = "#182c35" 
    text_color = "white"
    teal_text = "#489fb5" 
    
    style = ttk.Style()
    style.configure("Treeview.Heading", background="#0a1920", foreground=text_color, font=('Arial', 9, 'bold'), bordercolor=border_color, lightcolor=border_color, darkcolor=border_color)
    style.configure("Treeview", background="#0c131a", foreground=text_color, fieldbackground="#0c131a", font=('Arial', 9), rowheight=28, bordercolor=border_color)
    style.map("Treeview", background=[('selected', '#1a3340')])
    style.configure("TCombobox", fieldbackground="#111", background="#111", foreground="white", bordercolor=border_color)

    content = tk.Frame(parent, bg=bg_color, bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1)
    content.pack(fill="both", expand=True, padx=5, pady=5)
    
    header = tk.Frame(content, bg=bg_color, height=80, bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1)
    header.pack(fill="x", padx=10, pady=(10, 5))
    header.pack_propagate(False)
    
    logo_frame = tk.Frame(header, bg=bg_color, bd=1, relief="solid", highlightbackground=teal_text, highlightthickness=1, padx=15, pady=5)
    logo_frame.pack(side="left", padx=20, pady=10)
    logo_top = tk.Frame(logo_frame, bg=bg_color); logo_top.pack()
    tk.Label(logo_top, text="IN", fg="red", bg=bg_color, font=('Arial', 18, 'bold')).pack(side="left")
    tk.Label(logo_top, text="FAC", fg=teal_text, bg=bg_color, font=('Arial', 18, 'bold')).pack(side="left")
    tk.Label(logo_frame, text="INDIA", fg=teal_text, bg=bg_color, font=('Arial', 10, 'bold')).pack()

    tk.Label(header, text="TEST DATA CONSOLE", fg="white", bg=bg_color, font=('Arial', 24, 'bold')).pack(side="left", expand=True, padx=(0, 100))

    filter_bar = tk.Frame(content, bg=bg_color, bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1)
    filter_bar.pack(fill="x", padx=10, pady=5)
    filter_inner = tk.Frame(filter_bar, bg=bg_color, pady=15); filter_inner.pack(expand=True) 

    def mk_lbl(parent, txt):
        return tk.Label(parent, text=txt, bg=bg_color, fg="white", font=('Arial', 9, 'bold'))

    # PNO List
    try:
        with db.get_cursor() as cur:
            cur.execute("SELECT DISTINCT pno FROM testmaster ORDER BY pno")
            pno_list = ["ALL"] + [r[0] for r in cur.fetchall()]
    except Exception:
        pno_list = ["ALL"]

    mk_lbl(filter_inner, "PART NUMBER :").grid(row=0, column=0, sticky="e", padx=(0, 10))
    cb_pno = ttk.Combobox(filter_inner, values=pno_list, font=('Arial', 10), width=20, state="readonly")
    cb_pno.current(0)
    cb_pno.grid(row=0, column=1, sticky="w", padx=(0, 30))
    
    mk_lbl(filter_inner, "START DATE :").grid(row=0, column=2, sticky="e", padx=(0, 10), pady=5)
    ent_start = tk.Entry(filter_inner, font=('Arial', 10), width=18, bg="#111", fg="white", insertbackground="white")
    ent_start.insert(0, (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d"))
    ent_start.grid(row=0, column=3, sticky="w", padx=(0, 30), pady=5)
    
    mk_lbl(filter_inner, "END DATE :").grid(row=1, column=2, sticky="e", padx=(0, 10), pady=5)
    ent_end = tk.Entry(filter_inner, font=('Arial', 10), width=18, bg="#111", fg="white", insertbackground="white")
    ent_end.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))
    ent_end.grid(row=1, column=3, sticky="w", padx=(0, 30), pady=5)
    
    mk_lbl(filter_inner, "RESULT :").grid(row=0, column=4, sticky="e", padx=(0, 10))
    cb_result = ttk.Combobox(filter_inner, values=["ALL", "PASS", "FAIL"], font=('Arial', 10), width=15, state="readonly")
    cb_result.current(0)
    cb_result.grid(row=0, column=5, sticky="w", padx=(0, 30))
    
    btn_frame = tk.Frame(filter_inner, bg=bg_color); btn_frame.grid(row=0, column=6, rowspan=2, padx=10)
    
    table_outer = tk.Frame(content, bg=bg_color, bd=1, relief="solid", highlightbackground=border_color, highlightthickness=1)
    table_outer.pack(fill="both", expand=True, padx=10, pady=(5, 10))
    
    cols = ("SNO", "DATE", "TIME", "CUSTOMER NAME", "MODEL", "P/NUMBER", "P/NAME", "LOTNO", "ALC", "RESULT", "CHANNEL", "IR_VAL", "ACW_VAL", "CONTACT")
    tree = ttk.Treeview(table_outer, columns=cols, show="headings")
    hsb = ttk.Scrollbar(table_outer, orient="horizontal", command=tree.xview)
    tree.configure(xscrollcommand=hsb.set)
    hsb.pack(side="bottom", fill="x")
    
    vsb = ttk.Scrollbar(table_outer, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    tree.pack(side="top", fill="both", expand=True)
    
    col_widths = {"SNO": 40, "DATE": 80, "TIME": 70, "CUSTOMER NAME": 100, "MODEL": 80, "P/NUMBER": 100, "P/NAME": 100, "LOTNO": 140, "ALC": 50, "RESULT": 60, "CHANNEL": 60, "IR_VAL": 70, "ACW_VAL": 70, "CONTACT": 70}
    for col in cols: tree.heading(col, text=col); tree.column(col, width=col_widths.get(col, 80), anchor="center")

    def _do_search():
        tree.delete(*tree.get_children())
        pno = cb_pno.get(); start = ent_start.get(); end = ent_end.get(); res = cb_result.get()
        try:
            with db.get_cursor() as cur:
                query = """
                    SELECT m.date, m.time, (SELECT cname FROM settingmaster s WHERE s.pno=m.pno LIMIT 1) as cname, 
                           m.model, m.pno, m.pname, m.lotno, m.alc, m.result, 
                           r.channel, r.ir_resistance, r.acw_current, r.contact_result
                    FROM testmaster m
                    LEFT JOIN testresult r ON m.lotno = r.lotno
                    WHERE m.date >= %s AND m.date <= %s
                """
                params = [start, end]
                if pno != "ALL": query += " AND m.pno = %s"; params.append(pno)
                if res != "ALL": query += " AND m.result = %s"; params.append(res)
                query += " ORDER BY m.date DESC, m.time DESC, m.lotno, r.channel"
                
                cur.execute(query, tuple(params))
                for idx, row in enumerate(cur.fetchall(), start=1):
                    tree.insert("", "end", values=(idx, row[0], row[1], row[2] or "", row[3], row[4], row[5], row[6], row[7], row[8], row[9] or "", row[10] or "", row[11] or "", row[12] or ""))
        except Exception as ex: messagebox.showerror("DB Error", f"Failed to search: {ex}")

    def _do_export():
        rows = []
        for child in tree.get_children():
            rows.append(tree.item(child)["values"])
        if not rows:
            messagebox.showinfo("Export", "No data to export.")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")], title="Save Test Data")
        if filepath:
            try:
                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(cols)
                    writer.writerows(rows)
                messagebox.showinfo("Export", f"Data exported successfully to\n{filepath}")
            except Exception as ex:
                messagebox.showerror("Export Error", f"Failed to export: {ex}")

    search_btn = tk.Button(btn_frame, text="🔍 Search", bg="#0a2a30", fg="white", font=('Arial', 10, 'bold'), bd=1, relief="solid", highlightbackground=teal_text, highlightthickness=1, padx=15, pady=5, cursor="hand2", command=_do_search)
    search_btn.pack(side="left", padx=10)
    
    export_btn = tk.Button(btn_frame, text="📄 Export (CSV)", bg="#0a2a30", fg="white", font=('Arial', 10, 'bold'), bd=1, relief="solid", highlightbackground=teal_text, highlightthickness=1, padx=15, pady=5, cursor="hand2", command=_do_export)
    export_btn.pack(side="left", padx=10)
    
    _do_search() # Initial search
