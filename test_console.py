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
from vision_engine.vision_controller import VisionController, VisionResult
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
    from pymodbus.client import ModbusSerialClient
    _modbus_ok = True
except ImportError:
    _modbus_ok = False

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

try:
    import cv2
    from vision_engine import camera
    _cv2_ok = True
except ImportError:
    _cv2_ok = False

try:
    from PIL import Image, ImageTk
    _pil_ok = True
except ImportError:
    _pil_ok = False

import db

def _get_conn():
    return db.get_connection()

_CFG_PATH = os.path.join(os.path.dirname(__file__), "comport_cfg.ini")
def _load_cfg() -> dict:
    cfg = configparser.ConfigParser()
    cfg.read(_CFG_PATH)
    return {
        "io_port":    cfg.get("COM", "io_port",    fallback="0"),
        "io_baud":    cfg.getint("COM", "io_baud",  fallback=0),
        "hp_port":    cfg.get("COM", "hp_port",    fallback="0"),
        "hp_baud":    cfg.getint("COM", "hp_baud",  fallback=0),
        "machine_id": cfg.get("COM", "machine_id", fallback="PB1"),
        "scan_enabled": cfg.getboolean("COM", "scan_enabled", fallback=True),
    }
def _save_cfg(d: dict):
    cfg = configparser.ConfigParser()
    cfg["COM"] = {k: str(v) for k, v in d.items()}
    with open(_CFG_PATH, "w") as f:
        cfg.write(f)

# ISO/IEC 15434 labels carry non-printable separators, which render as nothing
# (or as boxes) in a Tk label. Show them as mnemonics so the operator sees the
# structure of what was scanned:
#   [)>[RS]06[GS]VT007[GS]P123[GS]S123[GS]T260905I1A2A6[GS][RS][EOT]
_SCAN_CTRL_NAMES = {
    "\x1e": "[RS]", "\x1d": "[GS]", "\x1f": "[US]",
    "\x04": "[EOT]", "\x05": "[ENQ]", "\r": "[CR]", "\n": "[LF]",
}

def _fmt_scan(raw: str) -> str:
    return "".join(_SCAN_CTRL_NAMES.get(ch, ch) for ch in raw)

def _scan_lot_ok(scanned: str, labelstr: str) -> bool:
    """PASS only if the lot number is a substring of the field that starts
    with "T" (e.g. T260905I1A2A6 -- date + traceability code), never the
    whole scanned string -- so a lot number that happens to also appear in
    another field (part number, serial, etc.) can't produce a false OK.

    Fields are split on any non-alphanumeric character rather than on the
    specific ISO 15434 control bytes, since a keyboard-wedge scanner does
    not reliably deliver GS/RS/EOT as literal insertable characters -- but
    the envelope punctuation and separators are non-alphanumeric either way,
    so splitting on "not alnum" isolates the same fields regardless of
    exactly which bytes the scanner actually sends.
    """
    if not labelstr:
        return False
    word = ""
    for ch in scanned + "\x00":
        if ch.isalnum():
            word += ch
        else:
            if word.startswith("T") and labelstr in word:
                return True
            word = ""
    return False

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
    if not _print_ok:
        print("[PRINT DEBUG] win32print not available (pywin32 not installed) -- cannot print")
        return
    if not os.path.exists(filename):
        print(f"[PRINT DEBUG] label file not found: {filename}")
        return
    try:
        installed = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        print(f"[PRINT DEBUG] installed printers: {installed}")
        if printer_name not in installed:
            print(f"[PRINT DEBUG] '{printer_name}' is NOT in the installed printers list above -- check exact spelling in Windows Settings > Printers & scanners")
    except Exception as ex:
        print(f"[PRINT DEBUG] could not enumerate printers: {ex}")
    try:
        print(f"[PRINT DEBUG] opening printer '{printer_name}' to send {filename}")
        hPrinter = win32print.OpenPrinter(printer_name)
        try:
            hJob = win32print.StartDocPrinter(hPrinter, 1, ("EOL Label", None, "RAW"))
            try:
                win32print.StartPagePrinter(hPrinter)
                with open(filename, "rb") as f:
                    data = f.read()
                    win32print.WritePrinter(hPrinter, data)
                win32print.EndPagePrinter(hPrinter)
                print(f"[PRINT DEBUG] sent {len(data)} bytes to '{printer_name}' OK")
            finally:
                win32print.EndDocPrinter(hPrinter)
        finally:
            win32print.ClosePrinter(hPrinter)
    except Exception as ex:
        print(f"[PRINT DEBUG] print FAILED: {ex}")
# ── Delta DVP PLC Modbus RTU Address Mapping ──────────────────────────────────
# Memory Coils (M):      base 0x0800  (write via FC05/FC15)
# Discrete Inputs (X):   base 0x0400  (read via FC02, octal numbering)
# Safety Relay:           M28 = 0x081C (switches Contact Test ↔ IR/ACW mode)
#
# Channel mapping (from hardware reference):
#   IR/ACW: CH1-CH8 -> M20-M27
#   CONTACT: CH1-CH8 -> M30-M37
#   ACK: CH1-CH8 -> X20-X27
# ──────────────────────────────────────────────────────────────────────────────

_PLC_IR_ACW_COILS = {
    1: 0x0814,  # M20
    2: 0x0815,  # M21
    3: 0x0816,  # M22
    4: 0x0817,  # M23
    5: 0x0818,  # M24
    6: 0x0819,  # M25
    7: 0x081A,  # M26
    8: 0x081B,  # M27
}

_PLC_CONTACT_COILS = {
    1: 0x081E,  # M30
    2: 0x081F,  # M31
    3: 0x0820,  # M32
    4: 0x0821,  # M33
    5: 0x0822,  # M34
    6: 0x0823,  # M35
    7: 0x0824,  # M36
    8: 0x0825,  # M37
}

_PLC_CH_INPUTS = {
    1: 0x0410,  # X20
    2: 0x0411,  # X21
    3: 0x0412,  # X22
    4: 0x0413,  # X23
    5: 0x0414,  # X24
    6: 0x0415,  # X25
    7: 0x0416,  # X26
    8: 0x0417,  # X27
}

_PLC_SAFETY_RELAY = 0x081C   # M28 — Contact Test ↔ IR/ACW mode switch
_PLC_SAFETY_ACK   = 0x0404   # X4 — Acknowledge input for safety relay (M28)
_PLC_ACK_BASE     = 0x0410   # X20 — start of 8 consecutive acknowledge inputs

# Physical PLC Inputs (X0-X3)
_PLC_START_INPUT      = 0x0400   # X0  — physical START button
_PLC_NG_RESET_INPUT   = 0x0401   # X1  — NG Reset
_PLC_CONTACT_OK_INPUT = 0x0402   # X2  — Contact OK
_PLC_REWORK_ON_INPUT  = 0x0403   # X3  — Rework on


class DeltaPLC:
    """Delta DVP PLC communication via Modbus ASCII (RS-485/RS-232)."""

    def __init__(self, port: str, baud: int = 9600, slave_id: int = 1):
        self._port = port
        self._baud = baud
        self._slave_id = slave_id
        self._client = None
        self._is_hv_mode = False

    def open(self) -> bool:
        if not _modbus_ok:
            return False
        try:
            self.close()
            self._client = ModbusSerialClient(
                framer='ascii',
                port=self._port,
                baudrate=self._baud,
                parity='E',
                stopbits=1,
                bytesize=7,
                timeout=1.5,
            )
            return self._client.connect()
        except Exception:
            return False

    def close(self):
        try:
            if self._client:
                self._client.close()
        except Exception:
            pass

    @property
    def is_open(self):
        return self._client is not None and self._client.is_socket_open()

    # ── Low-level Modbus helpers ─────────────────────────────────────────

    def write_coil(self, address: int, value: bool) -> bool:
        """Write a single coil (FC05)."""
        if not self.is_open:
            print(f"[PLC DEBUG] write_coil(0x{address:04X}, {value}): port not open!")
            return False
        try:
            result = self._client.write_coil(address, value=value, device_id=self._slave_id)
            ok = not result.isError()
            print(f"[PLC DEBUG] write_coil(0x{address:04X}, {value}): {'OK' if ok else f'FAILED: {result}'}")
            return ok
        except Exception as e:
            print(f"[PLC DEBUG] write_coil EXCEPTION: {e}")
            self.close()  # drop a dead handle now, instead of retrying it on every call after
            return False

    def read_input(self, address: int) -> bool:
        """Read a single discrete input (FC02) via bulk read for Delta PLC reliability."""
        if not self.is_open:
            print(f"[PLC DEBUG] read_input(0x{address:04X}): port not open!")
            return False
        try:
            base = 0x0400
            offset = address - base
            count = max(offset + 1, 8)
            print(f"[PLC DEBUG] read_discrete_inputs(base=0x{base:04X}, count={count}, slave={self._slave_id})")
            result = self._client.read_discrete_inputs(base, count=count, device_id=self._slave_id)
            if result.isError():
                print(f"[PLC DEBUG] 0x0400 base FAILED: {result}")
                # Fallback: try without 0x0400 offset
                result = self._client.read_discrete_inputs(0, count=count, device_id=self._slave_id)
                if result.isError():
                    print(f"[PLC DEBUG] base 0 also FAILED: {result}")
                    return False
                print(f"[PLC DEBUG] base 0 OK, bits={result.bits[:count]}, returning bit[{offset}]={result.bits[offset]}")
                return result.bits[offset] if 0 <= offset < len(result.bits) else False
            print(f"[PLC DEBUG] 0x0400 OK, bits={list(result.bits[:count])}, returning bit[{offset}]={result.bits[offset]}")
            return result.bits[offset] if 0 <= offset < len(result.bits) else False
        except Exception as e:
            print(f"[PLC DEBUG] read_input EXCEPTION: {e}")
            self.close()
            return False

    def read_inputs_bulk(self, address: int, count: int) -> list:
        """Read multiple consecutive discrete inputs (FC02)."""
        if not self.is_open:
            return [False] * count
        try:
            result = self._client.read_discrete_inputs(address, count=count, device_id=self._slave_id)
            if result.isError():
                # Fallback: try from base 0 with offset
                offset = address - 0x0400 if address >= 0x0400 else address
                result = self._client.read_discrete_inputs(0, offset + count, device_id=self._slave_id)
                if result.isError():
                    return [False] * count
                return list(result.bits[offset:offset + count])
            return list(result.bits[:count])
        except Exception:
            self.close()
            return [False] * count

    def read_coil(self, address: int) -> bool:
        """Read a single coil (FC01)."""
        if not self.is_open:
            return False
        try:
            result = self._client.read_coils(address, count=1, device_id=self._slave_id)
            if result.isError():
                return False
            return result.bits[0]
        except Exception:
            self.close()
            return False

    def read_coils_bulk(self, address: int, count: int) -> list:
        """Read multiple consecutive coils (FC01)."""
        if not self.is_open:
            return [False] * count
        try:
            result = self._client.read_coils(address, count=count, device_id=self._slave_id)
            if result.isError():
                return [False] * count
            return list(result.bits[:count])
        except Exception:
            self.close()
            return [False] * count

    # ── Channel relay control ────────────────────────────────────────────

    def set_channel(self, ch: int, on: bool) -> bool:
        """Turn a channel relay ON or OFF via its memory coil."""
        coils = _PLC_IR_ACW_COILS if self._is_hv_mode else _PLC_CONTACT_COILS
        addr = coils.get(ch)
        if addr is None:
            return False
        return self.write_coil(addr, on)

    def get_channel(self, ch: int) -> bool:
        """Read the actual physical state of a channel relay coil."""
        coils = _PLC_IR_ACW_COILS if self._is_hv_mode else _PLC_CONTACT_COILS
        addr = coils.get(ch)
        if addr is None:
            return False
        return self.read_coil(addr)

    def set_all_channels(self, n_ch: int, on: bool) -> bool:
        """Turn ON/OFF all channel relays."""
        ok = True
        for ch in range(1, min(n_ch, 8) + 1):
            if not self.set_channel(ch, on):
                ok = False
            time.sleep(0.02)
        return ok

    def reset_all_channels(self) -> bool:
        """Turn OFF all 8 channel relays (both Contact and IR/ACW coils)."""
        ok = True
        for addr in _PLC_IR_ACW_COILS.values():
            if not self.write_coil(addr, False):
                ok = False
        for addr in _PLC_CONTACT_COILS.values():
            if not self.write_coil(addr, False):
                ok = False
        return ok

    # ── Acknowledge / confirmation inputs ────────────────────────────────

    def read_channel_ack(self, ch: int) -> bool:
        """Read acknowledgment input for one channel (X20~X27)."""
        addr = _PLC_CH_INPUTS.get(ch)
        if addr is None:
            return False
        return self.read_input(addr)

    def read_all_acks(self, n_ch: int) -> dict:
        """Read all channel acknowledgment inputs X20~X27 in one shot."""
        bits = self.read_inputs_bulk(_PLC_ACK_BASE, 8)
        return {ch: bits[ch - 1] for ch in range(1, min(n_ch, 8) + 1)}

    def confirm_channels_on(self, n_ch: int, retries: int = 5, delay: float = 0.2) -> bool:
        """Verify all channel relays confirmed ON via X20~X27 with retries."""
        for _ in range(retries):
            acks = self.read_all_acks(n_ch)
            if all(acks.values()):
                return True
            time.sleep(delay)
        return False

    # ── Safety relay (CRITICAL — prevents HV short circuit) ──────────────

    def safety_relay_to_hv(self) -> bool:
        """Switch to IR/ACW (high-voltage) mode. MUST call before HV tests."""
        self._is_hv_mode = True
        return self.write_coil(_PLC_SAFETY_RELAY, False)

    def safety_relay_to_contact(self) -> bool:
        """Switch to Contact Test mode. MUST call after HV tests."""
        self._is_hv_mode = False
        return self.write_coil(_PLC_SAFETY_RELAY, True)

    # ── Physical PLC Inputs (X0-X3) ──────────────────────────────────────

    def is_start_pressed(self) -> bool:
        """Check if physical START button is pressed (X0)."""
        return self.read_input(_PLC_START_INPUT)

    def is_ng_reset_pressed(self) -> bool:
        """Check if NG Reset button is pressed (X1)."""
        return self.read_input(_PLC_NG_RESET_INPUT)

    def is_contact_ok(self) -> bool:
        """Check if Contact OK is signaled (X2)."""
        return self.read_input(_PLC_CONTACT_OK_INPUT)

    def is_rework_on(self) -> bool:
        """Check if Rework Mode is toggled on (X3)."""
        return self.read_input(_PLC_REWORK_ON_INPUT)


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
                time.sleep(0.5)
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
        try:
            self._ser.write((cmd + "\r\n").encode("ascii"))
            print(f"[HIPOT DEBUG] >> {cmd}")
        except Exception as e:
            print(f"[HIPOT DEBUG] write_line EXCEPTION on '{cmd}': {e}")
            self.close()
        time.sleep(0.025)
    def read_line(self) -> str:
        if not self.is_open: return ""
        try:
            line = self._ser.readline().decode("ascii", errors="ignore").strip()
            print(f"[HIPOT DEBUG] << {line!r}")
            return line
        except Exception as e:
            print(f"[HIPOT DEBUG] read_line EXCEPTION: {e}")
            return ""
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
        print(f"[HIPOT DEBUG] IR: commanded {ir_volt_kv:.4f} kV, MEAS? -> {response!r}, parsed value={ir_val}")
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
        print(f"[HIPOT DEBUG] ACW: commanded {acw_volt_kv:.4f} kV, MEAS? -> {response!r}, parsed value={acw_val}")
        return acw_min <= acw_val <= acw_max, acw_val

