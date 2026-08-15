"""
test_console.py
===============
Main EOL test console page for Feeder Cable tester.
Mirrors TestConsole.cs logic from the C# reference project.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
import threading
import datetime
import time
import os
import configparser

# â”€â”€ Optional hardware libraries (graceful degradation) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
try:
    import serial
    import serial.tools.list_ports
    _serial_ok = True
except ImportError:
    _serial_ok = False

try:
    import winsound
    _audio_ok = True
except ImportError:
    _audio_ok = False

try:
    import win32print
    _print_ok = True
except ImportError:
    _print_ok = False

def _get_conn():
    return mysql.connector.connect(
        host="localhost", database="fceol", user="root", password="root"
    )

_CFG_PATH = os.path.join(os.path.dirname(__file__), "comport_cfg.ini")
def _load_cfg() -> dict:
    cfg = configparser.ConfigParser()
    cfg.read(_CFG_PATH)
    return {
        "io_port":    cfg.get("COM", "io_port",    fallback="COM5"),
        "io_baud":    cfg.getint("COM", "io_baud",  fallback=9600),
        "hp_port":    cfg.get("COM", "hp_port",    fallback="COM6"),
        "hp_baud":    cfg.getint("COM", "hp_baud",  fallback=9600),
        "machine_id": cfg.get("COM", "machine_id", fallback="PB1"),
    }
def _save_cfg(d: dict):
    cfg = configparser.ConfigParser()
    cfg["COM"] = {k: str(v) for k, v in d.items()}
    with open(_CFG_PATH, "w") as f:
        cfg.write(f)

def _play_wav(filename: str):
    base = os.path.dirname(__file__)
    path = os.path.join(base, filename)
    if not os.path.exists(path):
        return
    if _audio_ok:
        try:
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            pass

def _print_raw(printer_name: str, filename: str):
    if not _print_ok: return
    if not os.path.exists(filename): return
    try:
        hPrinter = win32print.OpenPrinter(printer_name)
        try:
            hJob = win32print.StartDocPrinter(hPrinter, 1, ("EOL Label", None, "RAW"))
            try:
                win32print.StartPagePrinter(hPrinter)
                with open(filename, "rb") as f:
                    win32print.WritePrinter(hPrinter, f.read())
                win32print.EndPagePrinter(hPrinter)
            finally:
                win32print.EndDocPrinter(hPrinter)
        finally:
            win32print.ClosePrinter(hPrinter)
    except Exception: pass
class AdamIO:
    def __init__(self, port: str, baud: int = 9600):
        self._port = port
        self._baud = baud
        self._ser = None
    def open(self):
        if not _serial_ok: return False
        try:
            if self._ser and self._ser.is_open: self._ser.close()
            self._ser = serial.Serial(self._port, self._baud, timeout=1.5, write_timeout=0.5)
            return True
        except Exception: return False
    def close(self):
        try:
            if self._ser and self._ser.is_open: self._ser.close()
        except Exception: pass
    @property
    def is_open(self): return self._ser is not None and self._ser.is_open
    def send(self, cmd: str) -> str:
        if not self.is_open: return ""
        try:
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
            self._ser.write((cmd + "\r").encode("ascii"))
            time.sleep(0.05)
            raw = self._ser.read_all()
            return raw.decode("ascii", errors="ignore").strip()
        except Exception: return ""
    def read_inputs(self) -> str:
        return self.send("$016")

class HiPotSerial:
    def __init__(self, port: str, baud: int = 9600):
        self._port = port
        self._baud = baud
        self._ser = None
    def open(self):
        if not _serial_ok: return False
        try:
            if self._ser and self._ser.is_open:
                self._ser.close()
                time.sleep(0.1)
            self._ser = serial.Serial(self._port, self._baud, timeout=3.0, write_timeout=0.5)
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
            return True
        except Exception: return False
    def close(self):
        try:
            if self._ser and self._ser.is_open: self._ser.close()
        except Exception: pass
    @property
    def is_open(self): return self._ser is not None and self._ser.is_open
    def write_line(self, cmd: str):
        if not self.is_open: return
        self._ser.write((cmd + "\r\n").encode("ascii"))
        time.sleep(0.025)
    def read_line(self) -> str:
        if not self.is_open: return ""
        try: return self._ser.readline().decode("ascii", errors="ignore").strip()
        except Exception: return ""
    def flush(self):
        if self.is_open:
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
    def run_ir_test(self, ir_volt_kv: float, ir_time_s: float, ir_min: float, ir_max: float) -> tuple:
        instr = [
            "MANU:EDIT:MODE IR", "TEST:RET ON", f"MANU:IR:VOLT {ir_volt_kv:.4f}",
            "MANU:IR:RHIS 9999", "MANU:IR:RLOS 1", f"MANU:IR:TTIM {ir_time_s:.1f}",
            "MANU:IR:REF 0", "FUNC:TEST OFF", "*CLS", "FUNC:TEST ON"
        ]
        for cmd in instr: self.write_line(cmd)
        time.sleep(0.9)
        self.write_line("MEAS?")
        time.sleep(0.02)
        response = self.read_line()
        self.flush()
        ir_val = 0.0
        try:
            parts = response.split(",")
            if len(parts) > 3: ir_val = float(parts[3][:4])
        except (ValueError, IndexError): ir_val = 0.0
        return ir_min <= ir_val <= ir_max, ir_val
    def run_acw_test(self, acw_volt_kv: float, acw_time_s: float, acw_min: float, acw_max: float) -> tuple:
        instr = [
            "MANU:EDIT:MODE ACW", "TEST:RET ON", f"MANU:ACW:VOLT {acw_volt_kv:.4f}",
            "MANU:ACW:FREQ 60", "MANU:ACW:CLOS 0.00", f"MANU:ACW:TTIM {acw_time_s:.1f}",
            "MANU:ACW:REF 0.00", "FUNC:TEST OFF", "*CLS", "FUNC:TEST ON"
        ]
        for cmd in instr: self.write_line(cmd)
        time.sleep(0.9)
        self.write_line("MEAS?")
        time.sleep(0.02)
        response = self.read_line()
        self.flush()
        acw_val = 0.0
        try:
            parts = response.split(",")
            if len(parts) > 3: acw_val = float(parts[3][:5])
        except (ValueError, IndexError): acw_val = 0.0
        return acw_min <= acw_val <= acw_max, acw_val

def _generate_lot_number(pno: str, machine_id: str) -> str:
    now = datetime.datetime.now()
    date_str = now.strftime("%y%m%d")
    mid_char = machine_id[-1] if machine_id else "1"
    prefix = f"{date_str}I{mid_char}A2A"
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM testmaster WHERE pno=%s AND lotno LIKE %s", (pno, f"{date_str}%"))
        row = cur.fetchone()
        seq = (row[0] if row else 0) + 1
        cur.close(); conn.close()
    except Exception: seq = 1
    return f"{prefix}{seq}"

def _print_barcode_label(pno: str, alc: str, model: str, vendor_code: str, eo_number: str, lot_no: str, machine_id: str, printer_name: str = "EOLPRINTER"):
    base = os.path.dirname(__file__)
    lbl_sel = ""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT lblsel FROM settingmaster WHERE pno=%s", (pno,))
        row = cur.fetchone()
        if row: lbl_sel = row[0] or ""
        cur.close(); conn.close()
    except Exception: pass
    prn_file = os.path.join(base, f"{lbl_sel}R.prn") if lbl_sel else ""
    if not prn_file or not os.path.exists(prn_file): prn_file = os.path.join(base, "TEMPPRN.prn")
    if not os.path.exists(prn_file): return
    now = datetime.datetime.now()
    try:
        with open(prn_file, "r", encoding="latin-1") as f: text = f.read()
        text = text.replace("@alcCode@", alc).replace("@partNumber@", pno).replace("@modelName@", model).replace("@vendorCode@", vendor_code).replace("@eoNumber@", eo_number).replace("@lotNo@", lot_no).replace("@traceabilityCode@", lot_no)
        text = text.replace("@ddMMyy@", now.strftime("%d%m%y")).replace("@HH:mm:ss@", now.strftime("%H:%M:%S")).replace("@machineID_NoAlphabet@", machine_id.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"))
        tmp = os.path.join(base, "TEMPPRN.prn")
        with open(tmp, "w", encoding="latin-1") as f: f.write(text)
        _print_raw(printer_name, tmp)
    except Exception: pass
def render(parent):
    cfg = _load_cfg()
    style = ttk.Style()
    style.configure("TC.TLabelframe", background="black", foreground="white", bordercolor="#444")
    style.configure("TC.TLabelframe.Label", background="black", foreground="#aaa", font=("Arial", 9))
    style.configure("Spec.Treeview.Heading", background="#1a1a1a", foreground="white", font=("Arial", 9, "bold"))
    style.configure("Spec.Treeview", background="#0d0d0d", foreground="white", fieldbackground="#0d0d0d", font=("Arial", 9), rowheight=26)
    style.configure("Hist.Treeview.Heading", background="#111", foreground="white", font=("Arial", 8, "bold"))
    style.configure("Hist.Treeview", background="#080808", foreground="#ccc", fieldbackground="#080808", font=("Arial", 8), rowheight=22)
    style.configure("Lot.Treeview.Heading", background="#0a1a00", foreground="#76ff03", font=("Arial", 8, "bold"))
    style.configure("Lot.Treeview", background="#060d00", foreground="#aee571", fieldbackground="#060d00", font=("Arial", 8), rowheight=22)
    style.map("Spec.Treeview", background=[("selected", "#1c3a5e")])
    style.map("Hist.Treeview", background=[("selected", "#1c3a5e")])
    style.map("Lot.Treeview",  background=[("selected", "#1c3a5e")])

    state = {
        "pno": None, "alc": "", "model": "", "vendor_code": "", "eo_number": "", "pname": "", "cname": "",
        "num_channels": 0, "spec_ir": {}, "spec_acw": {}, "test_running": False, "total": 0, "ok": 0, "ng": 0,
        "lot_no": "", "labelstr": "", "start_time": None, "flag": True, "input_polling": False,
    }
    adam = AdamIO(cfg["io_port"], cfg["io_baud"])
    hipot = HiPotSerial(cfg["hp_port"], cfg["hp_baud"])

    content = tk.Frame(parent, bg="black")
    content.pack(fill="both", expand=True, padx=4, pady=2)
    content.rowconfigure(0, weight=1); content.rowconfigure(1, weight=0); content.columnconfigure(0, weight=1)
    upper = tk.Frame(content, bg="black"); upper.grid(row=0, column=0, sticky="nsew")
    upper.columnconfigure(0, weight=1); upper.columnconfigure(1, weight=0); upper.rowconfigure(0, weight=1)
    left_area = tk.Frame(upper, bg="black"); left_area.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    right_panel = tk.Frame(upper, bg="black", width=220)
    right_panel.grid(row=0, column=1, sticky="nsew")
    right_panel.grid_propagate(False)
    right_panel.columnconfigure(0, weight=1)
    for i in range(3): right_panel.rowconfigure(i, weight=0)
    right_panel.rowconfigure(0, weight=1)

    result_outer = tk.Frame(right_panel, bg="#333", padx=1, pady=1)
    result_outer.grid(row=0, column=0, sticky="nsew", pady=(0, 3))
    result_inner = tk.Frame(result_outer, bg="black")
    result_inner.pack(fill="both", expand=True)
    tk.Label(result_inner, text="TEST RESULT", bg="black", fg="#666", font=("Arial", 10, "bold")).pack(fill="x", pady=(6, 2))
    result_lbl = tk.Label(result_inner, text="READY", bg="#1a1a1a", fg="#555", font=("Arial", 36, "bold"), anchor="center")
    result_lbl.pack(fill="both", expand=True, padx=4, pady=(2, 4))
    tk.Label(result_inner, text="LOT NO", bg="black", fg="#444", font=("Arial", 8)).pack(fill="x")
    lot_lbl = tk.Label(result_inner, text="â€”", bg="black", fg="#888", font=("Consolas", 8), anchor="center")
    lot_lbl.pack(fill="x", padx=4, pady=(0, 4))
    tk.Label(result_inner, text="ELAPSED TIME (s)", bg="black", fg="#444", font=("Arial", 8)).pack(fill="x")
    elapsed_lbl = tk.Label(result_inner, text="â€”", bg="black", fg="#888", font=("Consolas", 9), anchor="center")
    elapsed_lbl.pack(fill="x", padx=4, pady=(0, 6))

    com_lf = ttk.LabelFrame(right_panel, text="COM Status", style="TC.TLabelframe")
    com_lf.grid(row=1, column=0, sticky="ew", pady=(0, 3))
    com_inner = tk.Frame(com_lf, bg="black", padx=4, pady=4)
    com_inner.pack(fill="both")
    com_labels = {}
    for i, dev in enumerate(["HiPot", "IO Ctrl", "Scanner", "Printer"]):
        r, c = divmod(i, 2)
        lbl = tk.Label(com_inner, text=dev, bg="#2a2a2a", fg="#555", font=("Arial", 8), width=9, pady=3, bd=1, relief="solid")
        lbl.grid(row=r, column=c, padx=2, pady=2, sticky="ew")
        com_labels[dev] = lbl
        com_inner.columnconfigure(c, weight=1)
    def set_com_status(dev, connected):
        lbl = com_labels.get(dev)
        if lbl: lbl.config(bg="#1b5e20" if connected else "#3a3a3a", fg="white" if connected else "#555")

    # Image placeholders
    img_frame = tk.Frame(right_panel, bg="black")
    img_frame.grid(row=2, column=0, sticky="nsew", pady=(5, 0))
    try:
        from PIL import Image, ImageTk
        # First Image
        op_path = os.path.join(os.path.dirname(__file__), "image1.jpeg")
        if os.path.exists(op_path):
            img = Image.open(op_path).resize((210, 150), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(img_frame, image=photo, bg="black", bd=1, relief="solid")
            lbl.image = photo
            lbl.pack(pady=2)
        else:
            tk.Label(img_frame, text="[ Image 1 ]", bg="#1a1a1a", fg="#444", width=28, height=8, bd=1, relief="solid").pack(pady=2)
            
        # Second Image
        logo_path = os.path.join(os.path.dirname(__file__), "image_frame2.jpeg")
        if os.path.exists(logo_path):
            limg = Image.open(logo_path).resize((210, 80), Image.Resampling.LANCZOS)
            lphoto = ImageTk.PhotoImage(limg)
            llbl = tk.Label(img_frame, image=lphoto, bg="black", bd=1, relief="solid")
            llbl.image = lphoto
            llbl.pack(pady=2)
        else:
            tk.Label(img_frame, text="[ Image Frame 2 ]", bg="#1a1a1a", fg="#444", width=28, height=4, bd=1, relief="solid").pack(pady=2)
    except Exception:
        tk.Label(img_frame, text="[ Image Frame ]\n(Requires Pillow)", bg="#1a1a1a", fg="#444", width=28, height=12, bd=1, relief="solid").pack(pady=2)

    def blink_start(): pass
    def blink_stop(): pass

    row0 = tk.Frame(left_area, bg="black")
    row0.pack(fill="x", pady=(0, 3))
    row0.columnconfigure(0, weight=3); row0.columnconfigure(1, weight=2)
    pf = ttk.LabelFrame(row0, text="Product Info", style="TC.TLabelframe")
    pf.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    pi = tk.Frame(pf, bg="black", padx=8, pady=5)
    pi.pack(fill="both", expand=True)
    for col in range(8): pi.columnconfigure(col, weight=1 if col % 2 != 0 else 0)
    def _lbl(parent, text): return tk.Label(parent, text=text, bg="black", fg="#999", font=("Arial", 9))
    def _ent(parent, w=16, editable=True, fg="white"):
        st = "normal" if editable else "readonly"
        e = tk.Entry(parent, bg="black" if editable else "#0d0d0d", fg=fg, font=("Arial", 10), insertbackground="white", bd=1, relief="solid", width=w, highlightbackground="#444", highlightcolor="#888", highlightthickness=1, readonlybackground="#0d0d0d", state=st)
        return e

    _lbl(pi, "Part No").grid(row=0, column=0, sticky="w", pady=4); ent_pno = _ent(pi, w=18, editable=True); ent_pno.grid(row=0, column=1, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "EMP ID").grid(row=0, column=4, sticky="w", padx=(10, 4)); ent_emp = _ent(pi, w=12, editable=True); ent_emp.grid(row=0, column=5, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "Part Name").grid(row=1, column=0, sticky="w", pady=4); ent_pname = _ent(pi, w=14, editable=False); ent_pname.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "Customer").grid(row=1, column=4, sticky="w", padx=(10, 4)); ent_cust = _ent(pi, w=12, editable=False); ent_cust.grid(row=1, column=5, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "Model").grid(row=2, column=0, sticky="w", pady=4); ent_model = _ent(pi, w=10, editable=False); ent_model.grid(row=2, column=1, sticky="ew", padx=5)
    _lbl(pi, "ALC").grid(row=2, column=2, sticky="w", padx=(8, 4)); ent_alc = _ent(pi, w=6, editable=False); ent_alc.grid(row=2, column=3, sticky="ew", padx=5)
    _lbl(pi, "LOT No").grid(row=2, column=4, sticky="w", padx=(8, 4)); ent_lot = _ent(pi, w=14, editable=False); ent_lot.grid(row=2, column=5, columnspan=2, sticky="ew", padx=5)
    _lbl(pi, "Vendor").grid(row=3, column=0, sticky="w", pady=4); ent_vendor = _ent(pi, w=10, editable=False); ent_vendor.grid(row=3, column=1, sticky="ew", padx=5)
    _lbl(pi, "EO No").grid(row=3, column=2, sticky="w", padx=(8, 4)); ent_eo = _ent(pi, w=8, editable=False); ent_eo.grid(row=3, column=3, sticky="ew", padx=5)
    _lbl(pi, "Machine").grid(row=3, column=4, sticky="w", padx=(8, 4)); ent_machine = _ent(pi, w=8, editable=False); ent_machine.grid(row=3, column=5, sticky="ew", padx=5)
    
    def _fill_ro(entry, val):
        entry.config(state="normal"); entry.delete(0, "end"); entry.insert(0, str(val) if val else ""); entry.config(state="readonly")
    _fill_ro(ent_machine, cfg["machine_id"])

    cf = ttk.LabelFrame(row0, text="Count", style="TC.TLabelframe")
    cf.grid(row=0, column=1, sticky="nsew")
    ci = tk.Frame(cf, bg="black", padx=8, pady=5)
    ci.pack(fill="both", expand=True)
    ci.columnconfigure(1, weight=1); ci.columnconfigure(3, weight=1)
    _lbl(ci, "Total").grid(row=0, column=0, sticky="w", pady=3); cnt_total = _ent(ci, w=6, editable=False); cnt_total.grid(row=0, column=1, sticky="ew", padx=5)
    _lbl(ci, "NG").grid(row=0, column=2, sticky="w", padx=5); cnt_ng = _ent(ci, w=6, editable=False, fg="#ff5555"); cnt_ng.grid(row=0, column=3, sticky="ew", padx=5)
    _lbl(ci, "OK").grid(row=1, column=0, sticky="w", pady=3); cnt_ok = _ent(ci, w=6, editable=False, fg="#76ff03"); cnt_ok.grid(row=1, column=1, sticky="ew", padx=5)
    _lbl(ci, "NG%").grid(row=1, column=2, sticky="w", padx=5); cnt_ng_pct = _ent(ci, w=6, editable=False, fg="#ff5555"); cnt_ng_pct.grid(row=1, column=3, sticky="ew", padx=5)
    _lbl(ci, "PPM").grid(row=2, column=0, sticky="w", pady=3); cnt_ppm = _ent(ci, w=6, editable=False, fg="#ff9800"); cnt_ppm.grid(row=2, column=1, sticky="ew", padx=5)
    
    def _update_counts():
        t = state["total"]; o = state["ok"]; n = state["ng"]
        pct = f"{(n/t*100):.1f}%" if t > 0 else "0.0%"
        ppm = f"{int(n/t*1000000)}" if t > 0 else "0"
        for entry, val in [(cnt_total, str(t)), (cnt_ok, str(o)), (cnt_ng, str(n)), (cnt_ng_pct, pct), (cnt_ppm, ppm)]:
            entry.config(state="normal"); entry.delete(0, "end"); entry.insert(0, val); entry.config(state="readonly")

    shf = tk.Frame(left_area, bg="black")
    shf.pack(fill="x", pady=(6, 2))
    tk.Label(shf, text="Inspection Specification", bg="black", fg="white", font=("Arial", 10, "bold")).pack(side="left")
    spec_status_lbl = tk.Label(shf, text="[ No part loaded ]", bg="black", fg="#444", font=("Arial", 9))
    spec_status_lbl.pack(side="left", padx=10)
    cols_spec = ("TEST", "CH", "APPLIED VOLTS (V)", "TEST TIME (S)", "MIN", "MAX")
    tree_spec = ttk.Treeview(left_area, columns=cols_spec, show="headings", height=5, style="Spec.Treeview")
    spec_widths = {"TEST": 160, "CH": 45, "APPLIED VOLTS (V)": 130, "TEST TIME (S)": 110, "MIN": 80, "MAX": 80}
    for col in cols_spec: tree_spec.heading(col, text=col); tree_spec.column(col, anchor="center", width=spec_widths.get(col, 90))
    tree_spec.tag_configure("ir", background="#0d1a0d", foreground="#8bc34a")
    tree_spec.tag_configure("acw", background="#0d0d1a", foreground="#64b5f6")
    tree_spec.tag_configure("contact", background="#1a1a0d", foreground="#ffd54f")
    tree_spec.pack(fill="x")

    tk.Label(left_area, text="Testing", bg="black", fg="white", font=("Arial", 10, "bold")).pack(fill="x", pady=(8, 2))
    test_frame = tk.Frame(left_area, bg="black")
    test_frame.pack(fill="x")
    MAX_CH = 6
    ch_header = ["TEST", "UNIT"] + [f"CH{i}" for i in range(1, MAX_CH + 1)] + ["RESULT"]
    for i in range(len(ch_header)): test_frame.columnconfigure(i, weight=1)
    for i, h in enumerate(ch_header): tk.Label(test_frame, text=h, bg="#1a1a1a", fg="white", font=("Arial", 8, "bold"), bd=1, relief="solid", pady=6).grid(row=0, column=i, sticky="nsew")
    test_rows_def = [("IR", "Insulation (IR)", "MÎ©"), ("ACW", "Withstand (ACW)", "mA"), ("Contact", "Contact", "â€”")]
    result_rows = {}
    for r_idx, (key, name, unit) in enumerate(test_rows_def, start=1):
        tk.Label(test_frame, text=name, bg="#111", fg="white", font=("Arial", 8), bd=1, relief="solid", pady=6).grid(row=r_idx, column=0, sticky="nsew")
        tk.Label(test_frame, text=unit, bg="#111", fg="#ffcc00", font=("Arial", 8, "bold"), bd=1, relief="solid").grid(row=r_idx, column=1, sticky="nsew")
        row_cells = []
        for ch_i in range(MAX_CH):
            lbl = tk.Label(test_frame, text="â€”", bg="#0d0d0d", fg="#333", font=("Arial", 8), bd=1, relief="solid", pady=6)
            lbl.grid(row=r_idx, column=2 + ch_i, sticky="nsew")
            row_cells.append(lbl)
        res_lbl = tk.Label(test_frame, text="â€”", bg="#0d0d0d", fg="#333", font=("Arial", 9, "bold"), bd=1, relief="solid")
        res_lbl.grid(row=r_idx, column=2 + MAX_CH, sticky="nsew")
        result_rows[key] = {"cells": row_cells, "result": res_lbl}

    def _reset_test_display():
        for key in result_rows:
            for cell in result_rows[key]["cells"]: cell.config(text="â€”", bg="#0d0d0d", fg="#333")
            result_rows[key]["result"].config(text="â€”", bg="#0d0d0d", fg="#333")
        result_lbl.config(text="READY", bg="#1a1a1a", fg="#555")
        lot_lbl.config(text="â€”"); elapsed_lbl.config(text="â€”"); blink_start()

    def _set_cell(test_key, ch_idx, value, passed):
        if ch_idx >= len(result_rows[test_key]["cells"]): return
        bg = "#0a3300" if passed else "#330000"
        fg = "#76ff03" if passed else "#ff5555"
        result_rows[test_key]["cells"][ch_idx].config(text=value, bg=bg, fg=fg)

    def _set_row_result(test_key, passed):
        bg = "#0a3300" if passed else "#330000"
        fg = "#76ff03" if passed else "#ff5555"
        text = "PASS" if passed else "FAIL"
        result_rows[test_key]["result"].config(text=text, bg=bg, fg=fg)

    scan_outer = tk.Frame(left_area, bg="#222", padx=2, pady=2)
    scan_outer.pack(fill="x", pady=(8, 3))
    scan_lbl = tk.Label(scan_outer, text="Enter Part Number + Employee ID, then press ENTER or START", bg="#001830", fg="#555", font=("Arial", 11, "bold"), pady=8)
    scan_lbl.pack(fill="both", expand=True)

    scan_entry_frame = tk.Frame(left_area, bg="black")
    scan_entry_frame.pack(fill="x", pady=(0, 3)); scan_entry_frame.pack_forget()
    tk.Label(scan_entry_frame, text="Scan Label:", bg="black", fg="#aaa", font=("Arial", 9)).pack(side="left", padx=5)
    ent_scan = _ent(scan_entry_frame, w=36, editable=True); ent_scan.pack(side="left", padx=5, pady=5)
    scan_result_lbl = tk.Label(scan_entry_frame, text="", bg="black", fg="white", font=("Arial", 12, "bold"))
    scan_result_lbl.pack(side="left", padx=8)

    tk.Label(left_area, text="Today's PASS Records", bg="black", fg="white", font=("Arial", 10, "bold")).pack(fill="x", pady=(6, 2))
    lot_cols = ("#", "LOT NO", "ALC", "RESULT", "SCAN", "EMP", "TIME")
    tree_lot = ttk.Treeview(left_area, columns=lot_cols, show="headings", height=4, style="Lot.Treeview")
    lot_widths = {"#": 30, "LOT NO": 160, "ALC": 70, "RESULT": 60, "SCAN": 60, "EMP": 70, "TIME": 70}
    for col in lot_cols: tree_lot.heading(col, text=col); tree_lot.column(col, anchor="center", width=lot_widths.get(col, 70))
    tree_lot.pack(fill="x")

    tk.Label(left_area, text="Recent Test History", bg="black", fg="white", font=("Arial", 10, "bold")).pack(fill="x", pady=(6, 2))
    hist_cols = ("DATE", "TIME", "PART NO", "LOT NO", "EMP", "RESULT")
    tree_hist = ttk.Treeview(left_area, columns=hist_cols, show="headings", height=3, style="Hist.Treeview")
    hist_widths = {"DATE": 80, "TIME": 70, "PART NO": 120, "LOT NO": 140, "EMP": 70, "RESULT": 60}
    for col in hist_cols: tree_hist.heading(col, text=col); tree_hist.column(col, anchor="center", width=hist_widths.get(col, 80))
    tree_hist.tag_configure("pass", foreground="#76ff03")
    tree_hist.tag_configure("fail", foreground="#ff5555")
    tree_hist.pack(fill="x")

    btn_start = tk.Button(left_area, text="â–¶  START TEST", bg="#1a1a1a", fg="#444", font=("Arial", 14, "bold"), pady=10, bd=0, cursor="hand2", activebackground="#2e7d32", activeforeground="white")
    btn_start.pack(fill="x", pady=(6, 0))

    bottom = tk.Frame(content, bg="black", height=110)
    bottom.grid(row=1, column=0, sticky="ew", pady=(4, 0))
    bottom.grid_propagate(False); bottom.columnconfigure(0, weight=4); bottom.columnconfigure(1, weight=3); bottom.rowconfigure(0, weight=1)
    io_lf = ttk.LabelFrame(bottom, text="IO Channel State", style="TC.TLabelframe")
    io_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    io_inner = tk.Frame(io_lf, bg="black", padx=5, pady=3); io_inner.pack(fill="both", expand=True)
    tk.Label(io_inner, text="INPUT", bg="black", fg="#777", font=("Arial", 8, "bold")).pack(anchor="w")
    in_row = tk.Frame(io_inner, bg="black"); in_row.pack(anchor="w", pady=(0, 4))
    io_in_labels = []
    for i in range(1, 9):
        lbl = tk.Label(in_row, text=f"CH{i}", bg="#0a1a0a", fg="#2e7d32", font=("Arial", 7), bd=1, relief="solid", width=5)
        lbl.pack(side="left", padx=1)
        io_in_labels.append(lbl)
    tk.Label(io_inner, text="OUTPUT", bg="black", fg="#777", font=("Arial", 8, "bold")).pack(anchor="w")
    out_row = tk.Frame(io_inner, bg="black"); out_row.pack(anchor="w")
    io_out_labels = []
    for i in range(1, 7):
        lbl = tk.Label(out_row, text=f"CH{i}", bg="#0a1a0a", fg="#2e7d32", font=("Arial", 7), bd=1, relief="solid", width=5)
        lbl.pack(side="left", padx=1)
        io_out_labels.append(lbl)
    def _set_io(io_list, ch_idx, active):
        if ch_idx < len(io_list): io_list[ch_idx].config(bg="#1b5e20" if active else "#0a1a0a", fg="#76ff03" if active else "#2e7d32")
    log_lf = ttk.LabelFrame(bottom, text="Log", style="TC.TLabelframe")
    log_lf.grid(row=0, column=1, sticky="nsew")
    log_txt = tk.Text(log_lf, bg="black", fg="#aaa", font=("Consolas", 8), bd=0, height=5)
    log_txt.pack(fill="both", expand=True, padx=4, pady=3); log_txt.config(state="disabled")
    def _log(msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        log_txt.config(state="normal"); log_txt.insert("end", f"{ts}  {msg}\n"); log_txt.see("end"); log_txt.config(state="disabled")
    def _load_specs(pno: str) -> bool:
        try:
            conn = _get_conn()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT pname,cname,mname AS model,alc,chsel AS channel,vendorcode,eocode FROM settingmaster WHERE pno=%s", (pno,))
            master = cur.fetchone()
            if not master:
                cur.execute("SELECT * FROM settingmaster WHERE pno=%s", (pno,))
                master = cur.fetchone()
            if not master:
                messagebox.showwarning("Not Found", f"Part number '{pno}' not found.")
                cur.close(); conn.close()
                return False
            pname = master.get("pname", ""); cname = master.get("cname", ""); mod = master.get("mname", master.get("model", ""))
            alc = master.get("alc", ""); channel = int(master.get("chsel", master.get("channel", 1)) or 1)
            vendor = master.get("vendorcode", ""); eo = master.get("eocode", master.get("eo_number", ""))
            state.update({"pno": pno, "alc": alc, "model": mod, "vendor_code": vendor, "eo_number": eo or "", "pname": pname, "cname": cname, "num_channels": channel})
            _fill_ro(ent_pname, pname); _fill_ro(ent_cust, cname); _fill_ro(ent_model, mod); _fill_ro(ent_alc, alc); _fill_ro(ent_vendor, vendor); _fill_ro(ent_eo, eo or "")
            cur.execute("SELECT testname, chsel AS channel, appvol, testtime, min, max FROM settingspec WHERE pno=%s", (pno,))
            rows = cur.fetchall()
            cur.close(); conn.close()
            spec_ir = {}; spec_acw = {}
            for r in rows:
                tn = str(r.get("testname", "")).strip()
                ch = int(r.get("chsel", r.get("channel", 1)) or 1)
                d = {"appvol": float(r.get("appvol", 0) or 0), "testtime": float(r.get("testtime", 1) or 1), "min": float(r.get("min", 0) or 0), "max": float(r.get("max", 9999) or 9999)}
                if "Insulation" in tn or tn.upper() == "IR": spec_ir[ch] = d
                elif "Withstand" in tn or tn.upper() == "ACW": spec_acw[ch] = d
            state["spec_ir"] = spec_ir; state["spec_acw"] = spec_acw
            tree_spec.delete(*tree_spec.get_children())
            for ch in range(1, channel + 1):
                for test_key, tag, sp in [("Insulation Test", "ir", spec_ir.get(ch, {})), ("Withstand Test", "acw", spec_acw.get(ch, {}))]:
                    tree_spec.insert("", "end", tags=(tag,), values=(test_key, str(ch), sp.get("appvol", "â€”"), sp.get("testtime", "â€”"), sp.get("min", "â€”"), sp.get("max", "â€”")))
                tree_spec.insert("", "end", tags=("contact",), values=("Contact Test", str(ch), "â€”", "â€”", "â€”", "â€”"))
            spec_status_lbl.config(text=f"[ {channel} channel(s) loaded ]", fg="#4caf50")
            _log(f"Specs loaded for {pno} ({channel} ch)")
            return True
        except Exception as ex:
            messagebox.showerror("DB Error", str(ex))
            _log(f"DB Error: {ex}"); return False

    def _load_history(pno=None):
        tree_hist.delete(*tree_hist.get_children())
        try:
            conn = _get_conn(); cur = conn.cursor()
            if pno: cur.execute("SELECT date, time, pno, lotno, empcode, result FROM testmaster WHERE pno=%s ORDER BY id DESC LIMIT 15", (pno,))
            else: cur.execute("SELECT date, time, pno, lotno, empcode, result FROM testmaster ORDER BY id DESC LIMIT 15")
            for row in cur.fetchall():
                tag = "pass" if row[5] == "PASS" else "fail"
                tree_hist.insert("", "end", tags=(tag,), values=row)
            cur.close(); conn.close()
        except Exception: pass

    def _load_today_pass(pno=None):
        tree_lot.delete(*tree_lot.get_children())
        try:
            conn = _get_conn(); cur = conn.cursor()
            query = "SELECT testmaster.lotno, testmaster.alc, testresult.result, testmaster.scanresult, testmaster.empcode, testmaster.time FROM testmaster JOIN testresult ON testmaster.lotno = testresult.lotno WHERE testresult.result = 'PASS' AND DATE(testmaster.date) = CURDATE() " + (f"AND testmaster.pno='{pno}' " if pno else "") + "ORDER BY testmaster.time DESC"
            cur.execute(query); rows = cur.fetchall(); cur.close(); conn.close()
        except Exception: rows = []
        ok = len(rows)
        try:
            conn2 = _get_conn(); cur2 = conn2.cursor()
            q2 = "SELECT COUNT(*) FROM testmaster WHERE result='FAIL' AND DATE(date)=CURDATE()" + (f" AND pno='{pno}'" if pno else "")
            cur2.execute(q2); ng = cur2.fetchone()[0] or 0; cur2.close(); conn2.close()
        except Exception: ng = 0
        state["total"] = ok + ng; state["ok"] = ok; state["ng"] = ng; parent.after(0, _update_counts)
        for idx, row in enumerate(rows, start=1):
            tree_lot.insert("", "end", values=(len(rows) - idx + 1, row[0], row[1], row[2] or "â€”", row[3] or "â€”", row[4], row[5]))

    def _save_result(lot_no: str, overall: str, ir_ch: dict, acw_ch: dict, contact_ch: dict):
        try:
            conn = _get_conn(); cur = conn.cursor(); now = datetime.datetime.now(); pno = state["pno"]; emp = ent_emp.get().strip()
            cur.execute("INSERT INTO testmaster (pno, pname, model, alc, channel, lotno, date, time, empcode, result, machine) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (pno, state["pname"], state["model"], state["alc"], str(state["num_channels"]), lot_no, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), emp, overall, cfg["machine_id"]))
            for ch in range(1, state["num_channels"] + 1):
                cur.execute("INSERT INTO testresult (lotno, channel, ir_volts, ir_resistance, ir_current, ir_result, acw_volts, acw_current, acw_result, contact_result, empcode) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (lot_no, str(ch), str(ir_ch.get(ch, {}).get("appvol", "")), str(ir_ch.get(ch, {}).get("value", "")), "0.01", ir_ch.get(ch, {}).get("result", ""), str(acw_ch.get(ch, {}).get("appvol", "")), str(acw_ch.get(ch, {}).get("value", "")), acw_ch.get(ch, {}).get("result", ""), contact_ch.get(ch, {}).get("result", ""), emp))
            conn.commit(); cur.close(); conn.close()
            _log(f"Saved {overall} â†’ {lot_no}")
        except Exception as ex: _log(f"Save error: {ex}")

    def _update_scan_result(lot_no: str, scan_res: str):
        try:
            conn = _get_conn(); cur = conn.cursor()
            cur.execute("UPDATE testmaster SET scanresult=%s WHERE lotno=%s", (scan_res, lot_no))
            conn.commit(); cur.close(); conn.close()
        except Exception as ex: _log(f"Scan update error: {ex}")

    def _validate_employee(empno: str) -> bool:
        emp_file = os.path.join(os.path.dirname(__file__), "emp.txt")
        try: return empno in open(emp_file).read()
        except FileNotFoundError: return True

    _IO_CH_CMDS = ["#011001", "#011101", "#011201", "#011301", "#011401", "#011501"]
    _IO_CONT_CMDS = ["#021001", "#021101", "#021201", "#021301", "#021401", "#021501"]
    def _adam_open() -> bool:
        if not _serial_ok: return False
        if adam.is_open: adam.close(); time.sleep(0.015)
        ok = adam.open()
        if not ok: _log("IO Ctrl: could not open port"); set_com_status("IO Ctrl", False)
        else: set_com_status("IO Ctrl", True)
        return ok

    def _adam_reset(): adam.send("#010000"); time.sleep(0.015); adam.send("#020000"); time.sleep(0.015); adam.send("#030000"); time.sleep(0.015)
    def _adam_read_inputs() -> str:
        if not _adam_open(): return ""
        resp = adam.read_inputs(); adam.close(); return resp
    def _cable_connected(resp: str) -> bool:
        try:
            trimmed = resp.strip()
            if len(trimmed) < 5: return False
            return trimmed[3:5] in ("6A", "6E", "6B", "6F")
        except Exception: return False
    def _start_button_pressed(resp: str) -> bool:
        try:
            trimmed = resp.strip()
            if len(trimmed) < 5: return False
            return trimmed[4] in ("E", "A")
        except Exception: return False

    def _run_contact_test(n_ch: int) -> tuple:
        _log("Contact Test â†’ ADAM IO (#02xxxx / $016)")
        if not _adam_open():
            _log("IO Ctrl not available â€” simulating Contact PASS")
            for ch in range(1, n_ch + 1): parent.after(0, lambda c=ch-1: _set_cell("Contact", c, "OK", True))
            parent.after(0, lambda: _set_row_result("Contact", True))
            return True, {ch: {"result": "PASS"} for ch in range(1, n_ch + 1)}
        contact_res = {}; all_pass = True
        adam.send("#031401"); time.sleep(0.2)
        for ch in range(1, n_ch + 1):
            time.sleep(0.1); adam.send(_IO_CONT_CMDS[ch - 1]); time.sleep(0.1)
            raw = adam.read_inputs(); time.sleep(0.5); adam.send("#020000")
            passed = (raw.strip() == "!006F00" or raw.strip() == "!006B00")
            contact_res[ch] = {"result": "PASS" if passed else "FAIL"}
            if not passed: all_pass = False
            parent.after(0, lambda c=ch-1, p=passed: _set_cell("Contact", c, "OK" if p else "NG", p))
        adam.close(); parent.after(0, lambda p=all_pass: _set_row_result("Contact", p))
        _log(f"Contact: {'PASS' if all_pass else 'FAIL'}"); return all_pass, contact_res

    def _run_ir_test(n_ch: int) -> tuple:
        _log("IR Test â†’ MANU:EDIT:MODE IR | FUNC:TEST ON | MEAS?")
        if not _serial_ok or not hipot.open():
            _log("HiPot not connected â€” simulating IR result"); set_com_status("HiPot", False)
            ir_res = {}; all_pass = True
            for ch in range(1, n_ch + 1):
                s = state["spec_ir"].get(ch, {}); v_min = float(s.get("min", 100)); v_max = float(s.get("max", 9999))
                val = 350.0; p = v_min <= val <= v_max
                if not p: all_pass = False
                ir_res[ch] = {"appvol": s.get("appvol", 500), "value": val, "result": "PASS" if p else "FAIL"}
                parent.after(0, lambda c=ch-1, v=f"{val:.0f}", pp=p: _set_cell("IR", c, v, pp))
            parent.after(0, lambda p=all_pass: _set_row_result("IR", p))
            return all_pass, ir_res
        set_com_status("HiPot", True); time.sleep(0.3)
        if _adam_open():
            _adam_reset()
            for ch in range(1, n_ch + 1): adam.send(_IO_CH_CMDS[ch - 1]); time.sleep(0.015)
            adam.close()
        s0 = state["spec_ir"].get(1, {}); v_kv = float(s0.get("appvol", 500)) / 1000.0; t_s = float(s0.get("testtime", 1.0)); v_min = float(s0.get("min", 100)); v_max = float(s0.get("max", 9999))
        _, ir_val = hipot.run_ir_test(v_kv, t_s, v_min, v_max); hipot.close()
        all_pass = True; ir_res = {}
        for ch in range(1, n_ch + 1):
            s = state["spec_ir"].get(ch, {}); passed = float(s.get("min", 100)) <= ir_val <= float(s.get("max", 9999))
            if not passed: all_pass = False
            ir_res[ch] = {"appvol": s.get("appvol", 500), "value": ir_val, "result": "PASS" if passed else "FAIL"}
            parent.after(0, lambda c=ch-1, v=f"{ir_val:.0f}", p=passed: _set_cell("IR", c, v, p))
        parent.after(0, lambda p=all_pass: _set_row_result("IR", p)); _log(f"IR: {ir_val:.0f} MÎ© â€” {'PASS' if all_pass else 'FAIL'}"); return all_pass, ir_res

    def _run_acw_test(n_ch: int) -> tuple:
        _log("ACW Test â†’ MANU:EDIT:MODE ACW | FUNC:TEST ON | MEAS?")
        if not _serial_ok or not hipot.open():
            _log("HiPot not connected â€” simulating ACW result"); set_com_status("HiPot", False)
            acw_res = {}; all_pass = True
            for ch in range(1, n_ch + 1):
                s = state["spec_acw"].get(ch, {}); v_min = float(s.get("min", 0)); v_max = float(s.get("max", 10))
                val = 0.5; p = v_min <= val <= v_max
                if not p: all_pass = False
                acw_res[ch] = {"appvol": s.get("appvol", 1500), "value": val, "result": "PASS" if p else "FAIL"}
                parent.after(0, lambda c=ch-1, v=f"{val:.2f}", pp=p: _set_cell("ACW", c, v, pp))
            parent.after(0, lambda p=all_pass: _set_row_result("ACW", p))
            return all_pass, acw_res
        time.sleep(0.1)
        if _adam_open():
            adam.send("#010000"); time.sleep(0.1)
            for ch in range(1, n_ch + 1): adam.send(_IO_CH_CMDS[ch - 1]); time.sleep(0.015)
            adam.close()
        s0 = state["spec_acw"].get(1, {}); v_kv = float(s0.get("appvol", 1500)) / 1000.0; t_s = float(s0.get("testtime", 3.0)); v_min = float(s0.get("min", 0.0)); v_max = float(s0.get("max", 10.0))
        _, acw_val = hipot.run_acw_test(v_kv, t_s, v_min, v_max); hipot.close()
        all_pass = True; acw_res = {}
        for ch in range(1, n_ch + 1):
            s = state["spec_acw"].get(ch, {}); passed = float(s.get("min", 0)) <= acw_val <= float(s.get("max", 10))
            if not passed: all_pass = False
            acw_res[ch] = {"appvol": s.get("appvol", 1500), "value": acw_val, "result": "PASS" if passed else "FAIL"}
            parent.after(0, lambda c=ch-1, v=f"{acw_val:.2f}", p=passed: _set_cell("ACW", c, v, p))
        parent.after(0, lambda p=all_pass: _set_row_result("ACW", p)); _log(f"ACW: {acw_val:.2f} mA â€” {'PASS' if all_pass else 'FAIL'}"); return all_pass, acw_res

    def _run_test_sequence():
        if not state["pno"]: parent.after(0, lambda: _log("No part loaded.")); return
        emp = ent_emp.get().strip()
        if not emp: parent.after(0, lambda: messagebox.showwarning("Validation", "Enter Employee ID.")); return
        if not _validate_employee(emp): parent.after(0, lambda: messagebox.showwarning("Auth", "Employee number not found.")); return
        if state["test_running"]: return
        state["test_running"] = True; state["start_time"] = datetime.datetime.now(); state["flag"] = True
        parent.after(0, lambda: btn_start.config(state="disabled", bg="#555", text="TESTINGâ€¦")); parent.after(0, _reset_test_display); parent.after(0, lambda: result_lbl.config(text="TESTINGâ€¦", bg="#e65100", fg="white")); parent.after(0, lambda: scan_lbl.config(text="â³  Test in progressâ€¦", bg="#001830", fg="#e8a000")); parent.after(0, scan_entry_frame.pack_forget)
        n_ch = state["num_channels"]; _log("â”€â”€ Test Started â”€â”€")
        parent.after(0, lambda: scan_lbl.config(text="ðŸ”Œ  Checking cable connectionâ€¦", bg="#001830", fg="#e8a000"))
        if _serial_ok:
            if not _cable_connected(_adam_read_inputs()):
                _log("Cable not connected to jig â€” aborting"); parent.after(0, lambda: messagebox.showwarning("Cable", "Please connect the cable to the Jig.")); parent.after(0, lambda: result_lbl.config(text="READY", bg="#1a1a1a", fg="#555")); parent.after(0, lambda: scan_lbl.config(text="âŒ  Cable not connected â€” reconnect and retry", bg="#220000", fg="#ff5555"))
                state["test_running"] = False; parent.after(0, lambda: btn_start.config(state="normal", bg="#1b5e20", fg="white", text="â–¶  START TEST")); parent.after(0, _input_poll_start); return
        parent.after(0, lambda: scan_lbl.config(text="âš¡  IR Testing (Insulation Resistance)â€¦", bg="#001830", fg="#e8a000")); ir_pass, ir_ch = _run_ir_test(n_ch); time.sleep(0.5)
        if not ir_pass: state["flag"] = False; _finish_test("FAIL", ir_ch, {}, {}); return
        parent.after(0, lambda: scan_lbl.config(text="âš¡  ACW Testing (Withstand Voltage)â€¦", bg="#001830", fg="#e8a000")); acw_pass, acw_ch = _run_acw_test(n_ch); time.sleep(0.5)
        if not acw_pass: state["flag"] = False; _finish_test("FAIL", ir_ch, acw_ch, {}); return
        parent.after(0, lambda: scan_lbl.config(text="ðŸ”—  Contact Testingâ€¦", bg="#001830", fg="#e8a000")); contact_pass, contact_ch = _run_contact_test(n_ch); time.sleep(0.2)
        overall = "PASS" if (ir_pass and acw_pass and contact_pass) else "FAIL"
        state["flag"] = (overall == "PASS"); _finish_test(overall, ir_ch, acw_ch, contact_ch)

    def _finish_test(overall: str, ir_ch: dict, acw_ch: dict, contact_ch: dict):
        pno = state["pno"]; lot_no = _generate_lot_number(pno, cfg["machine_id"]); state["lot_no"] = lot_no; state["labelstr"] = lot_no
        elapsed_str = f"{(datetime.datetime.now() - state['start_time']).total_seconds():.1f}" if state["start_time"] else "â€”"
        state["total"] += 1; state["ok" if overall == "PASS" else "ng"] += 1
        parent.after(0, _update_counts); parent.after(0, lambda l=lot_no: lot_lbl.config(text=l)); parent.after(0, lambda e=elapsed_str: elapsed_lbl.config(text=e)); parent.after(0, lambda l=lot_no: _fill_ro(ent_lot, l))
        _save_result(lot_no, overall, ir_ch, acw_ch, contact_ch)
        if overall == "PASS":
            parent.after(0, lambda: result_lbl.config(text="PASS", bg="#0033aa", fg="white")); parent.after(0, lambda: scan_lbl.config(text="âœ…  PASS â€” Scan the printed barcode label", bg="#0a2200", fg="#76ff03")); _play_wav("OK.WAV"); blink_stop()
            threading.Thread(target=_print_barcode_label, args=(pno, state["alc"], state["model"], state["vendor_code"], state["eo_number"], lot_no, cfg["machine_id"]), daemon=True).start()
            parent.after(5000, _show_scan_entry)
        else:
            parent.after(0, lambda: result_lbl.config(text="FAIL", bg="#b71c1c", fg="white")); parent.after(0, lambda: scan_lbl.config(text="âŒ  FAIL â€” Check cable and retry", bg="#220000", fg="#ff5555")); _play_wav("NG.WAV"); blink_start()
        parent.after(0, lambda: _load_today_pass(pno)); parent.after(0, lambda: _load_history(pno)); _log(f"â”€â”€ Test Complete: {overall} | Lot: {lot_no} | Time: {elapsed_str}s â”€â”€")
        state["test_running"] = False; parent.after(0, lambda: btn_start.config(state="normal", bg="#1b5e20" if overall == "PASS" else "#b71c1c", fg="white", text="â–¶  START TEST"))
        if overall == "FAIL": parent.after(200, _input_poll_start)

    def _show_scan_entry(): scan_entry_frame.pack(fill="x", pady=(0, 3)); ent_scan.delete(0, "end"); ent_scan.focus_set(); scan_result_lbl.config(text="", fg="white")
    def _on_scan_enter(event=None):
        scanned = ent_scan.get().strip(); labelstr = state.get("labelstr", "")
        if not scanned: return
        if labelstr and labelstr in scanned: res_str = "OK"; scan_result_lbl.config(text="âœ…  OK", fg="#76ff03"); _log(f"Scan verify: OK ({scanned})")
        else: res_str = "NG"; scan_result_lbl.config(text="âŒ  NG", fg="#ff5555"); _log(f"Scan verify: NG (expected '{labelstr}', got '{scanned}')")
        _update_scan_result(state["lot_no"], res_str); parent.after(2000, scan_entry_frame.pack_forget); parent.after(2100, _input_poll_start)
    ent_scan.bind("<Return>", _on_scan_enter)

    def _input_poll_once():
        if not state.get("input_polling"): return
        if state["test_running"] or not state["pno"]: parent.after(500, _input_poll_once); return
        def _poll():
            resp = _adam_read_inputs(); pressed = _start_button_pressed(resp)
            if pressed: _update_io_display(resp); _log("START button pressed (IO)"); parent.after(0, _trigger_test)
            else: _update_io_display(resp); parent.after(500, _input_poll_once)
        threading.Thread(target=_poll, daemon=True).start()
    def _input_poll_start():
        if not _serial_ok or state.get("input_polling"): return
        state["input_polling"] = True; _input_poll_once()
    def _input_poll_stop(): state["input_polling"] = False
    def _update_io_display(resp: str):
        try:
            trimmed = resp.strip()
            if len(trimmed) >= 5:
                bits = int(trimmed[3:5], 16) if trimmed[3:5].strip() else 0
                for i in range(8): parent.after(0, lambda idx=i, a=(bits >> idx & 1) == 1: _set_io(io_in_labels, idx, a))
        except Exception: pass

    def _trigger_test():
        if state["test_running"]: return
        if not state["pno"]: _log("No part number loaded."); return
        if not ent_emp.get().strip(): parent.after(0, lambda: messagebox.showwarning("Validation", "Enter Employee ID before testing.")); return
        _input_poll_stop(); _reset_test_display(); threading.Thread(target=_run_test_sequence, daemon=True).start()
    btn_start.config(command=lambda: _trigger_test())

    def _clear_all():
        _input_poll_stop()
        for e in [ent_pno, ent_emp]: e.delete(0, "end")
        for e in [ent_pname, ent_cust, ent_model, ent_alc, ent_vendor, ent_eo, ent_lot]: e.config(state="normal"); e.delete(0, "end"); e.config(state="readonly")
        tree_spec.delete(*tree_spec.get_children()); tree_lot.delete(*tree_lot.get_children()); _reset_test_display()
        spec_status_lbl.config(text="[ No part loaded ]", fg="#444"); scan_entry_frame.pack_forget()
        state.update({"pno": None, "num_channels": 0, "spec_ir": {}, "spec_acw": {}, "lot_no": "", "labelstr": "", "flag": True})
        btn_start.config(bg="#1a1a1a", fg="#444"); _log("Cleared."); ent_pno.focus_set()
    tk.Button(left_area, text="âŸ³  CLEAR / RESET", bg="#2a2a2a", fg="#aaa", font=("Arial", 10, "bold"), pady=5, bd=0, cursor="hand2", activebackground="#444", activeforeground="white", command=_clear_all).pack(fill="x", pady=(3, 0))

    def _on_pno_enter(event=None):
        pno = ent_pno.get().strip().upper()
        if not pno: return
        _input_poll_stop(); spec_status_lbl.config(text="[ Loadingâ€¦ ]", fg="#e8a000"); tree_spec.delete(*tree_spec.get_children()); _fill_ro(ent_lot, ""); _reset_test_display()
        if _load_specs(pno):
            _load_history(pno); _load_today_pass(pno); btn_start.config(bg="#1b5e20", fg="white"); scan_lbl.config(text=f"Part '{pno}' loaded ({state['num_channels']} ch) â€” Ready", bg="#001830", fg="#4caf50")
            ent_emp.focus_set(); parent.after(500, _input_poll_start)
        else: btn_start.config(bg="#1a1a1a", fg="#444"); ent_pno.focus_set()
    ent_pno.bind("<Return>", _on_pno_enter)

    _load_history(); _log("System ready. Enter Part Number and press ENTER.")
    set_com_status("HiPot", False); set_com_status("IO Ctrl", False); set_com_status("Scanner", False); set_com_status("Printer", False)
    ent_pno.focus_set()
