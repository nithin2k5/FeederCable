import tkinter as tk
from tkinter import ttk
import threading
from pymodbus.client import ModbusSerialClient
import os
import configparser

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

    _CFG_PATH = os.path.join(os.path.dirname(__file__), "comport_cfg.ini")
    cfg = configparser.ConfigParser()
    if os.path.exists(_CFG_PATH):
        cfg.read(_CFG_PATH)
    if "COM" not in cfg:
        cfg["COM"] = {}
        
    devices = [
        ("HIPOT", cfg["COM"].get("hp_port", "0"), cfg["COM"].get("hp_baud", "0"), "-"),
        ("LCR METER", cfg["COM"].get("lcr_port", "0"), cfg["COM"].get("lcr_baud", "0"), "-"),
        ("PLC", cfg["COM"].get("plc_port", "0"), cfg["COM"].get("plc_baud", "0"), "01"),
        ("Delta PLC", cfg["COM"].get("io_port", "0"), cfg["COM"].get("io_baud", "0"), "01"),
        ("IO Controller Cable", cfg["COM"].get("ioc_port", "0"), cfg["COM"].get("ioc_baud", "0"), "-"),
        ("Label Printer", cfg["COM"].get("printer_port", "0"), cfg["COM"].get("printer_baud", "0"), "-"),
        ("Scanner", cfg["COM"].get("scanner_port", "0"), cfg["COM"].get("scanner_baud", "0"), "-"),
    ]

    import serial.tools.list_ports
    
    # Fetch available COM ports
    available_ports = [port.device for port in serial.tools.list_ports.comports()]
    if not available_ports:
        available_ports = ["COM 1", "COM 2", "COM 3"]

    def mk_combo(parent, vals, current_val):
        cb = ttk.Combobox(parent, values=vals, font=('Arial', 10), width=10, state="readonly")
        if current_val in vals:
            cb.set(current_val)
        elif vals:
            cb.current(0)
        return cb

    baud_rates = ["9600", "14400", "19200", "38400", "57600", "115200"]
    sids = ["-", "01", "02", "03", "04", "05"]

    def log_msg(msg):
        log_text.config(state="normal")
        log_text.insert("end", msg + "\n")
        log_text.see("end")
        log_text.config(state="disabled")

    def test_connection(dev, cb_port, cb_baud, cb_sid, btn):
        if dev in ["PLC", "Delta PLC"]:
            port = cb_port.get()
            baud = cb_baud.get()
            sid_str = cb_sid.get()
            
            if port == "None" or not port:
                log_msg(f"{dev}: No port selected.")
                return
                
            try:
                baud_val = int(baud)
                sid_val = int(sid_str) if sid_str != "-" else 1
            except ValueError:
                log_msg(f"{dev}: Invalid baud rate or station ID.")
                return

            def _update_btn(text, bg, fg="white"):
                parent.after(0, lambda: btn.config(text=text, bg=bg, fg=fg))

            def _run_test():
                _update_btn("TESTING...", "#ff9800", "black")
                log_msg(f"Testing {dev} on {port} (Baud: {baud_val}, ID: {sid_val})...")
                try:
                    if dev == "Delta PLC":
                        # Delta PLC usually uses Modbus ASCII, 7, E, 1
                        client = ModbusSerialClient(framer='ascii', port=port, baudrate=baud_val, bytesize=7, parity='E', stopbits=1, timeout=1.5)
                    else:
                        # Generic PLC usually uses Modbus RTU, 8, N, 1
                        client = ModbusSerialClient(framer='rtu', port=port, baudrate=baud_val, bytesize=8, parity='N', stopbits=1, timeout=1.5)
                        
                    try:
                        if client.connect():
                            res = client.read_discrete_inputs(0, count=11, device_id=sid_val)
                            if res.isError():
                                log_msg(f"{dev} Error: Connected but no valid response.")
                                _update_btn("FAIL", "#f44336")
                            else:
                                log_msg(f"{dev} Success: Read P0-P10 values {res.bits[:11]} from {port}.")
                                _update_btn("PASS", "#4caf50")
                        else:
                            log_msg(f"{dev} Error: Could not open {port}.")
                            _update_btn("FAIL", "#f44336")
                    finally:
                        client.close()
                except Exception as e:
                    log_msg(f"{dev} Exception: {str(e)}")
                    _update_btn("FAIL", "#f44336")

            threading.Thread(target=_run_test, daemon=True).start()
        elif dev == "HIPOT":
            port = cb_port.get()
            baud = cb_baud.get()
            if port == "None" or not port:
                log_msg(f"{dev}: No port selected.")
                return
            try:
                baud_val = int(baud)
            except ValueError:
                log_msg(f"{dev}: Invalid baud rate.")
                return

            def _update_btn(text, bg, fg="white"):
                parent.after(0, lambda: btn.config(text=text, bg=bg, fg=fg))

            def _run_hipot_test():
                _update_btn("TESTING...", "#ff9800", "black")
                log_msg(f"Testing {dev} on {port} (Baud: {baud_val})...")
                try:
                    import serial
                    import time
                    ser = serial.Serial(port, baud_val, timeout=1.5, write_timeout=0.5)
                    ser.reset_input_buffer()
                    # Send standard SCPI identification query
                    ser.write(b"*IDN?\r\n")
                    time.sleep(0.1)
                    response = ser.readline().decode('ascii', errors='ignore').strip()
                    ser.close()
                    
                    if response:
                        log_msg(f"{dev} Success: Connected! Device responded: {response}")
                        _update_btn("PASS", "#4caf50")
                    else:
                        log_msg(f"{dev} Warning: Port opened, but no response received.")
                        _update_btn("FAIL", "#f44336")
                except Exception as e:
                    log_msg(f"{dev} Error: {str(e)}")
                    _update_btn("FAIL", "#f44336")

            threading.Thread(target=_run_hipot_test, daemon=True).start()
        else:
            log_msg(f"{dev}: Test not implemented yet.")

    combos = {}
    for r, (dev, port, baud, sid) in enumerate(devices, start=1):
        tk.Label(table_frame, text=dev, bg="#12151b", fg="white", font=('Arial', 11)).grid(row=r, column=0, sticky="w", padx=15, pady=10)
        
        # COM Port
        port_list = list(available_ports)
        if port not in port_list and port != "None":
            port_list.append(port)
        cb_port = mk_combo(table_frame, port_list, port)
        cb_port.grid(row=r, column=1, padx=15)
        
        # Hyphen
        tk.Label(table_frame, text="-", bg="#12151b", fg="white", font=('Arial', 11)).grid(row=r, column=2, padx=5)
        
        # Baud Rate
        baud_list = list(baud_rates)
        if baud not in baud_list:
            baud_list.append(baud)
        cb_baud = mk_combo(table_frame, baud_list, baud)
        cb_baud.grid(row=r, column=3, padx=15)
        
        # Station ID
        sid_list = list(sids)
        if sid not in sid_list:
            sid_list.append(sid)
        cb_sid = mk_combo(table_frame, sid_list, sid)
        cb_sid.grid(row=r, column=4, padx=15)
        
        # TEST Button
        btn = tk.Button(table_frame, text="TEST", bg="#e0e0e0", fg="black", font=('Arial', 10, 'bold'), width=10, bd=0)
        btn.config(command=lambda d=dev, cp=cb_port, cb=cb_baud, cs=cb_sid, b=btn: test_connection(d, cp, cb, cs, b))
        btn.grid(row=r, column=5, padx=15)
        
        combos[dev] = (cb_port, cb_baud, cb_sid)

    def save_settings():
        mapping = {
            "HIPOT": ("hp_port", "hp_baud"),
            "LCR METER": ("lcr_port", "lcr_baud"),
            "PLC": ("plc_port", "plc_baud"),
            "Delta PLC": ("io_port", "io_baud"),
            "IO Controller Cable": ("ioc_port", "ioc_baud"),
            "Label Printer": ("printer_port", "printer_baud"),
            "Scanner": ("scanner_port", "scanner_baud")
        }
        for dev, (cb_p, cb_b, cb_s) in combos.items():
            if dev in mapping:
                cfg["COM"][mapping[dev][0]] = cb_p.get()
                cfg["COM"][mapping[dev][1]] = cb_b.get()
        with open(_CFG_PATH, "w") as f:
            cfg.write(f)
        log_msg("Settings saved successfully!")

    # Bottom buttons
    bottom_bar = tk.Frame(panel, bg="#12151b")
    bottom_bar.pack(side="bottom", fill="x", padx=20, pady=(0, 20))
    
    tk.Button(bottom_bar, text="Complete", bg="#e0e0e0", fg="black", font=('Arial', 11, 'bold'), width=12, bd=0, pady=5, cursor="hand2").pack(side="right", padx=(5, 0))
    tk.Button(bottom_bar, text="Update", bg="#2196f3", fg="white", font=('Arial', 11, 'bold'), width=12, bd=0, pady=5, cursor="hand2").pack(side="right", padx=5)
    tk.Button(bottom_bar, text="Save", bg="#4caf50", fg="white", font=('Arial', 11, 'bold'), width=12, bd=0, pady=5, cursor="hand2", command=save_settings).pack(side="right", padx=5)

    # Text Area
    text_frame = tk.Frame(panel, bg="#12151b", bd=1, relief="solid", highlightbackground="#333", highlightthickness=1)
    text_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(10, 20))
    
    log_text = tk.Text(text_frame, bg="#12151b", fg="white", font=('Consolas', 11), bd=0, height=8)
    log_text.pack(fill="both", expand=True, padx=10, pady=10)
    log_text.insert("end", "!007F00\n")
    log_text.config(state="disabled")