def _generate_lot_number(pno: str, machine_id: str) -> str:
    now = datetime.datetime.now()
    date_str = now.strftime("%y%m%d")
    mid_char = machine_id[-1] if machine_id else "1"
    prefix = f"{date_str}I{mid_char}A2A"
    try:
        with db.get_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM testmaster WHERE pno=%s AND lotno LIKE %s", (pno, f"{date_str}%"))
            row = cur.fetchone()
            seq = (row[0] if row else 0) + 1
    except Exception as ex: 
        print(f"DB Error generating lot: {ex}")
        seq = 1
    return f"{prefix}{seq}"

def _print_barcode_label(pno: str, alc: str, model: str, vendor_code: str, eo_number: str, lot_no: str, machine_id: str, is_rework: bool = False, printer_name: str = "EOLPRINTER"):
    base = os.path.dirname(__file__)
    lbl_sel = ""
    try:
        with db.get_cursor() as cur:
            cur.execute("SELECT lblsel FROM settingmaster WHERE pno=%s", (pno,))
            row = cur.fetchone()
            if row: lbl_sel = row[0] or ""
    except Exception as ex:
        print(f"DB Error getting label: {ex}")
    # lblsel is the full path of the .prn template picked in Model Settings.
    # nice1.prn = regular-part template, nice1R.prn = rework-part template
    # (a sibling file with "R" inserted before the extension).
    suffix = "R" if is_rework else ""
    prn_file = ""
    if lbl_sel:
        root, ext = os.path.splitext(lbl_sel)
        prn_file = f"{root}{suffix}{ext or '.prn'}"
    print(f"[PRINT DEBUG] pno={pno} lblsel='{lbl_sel}' is_rework={is_rework} -> template={prn_file or '(none)'}")
    if not prn_file or not os.path.exists(prn_file):
        print(f"[PRINT DEBUG] template not found, falling back to TEMPPRN.prn")
        prn_file = os.path.join(base, "TEMPPRN.prn")
    if not os.path.exists(prn_file):
        print(f"[PRINT DEBUG] no label file at all ({prn_file}) -- aborting print")
        return
    now = datetime.datetime.now()
    try:
        with open(prn_file, "r", encoding="latin-1") as f: text = f.read()
        text = text.replace("@alcCode@", alc).replace("@partNumber@", pno).replace("@modelName@", model).replace("@vendorCode@", vendor_code).replace("@eoNumber@", eo_number).replace("@lotNo@", lot_no).replace("@traceabilityCode@", lot_no)
        text = text.replace("@ddMMyy@", now.strftime("%d%m%y")).replace("@HH:mm:ss@", now.strftime("%H:%M:%S")).replace("@machineID_NoAlphabet@", machine_id.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"))
        tmp = os.path.join(base, "TEMPPRN.prn")
        with open(tmp, "w", encoding="latin-1") as f: f.write(text)
        _print_raw(printer_name, tmp)
    except Exception as ex:
        print(f"[PRINT DEBUG] failed building/sending label: {ex}")

_CAM_CFG_PATH = os.path.join(os.path.dirname(__file__), "camera_cfg.ini")
def _load_cam_cfg() -> dict:
    cfg = configparser.ConfigParser()
    cfg.read(_CAM_CFG_PATH)
    return {
        "cam1_index":   cfg.getint("CAMERA", "cam1_index",   fallback=-1),
        "cam2_index":   cfg.getint("CAMERA", "cam2_index",   fallback=-1),
        "cam1_width":   cfg.getint("CAMERA", "cam1_width",   fallback=640),
        "cam1_height":  cfg.getint("CAMERA", "cam1_height",  fallback=480),
        "cam2_width":   cfg.getint("CAMERA", "cam2_width",   fallback=640),
        "cam2_height":  cfg.getint("CAMERA", "cam2_height",  fallback=480),
        "cam1_enabled": cfg.getboolean("CAMERA", "cam1_enabled", fallback=False),
        "cam2_enabled": cfg.getboolean("CAMERA", "cam2_enabled", fallback=False),
    }

class CameraFeed:
    """Streams a live camera feed into a tkinter Label widget.

    Reads through vision_engine.camera's reference-counted registry instead
    of opening its own cv2.VideoCapture. A DirectShow device only tolerates
    one open capture at a time -- a second independent VideoCapture on the
    same index (e.g. this live preview racing the vision inspection that
    runs mid-test on the same camera) raises an unrecoverable C++ exception
    inside OpenCV's DSHOW backend and takes the whole process down with it.
    """
    def __init__(self, label, cam_index, display_w=200, display_h=110, width=640, height=480):
        self._label = label
        self._cam_index = cam_index
        self._display_w = display_w
        self._display_h = display_h
        self._width = width
        self._height = height
        self._cam_stream = None
        self._running = False
        self._photo = None
        self._paused = False

    def start(self):
        if not _cv2_ok or not _pil_ok or self._cam_index < 0:
            return
        self._running = True
        threading.Thread(target=self._open_camera, daemon=True).start()

    def pause(self):
        """Freeze the live feed so a still (e.g. a vision-check overlay) stays put."""
        self._paused = True

    def resume(self):
        self._paused = False

    def _open_camera(self):
        self._cam_stream = camera.acquire(self._cam_index, self._width, self._height)
        if self._cam_stream is None or not self._cam_stream.wait_until_open(timeout=5.0):
            self._running = False
            if self._cam_stream is not None:
                self._cam_stream.release()
                self._cam_stream = None
            try:
                self._label.after(0, lambda: self._label.config(
                    text="Camera\nunavailable", fg="#ff5555"))
            except Exception:
                pass
            return
        self._stream()

    def _stream(self):
        if not self._running or self._cam_stream is None or not self._cam_stream.is_alive():
            return
        if self._paused:
            try:
                self._label.after(33, self._stream)
            except Exception:
                self.stop()
            return
        frame = self._cam_stream.latest()
        if frame is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (self._display_w, self._display_h))
            img = Image.fromarray(frame)
            self._photo = ImageTk.PhotoImage(img)
            try:
                self._label.config(image=self._photo, text="")
                self._label.image = self._photo
            except Exception:
                self.stop()
                return
        if self._running:
            try:
                self._label.after(33, self._stream)  # ~30fps
            except Exception:
                self.stop()

    def stop(self):
        self._running = False
        if self._cam_stream is not None:
            self._cam_stream.release()
        self._cam_stream = None

def render(parent):
    cfg = _load_cfg()
    style = ttk.Style()
    # Windows' native ttk theme ("vista") ignores Treeview/LabelFrame color
    # overrides outright -- every dark color configured below silently does
    # nothing under it, which is why the spec/history tables render as
    # plain white boxes instead of the intended dark theme. "clam" is a
    # theme that actually honors style.configure colors.
    try: style.theme_use("clam")
    except tk.TclError: pass
    style.configure("TC.TLabelframe", background="black", foreground="white", bordercolor="#444")
    style.configure("TC.TLabelframe.Label", background="black", foreground="#aaa", font=("Arial", 9))
    style.configure("Spec.Treeview.Heading", background="#1a1a1a", foreground="white", font=("Arial", 9, "bold"))
    style.configure("Spec.Treeview", background="#0d0d0d", foreground="white", fieldbackground="#0d0d0d", font=("Arial", 9), rowheight=26)
    style.configure("Hist.Treeview.Heading", background="#111", foreground="white", font=("Arial", 8, "bold"))
    style.configure("Hist.Treeview", background="#080808", foreground="#ccc", fieldbackground="#080808", font=("Arial", 8), rowheight=22)
    style.configure("Lot.Treeview.Heading", background="#0a1a00", foreground="#76ff03", font=("Arial", 8, "bold"))
    style.configure("Lot.Treeview", background="#060d00", foreground="#aee571", fieldbackground="#060d00", font=("Arial", 8), rowheight=22)
    # Column headers otherwise brighten on mouse-over / press -- pin each
    # heading style's color so it stays flat in every state.
    for heading_style, bg, fg in (
        ("Spec.Treeview.Heading", "#1a1a1a", "white"),
        ("Hist.Treeview.Heading", "#111", "white"),
        ("Lot.Treeview.Heading", "#0a1a00", "#76ff03"),
    ):
        style.map(heading_style, background=[("active", bg), ("pressed", bg)],
                  foreground=[("active", fg), ("pressed", fg)])
    style.map("Spec.Treeview", background=[("selected", "#1c3a5e")])
    style.map("Hist.Treeview", background=[("selected", "#1c3a5e")])
    style.map("Lot.Treeview",  background=[("selected", "#1c3a5e")])

    try:
        db.ensure_column("testmaster", "visionimg", "VARCHAR(255)")
    except Exception:
        pass  # DB may be unreachable right now -- don't block the page for it

    state = {
        "pno": None, "alc": "", "model": "", "vendor_code": "", "eo_number": "", "pname": "", "cname": "",
        "num_channels": 0, "spec_ir": {}, "spec_acw": {}, "test_running": False, "total": 0, "ok": 0, "ng": 0,
        "lot_no": "", "labelstr": "", "start_time": None, "flag": True, "input_polling": False,
        "last_vision_result": None, "is_rework": False,
    }
    plc = DeltaPLC(cfg["io_port"], cfg["io_baud"])
    hipot = HiPotSerial(cfg["hp_port"], cfg["hp_baud"])

    content = tk.Frame(parent, bg="black")
    content.pack(fill="both", expand=True, padx=4, pady=2)

    _real_after = parent.after
    def _after(delay, fn=None, *args):
        """_after(), but the callback is dropped if this page has since
        been navigated away from. Background threads (the test sequence, PLC
        polling) schedule their UI updates with this — without the guard, a
        callback that outlives page navigation hits a destroyed widget and
        throws 'invalid command name', which cascades into a flood of
        Tkinter callback errors.
        """
        if fn is None:
            return _real_after(delay)
        def _guarded(*a):
            if content.winfo_exists():
                fn(*a)
        return _real_after(delay, _guarded, *args)
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
    rework_lbl = tk.Label(result_inner, text="", bg="black", fg="#ff9100", font=("Arial", 11, "bold"), anchor="center")
    rework_lbl.pack(fill="x", padx=4, pady=(0, 2))
    tk.Label(result_inner, text="LOT NO", bg="black", fg="#444", font=("Arial", 8)).pack(fill="x")
    lot_lbl = tk.Label(result_inner, text="—", bg="black", fg="#888", font=("Consolas", 8), anchor="center")
    lot_lbl.pack(fill="x", padx=4, pady=(0, 4))
    tk.Label(result_inner, text="ELAPSED TIME (s)", bg="black", fg="#444", font=("Arial", 8)).pack(fill="x")
    elapsed_lbl = tk.Label(result_inner, text="—", bg="black", fg="#888", font=("Consolas", 9), anchor="center")
    elapsed_lbl.pack(fill="x", padx=4, pady=(0, 6))

    com_lf = ttk.LabelFrame(right_panel, text="COM Status", style="TC.TLabelframe")
    
    # Initialize local vision controller (headless, no UI panel)
    try:
        from vision_engine.vision_controller import get_vision_controller
        vision_ctrl = get_vision_controller()
    except Exception as e:
        vision_ctrl = None
        print(f"Vision controller init error: {e}")

    # Move COM status down to row 2, and Camera down to row 3

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
        def _update():
            try:
                if lbl.winfo_exists(): lbl.config(bg="#1b5e20" if connected else "#3a3a3a", fg="white" if connected else "#555")
            except Exception: pass
        if lbl:
            try: _after(0, _update)
            except Exception: pass

    # Camera frames — live feed from OpenCV
    cam_cfg = _load_cam_cfg()
    cam_frame = tk.Frame(right_panel, bg="black")
    cam_frame.grid(row=2, column=0, sticky="nsew", pady=(5, 0))
    _cam_feeds = []  # track for cleanup
    cam_labels = {}       # cam_id -> preview Label
    cam_feeds_by_id = {}  # cam_id -> CameraFeed (only when a live feed is running)
    cam_default_text = {}  # cam_id -> the label's placeholder text


    def _open_camera_popup(e, cam_id):
        dlg = tk.Toplevel(parent)
        dlg.title(f"Camera {cam_id} Configuration")
        dlg.geometry("400x320")
        dlg.configure(bg="#222")
        dlg.transient(parent)
        dlg.grab_set()

        cfg = _load_cam_cfg()
        
        try:
            import cv2
            cameras = []
            for i in range(5):
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        cameras.append({"index": i, "name": f"Camera {i}", "width": w, "height": h})
                    cap.release()
        except:
            cameras = []
            
        cam_options = ["Disabled"] + [f"{c['name']} (index {c['index']})" for c in cameras]
        cam_indices = [-1] + [c["index"] for c in cameras]
        
        resolutions = [("320x240", 320, 240), ("640x480", 640, 480), ("800x600", 800, 600), ("1280x720", 1280, 720)]
        res_options = [r[0] for r in resolutions]

        # Camera Config
        lf = tk.LabelFrame(dlg, text=f"Camera {cam_id}", bg="#222", fg="#e8a000", font=("Arial", 10, "bold"))
        lf.pack(fill="x", padx=10, pady=5)
        
        tk.Label(lf, text="Device:", bg="#222", fg="white").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        cmb_c = ttk.Combobox(lf, values=cam_options, state="readonly", width=25)
        
        c_idx_key = f"cam{cam_id}_index"
        c_en_key = f"cam{cam_id}_enabled"
        try:
            c_idx = cam_indices.index(cfg[c_idx_key]) if cfg[c_en_key] else 0
        except ValueError:
            c_idx = 0
        cmb_c.current(c_idx)
        cmb_c.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(lf, text="Resolution:", bg="#222", fg="white").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        cmb_r = ttk.Combobox(lf, values=res_options, state="readonly", width=25)
        try:
            w_key, h_key = f"cam{cam_id}_width", f"cam{cam_id}_height"
            r_idx = res_options.index(f"{cfg[w_key]}x{cfg[h_key]}")
        except ValueError:
            r_idx = 1
        cmb_r.current(r_idx)
        cmb_r.grid(row=1, column=1, padx=5, pady=5)

        # Active Dataset config (vision_config.json)
        lf3 = tk.LabelFrame(dlg, text="Active Vision Dataset (Current Part)", bg="#222", fg="#e8a000", font=("Arial", 10, "bold"))
        lf3.pack(fill="x", padx=10, pady=5)
        
        from vision_engine.vision_controller import load_vision_config, save_vision_config
        v_cfg = load_vision_config()
        current_part = state.get("pno", "")
        
        import os, glob
        models_dir = os.path.join(os.path.dirname(__file__), "vision_models")
        datasets = [os.path.basename(f) for f in glob.glob(os.path.join(models_dir, "*.npz"))]
        
        tk.Label(lf3, text=f"Part: {current_part if current_part else 'None Loaded'}", bg="#222", fg="white").grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        
        tk.Label(lf3, text="Dataset:", bg="#222", fg="white").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        cmb_dataset = ttk.Combobox(lf3, values=["(None)"] + datasets, state="readonly", width=25)
        
        current_mapped = v_cfg.get("part_mapping", {}).get(current_part)
        if current_mapped in datasets:
            cmb_dataset.current(datasets.index(current_mapped) + 1)
        else:
            cmb_dataset.current(0)
            
        cmb_dataset.grid(row=1, column=1, padx=5, pady=5)

        def _save():
            d_sel = cmb_c.current()
            r_sel = cmb_r.current()
            
            # Update only this camera's settings
            cfg[f"cam{cam_id}_index"] = cam_indices[d_sel] if d_sel > 0 else -1
            cfg[f"cam{cam_id}_enabled"] = d_sel > 0
            cfg[f"cam{cam_id}_width"] = resolutions[r_sel][1]
            cfg[f"cam{cam_id}_height"] = resolutions[r_sel][2]
            
            import configparser
            new_cam = configparser.ConfigParser()
            new_cam["CAMERA"] = {k: str(v) for k, v in cfg.items()}
            with open(_CAM_CFG_PATH, "w") as f:
                new_cam.write(f)
                
            # Save Dataset mapping
            if current_part:
                ds_val = cmb_dataset.get()
                if ds_val == "(None)":
                    v_cfg.get("part_mapping", {}).pop(current_part, None)
                else:
                    if "part_mapping" not in v_cfg:
                        v_cfg["part_mapping"] = {}
                    v_cfg["part_mapping"][current_part] = ds_val
                save_vision_config(v_cfg)
                
            dlg.destroy()
            
            # Reload page to apply changes
            try: parent.winfo_toplevel().event_generate("<<NavigateHome>>")
            except: pass

        tk.Button(dlg, text="Save Settings", bg="#1b5e20", fg="white", font=("Arial", 11, "bold"), bd=0, padx=20, pady=8, command=_save).pack(pady=15)

    def nav_camera(e, cam_id):
        # Stop feeds before popup
        for feed in _cam_feeds:
            feed.stop()
        _open_camera_popup(e, cam_id)


    def _make_cam_widget(container_parent, cam_label, cam_index, enabled, cam_id, cam_w=640, cam_h=480):
        """Create a camera frame — live feed if configured, placeholder otherwise."""
        container = tk.Frame(container_parent, bg="#1a1a1a", bd=1, relief="solid",
                             width=210, height=115)
        container.pack_propagate(False)
        container.pack(pady=(0, 4))

        lbl = tk.Label(container, text=f"[ {cam_label} ]\n(Click to configure)",
                       bg="#1a1a1a", fg="#555", font=("Arial", 10, "bold"), cursor="hand2")
        lbl.pack(fill="both", expand=True)
        container.bind("<Button-1>", lambda e, cid=cam_id: nav_camera(e, cid))
        lbl.bind("<Button-1>", lambda e, cid=cam_id: nav_camera(e, cid))
        cam_labels[cam_id] = lbl
        cam_default_text[cam_id] = lbl.cget("text")

        if enabled and cam_index >= 0 and _cv2_ok and _pil_ok:
            feed = CameraFeed(lbl, cam_index, display_w=208, display_h=113, width=cam_w, height=cam_h)
            feed.start()
            _cam_feeds.append(feed)
            cam_feeds_by_id[cam_id] = feed

        return container, lbl

    _make_cam_widget(cam_frame, "CAMERA 1", cam_cfg["cam1_index"], cam_cfg["cam1_enabled"], 1, cam_cfg["cam1_width"], cam_cfg["cam1_height"])
    _make_cam_widget(cam_frame, "CAMERA 2", cam_cfg["cam2_index"], cam_cfg["cam2_enabled"], 2, cam_cfg["cam2_width"], cam_cfg["cam2_height"])

    # Cleanup camera feeds and the PLC input-polling loop when the page is destroyed.
    # Without this, navigating away (e.g. to COM Port Settings) left the X0
    # "waiting for physical START" poll looping forever in the background,
    # opening/closing the same COM port every ~500ms and fighting any other
    # page's own attempt to open it.
    def _on_page_destroy(e):
        if e.widget == content:
            for feed in _cam_feeds:
                feed.stop()
            state["input_polling"] = False
            try: plc.close()
            except Exception: pass
    content.bind("<Destroy>", _on_page_destroy)

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

    _lbl(pi, "Part No").grid(row=0, column=0, sticky="w", pady=4); ent_pno = _ent(pi, w=18, editable=False); ent_pno.grid(row=0, column=1, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "EMP ID").grid(row=0, column=4, sticky="w", padx=(10, 4)); ent_emp = _ent(pi, w=12, editable=True); ent_emp.grid(row=0, column=5, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "Part Name").grid(row=1, column=0, sticky="w", pady=4); ent_pname = _ent(pi, w=14, editable=False); ent_pname.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "Customer").grid(row=1, column=4, sticky="w", padx=(10, 4)); ent_cust = _ent(pi, w=12, editable=False); ent_cust.grid(row=1, column=5, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "Model").grid(row=2, column=0, sticky="w", pady=4); ent_model = _ent(pi, w=10, editable=False); ent_model.grid(row=2, column=1, sticky="ew", padx=5)
    _lbl(pi, "ALC").grid(row=2, column=2, sticky="w", padx=(8, 4)); ent_alc = _ent(pi, w=6, editable=False); ent_alc.grid(row=2, column=3, sticky="ew", padx=5)
    _lbl(pi, "LOT No").grid(row=2, column=4, sticky="w", padx=(8, 4)); ent_lot = _ent(pi, w=14, editable=False); ent_lot.grid(row=2, column=5, columnspan=2, sticky="ew", padx=5)
    _lbl(pi, "Vendor").grid(row=3, column=0, sticky="w", pady=4); ent_vendor = _ent(pi, w=10, editable=False); ent_vendor.grid(row=3, column=1, sticky="ew", padx=5)
    _lbl(pi, "EO No").grid(row=3, column=2, sticky="w", padx=(8, 4)); ent_eo = _ent(pi, w=8, editable=False); ent_eo.grid(row=3, column=3, sticky="ew", padx=5)
    _lbl(pi, "Machine").grid(row=3, column=4, sticky="w", padx=(8, 4)); ent_machine = _ent(pi, w=8, editable=False); ent_machine.grid(row=3, column=5, sticky="ew", padx=5)
    _lbl(pi, "JIG Scan").grid(row=4, column=0, sticky="w", pady=4); ent_jig = _ent(pi, w=18, editable=False); ent_jig.grid(row=4, column=1, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "Test Type").grid(row=4, column=4, sticky="w", padx=(8, 4)); ent_testtype = _ent(pi, w=8, editable=False); ent_testtype.grid(row=4, column=5, sticky="ew", padx=5)
    
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
    MAX_CH = 8
    ch_header = ["TEST", "UNIT"] + [f"CH{i}" for i in range(1, MAX_CH + 1)] + ["RESULT"]
    for i in range(len(ch_header)): test_frame.columnconfigure(i, weight=1)
    for i, h in enumerate(ch_header): tk.Label(test_frame, text=h, bg="#1a1a1a", fg="white", font=("Arial", 8, "bold"), bd=1, relief="solid", pady=6).grid(row=0, column=i, sticky="nsew")
    test_rows_def = [("IR", "Insulation (IR)", "MÎ©"), ("ACW", "Withstand (ACW)", "mA"), ("Contact", "Contact", "—")]
    result_rows = {}
    for r_idx, (key, name, unit) in enumerate(test_rows_def, start=1):
        tk.Label(test_frame, text=name, bg="#111", fg="white", font=("Arial", 8), bd=1, relief="solid", pady=6).grid(row=r_idx, column=0, sticky="nsew")
        tk.Label(test_frame, text=unit, bg="#111", fg="#ffcc00", font=("Arial", 8, "bold"), bd=1, relief="solid").grid(row=r_idx, column=1, sticky="nsew")
        row_cells = []
        for ch_i in range(MAX_CH):
            lbl = tk.Label(test_frame, text="—", bg="#0d0d0d", fg="#333", font=("Arial", 8), bd=1, relief="solid", pady=6)
            lbl.grid(row=r_idx, column=2 + ch_i, sticky="nsew")
            row_cells.append(lbl)
        res_lbl = tk.Label(test_frame, text="—", bg="#0d0d0d", fg="#333", font=("Arial", 9, "bold"), bd=1, relief="solid")
        res_lbl.grid(row=r_idx, column=2 + MAX_CH, sticky="nsew")
        result_rows[key] = {"cells": row_cells, "result": res_lbl}

    def _reset_test_display():
        for key in result_rows:
            for cell in result_rows[key]["cells"]: cell.config(text="—", bg="#0d0d0d", fg="#333")
            result_rows[key]["result"].config(text="—", bg="#0d0d0d", fg="#333")
        result_lbl.config(text="READY", bg="#1a1a1a", fg="#555")
        lot_lbl.config(text="—"); elapsed_lbl.config(text="—"); blink_start()

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
    bottom.grid_propagate(False)
    bottom.columnconfigure(0, weight=0)   # I/O: only as wide as its indicator grid
    bottom.columnconfigure(1, weight=3)   # Label Scan Result
    bottom.columnconfigure(2, weight=2)   # Log
    bottom.rowconfigure(0, weight=1)
    io_lf = ttk.LabelFrame(bottom, text="PLC I/O Channel Status", style="TC.TLabelframe")
    io_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    io_inner = tk.Frame(io_lf, bg="black", padx=4, pady=3); io_inner.pack(fill="both", expand=True)

    # Cell and row-label widths are shared by every row so the M coils, the X
    # inputs and the channel-number header stay in one vertical grid. A cell is
    # exactly wide enough for its "M29"/"X20" text.
    _IO_CELL_W, _IO_LBL_W, _IO_GAP = 3, 9, 6

    # ── ROW 0: channel-number header, aligned with the M/X columns below ──
    # so a lit cell reads as "channel N", not "go look up what M32 means".
    hdr_row = tk.Frame(io_inner, bg="black"); hdr_row.pack(anchor="w")
    tk.Label(hdr_row, text="CH #:", bg="black", fg="#555", font=("Arial", 7), width=_IO_LBL_W, anchor="w").pack(side="left")
    tk.Label(hdr_row, text="", bg="black", width=_IO_CELL_W).pack(side="left", padx=(0, _IO_GAP))  # spacer over Safety/ACK cell
    for ch in range(1, 9):
        tk.Label(hdr_row, text=str(ch), bg="black", fg="#555", font=("Arial", 7), width=_IO_CELL_W).pack(side="left", padx=1)
    tk.Frame(hdr_row, bg="black", width=_IO_GAP).pack(side="left")
    for ch in range(1, 9):
        tk.Label(hdr_row, text=str(ch), bg="black", fg="#555", font=("Arial", 7), width=_IO_CELL_W).pack(side="left", padx=1)

    # ── ROW 1: PLC Outputs (M Coils) ──
    out_row = tk.Frame(io_inner, bg="black"); out_row.pack(anchor="w", pady=(2, 5))
    tk.Label(out_row, text="OUT (M):", bg="black", fg="#777", font=("Arial", 8, "bold"), width=_IO_LBL_W, anchor="w").pack(side="left")

    # Safety Relay
    safety_lbl = tk.Label(out_row, text="M28", bg="#0d0d0d", fg="#3a3a3a", font=("Arial", 7, "bold"), bd=1, relief="solid", width=_IO_CELL_W)
    safety_lbl.pack(side="left", padx=(0, _IO_GAP))

    # Contact Relays
    io_contact_labels = []
    for i in range(1, 9):
        lbl = tk.Label(out_row, text=f"M{29+i}", bg="#0d0d0d", fg="#3a3a3a", font=("Arial", 7), bd=1, relief="solid", width=_IO_CELL_W)
        lbl.pack(side="left", padx=1)
        io_contact_labels.append(lbl)

    tk.Frame(out_row, bg="black", width=_IO_GAP).pack(side="left")

    # HV Relays
    io_ir_acw_labels = []
    for i in range(1, 9):
        lbl = tk.Label(out_row, text=f"M{19+i}", bg="#0d0d0d", fg="#3a3a3a", font=("Arial", 7), bd=1, relief="solid", width=_IO_CELL_W)
        lbl.pack(side="left", padx=1)
        io_ir_acw_labels.append(lbl)

    # ── ROW 2: PLC Inputs (X Pins) ──
    in_row = tk.Frame(io_inner, bg="black"); in_row.pack(anchor="w", pady=(0, 2))
    tk.Label(in_row, text="IN (X):", bg="black", fg="#777", font=("Arial", 8, "bold"), width=_IO_LBL_W, anchor="w").pack(side="left")

    # Safety ACK
    x4_lbl = tk.Label(in_row, text="X4", bg="#141008", fg="#4a3f26", font=("Arial", 7, "bold"), bd=1, relief="solid", width=_IO_CELL_W)
    x4_lbl.pack(side="left", padx=(0, _IO_GAP))

    # Contact OK (aligns under M30)
    x2_lbl = tk.Label(in_row, text="X2", bg="#141008", fg="#4a3f26", font=("Arial", 7, "bold"), bd=1, relief="solid", width=_IO_CELL_W)
    x2_lbl.pack(side="left", padx=1)

    # Empty space to pad under M31-M37
    for i in range(2, 9):
        tk.Label(in_row, text="", bg="black", width=_IO_CELL_W).pack(side="left", padx=1)

    tk.Frame(in_row, bg="black", width=_IO_GAP).pack(side="left")

    # HV ACKs (aligns under M20-M27)
    io_in_labels = []
    for i in range(1, 9):
        lbl = tk.Label(in_row, text=f"X{19+i}", bg="#141008", fg="#4a3f26", font=("Arial", 7), bd=1, relief="solid", width=_IO_CELL_W)
        lbl.pack(side="left", padx=1)
        io_in_labels.append(lbl)
    
    # Off = flat near-black, blending into the panel like an unlit bulb.
    # On = a solid, vivid fill with dark text -- meant to visibly pop, not
    # just shift to a slightly different shade of dark. Relays (M coils) and
    # acks (X inputs) keep their own colors in both states -- green-family
    # for relays, amber-family for acks -- so the two stay visually separate
    # categories even when both are off, not just two shades of "off".
    _IO_OFF_BG,     _IO_OFF_FG     = "#0d0d0d", "#3a3a3a"    # relays, off
    _IO_ON_BG,      _IO_ON_FG      = "#00e676", "#003d14"    # relays, on (vivid green)
    _IO_ACK_OFF_BG, _IO_ACK_OFF_FG = "#141008", "#4a3f26"    # acks, off (dark amber tint)
    _IO_ACK_ON_BG,  _IO_ACK_ON_FG  = "#ffea00", "#3d3300"    # acks, on (vivid amber)

    def _set_io(io_list, ch_idx, active):
        is_ack = io_list is io_in_labels
        on_bg, on_fg = (_IO_ACK_ON_BG, _IO_ACK_ON_FG) if is_ack else (_IO_ON_BG, _IO_ON_FG)
        off_bg, off_fg = (_IO_ACK_OFF_BG, _IO_ACK_OFF_FG) if is_ack else (_IO_OFF_BG, _IO_OFF_FG)
        try:
            if ch_idx < len(io_list) and io_list[ch_idx].winfo_exists():
                io_list[ch_idx].config(bg=on_bg if active else off_bg, fg=on_fg if active else off_fg)
        except Exception: pass

    def _set_safety_indicator(active):
        try:
            if safety_lbl.winfo_exists(): safety_lbl.config(bg=_IO_ON_BG if active else _IO_OFF_BG, fg=_IO_ON_FG if active else _IO_OFF_FG)
        except Exception: pass

    def _set_x2_indicator(active):
        try:
            if x2_lbl.winfo_exists(): x2_lbl.config(bg=_IO_ACK_ON_BG if active else _IO_ACK_OFF_BG, fg=_IO_ACK_ON_FG if active else _IO_ACK_OFF_FG)
        except Exception: pass

    def _set_x4_indicator(active):
        try:
            if x4_lbl.winfo_exists(): x4_lbl.config(bg=_IO_ACK_ON_BG if active else _IO_ACK_OFF_BG, fg=_IO_ACK_ON_FG if active else _IO_ACK_OFF_FG)
        except Exception: pass

    _rework_blink = {"active": False, "on": False}

    def _rework_blink_tick():
        if not _rework_blink["active"]:
            try: rework_lbl.config(text="")
            except Exception: pass
            return
        _rework_blink["on"] = not _rework_blink["on"]
        try:
            rework_lbl.config(text="⚠  REWORK PART  ⚠" if _rework_blink["on"] else "")
        except Exception: pass
        _after(500, _rework_blink_tick)

    def _set_rework_active(active: bool):
        """X3 (rework select) is high -- this cable is a rework part, not a
        fresh one. Drives the blinking badge and, at test time, which barcode
        template gets printed (plain vs. the R-suffixed rework template).
        """
        was_active = _rework_blink["active"]
        state["is_rework"] = active
        _rework_blink["active"] = active
        if active and not was_active:
            _rework_blink["on"] = False
            _after(0, _rework_blink_tick)
        elif not active:
            _after(0, lambda: rework_lbl.config(text=""))

    def _clear_all_io_indicators():
        """Force every per-channel output/ack indicator back to its resting
        (off) look immediately, instead of waiting for the background poll
        loop to notice the PLC is idle -- that gap is exactly the window
        where a just-finished test still shows stale "glowing" pins, most
        visibly after a PASS since polling doesn't resume until the operator
        scans the label.
        """
        for i in range(8):
            _after(0, lambda idx=i: (_set_io(io_contact_labels, idx, False),
                                      _set_io(io_ir_acw_labels, idx, False),
                                      _set_io(io_in_labels, idx, False)))
    scan_lf = ttk.LabelFrame(bottom, text="Label Scan Result", style="TC.TLabelframe")
    scan_lf.grid(row=0, column=1, sticky="nsew", padx=(0, 4))
    scan_inner = tk.Frame(scan_lf, bg="black", padx=6, pady=4); scan_inner.pack(fill="both", expand=True)

    scan_verdict_lbl = tk.Label(scan_inner, text="—", bg="black", fg="#555",
                                font=("Arial", 11, "bold"), anchor="w")
    scan_verdict_lbl.pack(fill="x")

    # The operator never has to click anywhere -- after a PASS this entry
    # gets keyboard focus directly, so a keyboard-wedge scanner's trigger
    # pull types the code straight in here and its own Enter submits it.
    ent_scan = _ent(scan_inner, editable=False)
    ent_scan.pack(fill="x", pady=(3, 3))

    def _lock_scan_entry():
        try:
            if ent_scan.winfo_exists():
                ent_scan.delete(0, "end")
                ent_scan.config(state="readonly")
        except Exception: pass

    # The scanned code is long and full of separators; wrap it rather than
    # truncate, so the operator can read the whole thing against the part.
    scan_data_lbl = tk.Label(scan_inner, text="Waiting for scan…", bg="black", fg="#666",
                             font=("Consolas", 8), anchor="nw", justify="left", wraplength=300)
    scan_data_lbl.pack(fill="both", expand=True, pady=(2, 0))

    def _set_scan_box(verdict: str, raw: str = ""):
        """verdict: "OK" | "NG" | "" (idle)."""
        colors = {"OK": ("✅  OK", "#76ff03"), "NG": ("❌  NG", "#ff5555")}
        text, fg = colors.get(verdict, ("—", "#555"))
        idle = "Waiting for scan…" if cfg.get("scan_enabled", True) else "Scan verification disabled"
        try:
            if scan_verdict_lbl.winfo_exists():
                scan_verdict_lbl.config(text=text, fg=fg)
            if scan_data_lbl.winfo_exists():
                scan_data_lbl.config(text=_fmt_scan(raw) if raw else idle,
                                     fg="#ccc" if raw else "#666")
        except Exception: pass
    _set_scan_box("")

    def _fit_scan_wrap(event):
        # wraplength is in pixels and has to follow the panel, or a long code
        # spills past the edge instead of wrapping inside it.
        try:
            if scan_data_lbl.winfo_exists(): scan_data_lbl.config(wraplength=max(event.width - 16, 80))
        except Exception: pass
    scan_inner.bind("<Configure>", _fit_scan_wrap)

    log_lf = ttk.LabelFrame(bottom, text="Log", style="TC.TLabelframe")
    log_lf.grid(row=0, column=2, sticky="nsew")
    log_txt = tk.Text(log_lf, bg="black", fg="#aaa", font=("Consolas", 8), bd=0, height=5)
    log_txt.pack(fill="both", expand=True, padx=4, pady=3); log_txt.config(state="disabled")
    def _log(msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        def _do_log():
            try:
                if log_txt.winfo_exists():
                    log_txt.config(state="normal"); log_txt.insert("end", f"{ts}  {msg}\n"); log_txt.see("end"); log_txt.config(state="disabled")
            except Exception: pass
        try: _after(0, _do_log)
        except Exception: pass
    def _load_specs(pno: str) -> bool:
        try:
            with db.get_dict_cursor() as cur:
                cur.execute("SELECT pname,cname,mname AS model,alc,chsel AS channel,vendorcode,eocode,testmode FROM settingmaster WHERE pno=%s", (pno,))
                master = cur.fetchone()
                if not master:
                    cur.execute("SELECT * FROM settingmaster WHERE pno=%s", (pno,))
                    master = cur.fetchone()
                if not master:
                    messagebox.showwarning("Not Found", f"Part number '{pno}' not found.")
                    return False
                pname = master.get("pname", ""); cname = master.get("cname", ""); mod = master.get("mname", master.get("model", ""))
                alc = master.get("alc", ""); channel = int(master.get("chsel", master.get("channel", 1)) or 1)
                vendor = master.get("vendorcode", ""); eo = master.get("eocode", master.get("eo_number", ""))
                testmode = master.get("testmode", "Combined")
                if testmode: testmode = testmode.strip()
                state.update({"pno": pno, "alc": alc, "model": mod, "vendor_code": vendor, "eo_number": eo or "", "pname": pname, "cname": cname, "num_channels": channel, "testmode": testmode})
                _fill_ro(ent_pname, pname); _fill_ro(ent_cust, cname); _fill_ro(ent_model, mod); _fill_ro(ent_alc, alc); _fill_ro(ent_vendor, vendor); _fill_ro(ent_eo, eo or ""); _fill_ro(ent_testtype, testmode)
                cur.execute("SELECT testname, chsel AS channel, appvol, testtime, min, max FROM settingspec WHERE pno=%s", (pno,))
                rows = cur.fetchall()
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
                    tree_spec.insert("", "end", tags=(tag,), values=(test_key, str(ch), sp.get("appvol", "—"), sp.get("testtime", "—"), sp.get("min", "—"), sp.get("max", "—")))
                tree_spec.insert("", "end", tags=("contact",), values=("Contact Test", str(ch), "—", "—", "—", "—"))
            spec_status_lbl.config(text=f"[ {channel} channel(s) loaded ]", fg="#4caf50")
            _log(f"Specs loaded for {pno} ({channel} ch)")
            return True
        except Exception as ex:
            messagebox.showerror("DB Error", str(ex))
            _log(f"DB Error: {ex}"); return False

    def _load_history(pno=None):
        tree_hist.delete(*tree_hist.get_children())
        try:
            with db.get_cursor() as cur:
                if pno: cur.execute("SELECT date, time, pno, lotno, empcode, result FROM testmaster WHERE pno=%s ORDER BY id DESC LIMIT 15", (pno,))
                else: cur.execute("SELECT date, time, pno, lotno, empcode, result FROM testmaster ORDER BY id DESC LIMIT 15")
                for row in cur.fetchall():
                    tag = "pass" if row[5] == "PASS" else "fail"
                    tree_hist.insert("", "end", tags=(tag,), values=row)
        except Exception: pass

    def _load_today_pass(pno=None):
        tree_lot.delete(*tree_lot.get_children())
        try:
            with db.get_cursor() as cur:
                query = "SELECT testmaster.lotno, testmaster.alc, testresult.result, testmaster.scanresult, testmaster.empcode, testmaster.time FROM testmaster JOIN testresult ON testmaster.lotno = testresult.lotno WHERE testresult.result = 'PASS' AND DATE(testmaster.date) = CURDATE() " + (f"AND testmaster.pno='{pno}' " if pno else "") + "ORDER BY testmaster.time DESC"
                cur.execute(query); rows = cur.fetchall()
        except Exception: rows = []
        ok = len(rows)
        try:
            with db.get_cursor() as cur2:
                q2 = "SELECT COUNT(*) FROM testmaster WHERE result='FAIL' AND DATE(date)=CURDATE()" + (f" AND pno='{pno}'" if pno else "")
                cur2.execute(q2); ng = cur2.fetchone()[0] or 0
        except Exception: ng = 0
        state["total"] = ok + ng; state["ok"] = ok; state["ng"] = ng; _after(0, _update_counts)
        for idx, row in enumerate(rows, start=1):
            tree_lot.insert("", "end", values=(len(rows) - idx + 1, row[0], row[1], row[2] or "—", row[3] or "—", row[4], row[5]))

    _VISION_IMG_DIR = os.path.join(os.path.dirname(__file__), "vision_captures")

    def _save_vision_pass_image(lot_no: str) -> str:
        """If vision passed on this cycle, save the judged (boxed) frame to
        vision_captures/<lotno>.jpg and return its path, else None.
        """
        result = state.get("last_vision_result")
        if result is None or result.judgement != "OK" or not _cv2_ok:
            return None
        frame = _annotate_vision_frame(result)
        if frame is None:
            return None
        try:
            os.makedirs(_VISION_IMG_DIR, exist_ok=True)
            path = os.path.join(_VISION_IMG_DIR, f"{lot_no}.jpg")
            cv2.imwrite(path, frame)
            _log(f"Vision pass image saved: {path}")
            return path
        except Exception as ex:
            _log(f"Vision image save error: {ex}")
            return None

    def _save_result(lot_no: str, overall: str, ir_ch: dict, acw_ch: dict, contact_ch: dict, vision_img: str = None):
        try:
            with db.get_cursor(commit=True) as cur:
                now = datetime.datetime.now(); pno = state["pno"]; emp = ent_emp.get().strip()
                cur.execute("INSERT INTO testmaster (pno, pname, model, alc, channel, lotno, date, time, empcode, result, machine, visionimg) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (pno, state["pname"], state["model"], state["alc"], str(state["num_channels"]), lot_no, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), emp, overall, cfg["machine_id"], vision_img))
                for ch in range(1, state["num_channels"] + 1):
                    cur.execute("INSERT INTO testresult (lotno, channel, ir_volts, ir_resistance, ir_current, ir_result, acw_volts, acw_current, acw_result, contact_result) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (lot_no, str(ch), str(ir_ch.get(ch, {}).get("appvol", "")), str(ir_ch.get(ch, {}).get("value", "")), "0.01", ir_ch.get(ch, {}).get("result", ""), str(acw_ch.get(ch, {}).get("appvol", "")), str(acw_ch.get(ch, {}).get("value", "")), acw_ch.get(ch, {}).get("result", ""), contact_ch.get(ch, {}).get("result", "")))
            _log(f"Saved {overall} â†’ {lot_no}")
        except Exception as ex: _log(f"Save error: {ex}")

    def _update_scan_result(lot_no: str, scan_res: str):
        try:
            with db.get_cursor(commit=True) as cur:
                cur.execute("UPDATE testmaster SET scanresult=%s WHERE lotno=%s", (scan_res, lot_no))
        except Exception as ex: _log(f"Scan update error: {ex}")

    def _validate_employee(empno: str) -> bool:
        emp_file = os.path.join(os.path.dirname(__file__), "emp.txt")
        try: return empno in open(emp_file).read()
        except FileNotFoundError: return True

    def _plc_open() -> bool:
        """Open PLC Modbus RTU connection."""
        if not _modbus_ok: return False
        if plc.is_open: plc.close(); time.sleep(0.05)
        ok = plc.open()
        if not ok: _log("PLC: could not open Modbus RTU port"); set_com_status("IO Ctrl", False)
        else: set_com_status("IO Ctrl", True)
        return ok

    def _run_contact_test(n_ch: int) -> tuple:
        """Contact test via PLC — set each channel coil, read acknowledge input."""
        _log("Contact Test → PLC Modbus (M coils / X inputs)")
        if not _plc_open():
            _log("CRITICAL: PLC Modbus port blocked or disconnected!")
            return False, {ch: {"result": "FAIL"} for ch in range(1, n_ch + 1)}
        # Ensure safety relay is in Contact Test mode
        _log("M28 (Safety Relay) -> ON (Contact Mode)")
        plc.safety_relay_to_contact()
        _after(0, lambda: _set_safety_indicator(True))
        time.sleep(0.5)
        x4_ack = plc.read_input(_PLC_SAFETY_ACK)
        _log(f"X4 (Safety ACK): {'OK' if x4_ack else 'NO ACK!'}")
        _after(0, lambda a=x4_ack: _set_x4_indicator(a))
        contact_res = {}; all_pass = True
        for ch in range(1, n_ch + 1):
            _log(f"Contact Test: Testing CH{ch}...")
            # Turn ON channel coil
            _log(f"CH{ch} -> ON")
            plc.set_channel(ch, True)
            _after(0, lambda c=ch-1: _set_io(io_contact_labels, c, True))
            time.sleep(0.5)
            # Verify X2 is still True (Contact OK)
            # Note: X20-X27 are hardware-linked to IR/ACW relays only, so we do not check them here.
            x2_passed = plc.is_contact_ok()
            _log(f"X2 (Contact OK): {'OK (High)' if x2_passed else 'NG (Low)'}")
            passed = x2_passed
            
            contact_res[ch] = {"result": "PASS" if passed else "FAIL"}
            if not passed:
                all_pass = False
                _log(f"Contact (CH{ch}): Failed — X2 (Contact OK) went Low!")
            _after(0, lambda c=ch-1, p=passed: _set_cell("Contact", c, "OK" if p else "NG", p))
            # Turn OFF channel coil before next
            _log(f"CH{ch} -> OFF")
            plc.set_channel(ch, False)
            _after(0, lambda c=ch-1: _set_io(io_contact_labels, c, False))
            time.sleep(0.5)
        plc.close()
        _after(0, lambda p=all_pass: _set_row_result("Contact", p))
        _log(f"Contact: {'PASS' if all_pass else 'FAIL'}"); return all_pass, contact_res

    def _run_contact_ch1_check() -> bool:
        """Quick contact check on CH1 only — verifies cable is in jig."""
        _log("Contact CH1 check → cable in jig?")
        if not _plc_open():
            _log("CRITICAL: PLC Modbus port blocked or disconnected!")
            return False
            
        # 1) Turn on Safety Relay and confirm X4
        _log("M28 (Safety Relay) -> ON (Contact Mode)")
        plc.safety_relay_to_contact()
        time.sleep(0.5)
        x4_ack = plc.read_input(_PLC_SAFETY_ACK)
        _log(f"X4 (Safety ACK): {'OK (High)' if x4_ack else 'NO ACK! (Low)'}")
        _after(0, lambda a=x4_ack: _set_x4_indicator(a))
        
        # 2) Turn on CH1 and read X2
        plc.set_channel(1, True)
        _after(0, lambda: _set_io(io_contact_labels, 0, True))
        time.sleep(0.5)
        passed_ack = plc.read_channel_ack(1)
        passed_x2 = plc.is_contact_ok()
        _after(0, lambda a=passed_ack: _set_io(io_in_labels, 0, a))
        
        plc.set_channel(1, False)
        _after(0, lambda: _set_io(io_contact_labels, 0, False))
        
        if not passed_x2:
            _log("CH1 contact: NG — X2 (Contact OK) is False. Cable not detected.")
            plc.close()
            return False
            
        _log("CH1 contact: OK — X2 is High (cable in jig)")
        
        # 3) Turn off safety relay M28 and ensure no X4 feedback is received
        _log("M28 (Safety Relay) -> OFF (Preparing for HV Mode)")
        plc.safety_relay_to_hv()
        _after(0, lambda: _set_safety_indicator(False))
        time.sleep(0.5)
        x4_off = plc.read_input(_PLC_SAFETY_ACK)
        _log(f"X4 (Safety ACK): {'Still ON! (WARNING)' if x4_off else 'OFF (Low - OK)'}")
        _after(0, lambda a=x4_off: _set_x4_indicator(a))
        
        plc.close()
        return True

    def _plc_reset():
        """Reset all channel coils and safety relay to OFF."""
        plc.reset_all_channels()
        _log("M28 (Safety Relay) -> ON (Contact Mode)")
        plc.safety_relay_to_contact()
        time.sleep(0.05)

    def _check_contact_ok() -> bool:
        """Check if Contact OK is signaled via PLC input."""
        if not _plc_open(): return False
        connected = plc.is_contact_ok()
        plc.close()
        return connected



    def _run_ir_test(n_ch: int) -> tuple:
        _log("IR Test → MANU:EDIT:MODE IR | FUNC:TEST ON | MEAS?")
        if not _serial_ok or not hipot.open():
            _log("CRITICAL: HiPot not connected or port blocked!")
            set_com_status("HiPot", False)
            return False, {ch: {"result": "FAIL"} for ch in range(1, n_ch + 1)}
        if not _plc_open():
            _log("CRITICAL: PLC Modbus port blocked or disconnected!")
            return False, {ch: {"result": "FAIL"} for ch in range(1, n_ch + 1)}
            
        set_com_status("HiPot", True); time.sleep(0.5)
        if _plc_open():
            _log("M28 (Safety Relay) -> OFF (HV Mode)")
            plc.safety_relay_to_hv()
            _after(0, lambda: _set_safety_indicator(False))
            time.sleep(0.5)
            x4_ack = plc.read_input(_PLC_SAFETY_ACK)
            _log(f"X4 (Safety ACK): {'OK' if x4_ack else 'NO ACK!'}")
            _after(0, lambda a=x4_ack: _set_x4_indicator(a))
            
        all_pass = True; ir_res = {}
        if state.get("testmode", "Combined").strip().lower() == "combined":
            _log("IR Test: Testing all channels (Combined)...")
            if plc.is_open:
                plc.set_all_channels(n_ch, True)
                for i in range(n_ch): _after(0, lambda idx=i: _set_io(io_ir_acw_labels, idx, True))
                time.sleep(0.5)
                for ch in range(1, n_ch + 1):
                    ack = plc.read_channel_ack(ch)
                    _after(0, lambda c=ch-1, a=ack: _set_io(io_in_labels, c, a))
                    if not ack:
                        _log(f"IR (Combined): Channel {ch} ACK failed!")
                        all_pass = False
            s0 = state["spec_ir"].get(1, {}); v_kv = float(s0.get("appvol", 500)) / 1000.0; t_s = float(s0.get("testtime", 1.0)); v_min = float(s0.get("min", 100)); v_max = float(s0.get("max", 9999))
            _log(f"IR: commanding {s0.get('appvol', 500):.0f} V ({v_kv:.4f} kV) for {t_s:.1f}s")
            _, ir_val = hipot.run_ir_test(v_kv, t_s, v_min, v_max)
            for ch in range(1, n_ch + 1):
                s = state["spec_ir"].get(ch, {}); passed = float(s.get("min", 100)) <= ir_val <= float(s.get("max", 9999))
                if not passed: all_pass = False
                ir_res[ch] = {"appvol": s.get("appvol", 500), "value": ir_val, "result": "PASS" if passed else "FAIL"}
                _after(0, lambda c=ch-1, v=f"{ir_val:.0f}", p=passed: _set_cell("IR", c, v, p))
            if plc.is_open:
                plc.set_all_channels(n_ch, False)
                for i in range(n_ch): _after(0, lambda idx=i: (_set_io(io_ir_acw_labels, idx, False), _set_io(io_in_labels, idx, False)))
            _log(f"IR (Combined): {ir_val:.0f} MΩ — {'PASS' if all_pass else 'FAIL'}")
        else:
            for ch in range(1, n_ch + 1):
                _log(f"IR Test: Testing CH{ch}...")
                ack_ok = True
                if plc.is_open:
                    _log(f"CH{ch} -> ON")
                    plc.set_channel(ch, True)
                    _after(0, lambda idx=ch-1: _set_io(io_ir_acw_labels, idx, True))
                    time.sleep(0.5)
                    ack_ok = plc.read_channel_ack(ch)
                    _after(0, lambda idx=ch-1, a=ack_ok: _set_io(io_in_labels, idx, a))
                    if not ack_ok:
                        _log(f"IR (Individual): Channel {ch} ACK failed!")
                        all_pass = False
                s = state["spec_ir"].get(ch, {}); v_kv = float(s.get("appvol", 500)) / 1000.0; t_s = float(s.get("testtime", 1.0)); v_min = float(s.get("min", 100)); v_max = float(s.get("max", 9999))
                _log(f"IR CH{ch}: commanding {s.get('appvol', 500):.0f} V ({v_kv:.4f} kV) for {t_s:.1f}s")
                _, ir_val = hipot.run_ir_test(v_kv, t_s, v_min, v_max)
                passed = float(s.get("min", 100)) <= ir_val <= float(s.get("max", 9999))
                if not passed or not ack_ok: all_pass = False
                ir_res[ch] = {"appvol": s.get("appvol", 500), "value": ir_val, "result": "PASS" if (passed and ack_ok) else "FAIL"}
                _after(0, lambda c=ch-1, v=f"{ir_val:.0f}", p=(passed and ack_ok): _set_cell("IR", c, v, p))
                if plc.is_open:
                    _log(f"CH{ch} -> OFF")
                    plc.set_channel(ch, False)
                    _after(0, lambda idx=ch-1: (_set_io(io_ir_acw_labels, idx, False), _set_io(io_in_labels, idx, False)))
                    time.sleep(0.05)
            _log(f"IR (Individual): {'PASS' if all_pass else 'FAIL'}")

        hipot.close()
        if plc.is_open: plc.close()
        _after(0, lambda p=all_pass: _set_row_result("IR", p))
        return all_pass, ir_res

    def _run_acw_test(n_ch: int) -> tuple:
        _log("ACW Test → MANU:EDIT:MODE ACW | FUNC:TEST ON | MEAS?")
        if not _serial_ok or not hipot.open():
            _log("CRITICAL: HiPot not connected or port blocked!")
            set_com_status("HiPot", False)
            return False, {ch: {"result": "FAIL"} for ch in range(1, n_ch + 1)}
        if not _plc_open():
            _log("CRITICAL: PLC Modbus port blocked or disconnected!")
            return False, {ch: {"result": "FAIL"} for ch in range(1, n_ch + 1)}
            
        time.sleep(0.5)
        if _plc_open():
            _log("M28 (Safety Relay) -> OFF (HV Mode)")
            plc.safety_relay_to_hv()
            _after(0, lambda: _set_safety_indicator(False))
            time.sleep(0.5)
            x4_ack = plc.read_input(_PLC_SAFETY_ACK)
            _log(f"X4 (Safety ACK): {'OK' if x4_ack else 'NO ACK!'}")
            _after(0, lambda a=x4_ack: _set_x4_indicator(a))
            
        all_pass = True; acw_res = {}
        if state.get("testmode", "Combined").strip().lower() == "combined":
            _log("ACW Test: Testing all channels (Combined)...")
            if plc.is_open:
                plc.set_all_channels(n_ch, True)
                for i in range(n_ch): _after(0, lambda idx=i: _set_io(io_ir_acw_labels, idx, True))
                time.sleep(0.5)
                for ch in range(1, n_ch + 1):
                    ack = plc.read_channel_ack(ch)
                    _after(0, lambda c=ch-1, a=ack: _set_io(io_in_labels, c, a))
                    if not ack:
                        _log(f"ACW (Combined): Channel {ch} ACK failed!")
                        all_pass = False
            s0 = state["spec_acw"].get(1, {}); v_kv = float(s0.get("appvol", 1500)) / 1000.0; t_s = float(s0.get("testtime", 3.0)); v_min = float(s0.get("min", 0.0)); v_max = float(s0.get("max", 10.0))
            _log(f"ACW: commanding {s0.get('appvol', 1500):.0f} V ({v_kv:.4f} kV) for {t_s:.1f}s")
            _, acw_val = hipot.run_acw_test(v_kv, t_s, v_min, v_max)
            for ch in range(1, n_ch + 1):
                s = state["spec_acw"].get(ch, {}); passed = float(s.get("min", 0)) <= acw_val <= float(s.get("max", 10))
                if not passed: all_pass = False
                acw_res[ch] = {"appvol": s.get("appvol", 1500), "value": acw_val, "result": "PASS" if passed else "FAIL"}
                _after(0, lambda c=ch-1, v=f"{acw_val:.2f}", p=passed: _set_cell("ACW", c, v, p))
            if plc.is_open:
                plc.set_all_channels(n_ch, False)
                for i in range(n_ch): _after(0, lambda idx=i: (_set_io(io_ir_acw_labels, idx, False), _set_io(io_in_labels, idx, False)))
            _log(f"ACW (Combined): {acw_val:.2f} mA — {'PASS' if all_pass else 'FAIL'}")
        else:
            for ch in range(1, n_ch + 1):
                _log(f"ACW Test: Testing CH{ch}...")
                ack_ok = True
                if plc.is_open:
                    _log(f"CH{ch} -> ON")
                    plc.set_channel(ch, True)
                    _after(0, lambda idx=ch-1: _set_io(io_ir_acw_labels, idx, True))
                    time.sleep(0.5)
                    ack_ok = plc.read_channel_ack(ch)
                    _after(0, lambda idx=ch-1, a=ack_ok: _set_io(io_in_labels, idx, a))
                    if not ack_ok:
                        _log(f"ACW (Individual): Channel {ch} ACK failed!")
                        all_pass = False
                s = state["spec_acw"].get(ch, {}); v_kv = float(s.get("appvol", 1500)) / 1000.0; t_s = float(s.get("testtime", 3.0)); v_min = float(s.get("min", 0.0)); v_max = float(s.get("max", 10.0))
                _log(f"ACW CH{ch}: commanding {s.get('appvol', 1500):.0f} V ({v_kv:.4f} kV) for {t_s:.1f}s")
                _, acw_val = hipot.run_acw_test(v_kv, t_s, v_min, v_max)
                passed = float(s.get("min", 0)) <= acw_val <= float(s.get("max", 10))
                if not passed or not ack_ok: all_pass = False
                acw_res[ch] = {"appvol": s.get("appvol", 1500), "value": acw_val, "result": "PASS" if (passed and ack_ok) else "FAIL"}
                _after(0, lambda c=ch-1, v=f"{acw_val:.2f}", p=(passed and ack_ok): _set_cell("ACW", c, v, p))
                if plc.is_open:
                    _log(f"CH{ch} -> OFF")
                    plc.set_channel(ch, False)
                    _after(0, lambda idx=ch-1: (_set_io(io_ir_acw_labels, idx, False), _set_io(io_in_labels, idx, False)))
                    time.sleep(0.05)
            _log(f"ACW (Individual): {'PASS' if all_pass else 'FAIL'}")

        hipot.close()
        if plc.is_open:
            plc.set_all_channels(n_ch, False)
            _log("M28 (Safety Relay) -> ON (Contact Mode)")
            plc.safety_relay_to_contact()
            time.sleep(0.5)
            x4_ack = plc.read_input(_PLC_SAFETY_ACK)
            _log(f"X4 (Safety ACK): {'OK' if x4_ack else 'NO ACK!'}")
            _after(0, lambda a=x4_ack: _set_x4_indicator(a))
            plc.close()
        for i in range(n_ch): _after(0, lambda idx=i: (_set_io(io_ir_acw_labels, idx, False), _set_io(io_in_labels, idx, False)))
        _after(0, lambda: _set_safety_indicator(True))
        _after(0, lambda p=all_pass: _set_row_result("ACW", p))
        return all_pass, acw_res

    def _run_test_sequence():
        if not state["pno"]: _after(0, lambda: _log("No part loaded.")); return
        emp = ent_emp.get().strip()
        if not emp: _after(0, lambda: messagebox.showwarning("Validation", "Enter Employee ID.")); return
        if not _validate_employee(emp): _after(0, lambda: messagebox.showwarning("Auth", "Employee number not found.")); return
        if state["test_running"]: return
        state["test_running"] = True; state["start_time"] = datetime.datetime.now(); state["flag"] = True; state["last_vision_result"] = None
        _after(0, lambda: btn_start.config(state="disabled", bg="#555", text="TESTING...")); _after(0, _reset_test_display); _after(0, lambda: result_lbl.config(text="TESTING...", bg="#e65100", fg="white")); _after(0, lambda: scan_lbl.config(text="⏳  Test in progress...", bg="#001830", fg="#e8a000")); _after(0, _lock_scan_entry)
        n_ch = state["num_channels"]; _log("── Test Started ──")

        # Re-check X3 (rework select) fresh for this cycle -- the background
        # poll that normally tracks it is stopped for the whole test, and
        # this flag decides which barcode template gets printed at the end.
        if _plc_open():
            is_rework = plc.is_rework_on()
            plc.close()
            _log(f"X3 (Rework select): {'ON — rework part' if is_rework else 'OFF — regular part'}")
            _after(0, lambda a=is_rework: _set_rework_active(a))

        # --- VISION VERIFICATION (Contour Matching) ---
        _after(0, lambda: scan_lbl.config(text="👁  Vision Verification...", bg="#001830", fg="#e8a000"))
        if vision_ctrl:
            
            vision_ctrl.reload_config()

            if not vision_ctrl.has_model(state["pno"]):
                _log(f"Vision WARNING: No vision model configured for part '{state['pno']}'. Skipping vision.")
            else:
                # Run inspection (capture frame + contour match)
                vision_result = vision_ctrl.inspect(state["pno"])
                state["vision_result"] = vision_result.judgement
                state["last_vision_result"] = vision_result
                _after(0, lambda r=vision_result: _show_vision_frame(r))

                if vision_result.judgement == "ERROR":
                    _log(f"Vision ERROR: {vision_result.error}. Skipping vision.")
                elif not vision_result.ok:
                    _log(f"Vision NG: {vision_result.error} (score={vision_result.match_score:.4f}). Skipping vision.")
                else:
                    _log(f"Vision OK: score={vision_result.match_score:.4f} in {vision_result.processing_time_ms}ms")
        else:
            _log("Vision skipped (not initialized/disabled). Proceeding with electrical tests.")
        # --- END VISION VERIFICATION ---

        _after(0, lambda: scan_lbl.config(text="Checking contact (CH1)...", bg="#001830", fg="#e8a000"))
        if _modbus_ok:
            if not _run_contact_ch1_check():
                _log("Contact NOT OK (X2) — aborting"); _after(0, lambda: messagebox.showwarning("Contact", "Contact NOT OK. Please check the jig.")); _after(0, lambda: result_lbl.config(text="READY", bg="#1a1a1a", fg="#555")); _after(0, lambda: scan_lbl.config(text="❌  Contact NOT OK — check and retry", bg="#220000", fg="#ff5555"))
                _clear_all_io_indicators()
                state["test_running"] = False; _after(0, lambda: btn_start.config(state="normal", bg="#1b5e20", fg="white", text="▶  START TEST")); _after(0, _input_poll_start); return
        _after(0, lambda: scan_lbl.config(text="⚡  IR Testing (Insulation Resistance)...", bg="#001830", fg="#e8a000")); ir_pass, ir_ch = _run_ir_test(n_ch); time.sleep(0.5)
        if not ir_pass: state["flag"] = False; _finish_test("FAIL", ir_ch, {}, {}); return
        _after(0, lambda: scan_lbl.config(text="âš¡  ACW Testing (Withstand Voltage)â€¦", bg="#001830", fg="#e8a000")); acw_pass, acw_ch = _run_acw_test(n_ch); time.sleep(0.5)
        if not acw_pass: state["flag"] = False; _finish_test("FAIL", ir_ch, acw_ch, {}); return
        _after(0, lambda: scan_lbl.config(text="🔗  Contact Testing…", bg="#001830", fg="#e8a000")); contact_pass, contact_ch = _run_contact_test(n_ch); time.sleep(0.2)
        overall = "PASS" if (ir_pass and acw_pass and contact_pass) else "FAIL"
        state["flag"] = (overall == "PASS"); _finish_test(overall, ir_ch, acw_ch, contact_ch)

    def _finish_test(overall: str, ir_ch: dict, acw_ch: dict, contact_ch: dict):
        _clear_all_io_indicators()
        if _plc_open():
            _log("Resetting all PLC pins (Contact + IR/ACW + Safety Relay)...")
            plc.reset_all_channels()
            plc.safety_relay_to_hv() # Resets M28 to False (default state)
            plc.close()
        _after(0, lambda: _set_safety_indicator(False))  # match the physical reset above
            
        pno = state["pno"]; lot_no = _generate_lot_number(pno, cfg["machine_id"]); state["lot_no"] = lot_no; state["labelstr"] = lot_no
        elapsed_str = f"{(datetime.datetime.now() - state['start_time']).total_seconds():.1f}" if state["start_time"] else "—"
        state["total"] += 1; state["ok" if overall == "PASS" else "ng"] += 1
        _after(0, _update_counts); _after(0, lambda l=lot_no: lot_lbl.config(text=l)); _after(0, lambda e=elapsed_str: elapsed_lbl.config(text=e)); _after(0, lambda l=lot_no: _fill_ro(ent_lot, l))
        vision_img_path = _save_vision_pass_image(lot_no)
        _save_result(lot_no, overall, ir_ch, acw_ch, contact_ch, vision_img_path)
        if overall == "PASS":
            _after(0, lambda: result_lbl.config(text="PASS", bg="#0033aa", fg="white")); _after(0, lambda: scan_lbl.config(text="✅  PASS — Scan the printed barcode label", bg="#0a2200", fg="#76ff03")); _play_wav("OK.WAV"); blink_stop()
            threading.Thread(target=_print_barcode_label, args=(pno, state["alc"], state["model"], state["vendor_code"], state["eo_number"], lot_no, cfg["machine_id"], state.get("is_rework", False)), daemon=True).start()
            if cfg.get("scan_enabled", True):
                # Focus immediately, not after a delay: printers eject a label
                # fast enough that a delay left the entry still readonly when
                # the operator's actual scan arrived, dropping it silently and
                # leaving the box showing the previous part's result -- which
                # reads exactly like results lagging one part behind.
                _after(0, _show_scan_entry)
            else:
                _after(0, lambda: _set_scan_box(""))
                _after(500, _input_poll_start)
        else:
            _after(0, lambda: result_lbl.config(text="FAIL", bg="#b71c1c", fg="white")); _after(0, lambda: scan_lbl.config(text="âŒ  FAIL — Check cable and retry", bg="#220000", fg="#ff5555")); _play_wav("NG.WAV"); blink_start()
        _after(0, lambda: _load_today_pass(pno)); _after(0, lambda: _load_history(pno)); _log(f"â”€â”€ Test Complete: {overall} | Lot: {lot_no} | Time: {elapsed_str}s â”€â”€")
        state["test_running"] = False; _after(0, lambda: btn_start.config(state="normal", bg="#1b5e20" if overall == "PASS" else "#b71c1c", fg="white", text="â–¶  START TEST"))
        if overall == "FAIL": _after(200, _input_poll_start)

    def _show_scan_entry():
        """Called once a PASS has had time to print. Puts keyboard focus on
        the entry inside the Label Scan Result box, so a keyboard-wedge
        scanner's trigger pull -- which just "types" the code followed by
        its own Enter -- lands there directly with no click needed."""
        try:
            ent_scan.config(state="normal"); ent_scan.delete(0, "end"); ent_scan.focus_set()
        except Exception: pass
        _set_scan_box("")
    def _on_scan_enter(event=None):
        scanned = ent_scan.get().strip(); labelstr = state.get("labelstr", "")
        if not scanned: return
        print(f"[SCAN DEBUG] labelstr={labelstr!r} scanned={scanned!r} result={_scan_lot_ok(scanned, labelstr)}")
        if _scan_lot_ok(scanned, labelstr): res_str = "OK"; _log(f"Scan verify: OK ({_fmt_scan(scanned)})")
        else: res_str = "NG"; _log(f"Scan verify: NG (expected '{labelstr}', got '{_fmt_scan(scanned)}')")
        _set_scan_box(res_str, scanned)
        _update_scan_result(state["lot_no"], res_str); _after(2000, _lock_scan_entry); _after(2100, _input_poll_start)
    ent_scan.bind("<Return>", _on_scan_enter)

    def _input_poll_once():
        if not state.get("input_polling"): return
        if state["test_running"] or not state["pno"]: _after(500, _input_poll_once); return
        def _poll():
            pressed = _update_io_display()
            if pressed: _log("START button pressed (PLC X1)"); _after(0, _trigger_test)
            else: _after(500, _input_poll_once)
        threading.Thread(target=_poll, daemon=True).start()
    def _input_poll_start():
        if not _modbus_ok or state.get("input_polling"): return
        state["input_polling"] = True; _input_poll_once()
    def _input_poll_stop(): state["input_polling"] = False
    def _update_io_display() -> bool:
        """Refresh IO indicators from PLC (reads X0~X7 and X20~X27 inputs and
        actual channel coils) in a single open/close cycle, and report whether
        the physical START button (X0) is pressed.

        This used to be two separate open/close cycles per poll tick (one just
        to check X0, another for everything else) — reopening the port only
        ~15ms after closing it was flaky on this USB-serial adapter and was
        the main source of intermittent "could not open Modbus RTU port"
        errors, including fighting a manual test from COM Port Settings.
        """
        if not _plc_open(): return False
        pressed = False
        try:
            # Sync inputs (X20-X27)
            bits = plc.read_inputs_bulk(0x0410, 8)
            for i in range(8): _after(0, lambda idx=i, a=bits[i]: _set_io(io_in_labels, idx, a))
            # Sync actual outputs (M20-M27 and M30-M37)
            ir_acw_bits = plc.read_coils_bulk(0x0814, 8)
            contact_bits = plc.read_coils_bulk(0x081E, 8)
            for ch in range(1, 9):
                o_ir = ir_acw_bits[ch-1] if ir_acw_bits and len(ir_acw_bits) >= ch else False
                o_cont = contact_bits[ch-1] if contact_bits and len(contact_bits) >= ch else False
                _after(0, lambda idx=ch-1, o_ir=o_ir, o_cont=o_cont: (_set_io(io_ir_acw_labels, idx, o_ir), _set_io(io_contact_labels, idx, o_cont)))
                
            # Sync safety relay (M28)
            m28_state = plc.read_coil(0x081C)
            _after(0, lambda a=m28_state: _set_safety_indicator(a))
            
            # Sync X0-X7 to get X0 (START), X2 (Contact OK), X3 (Rework select) and X4 (Safety ACK)
            x0_7_bits = plc.read_inputs_bulk(0x0400, 8)
            pressed = x0_7_bits[0] if x0_7_bits else False
            x2_state = x0_7_bits[2] if x0_7_bits and len(x0_7_bits) > 2 else False
            x3_state = x0_7_bits[3] if x0_7_bits and len(x0_7_bits) > 3 else False
            x4_state = x0_7_bits[4] if x0_7_bits and len(x0_7_bits) > 4 else False
            _after(0, lambda a=x2_state: _set_x2_indicator(a))
            _after(0, lambda a=x3_state: _set_rework_active(a))
            _after(0, lambda a=x4_state: _set_x4_indicator(a))
        except Exception: pass
        finally: plc.close()
        return pressed

    def _trigger_test():
        if state["test_running"]: return
        if not state["pno"]: _log("No part number loaded."); return
        if not ent_emp.get().strip(): _after(0, lambda: messagebox.showwarning("Validation", "Enter Employee ID before testing.")); return
        _input_poll_stop(); _reset_test_display(); threading.Thread(target=_run_test_sequence, daemon=True).start()
    btn_start.config(command=lambda: _trigger_test())

    def _clear_all():
        _input_poll_stop()
        ent_emp.config(state="normal"); ent_emp.delete(0, "end"); ent_emp.config(bg="black")
        ent_pno.config(state="normal"); ent_pno.delete(0, "end"); ent_pno.config(state="readonly", bg="#0d0d0d")
        ent_jig.config(state="normal"); ent_jig.delete(0, "end"); ent_jig.config(state="readonly", bg="#0d0d0d")
        for e in [ent_pname, ent_cust, ent_model, ent_alc, ent_vendor, ent_eo, ent_lot, ent_testtype]: e.config(state="normal"); e.delete(0, "end"); e.config(state="readonly")
        tree_spec.delete(*tree_spec.get_children()); tree_lot.delete(*tree_lot.get_children()); _reset_test_display()
        spec_status_lbl.config(text="[ No part loaded ]", fg="#444"); _lock_scan_entry(); _set_scan_box("")
        state.update({"pno": None, "num_channels": 0, "spec_ir": {}, "spec_acw": {}, "lot_no": "", "labelstr": "", "flag": True, "last_vision_result": None})
        btn_start.config(bg="#1a1a1a", fg="#444"); _log("Cleared."); ent_emp.focus_set()
    tk.Button(left_area, text="⟳  CLEAR / RESET", bg="#2a2a2a", fg="#aaa", font=("Arial", 10, "bold"), pady=5, bd=0, cursor="hand2", activebackground="#444", activeforeground="white", command=_clear_all).pack(fill="x", pady=(3, 0))

    def _on_emp_enter(event=None):
        emp = ent_emp.get().strip()
        if not emp: return
        if not _validate_employee(emp):
            messagebox.showwarning("Auth", "Employee number not found.")
            ent_emp.delete(0, "end")
            return
        _log(f"Employee {emp} validated.")
        ent_emp.config(state="readonly", bg="#0d0d0d")
        ent_pno.config(state="normal", bg="black")
        ent_pno.focus_set()
    ent_emp.bind("<Return>", _on_emp_enter)

    def _on_pno_enter(event=None):
        pno = ent_pno.get().strip().upper()
        if not pno: return
        _log(f"Part Number '{pno}' entered. Waiting for JIG scan.")
        ent_pno.config(state="readonly", bg="#0d0d0d")
        ent_jig.config(state="normal", bg="black")
        ent_jig.focus_set()
    ent_pno.bind("<Return>", _on_pno_enter)

    _overlay_jobs = {}  # cam_id -> pending _after() id for reverting the overlay

    def _restore_cam(cam_id):
        lbl = cam_labels.get(cam_id)
        if lbl is None:
            return
        feed = cam_feeds_by_id.get(cam_id)
        if feed:
            feed.resume()
        else:
            try:
                lbl.config(image="", text=cam_default_text.get(cam_id, ""))
                lbl.image = None
            except Exception:
                pass

    def _annotate_vision_frame(result):
        """The frame vision judged, with the detected match boxed and scored
        on it (green=OK, red=NG, orange=ERROR). Shared by the live camera-panel
        overlay and the pass-image saved to disk, so both show the same thing.
        """
        if not _cv2_ok or result.frame is None:
            return None
        colors = {"OK": (0, 200, 0), "NG": (0, 0, 255), "ERROR": (0, 165, 255)}  # BGR
        color = colors.get(result.judgement, (0, 165, 255))
        frame = result.frame.copy()
        if result.match_box:
            x, y, w, h = result.match_box
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
            cv2.putText(frame, f"{result.judgement} {result.match_score:.2f}",
                        (x, max(14, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)
        return frame

    def _show_vision_frame(result):
        """Paint the frame vision judged, with the detected match boxed on it,
        into that camera's preview panel — so the operator sees *what* the
        matcher found, not just a score. Reverts to the live feed a few
        seconds later.
        """
        if not (_cv2_ok and _pil_ok) or result.frame is None or not vision_ctrl:
            return
        cam_id = 2 if vision_ctrl.config.get("camera_source", "cam1") == "cam2" else 1
        lbl = cam_labels.get(cam_id)
        if lbl is None:
            return

        frame = _annotate_vision_frame(result)
        feed = cam_feeds_by_id.get(cam_id)
        if feed:
            feed.pause()

        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb = cv2.resize(rgb, (208, 113))
            photo = ImageTk.PhotoImage(Image.fromarray(rgb))
            lbl.config(image=photo, text="")
            lbl.image = photo
        except Exception:
            return

        prev_job = _overlay_jobs.get(cam_id)
        if prev_job is not None:
            try: parent.after_cancel(prev_job)
            except Exception: pass
        _overlay_jobs[cam_id] = _after(4000, lambda cid=cam_id: _restore_cam(cid))

    def _vision_check_loaded_part(pno: str):
        """Verify the just-loaded part in front of the camera, before testing starts.

        Runs the same inspect() path the cycle uses, so the operator finds out the
        part is wrong (or the camera is blind) while they can still act on it —
        not after committing to a run. Off the UI thread: a capture takes ~1.5s
        and must not freeze the console.
        """
        base = f"Part '{pno}' loaded ({state['num_channels']} ch)"

        def _paint(suffix, fg, bg="#001830"):
            scan_lbl.config(text=f"{base} — {suffix}", bg=bg, fg=fg)

        if not vision_ctrl:
            _paint("Ready", "#4caf50"); return

        vision_ctrl.reload_config()
        if not vision_ctrl.has_model(pno):
            _log(f"Vision WARNING: No vision model configured for part '{pno}'.")
            _paint("NO VISION MODEL", "#e8a000"); return

        _paint("👁  Checking vision…", "#e8a000")

        def _work():
            try:
                result = vision_ctrl.inspect(pno)
            except Exception as ex:
                # Never leave the operator staring at "Checking vision…" forever.
                result = VisionResult(ok=False, judgement="ERROR", part_number=pno,
                                      error=str(ex))

            def _apply():
                # The operator may have moved on to another part while the
                # capture was in flight — a stale verdict must not overwrite it.
                if state.get("pno") != pno: return
                state["vision_result"] = result.judgement
                _show_vision_frame(result)
                if result.judgement == "OK":
                    _log(f"Vision OK: score={result.match_score:.4f} in {result.processing_time_ms}ms")
                    _paint(f"Vision OK ({result.match_score:.2f})", "#4caf50")
                elif result.judgement == "NG":
                    _log(f"Vision NG: {result.error} (score={result.match_score:.4f})")
                    _paint(f"VISION NG ({result.match_score:.2f}) — check the part", "#ff5555", bg="#220000")
                else:
                    _log(f"Vision ERROR: {result.error}")
                    _paint(f"VISION ERROR — {result.error}", "#e8a000")
            try: _after(0, _apply)
            except Exception: pass

        threading.Thread(target=_work, daemon=True).start()

    def _on_jig_enter(event=None):
        jig = ent_jig.get().strip().upper()
        if not jig: return
        pno = ent_pno.get().strip().upper()
        
        if not jig.endswith("J"):
            messagebox.showwarning("JIG Error", "End of the JIG label 'J' is compulsory. Please insert correct JIG.")
            ent_jig.delete(0, "end"); ent_jig.focus_set(); return
            
        if jig[:-1] != pno:
            messagebox.showwarning("JIG Error", "Master cable and master JIG are not same. Please insert correct JIG.")
            ent_jig.delete(0, "end"); ent_jig.focus_set(); return
            
        _log("JIG validated.")
        ent_jig.config(state="readonly", bg="#0d0d0d")
        
        _input_poll_stop(); spec_status_lbl.config(text="[ Loading… ]", fg="#e8a000"); tree_spec.delete(*tree_spec.get_children()); _fill_ro(ent_lot, ""); _reset_test_display()
        if _load_specs(pno):
            _load_history(pno); _load_today_pass(pno); btn_start.config(bg="#1b5e20", fg="white")
            _vision_check_loaded_part(pno)
            btn_start.focus_set(); _after(500, _input_poll_start)
        else:
            btn_start.config(bg="#1a1a1a", fg="#444"); _clear_all()
    ent_jig.bind("<Return>", _on_jig_enter)

    _load_history(); _log("System ready. Enter Employee ID and press ENTER.")
    set_com_status("HiPot", False); set_com_status("IO Ctrl", False); set_com_status("Scanner", False); set_com_status("Printer", False)
    ent_emp.focus_set()
