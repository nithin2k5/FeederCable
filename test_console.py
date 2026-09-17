"""
test_console.py
===============
Main EOL test console page for Feeder Cable tester.
Mirrors TestConsole.cs logic from the C# reference project.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
import mysql.connector
import threading
import datetime
from vision_engine.vision_controller import VisionController, VisionResult
import time
import os
import re
import configparser

# ── Type scale ────────────────────────────────────────────────────────────────
# Every font size on this page goes through _fs(), and every pixel dimension
# that exists only to hold text through _px(), so the whole console can be
# sized from this one number. The sizes below were picked at a desk; the
# operator reads this screen standing a metre back from the machine.
_FONT_SCALE = 1.2


def _fs(size: int) -> int:
    """A point size, scaled."""
    return max(1, round(size * _FONT_SCALE))


def _px(dim: int) -> int:
    """A pixel dimension of a box built around text, scaled with the text."""
    return round(dim * _FONT_SCALE)

# ── Optional hardware libraries (graceful degradation) ─────────────────────────
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

# ── Device presence, for the COM Status pills ─────────────────────────────────
# The label printer and the barcode scanner are not serial devices this page
# opens, so there is no port to probe: Windows either has them or it does not.
# Both names are the ones Windows shows -- Printers & scanners for the first,
# Device Manager for the second.
_PRINTER_NAME = "EOLPRINTER"
_SCANNER_NAME = "POS HID Barcode scanner"
# The lot (box) label goes to its own printer, on its own stock -- the part
# labels on EOLPRINTER are 35x25mm and come out one per PASS, and a lot label
# in that stream would be read as a part's label.
_LOT_PRINTER_NAME = "LOTPRINTER"

def _printer_online(name: str = _PRINTER_NAME) -> bool:
    """True when a printer by this name is installed and usable.

    Installed is not the same as usable: a printer someone has set to "Use
    Printer Offline", or one reporting an error, still enumerates, and a pill
    that went green for it would be lying about where the labels are going.
    """
    if not _print_ok:
        return False
    try:
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        wanted = name.strip().lower()
        match = next((p[2] for p in win32print.EnumPrinters(flags)
                      if str(p[2]).strip().lower() == wanted), None)
        if match is None:
            return False
    except Exception:
        return False
    # Being in the list is the fact that matters; the status query below only
    # refines it. Some drivers refuse a level-2 read, and a pill that went red
    # over a driver quirk would send an operator hunting for a printer that is
    # sitting there working, so a failed refinement keeps the "it is there".
    try:
        h = win32print.OpenPrinter(match)
        try:
            info = win32print.GetPrinter(h, 2)
        finally:
            win32print.ClosePrinter(h)
        status = int(info.get("Status", 0) or 0)
        attrs = int(info.get("Attributes", 0) or 0)
        bad = (getattr(win32print, "PRINTER_STATUS_OFFLINE", 0x00000080)
               | getattr(win32print, "PRINTER_STATUS_ERROR", 0x00000002)
               | getattr(win32print, "PRINTER_STATUS_NOT_AVAILABLE", 0x00001000))
        PRINTER_ATTRIBUTE_WORK_OFFLINE = 0x00000400
        return not (status & bad) and not (attrs & PRINTER_ATTRIBUTE_WORK_OFFLINE)
    except Exception:
        return True


def _pnp_device_present(name: str) -> bool:
    """True when Windows currently reports a plugged-in device by this name.

    SetupAPI rather than WMI: the scanner is a keyboard-wedge HID device with
    no port to open, and this needs no extra dependency, no COM apartment and
    no subprocess -- it just walks the present-device list and stops at the
    first match. Names are compared case-insensitively, and a substring
    counts, so a scanner that enumerates with a trailing revision still
    registers.
    """
    import ctypes
    from ctypes import wintypes

    class _DEVINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("ClassGuid", ctypes.c_byte * 16),
                    ("DevInst", wintypes.DWORD), ("Reserved", ctypes.POINTER(wintypes.ULONG))]

    DIGCF_PRESENT, DIGCF_ALLCLASSES = 0x02, 0x04
    SPDRP_DEVICEDESC, SPDRP_FRIENDLYNAME = 0x00, 0x0C
    INVALID_HANDLE = ctypes.c_void_p(-1).value
    try:
        api = ctypes.WinDLL("setupapi", use_last_error=True)
    except Exception:
        return False
    api.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    api.SetupDiGetClassDevsW.restype = wintypes.HANDLE
    api.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
    api.SetupDiEnumDeviceInfo.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(_DEVINFO)]
    api.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
    api.SetupDiGetDeviceRegistryPropertyW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(_DEVINFO), wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    api.SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL

    wanted = name.strip().lower()
    if not wanted:
        return False
    h = api.SetupDiGetClassDevsW(None, None, None, DIGCF_PRESENT | DIGCF_ALLCLASSES)
    if not h or h == INVALID_HANDLE:
        return False
    try:
        d = _DEVINFO(); d.cbSize = ctypes.sizeof(_DEVINFO)
        buf = ctypes.create_unicode_buffer(512)
        i = 0
        while api.SetupDiEnumDeviceInfo(h, i, ctypes.byref(d)):
            i += 1
            for prop in (SPDRP_FRIENDLYNAME, SPDRP_DEVICEDESC):
                if api.SetupDiGetDeviceRegistryPropertyW(h, ctypes.byref(d), prop, None,
                                                         ctypes.byref(buf), ctypes.sizeof(buf), None):
                    dev = (buf.value or "").strip().lower()
                    if dev and (dev == wanted or wanted in dev):
                        return True
                    break
        return False
    except Exception:
        return False
    finally:
        try: api.SetupDiDestroyDeviceInfoList(h)
        except Exception: pass


def _scanner_present(name: str = _SCANNER_NAME) -> bool:
    """True when the barcode scanner is plugged in."""
    return _pnp_device_present(name)


import auth
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
        "lot_label_enabled": cfg.getboolean("COM", "lot_label_enabled", fallback=True),
    }
def _save_cfg(d: dict):
    cfg = configparser.ConfigParser()
    cfg["COM"] = {k: str(v) for k, v in d.items()}
    with open(_CFG_PATH, "w") as f:
        cfg.write(f)

def _save_cfg_key(key: str, value):
    """Write one [COM] key, leaving everything else in the file alone.

    Deliberately not _save_cfg(): that rebuilds the whole [COM] section out of
    the six keys this page happens to load, which would drop every other
    device's port and baud that COM Settings keeps in the same file.
    """
    cfg = configparser.ConfigParser()
    cfg.read(_CFG_PATH)
    if not cfg.has_section("COM"):
        cfg.add_section("COM")
    cfg.set("COM", key, str(value))
    with open(_CFG_PATH, "w") as f:
        cfg.write(f)

# ISO/IEC 15434 labels carry non-printable separators, which render as nothing
# (or as boxes) in a Tk label. Show them as mnemonics so the operator sees the
# structure of what was scanned:
#   [)>[RS]06[GS]VT007[GS]P123[GS]S123[GS]T260905I1A2A0000006[GS][RS][EOT]
_SCAN_CTRL_NAMES = {
    "\x1e": "[RS]", "\x1d": "[GS]", "\x1f": "[US]",
    "\x04": "[EOT]", "\x05": "[ENQ]", "\r": "[CR]", "\n": "[LF]",
}

def _fmt_scan(raw: str) -> str:
    return "".join(_SCAN_CTRL_NAMES.get(ch, ch) for ch in raw)

def _scan_lot_ok(scanned: str, labelstr: str) -> bool:
    """PASS only if the lot number is a substring of one whole field of the
    scanned data, never spanning across a field boundary -- so a lot number
    that happens to only partially overlap two adjacent fields (part number,
    serial, etc.) can't produce a false OK.

    Fields are split on any non-alphanumeric character rather than on the
    specific ISO 15434 control bytes, since a keyboard-wedge scanner does
    not reliably deliver GS/RS/EOT as literal insertable characters -- but
    the envelope punctuation and separators are non-alphanumeric either way,
    so splitting on "not alnum" isolates the same fields regardless of
    exactly which bytes the scanner actually sends. Some label formats wrap
    the lot number in an ISO 15434 field starting with "T" (e.g.
    T260905I1A2A0000006); others (most current templates) print the bare lot
    number with no prefix at all -- either way the lot number is a substring
    of that one field, so checking membership in the field is enough.
    """
    if not labelstr:
        return False
    word = ""
    for ch in scanned + "\x00":
        if ch.isalnum():
            word += ch
        else:
            if labelstr in word:
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

def _print_raw(printer_name: str, filename: str) -> bool:
    """Send a .prn file to a printer verbatim. True when the spooler took it.

    The return value is for callers that tell the operator what happened --
    the lot label, which is printed once per box on an explicit click. The
    per-part callers ignore it and rely on the console trace, as before.
    """
    if not _print_ok:
        print("[PRINT DEBUG] win32print not available (pywin32 not installed) -- cannot print")
        return False
    if not os.path.exists(filename):
        print(f"[PRINT DEBUG] label file not found: {filename}")
        return False
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
        return True
    except Exception as ex:
        print(f"[PRINT DEBUG] print FAILED: {ex}")
        return False
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

# X0-X27 and M20-M37 are each one unbroken run of addresses. That is what lets
# the polling loop read every input the panel shows in a single transaction and
# every coil in a second one, instead of five reads for the same picture.
_PLC_X_BASE  = 0x0400   # X0  — X0-X7, then the unused X10-X17, then X20-X27
_PLC_X_COUNT = 24
_PLC_M_BASE  = 0x0814   # M20 — M20-M27, M28, the unused M29, then M30-M37
_PLC_M_COUNT = 18

# How long M28 is given to physically change over before X4 is read for its
# acknowledgement. Paid only when the relay actually has to move: a phase that
# asks for the mode the previous one left it in used to sleep this again for a
# relay that was already there and already settled, and the cycle ran through
# three such switches.
_RELAY_SETTLE_S = 0.5

# The quiet the USB-serial adapter needs between a close and the next open of
# the same port. Reopening sooner is the pattern it drops transactions on. It
# used to be spent only inside one helper, while the phase boundaries -- where
# a port really is closed and immediately reopened -- covered it by accident,
# with half-second spacers that were not there for this and did not say so.
_PORT_REOPEN_QUIET_S = 0.05

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
        self._closed_at = 0.0
        # None, not False: nothing has driven M28 yet this session, so the
        # relay's physical position is unknown. Callers pay the settle on the
        # first switch and skip it only once this has been set by a write of
        # their own. It reads as "contact mode" for coil selection either way,
        # which is what False meant here before.
        self._is_hv_mode = None

    def open(self) -> bool:
        if not _modbus_ok:
            return False
        try:
            self.close()
            # Whatever is left of the adapter's quiet period, and nothing if it
            # has already passed -- which it has, any time the port has been
            # shut for longer than it takes to get back here.
            quiet = self._closed_at + _PORT_REOPEN_QUIET_S - time.time()
            if quiet > 0:
                time.sleep(quiet)
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
        # Stamped only when a handle was actually open. open() closes before it
        # opens, and stamping that unconditionally would have every open wait
        # out a quiet period for a port that was already shut.
        was_open = False
        try:
            if self._client:
                was_open = self._client.is_socket_open()
                self._client.close()
        except Exception:
            pass
        finally:
            if was_open:
                self._closed_at = time.time()

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

    def write_coils(self, address: int, values: list) -> bool:
        """Write a run of consecutive coils in one transaction (FC15).

        The eight channel relays of either mode are one unbroken run of
        addresses, so driving them is one frame rather than eight. At 9600
        baud with ASCII framing each frame is ~35ms on the wire, and the
        per-coil loop this replaces paid that eight times over plus a 20ms
        sleep between each -- about 0.45s to do what one frame does.

        Falls back to the single-coil loop if the PLC refuses FC15, so a
        controller that does not implement it behaves exactly as before.
        """
        if not self.is_open:
            print(f"[PLC DEBUG] write_coils(0x{address:04X}, {values}): port not open!")
            return False
        try:
            result = self._client.write_coils(address, values=values, device_id=self._slave_id)
            if not result.isError():
                print(f"[PLC DEBUG] write_coils(0x{address:04X}, {values}): OK")
                return True
            print(f"[PLC DEBUG] write_coils(0x{address:04X}) refused ({result}) "
                  f"-- falling back to one coil at a time")
        except Exception as e:
            print(f"[PLC DEBUG] write_coils EXCEPTION: {e} -- falling back to one coil at a time")
            self.close()
            return False
        ok = True
        for i, v in enumerate(values):
            if not self.write_coil(address + i, v):
                ok = False
        return ok

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

    def read_inputs_bulk(self, address: int, count: int, strict: bool = False) -> list:
        """Read multiple consecutive discrete inputs (FC02).

        strict=True returns None instead of all-False when the read fails, so a
        caller can tell a refused read from a genuine "every input is low" --
        they are the same list otherwise, and a panel that blanks itself on a
        dropped frame looks exactly like a machine with nothing energised.
        """
        fail = None if strict else [False] * count
        if not self.is_open:
            return fail
        try:
            result = self._client.read_discrete_inputs(address, count=count, device_id=self._slave_id)
            if result.isError():
                # Fallback: try from base 0 with offset
                offset = address - 0x0400 if address >= 0x0400 else address
                result = self._client.read_discrete_inputs(0, offset + count, device_id=self._slave_id)
                if result.isError():
                    return fail
                return list(result.bits[offset:offset + count])
            return list(result.bits[:count])
        except Exception:
            self.close()
            return fail

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

    def read_coils_bulk(self, address: int, count: int, strict: bool = False) -> list:
        """Read multiple consecutive coils (FC01). strict=True as above."""
        fail = None if strict else [False] * count
        if not self.is_open:
            return fail
        try:
            result = self._client.read_coils(address, count=count, device_id=self._slave_id)
            if result.isError():
                return fail
            return list(result.bits[:count])
        except Exception:
            self.close()
            return fail

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
        """Turn ON/OFF all channel relays of the current mode, in one frame.

        The relays of one mode are consecutive, so this is a single FC15 where
        it used to be one FC05 per channel with a 20ms sleep after each. Same
        coils, same values; the caller still confirms them against X20-X27
        before anything is judged on them.
        """
        coils = _PLC_IR_ACW_COILS if self._is_hv_mode else _PLC_CONTACT_COILS
        n = min(n_ch, 8)
        base = coils.get(1)
        if base is None or n < 1:
            return False
        return self.write_coils(base, [on] * n)

    def reset_all_channels(self) -> bool:
        """Turn OFF all 8 channel relays (both Contact and IR/ACW coils).

        Two frames, one per mode's run. They are written separately rather
        than as one 18-coil block because M28 -- the safety relay -- sits
        between them, and a single block spanning both would drive it too.
        """
        ir_ok = self.write_coils(_PLC_IR_ACW_COILS[1], [False] * 8)
        contact_ok = self.write_coils(_PLC_CONTACT_COILS[1], [False] * 8)
        return ir_ok and contact_ok

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

    def confirm_channel_on(self, ch: int, timeout: float = 0.5, poll: float = 0.02) -> bool:
        """Wait until one channel relay acknowledges ON via its X20~X27 input.

        The Individual-mode twin of confirm_channels_on, bounded the same way
        and returning the same thing a single read after the old fixed sleep
        returned: True if the relay is up, False if it never came up inside
        the wait.
        """
        deadline = time.time() + timeout
        while True:
            if self.read_channel_ack(ch):
                return True
            if time.time() >= deadline:
                return False
            time.sleep(poll)

    def confirm_channels_on(self, n_ch: int, timeout: float = 0.5, poll: float = 0.02) -> bool:
        """Wait until every channel relay acknowledges ON via X20~X27.

        Bounded by `timeout` rather than a retry count, so a caller can hold it
        to exactly the fixed sleep it stands in for: all relays up returns in a
        couple of Modbus reads, and one that never comes up costs no more than
        the wait it replaced.
        """
        deadline = time.time() + timeout
        while True:
            if all(self.read_all_acks(n_ch).values()):
                return True
            if time.time() >= deadline:
                return False
            time.sleep(poll)

    # ── Safety relay (CRITICAL — prevents HV short circuit) ──────────────

    @property
    def is_hv_mode(self):
        """True in IR/ACW mode, False in Contact mode, None if nothing has said."""
        return self._is_hv_mode

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


# The measurement sits in the fourth comma separated field of a MEAS? reply.
# It can carry a unit suffix and comes back in exponent form on large readings,
# so the number is matched out of the field rather than sliced to a fixed
# width: the old fixed slice read "1.234E+04" as 1.23 and a field with a
# leading space as a tenth of its real value.
_MEAS_FIELD = 3
_MEAS_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
# Text shown in the grid, and the per-channel verdict stored against the run,
# when a channel was never actually measured.
_NO_READING_TEXT = "NO RD"
_NO_READING_RESULT = "COMM"
# Stored against a channel the part has no usable limit for. It is not a PASS
# and it is not a measurement failure -- it says the part was never specified,
# which is a different thing to fix.
_NO_LIMIT_RESULT = "NOSPEC"
_NO_SPEC_TEXT = "NO SPEC"
# Every field a channel needs before it can be tested at all. Two of them
# say what to do to the part and two say how to judge it, and a channel is
# not testable without all four.
_SPEC_FIELDS = ("appvol", "testtime", "min", "max")

# The instrument judges every test itself, against the limits in its own setup,
# and returns that judgement in the same reply as the number. It was read for
# the number alone, so a part the GPT-9803 had already failed was re-judged in
# Python against the database and labelled PASS. These match its verdict
# wherever it sits in the reply, because the field order differs between the
# MEAS? response and the result line TEST:RET ON volunteers when a test ends.
_VERDICT_FAIL = re.compile(r"(?<![A-Z])(FAIL|F_AIL|NG|HIGH|LOW|OVER)(?![A-Z])", re.I)
_VERDICT_PASS = re.compile(r"(?<![A-Z])(PASS|GOOD)(?![A-Z])", re.I)
# The second field of a reply is the instrument's state, and while the test is
# under way it reads TEST rather than a verdict:
#
#     ACW,TEST ,1.000kV,0.002 mA ,T=001.7S
#
# That is a reply from during the test: no judgement on it yet, and a number
# that is only where the current had got to. Seeing it means the dwell ended
# before the test did, which _RAMP_TIME_S is what stops -- it is logged rather
# than worked around, because by then the reading is already wrong.
_MEAS_RUNNING = re.compile(r"(?<![A-Z])(TEST|RAMP)(?![A-Z])", re.I)
# The instrument ramps the voltage up before the programmed test time starts,
# so a test lasts ramp + TTIM and a dwell of TTIM alone expires part way
# through it. The ramp is a setting, not a constant, and left alone it holds
# whatever the front panel was last set to -- which is why replies were coming
# back mid-test. TestConsole.cs pinned it at 0.1 s for exactly this reason
# (MANU:RTIMe 0.1), and that is the number the dwell is built around.
_RAMP_TIME_S = 0.1
# How long past the expected end to keep asking before giving up on the
# instrument ever reporting itself idle.
_TEST_END_MARGIN_S = 2.0
# Nothing is asked until this has passed, so that a reply of OFF is the test
# having finished rather than it not having started. FUNC:TEST ON returns
# before the instrument is under way, and asking straight after it would read
# the state it was in beforehand.
_TEST_START_GRACE_S = _RAMP_TIME_S + 0.2

_TEST_STATE_OFF = re.compile(r"(?<![A-Z])OFF(?![A-Z])", re.I)
_TEST_STATE_ON = re.compile(r"(?<![A-Z])ON(?![A-Z])", re.I)


def _parse_test_state(reply: str):
    """True while a test is running, False once it is over, None if unreadable.

    None is not False. A reply that cannot be read is not the instrument
    saying it has finished, and treating it as one would take the
    measurement mid-test -- which is the thing this is here to stop.
    """
    text = (reply or "").strip()
    if not text: return None
    if _TEST_STATE_OFF.search(text): return False
    if _TEST_STATE_ON.search(text): return True
    if text == "0": return False
    if text == "1": return True
    return None


def _meas_running(response: str) -> bool:
    """Whether the reply says the test was still going when it was produced."""
    return bool(_MEAS_RUNNING.search(response or ""))


def _parse_verdict(response: str):
    """The instrument's own PASS/FAIL, or None if the reply does not carry one.

    None means "it did not say", never "it said PASS". A reply with no verdict
    in it leaves the channel resting on the spec comparison alone, and that is
    logged, because it is the condition this whole check exists to catch.
    """
    text = response or ""
    if _VERDICT_FAIL.search(text): return "FAIL"
    if _VERDICT_PASS.search(text): return "PASS"
    return None


class _Reading(object):
    """One measurement: the number, what the instrument made of it, whether the
    limits it judged against are the ones the part is specified to, and the
    reply all of that was read out of.

    The raw reply is kept so it can go on the operator's log rather than only
    to stdout, which the windowed build throws away. A reading that looks
    wrong is answerable from the line, without rebuilding with --console.
    """

    __slots__ = ("value", "verdict", "limits_set", "raw")

    def __init__(self, value=None, verdict=None, limits_set=False, raw=""):
        self.value = value
        self.verdict = verdict
        self.limits_set = limits_set
        self.raw = raw


# Whether each keyword is the top of its window or the bottom, which is what
# decides the direction a limit gets tighter in. An instrument that cannot
# hold the value asked for clamps it to its own range -- MANU:IR:RLOS 0 comes
# back as 1, because 1 MOhm is as low as this tester's resistance floor goes.
# A clamp towards the middle of the window is the instrument judging more
# strictly than the part is specified to, which can only fail a part the spec
# would also have to question; a clamp outwards is it judging more loosely,
# and that is the thing none of this may allow.
_LIMIT_IS_UPPER = {
    "MANU:ACW:CHIS": True,   "MANU:IR:RHIS":  True,
    "MANU:ACW:CLOS": False,  "MANU:IR:RLOS":  False,
}


def _spec_number(raw):
    """One spec field as it was typed, or None when the row does not carry it."""
    if raw is None: return None
    try: return float(raw)
    except (TypeError, ValueError): return None


def _spec_missing(spec: dict) -> list:
    """Which of a channel's spec fields are not filled in. Empty means testable.

    Nothing here is defaulted. The applied voltage used to fall back to 1500 V
    for a withstand test and 500 V for insulation when the row did not carry
    one, which put a voltage nobody had chosen across a part -- a blank in the
    database deciding what goes into the cable. A channel that is not fully
    specified is not tested.

    A zero voltage or a zero duration counts as missing rather than as a
    value: there is no test to run at either, and both are what an empty
    column reads as once it has been through float().
    """
    spec = spec or {}
    missing = []
    for f in _SPEC_FIELDS:
        v = spec.get(f)
        if v is None or (f in ("appvol", "testtime") and float(v) <= 0):
            missing.append(f)
    return missing


def _spec_field_detail(spec: dict, field: str) -> str:
    """One unusable spec field, described by what is actually in it.

    "max is not filled in" sends an operator to a Model Settings box with
    9999 sitting in it, and there is nothing there to act on. A withstand
    limit of 9999 mA is dropped because it cannot be a limit, not because it
    is empty, and those are different things to fix -- so the message says
    which one it is and quotes the cell.
    """
    value = (spec or {}).get("raw", {}).get(field)
    text = "" if value is None else str(value).strip()
    if text == "":
        return f"{field} is blank"
    return f"{field} is '{text}', which is not a usable value"


def _channel_passed(reading, lo, hi) -> bool:
    """Whether one channel passed -- and both judges have to agree that it did.

    The instrument's verdict comes first: it is the one measuring, its limits
    are the ones the current was actually compared against as it flowed, and if
    it says FAIL then the part failed whatever the database thinks. The spec
    window is then applied on top, so a limit tightened in Model Settings still
    bites even on an instrument set looser.

    No reading, no limits, or a limit the part does not carry is not a pass.
    """
    if reading is None or reading.value is None: return False
    if reading.verdict == "FAIL": return False
    if lo is None or hi is None: return False
    return lo <= reading.value <= hi


def _meas_dwell(test_time_s: float) -> float:
    """How long to hold the test before reading it back.

    Long enough for the programmed test time to elapse, so the reading is the
    end-of-dwell value the spec limits are written against rather than one
    taken while the cable is still charging. The 0.9 s floor keeps the old
    behaviour for parts specced shorter than that.

    The ramp is part of that wait. A test runs for the ramp and then for the
    programmed time, so a dwell of TTIM + a margin ends while the instrument
    is still testing and MEAS? answers with a mid-test line.
    """
    try: return max(float(test_time_s) + _RAMP_TIME_S + 0.3, 0.9)
    except (TypeError, ValueError): return 0.9 + _RAMP_TIME_S


def _parse_meas(response: str):
    """The measured number from a MEAS? reply, or None if there isn't one.

    None is not 0.0 on purpose. An empty reply, a short one and one whose
    measurement field holds no number are all comms faults, and filing them as
    a reading of zero made them indistinguishable from a part that genuinely
    failed its insulation.
    """
    parts = (response or "").split(",")
    if len(parts) <= _MEAS_FIELD: return None
    m = _MEAS_NUMBER.search(parts[_MEAS_FIELD])
    if not m: return None
    try: return float(m.group())
    except ValueError: return None


def _meas_text(value, fmt: str) -> str:
    """Grid and log text for one measurement -- the number, or NO RD."""
    if value is None: return _NO_READING_TEXT
    try: return format(float(value), fmt)
    except (TypeError, ValueError): return _NO_READING_TEXT


def _chan_result(reading, spec: dict, passed: bool) -> str:
    """The per-channel verdict stored against the run.

    A channel that was never measured stores COMM, and one the part has no
    limits for stores NOSPEC. Neither is a FAIL -- the part is not at fault
    for a comms drop or a blank row in Model Settings, and filing them as
    failures hides both. Neither is a PASS either.
    """
    if reading is None or reading.value is None: return _NO_READING_RESULT
    if spec.get("min") is None or spec.get("max") is None: return _NO_LIMIT_RESULT
    return "PASS" if passed else "FAIL"


def _meas_db(value) -> str:
    """Measurement as stored. A channel with no reading stores blank, not 0."""
    return "" if value is None else str(value)


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
            # A write timeout this generous only fires on a genuinely stuck
            # port. The longest command here is ~30 ms on the wire at 9600
            # baud, and the old 0.5 s tripped on ordinary flow-control stalls
            # -- which then closed the port for the rest of the run.
            self._ser = serial.Serial(self._port, self._baud, timeout=3.0, write_timeout=2.0)
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
    def ensure_open(self) -> bool:
        """Reopen the port if something closed it part way through a run.

        The port is opened once for a whole test phase rather than once per
        channel, so a single failed write used to leave every remaining
        channel writing into a closed port and reading nothing back -- which
        the caller then filed as a measurement of zero.
        """
        if self.is_open: return True
        print("[HIPOT DEBUG] port closed mid-run -- reopening")
        return self.open()
    def write_line(self, cmd: str) -> bool:
        """Send one command; False if it could not be got onto the wire.

        A failed write reopens the port and retries once, so a momentary stall
        costs one command instead of every channel after it.
        """
        for attempt in (1, 2):
            if not self.ensure_open(): break
            try:
                self._ser.write((cmd + "\r\n").encode("ascii"))
                print(f"[HIPOT DEBUG] >> {cmd}")
                time.sleep(0.025)
                return True
            except Exception as e:
                print(f"[HIPOT DEBUG] write_line EXCEPTION on '{cmd}' (attempt {attempt}): {e}")
                self.close()
        print(f"[HIPOT DEBUG] write_line GAVE UP on '{cmd}'")
        return False
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
    def stop_test(self):
        """Take the tester out of the TEST state and clear its status.

        MANU:EDIT: setup commands -- the mode switch included -- are only
        accepted while the instrument is idle. Anything sent while a test is
        still running is dropped on the floor, so every run has to start from
        a stopped instrument rather than stopping itself halfway through its
        own setup.
        """
        self.write_line("FUNC:TEST OFF")
        self.write_line("*CLS")
        time.sleep(0.3)
        self.flush()
    def set_limit(self, key: str, value: float, label: str) -> bool:
        """Program one judgement limit and read it back. False if it did not take.

        The limits were never sent. Only MANU:ACW:CLOS went out, which is the
        current *low* limit; the high limit that decides PASS/FAIL on the
        instrument was left holding whatever the front panel had, so it judged
        against one number while the console judged against another.

        Every write is read back because an instrument accepts a command it
        does not recognise in silence -- a mistyped keyword, or a limit outside
        the range of this model, leaves no error to see and the old setting
        still in force. Reading it back is the only way to know the limit being
        judged against is the one asked for.

        """
        text = f"{value:.4f}"
        if not self.write_line(f"{key} {text}"):
            print(f"[HIPOT DEBUG] {label}: could not send {key}")
            return False
        if not self.write_line(f"{key}?"):
            print(f"[HIPOT DEBUG] {label}: could not query {key} back")
            return False
        time.sleep(0.05)
        reply = self.read_line()
        got = _MEAS_NUMBER.search(reply or "")
        if not got:
            print(f"[HIPOT DEBUG] {label}: {key} read back as {reply!r} -- no number in it")
            return False
        try: back = float(got.group())
        except ValueError:
            print(f"[HIPOT DEBUG] {label}: {key} read back as {reply!r} -- unparseable")
            return False
        # The instrument rounds to its own resolution, so this is "close
        # enough to be the value asked for", not equality.
        if abs(back - float(value)) <= max(abs(float(value)) * 0.001, 1e-4):
            return True
        upper = _LIMIT_IS_UPPER.get(key)
        if upper is not None and ((back < float(value)) if upper else (back > float(value))):
            print(f"[HIPOT DEBUG] {label}: {key} asked for {text}, instrument holds "
                  f"{back} -- clamped to its own range, and tighter than asked, "
                  f"so it stands")
            return True
        print(f"[HIPOT DEBUG] {label}: {key} set to {text} but reads back {back} "
              f"-- looser than asked, REFUSED")
        return False

    def wait_for_test_end(self, dwell_s: float, label: str) -> bool:
        """Ask the instrument when its test is over, rather than timing it here.

        FUNC:TEST? is the instrument answering for its own state, which beats
        any arithmetic on this side about ramp times and programmed durations
        -- those were guesses about a machine that can simply be asked.

        The buffer is cleared before each question because TEST:RET ON has the
        instrument volunteering status lines throughout, and the answer wanted
        here is to the question just asked.

        False means it never said so: the timeout ran out, or FUNC:TEST? is not
        answering in a way this can read. Either way the caller goes on to
        measure, because a reading that has to be questioned is worth more than
        no reading at all -- and the reply it gets will say TEST on it.
        """
        time.sleep(_TEST_START_GRACE_S)
        deadline = time.time() + dwell_s + _TEST_END_MARGIN_S
        unreadable = 0
        while time.time() < deadline:
            self.flush()
            if not self.write_line("FUNC:TEST?"):
                return False
            time.sleep(0.05)
            reply = self.read_line()
            state = _parse_test_state(reply)
            if state is False:
                return True
            if state is None:
                unreadable += 1
                if unreadable >= 3:
                    print(f"[HIPOT DEBUG] {label}: FUNC:TEST? not readable "
                          f"({reply!r}) -- waiting {dwell_s:.1f}s instead")
                    time.sleep(dwell_s)
                    return False
            else:
                unreadable = 0
            time.sleep(0.1)
        print(f"[HIPOT DEBUG] {label}: still testing after "
              f"{dwell_s + _TEST_END_MARGIN_S:.1f}s")
        return False

    def _measure(self, instr: list, dwell_s: float, label: str):
        """Run one configured test and read it back. None means no reading.

        The instrument is stopped and its buffer flushed on both sides of the
        measurement. TEST:RET ON makes it volunteer a result line of its own
        when the test ends, and with only a trailing flush that line landed
        after the flush and was still sitting there when the next channel came
        to read -- so the next channel parsed the previous one's leftovers.

        Nothing here falls back to 0.0. A failed write, a timed-out read and a
        reply with no number in it all return a reading of None, so the caller
        can tell a comms fault from a part that really does measure zero.

        The instrument's own verdict comes back with the number. The reply was
        being read for the number alone and the judgement thrown away, which
        left the console free to pass a part the instrument had just failed.

        Callers arrive with the instrument already stopped -- run_ir_test and
        run_acw_test both open with stop_test() and send only setup between
        there and here, none of which starts a test. So this clears the buffer
        rather than stopping what is not running.
        """
        self.flush()
        sent = all([self.write_line(cmd) for cmd in instr])
        if not sent:
            print(f"[HIPOT DEBUG] {label}: setup did not reach the instrument")
            self.stop_test()
            return _Reading(raw="<setup did not reach the instrument>")
        # Wait for the instrument to report itself idle rather than sleeping a
        # computed dwell and hoping. The dwell is still worked out, but only as
        # the basis for how long to keep asking.
        self.wait_for_test_end(dwell_s, label)
        # TEST:RET ON makes the instrument send lines of its own while the test
        # runs, and they queue in front of the answer to MEAS?. Clearing them
        # first is what makes the next line read the answer to this question
        # rather than the instrument's report from some earlier moment.
        self.flush()
        if not self.write_line("MEAS?"):
            self.stop_test()
            return _Reading(raw="<MEAS? could not be sent>")
        time.sleep(0.05)
        response = self.read_line()
        self.stop_test()
        value = _parse_meas(response)
        verdict = _parse_verdict(response)
        if _meas_running(response):
            print(f"[HIPOT DEBUG] {label}: reply came back mid-test -- the dwell "
                  f"ended before the instrument did. This reading is not the "
                  f"settled one; check MANU:RTIMe against _RAMP_TIME_S.")
        print(f"[HIPOT DEBUG] {label}: MEAS? -> {response!r}, parsed value={value}, verdict={verdict}")
        if verdict is None:
            print(f"[HIPOT DEBUG] {label}: no PASS/FAIL in the reply -- "
                  f"this channel rests on the spec comparison alone")
        return _Reading(value, verdict, raw=response)
    def run_ir_test(self, ir_volt_kv: float, ir_time_s: float, ir_min, ir_max) -> _Reading:
        """One IR test at the part's own limits. Returns what was read and judged.

        RHIS/RLOS were hardcoded to 9999 and 1 -- a window nothing can fall
        outside -- so the instrument passed every insulation test it ever ran
        and only the console's own comparison decided anything. They now carry
        the part's limits, which is what makes the instrument's verdict worth
        reading back.
        """
        label = f"IR @ {ir_volt_kv:.4f} kV"
        self.stop_test()
        if not self.write_line("MANU:EDIT:MODE IR"):
            return _Reading()
        limits_set = (ir_min is not None and ir_max is not None
                      and self.set_limit("MANU:IR:RHIS", ir_max, label)
                      and self.set_limit("MANU:IR:RLOS", ir_min, label))
        # The limits go out twice on purpose. The pass above proves the
        # instrument understood the keyword and took the value -- it is the
        # readback that proves it, and it has to happen before the test
        # starts. These then go out again after _measure has re-selected the
        # mode, so whatever a mode switch does to the setup, the limits in
        # force when the voltage is applied are the ones asked for.
        limits = ([f"MANU:IR:RHIS {ir_max:.4f}", f"MANU:IR:RLOS {ir_min:.4f}"]
                  if limits_set else [])
        instr = [
            "MANU:EDIT:MODE IR", "TEST:RET ON", f"MANU:IR:VOLT {ir_volt_kv:.4f}",
        ] + limits + [
            f"MANU:IR:TTIM {ir_time_s:.1f}", "MANU:IR:REF 0",
            f"MANU:RTIMe {_RAMP_TIME_S}", "FUNC:TEST ON"
        ]
        reading = self._measure(instr, _meas_dwell(ir_time_s), label)
        reading.limits_set = limits_set
        return reading
    def run_acw_test(self, acw_volt_kv: float, acw_time_s: float, acw_min, acw_max) -> _Reading:
        """One ACW test at the part's own limits. Returns what was read and judged.

        CHIS -- the current high limit, the number that decides PASS or FAIL on
        this instrument -- was never sent at all. Only CLOS, the low limit,
        went out. The GPT-9803 judged against whatever the front panel was left
        on, which is why it failed channels the console passed.
        """
        label = f"ACW @ {acw_volt_kv:.4f} kV"
        self.stop_test()
        if not self.write_line("MANU:EDIT:MODE ACW"):
            return _Reading()
        limits_set = (acw_min is not None and acw_max is not None
                      and self.set_limit("MANU:ACW:CHIS", acw_max, label)
                      and self.set_limit("MANU:ACW:CLOS", acw_min, label))
        # Sent twice on purpose -- see run_ir_test.
        limits = ([f"MANU:ACW:CHIS {acw_max:.4f}", f"MANU:ACW:CLOS {acw_min:.4f}"]
                  if limits_set else [])
        instr = [
            "MANU:EDIT:MODE ACW", "TEST:RET ON", f"MANU:ACW:VOLT {acw_volt_kv:.4f}",
            "MANU:ACW:FREQ 60",
        ] + limits + [
            f"MANU:ACW:TTIM {acw_time_s:.1f}", "MANU:ACW:REF 0.00",
            f"MANU:RTIMe {_RAMP_TIME_S}", "FUNC:TEST ON"
        ]
        reading = self._measure(instr, _meas_dwell(acw_time_s), label)
        reading.limits_set = limits_set
        return reading

def _generate_lot_number(pno: str, machine_id: str) -> str:
    """Next lot number for this part, this machine, today: <yymmdd>I<machine>A2A<nnnnnnn>.

    The serial is zero-padded to seven digits (0000001, 0000002, ... ) so every
    label carries a fixed-width code, the way the original C# console padded its
    own.

    The sequence belongs to the part number, so every part starts its own run
    at 1 each day rather than continuing the previous part's numbering. Two
    parts therefore share a lot string on the same day, which is why a test
    run is identified by the (pno, lotno) pair everywhere it is stored or
    looked up -- testmaster is keyed UNIQUE (pno, lotno), and testresult
    carries the part number alongside the lot so its per-channel rows cannot
    be confused with another part's run of the same number.

    Continuing from the highest number this part has already been issued today
    (rather than from a row count) stops a deleted record from re-issuing a
    number that is already on a printed label. Lots issued before this width
    went in -- unpadded, or padded to four digits -- still read back correctly,
    since int() ignores the leading zeros and the width alike.
    """
    now = datetime.datetime.now()
    date_str = now.strftime("%y%m%d")
    mid_char = machine_id[-1] if machine_id else "1"
    prefix = f"{date_str}I{mid_char}A2A"
    highest = 0
    try:
        with db.get_cursor() as cur:
            cur.execute("SELECT lotno FROM testmaster WHERE pno=%s AND lotno LIKE %s",
                        (pno, f"{prefix}%"))
            for (lot,) in cur.fetchall():
                tail = str(lot)[len(prefix):]
                if tail.isdigit():
                    highest = max(highest, int(tail))
    except Exception as ex:
        print(f"DB Error generating lot: {ex}")
    return f"{prefix}{highest + 1:07d}"

def _fmt_channel_values(ch_res: dict, n_ch: int, fmt: str) -> str:
    """One channel's measured value per slot, in channel order, comma separated.

    Formatted the way the Testing grid showed it -- IR to the whole MO, ACW to
    three decimals -- so the number on the label is the number the operator
    watched go past rather than a second rounding of it.

    A channel with no reading leaves its slot empty instead of being dropped:
    the nth value between the commas has to stay CH n, or a label with a gap in
    it reads as a different channel's result.
    """
    out = []
    for ch in range(1, n_ch + 1):
        value = (ch_res or {}).get(ch, {}).get("value")
        try:
            out.append(format(float(value), fmt))
        except (TypeError, ValueError):
            out.append("")
    return ",".join(out)


# ── Lot date code ─────────────────────────────────────────────────────────────
# The three character code that stands for today's date on a label: one
# character for the day, one for the month, one for the year, in that order.
#
# The characters themselves are not derived, they are looked up in
# "DAY CODE.txt", "MONTH CODE.txt" and "YEAR CODE.txt" beside this file --
# plain comma separated tables, day 1 first, month 1 first, YEAR_FIRST first.
# Keeping them in files rather than in code is the point: a customer with a
# different coding scheme is a text edit, not a rebuild, and the tables are
# re-read on every print so an edit takes effect on the very next label.
_LOT_CODE_TABLES = {"day": "DAY CODE.txt", "month": "MONTH CODE.txt",
                    "year": "YEAR CODE.txt"}
# The customer's year sequence began at 2021, so that is the year the first
# entry in the year table stands for -- not the year the feature was written.
# Getting this wrong offsets every year code, which is why it is named here
# once rather than worked out from the table's length.
_LOT_CODE_YEAR_FIRST = 2021
# Used only when a table is missing, empty or unreadable, so a broken file
# still prints a label instead of stopping the line. These have to stay in step
# with the shipped files by hand: a station whose table went missing would
# otherwise print a code nobody chose and give no sign of it. As shipped, days
# A-Z then 1-5, months A-L, and years Q-Z then A-J for 2021 through 2040 -- the
# year letters run off the end of the alphabet at 2030 and carry on from A, so
# they are spelled out rather than counted from one starting letter.
_LOT_CODE_FALLBACK = {
    "day":   [chr(ord("A") + i) for i in range(26)] + [str(d) for d in range(1, 6)],
    "month": [chr(ord("A") + i) for i in range(12)],
    "year":  [chr(ord("Q") + i) for i in range(10)] + [chr(ord("A") + i) for i in range(10)],
}
# What goes on the label when the date falls outside a table -- a year past the
# end of the year table, say, or one before it starts. Deliberately something an
# operator will notice rather than a character that reads as a real code.
_LOT_CODE_UNKNOWN = "?"


def _read_lot_code_table(kind: str) -> list:
    """One code table, from its file, falling back to the built-in copy."""
    path = os.path.join(os.path.dirname(__file__), _LOT_CODE_TABLES[kind])
    try:
        with open(path, "r", encoding="latin-1") as f:
            raw = f.read().strip()
        # The tables are maintained by hand, and a hand written list tends to
        # get a full stop on the end of it: "...,3,4,5." Drop one closing stop
        # so the last entry is the single character the rest of the table is,
        # rather than "5." -- a label two characters wide in one slot, printed
        # only on the 31st, is exactly the kind of fault that reaches the
        # customer before anyone here sees it.
        if raw.endswith("."):
            raw = raw[:-1]
        table = [part.strip() for part in raw.split(",")]
        table = [part for part in table if part]
        if table:
            return table
        print(f"[LOT CODE] {path} holds no entries -- using the built-in table")
    except Exception as ex:
        print(f"[LOT CODE] cannot read {path} ({ex}) -- using the built-in table")
    return list(_LOT_CODE_FALLBACK[kind])


def _lot_3_letters(when: datetime.datetime = None) -> str:
    """Today's date as the three character lot code, year then month then day.

    Y/M/D, most significant first, the way a date is written when it is going
    to be sorted or compared. It was built D/M/Y here, which reads the way a
    date is spoken and is the wrong way round for a code.

    Pass `when` to code a date other than now; the label printers leave it
    unset and get the system date.
    """
    now = when or datetime.datetime.now()
    slots = (("year", now.year - _LOT_CODE_YEAR_FIRST),
             ("month", now.month - 1), ("day", now.day - 1))
    out = []
    for kind, index in slots:
        table = _read_lot_code_table(kind)
        if 0 <= index < len(table):
            out.append(table[index])
        else:
            print(f"[LOT CODE] no {kind} code for {now:%d/%m/%Y}: "
                  f"{_LOT_CODE_TABLES[kind]} holds {len(table)} entries")
            out.append(_LOT_CODE_UNKNOWN)
    return "".join(out)


def _apply_lot_3_letters(text: str, code: str) -> str:
    """Substitute the lot code placeholder, with or without its closing @.

    @lot3letters@ is the spelling that matches every other placeholder, but a
    template written as @lot3letters is accepted too -- an unclosed one would
    otherwise print as itself and the mistake is easy to make. The closed form
    goes first so the bare replacement cannot leave a stray @ behind.
    """
    return text.replace("@lot3letters@", code).replace("@lot3letters", code)


def _print_barcode_label(pno: str, alc: str, model: str, vendor_code: str, eo_number: str, lot_no: str, machine_id: str, is_rework: bool = False, num_channels: int = 0, ir_ch: dict = None, acw_ch: dict = None, printer_name: str = _PRINTER_NAME):
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
        # The measured readings, CH1 first: "1204,1198,1210" for a 3-channel
        # part. A template that wants them per channel can still have them --
        # splitting one field on the comma is the label designer's job, and it
        # beats a placeholder per channel on a part whose channel count varies.
        text = _apply_lot_3_letters(text, _lot_3_letters(now))
        text = text.replace("@irValues@", _fmt_channel_values(ir_ch, num_channels, ".0f"))
        text = text.replace("@acwValues@", _fmt_channel_values(acw_ch, num_channels, ".3f"))
        tmp = os.path.join(base, "TEMPPRN.prn")
        with open(tmp, "w", encoding="latin-1") as f: f.write(text)
        _print_raw(printer_name, tmp)
    except Exception as ex:
        print(f"[PRINT DEBUG] failed building/sending label: {ex}")

# 35 mm at 203 dpi (8 dots/mm), and the TSPL internal fonts that are fixed
# width -- cell width in dots, so a rendered line's width is exactly
# len(text) * cell * multiplier.
# TSPL's internal fonts are sized in dots, so a label's width in mm only
# becomes a usable number with this. 8 dots/mm is 203 dpi, which is what the
# font widths below are measured at.
# 300 dpi. TSPL counts in dots and this was set to 8 dots/mm, which is a
# 203 dpi printer -- so every width here was computed against 280 dots of a
# stock that is really 420, and the anchor meant to sit 15 dots from the edge
# sat 155 dots in. That is the indent that three attempts at this label's
# alignment were all looking at: the maths was placing the block correctly on
# a label a third narrower than the one in the printer.
#
# Measured off a printed END marker: the block started 36% of the way across
# the stock. With one anchor for every line, reading-left = label_w - 265, so
# label_w = 265 / (1 - 0.36) = 411 dots, which is 11.8 dots/mm on 35 mm --
# 300 dpi, where TSPL counts 12 dots to the millimetre.
_MARKER_DPMM = 12
# 35 mm, the stock MARKER.prn is written for. Only used if its SIZE line
# cannot be read.
_MARKER_LABEL_W_DEFAULT = 35 * _MARKER_DPMM
# Every number below is LOTPRN.prn's, not one worked out here. That label
# prints on this same 35 x 25 mm stock at this same rotation, and it is the
# layout going out on boxes today -- so its geometry is known good, where this
# one's has been derived from first principles twice and been wrong both
# times. LOTPRN anchors every line at x=265 on 280 dots of stock, a
# reading-left margin of 15; its title sits at y=172 and its field rows step
# down by 24 from y=140.
_MARKER_LEFT_MARGIN = 280 - 265
_MARKER_TITLE_Y = 172
_MARKER_FIRST_ROW_Y = 140
_MARKER_ROW_PITCH = 24
# The internal bitmap fonts are 12 and 16 dots wide on a 203 dpi printer and
# scale with the head, so on this one they are half again as wide. Only the
# overflow guard reads these; getting them wrong lets a line run off the edge
# rather than misplacing the block.
_MARKER_FONT_W = {"2": 18, "3": 24}
_MARKER_SIZE_LINE = re.compile(r"^\s*SIZE\s+([\d.]+)\s*mm", re.I | re.M)


def _marker_label_width(template: str) -> int:
    """The label's width in dots, taken from the template's own SIZE line.

    The stock is declared once, at the top of MARKER.prn, and every line
    position here is worked out from it. Reading it back from the template
    means changing the stock there moves the text with it, instead of leaving
    it positioned for a label that is no longer being printed on.
    """
    m = _MARKER_SIZE_LINE.search(template or "")
    if not m: return _MARKER_LABEL_W_DEFAULT
    try: return int(round(float(m.group(1)) * _MARKER_DPMM))
    except ValueError: return _MARKER_LABEL_W_DEFAULT

def _marker_line(y: int, font: str, mul: int, content: str, label_w: int) -> str:
    """One TSPL TEXT line, rotation 180, positioned without the printer's help.

    TSPL's own alignment argument is not supported across all TSC firmware,
    but these internal fonts are fixed width, so a line's rendered width is
    exact and the position can just be computed.

    Every line takes the same x, and that is what left aligns them. This has
    been got wrong twice, in both directions, so here is the actual geometry.

    Under rotation 180 a line grows in -x from its anchor, so it occupies
    printer-x [x - width, x]. Reading it means turning the label around, and
    that turn reverses the axis: printer-x P is read at label_w - P. The span
    is therefore read as [label_w - x, label_w - x + width], and the anchor --
    the end the *printer* treats as trailing -- is the end the *reader* sees
    first. One x for every line is one left margin for every line.

    The trap is stopping at the printer's own span. "The line ends at its
    anchor, so a shared anchor lines up trailing edges" is true and still
    gives a left aligned block, because the label is read the other way up.
    Adding each line's width to spread the anchors, as the previous attempt
    did, right aligns it instead.

    Four templates settle it rather than any reasoning here. VW DATAMATRIX,
    nice DATAMATRIX1 and TEMPPRN each put four lines of plainly different
    lengths at a flat x=90, all at rotation 180 and all written by the label
    designer, which would not emit that for anything but an aligned block.
    LOTPRN does the same at x=265 on this same 35 mm stock, and that one goes
    out on boxes today.

    A line too long for the stock is pushed back to the edge rather than
    hanging off it, which breaks it out of alignment with the rest --
    visibly, which is the point. Nothing is silently cropped.
    """
    width = len(content) * _MARKER_FONT_W[font] * mul
    x = min(max(width, label_w - _MARKER_LEFT_MARGIN), label_w)
    return f'TEXT {x},{y},"{font}",180,{mul},{mul},"{content}"'

def _print_marker_label(pno: str, marker: str, machine_id: str, printer_name: str = _PRINTER_NAME):
    """Print the text-only label that brackets a part's run on the roll.

    START goes out when a part finishes loading, END when it is released or
    the program closes, so the roll shows where one part's output stops and
    the next begins. There is no barcode or data matrix on it -- nothing scans
    this label, it is read by eye.

    MARKER.prn holds the stock setup (size, gap, tear) and the body is
    generated here, because placing each line needs its rendered width.
    """
    base = os.path.dirname(__file__)
    prn_file = os.path.join(base, "MARKER.prn")
    if not os.path.exists(prn_file):
        print(f"[PRINT DEBUG] marker template not found ({prn_file}) -- aborting print")
        return
    try:
        with open(prn_file, "r", encoding="latin-1") as f: template = f.read()
    except Exception as ex:
        print(f"[PRINT DEBUG] could not read marker template: {ex}")
        return
    # Read before the body is built, not after: the stock size in it is what
    # the line positions are measured against.
    label_w = _marker_label_width(template)
    now = datetime.datetime.now()
    # Captions padded to the longest one so the colons line up down the block.
    #
    # Date and time share one row. They are one fact about the run -- when it
    # opened, when it closed -- and split across two rows they cost a line of
    # a four line label for no reading anyone does by eye. The time is minutes
    # only: with seconds the row comes to 25 characters, and at 12 dots a
    # character in font "2" that is 300 dots against a 280 dot label, so the
    # D&T caption would print off the edge. Seconds are still recorded where
    # they are used, on the part label and in testmaster.
    fields = [f"{cap:<5} : {val}" for cap, val in (
        ("P/NO",  pno),
        ("D&T",   now.strftime("%d/%m/%y %H:%M")),
        ("MC ID", machine_id),
    )]
    # Read top to bottom on the label; with rotation 180 that is y descending.
    # Title then rows, on LOTPRN's own title height and row pitch, so the two
    # labels coming off this machine are laid out the same way. Three rows
    # against that label's six leaves the lower part of the stock clear, which
    # is what LOTPRN would look like with three fields on it.
    rows = [_MARKER_FIRST_ROW_Y - i * _MARKER_ROW_PITCH for i in range(len(fields))]
    body = '\r\n'.join(
        [_marker_line(_MARKER_TITLE_Y, "3", 1, f"{marker} LABEL", label_w)]
        + [_marker_line(y, "2", 1, f, label_w) for y, f in zip(rows, fields)]
    )
    try:
        text = template.replace("@body@", body)
        # A scratch file per marker: _print_barcode_label owns TEMPPRN.prn and
        # both printers run on background threads, so any shared scratch file
        # could be overwritten between write and send.
        tmp = os.path.join(base, f"TEMPMARKER_{marker}.prn")
        with open(tmp, "w", encoding="latin-1") as f: f.write(text)
        _print_raw(printer_name, tmp)
    except Exception as ex:
        print(f"[PRINT DEBUG] failed building/sending marker label: {ex}")

def _print_lot_label(pno: str, model: str, alc: str, vendor_code: str, eo_number: str,
                     lot_no: str, qty: int, count: int, emp: str, machine_id: str,
                     printer_name: str = _LOT_PRINTER_NAME) -> bool:
    """Print the box label for a lot. True when it went to the spooler.

    Fired from the lot dialog's OK button, never from the test cycle: the
    label is for a box the operator is closing, and printing it the instant
    the count ticked over put it on the roll while they were still holding the
    part that tripped it.

    Also called by the Report page for a box left part-filled, where the
    quantity is typed rather than counted. Same template, same fields, same
    label -- what differs is only how the numbers on it were arrived at.

    LOTPRN.prn is a plain TSPL template with @placeholders@ in it, the same
    arrangement the part labels use, so the layout can be redrawn in the label
    designer without touching this file.
    """
    base = os.path.dirname(__file__)
    prn_file = os.path.join(base, "LOTPRN.prn")
    if not os.path.exists(prn_file):
        print(f"[PRINT DEBUG] lot label template not found ({prn_file}) -- aborting print")
        return False
    now = datetime.datetime.now()
    fields = {
        "@partNumber@":  pno,
        "@modelName@":   model,
        "@alcCode@":     alc,
        "@vendorCode@":  vendor_code,
        "@eoNumber@":    eo_number,
        "@lotNo@":       lot_no,
        "@lotQty@":      str(qty),
        "@lotCount@":    str(count),
        "@empCode@":     emp,
        "@machineID@":   machine_id,
        "@machineID_NoAlphabet@": machine_id.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                                    "abcdefghijklmnopqrstuvwxyz"),
        "@ddMMyy@":      now.strftime("%d%m%y"),
        "@dd/MM/yy@":    now.strftime("%d/%m/%y"),
        "@HH:mm:ss@":    now.strftime("%H:%M:%S"),
    }
    try:
        with open(prn_file, "r", encoding="latin-1") as f:
            text = f.read()
        for key, val in fields.items():
            text = text.replace(key, val or "")
        text = _apply_lot_3_letters(text, _lot_3_letters(now))
        # Its own scratch file: the part label owns TEMPPRN.prn and the marker
        # labels own TEMPMARKER_*.prn, and all three go out on background
        # threads that can overlap.
        tmp = os.path.join(base, "TEMPLOTPRN.prn")
        with open(tmp, "w", encoding="latin-1") as f:
            f.write(text)
        return _print_raw(printer_name, tmp)
    except Exception as ex:
        print(f"[PRINT DEBUG] failed building/sending lot label: {ex}")
        return False

# render() publishes a callback here so main.py can close out the loaded
# part's run when the program exits; None when no Test Console page is live.
_ACTIVE = {"close_out": None}

def close_out_run() -> bool:
    """Print the END label for whatever part is still loaded, if any.

    Called by main.py on window close. Deliberately synchronous: the marker
    printers otherwise use daemon threads, which die the moment the
    interpreter exits, so a threaded print here would usually never reach the
    spooler.

    False means the operator called the close off and the window should stay
    open. Anything else -- no console page, or a close-out that threw -- is
    True: a fault in here must not leave a station that cannot be shut down.
    """
    fn = _ACTIVE.get("close_out")
    if fn is None: return True
    try: return fn() is not False
    except Exception as ex:
        print(f"[PRINT DEBUG] close-out failed: {ex}")
        return True

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
    style.configure("TC.TLabelframe.Label", background="black", foreground="#aaa", font=("Arial", _fs(9)))
    style.configure("Spec.Treeview.Heading", background="#1a1a1a", foreground="white", font=("Arial", _fs(9), "bold"))
    style.configure("Spec.Treeview", background="#0d0d0d", foreground="white", fieldbackground="#0d0d0d", font=("Arial", _fs(9)), rowheight=_px(26))
    # Read standing up, a metre or so back, so the day's lots are sized to be
    # legible from there. rowheight follows the type, or the taller glyphs
    # clip against the row above.
    style.configure("Lot.Treeview.Heading", background="#0a1a00", foreground="white", font=("Arial", _fs(10), "bold"))
    style.configure("Lot.Treeview", background="#060d00", foreground="#aee571", fieldbackground="#060d00", font=("Arial", _fs(11)), rowheight=_px(28))
    # Column headers otherwise brighten on mouse-over / press -- pin each
    # heading style's color so it stays flat in every state.
    for heading_style, bg, fg in (
        ("Spec.Treeview.Heading", "#1a1a1a", "white"),
        ("Lot.Treeview.Heading", "#0a1a00", "white"),
    ):
        style.map(heading_style, background=[("active", bg), ("pressed", bg)],
                  foreground=[("active", fg), ("pressed", fg)])
    style.map("Spec.Treeview", background=[("selected", "#1c3a5e")])
    style.map("Lot.Treeview",  background=[("selected", "#1c3a5e")])

    try:
        db.ensure_column("testmaster", "visionimg", "VARCHAR(255)")
        # Per-camera vision verdicts. One taught model per part is run against
        # each enabled camera, so the record shows which camera saw the part
        # rather than a single verdict for the whole station.
        db.ensure_column("testmaster", "cam1result", "VARCHAR(10)")
        db.ensure_column("testmaster", "cam2result", "VARCHAR(10)")
        # A test run is identified by (part number, lot number), because the lot
        # sequence restarts at 1 for each part every day. A live DB created
        # before that carries a UNIQUE index on lotno alone, which rejects the
        # second part's first lot of the day outright, and a testresult table
        # with no part number, whose per-channel rows would then be ambiguous
        # between two parts sharing a lot string.
        db.ensure_column("testresult", "pno", "VARCHAR(50)")
        with db.get_cursor(commit=True) as _cur:
            _cur.execute("UPDATE testresult r JOIN testmaster m ON r.lotno = m.lotno "
                         "SET r.pno = m.pno WHERE r.pno IS NULL")
        db.drop_index("testmaster", "lotno")
        db.ensure_unique_index("testmaster", "uq_pno_lotno", "pno, lotno")
    except Exception as ex:
        # DB may be unreachable right now -- don't block the page for it
        print(f"[DB MIGRATION] skipped: {ex}")

    state = {
        "pno": None, "alc": "", "model": "", "vendor_code": "", "eo_number": "", "pname": "", "cname": "",
        "num_channels": 0, "spec_ir": {}, "spec_acw": {}, "test_running": False, "awaiting_scan": False, "dev_polling": False, "total": 0, "ok": 0, "ng": 0,
        "lot_no": "", "labelstr": "", "start_time": None, "flag": True, "input_polling": False,
        "last_vision_result": None, "is_rework": False,
        "ct_last": None, "batch_no": 0, "batch_ok": 0, "batch_reason": "", "batch_shown": None,
        "cam_results": {1: None, 2: None},
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
    # The sidebar runs the full height of the page (rowspan 2), so the bottom
    # row -- PLC I/O / Label Scan Result / Log -- ends where the left column
    # ends instead of running underneath the sidebar. That leaves COM Status a
    # home at the very bottom of the sidebar, level with the bottom row.
    content.rowconfigure(0, weight=1); content.rowconfigure(1, weight=0)
    content.columnconfigure(0, weight=1); content.columnconfigure(1, weight=0)
    left_area = tk.Frame(content, bg="black"); left_area.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    right_panel = tk.Frame(content, bg="black", width=_px(220))
    right_panel.grid(row=0, column=1, rowspan=2, sticky="nsew")
    right_panel.grid_propagate(False)
    right_panel.columnconfigure(0, weight=1)
    # Sidebar order, top to bottom: cameras, verdict block, lot/time strip,
    # REWORK, COM Status.
    for i in range(5): right_panel.rowconfigure(i, weight=0)
    right_panel.rowconfigure(1, weight=1)   # result block absorbs leftover space

    # The verdict is the only thing in this block, filling it edge to edge so
    # it reads from across the line; the lot number and elapsed time sit in a
    # slim strip underneath rather than inside it.
    result_outer = tk.Frame(right_panel, bg="#333", padx=1, pady=1)
    result_outer.grid(row=1, column=0, sticky="nsew", pady=(0, 3))
    result_lbl = tk.Label(result_outer, text="READY", bg="#1a1a1a", fg="#555", font=("Arial", _fs(30), "bold"), anchor="center")
    result_lbl.pack(fill="both", expand=True)

    def _set_verdict(text, bg, fg):
        """Set the verdict, sized to the sidebar. "TESTING" is half again as
        wide as "PASS", so one fixed size either clips it or wastes the block
        on the short words -- pick the size from the word instead."""
        result_lbl.config(text=text, bg=bg, fg=fg,
                          font=("Arial", _fs(30) if len(text) <= 5 else _fs(22), "bold"))

    # Lot number and elapsed time tuck under the verdict as a two-line strip:
    # caption left, value right, small enough that the verdict block keeps
    # essentially all of the sidebar's spare height.
    meta = tk.Frame(right_panel, bg="black")
    meta.grid(row=2, column=0, sticky="ew", padx=2, pady=(0, 3))
    meta.columnconfigure(1, weight=1)
    _META_CAP = {"bg": "black", "fg": "#444", "font": ("Arial", _fs(7)), "anchor": "w"}
    _META_VAL = {"bg": "black", "fg": "#888", "font": ("Consolas", _fs(8)), "anchor": "e"}
    tk.Label(meta, text="LOT NO", **_META_CAP).grid(row=0, column=0, sticky="w")
    lot_lbl = tk.Label(meta, text="—", **_META_VAL)
    lot_lbl.grid(row=0, column=1, sticky="ew", padx=(4, 0))
    tk.Label(meta, text="TIME (s)", **_META_CAP).grid(row=1, column=0, sticky="w")
    elapsed_lbl = tk.Label(meta, text="—", **_META_VAL)
    elapsed_lbl.grid(row=1, column=1, sticky="ew", padx=(4, 0))

    # Rework indicator sits between the verdict block and COM Status, styled
    # like a COM Status pill (bordered box, always showing its name) -- so it
    # stays readable without stealing room from the verdict. Blinking is done
    # by swapping its color, not its text, while X3 (rework select) is high.
    rework_lbl = tk.Label(right_panel, text="REWORK", bg="#2a2a2a", fg="#555",
                          font=("Arial", _fs(8)), pady=3, bd=1, relief="solid")
    rework_lbl.grid(row=3, column=0, sticky="ew", pady=(0, 3))

    com_lf = ttk.LabelFrame(right_panel, text="COM Status", style="TC.TLabelframe")
    
    # Initialize local vision controller (headless, no UI panel)
    try:
        from vision_engine.vision_controller import get_vision_controller
        vision_ctrl = get_vision_controller()
    except Exception as e:
        vision_ctrl = None
        print(f"Vision controller init error: {e}")

    com_lf.grid(row=4, column=0, sticky="ew")
    com_inner = tk.Frame(com_lf, bg="black", padx=4, pady=4)
    com_inner.pack(fill="both")
    com_labels = {}
    for i, dev in enumerate(["HiPot", "IO Ctrl", "Scanner", "Printer"]):
        r, c = divmod(i, 2)
        lbl = tk.Label(com_inner, text=dev, bg="#2a2a2a", fg="#555", font=("Arial", _fs(8)), width=9, pady=3, bd=1, relief="solid")
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

    # The printer and the scanner have no port this page opens, so unlike
    # HiPot and IO Ctrl -- whose pills follow the serial calls the test
    # sequence makes -- their state has to be asked for. Both lookups touch
    # Windows (printer spooler, device list) and the device walk takes about
    # a second, so the poll runs on its own thread and only repaints on a
    # change, which also keeps the log to one line per plug or unplug.
    _DEV_POLL_MS = 10000
    _dev_seen = {"Printer": None, "Scanner": None}

    def _device_status_once():
        if not state.get("dev_polling"): return
        def _work():
            found = {"Printer": _printer_online(_PRINTER_NAME),
                     "Scanner": _scanner_present(_SCANNER_NAME)}
            names = {"Printer": _PRINTER_NAME, "Scanner": _SCANNER_NAME}
            for dev, ok in found.items():
                if _dev_seen[dev] == ok: continue
                first = _dev_seen[dev] is None
                _dev_seen[dev] = ok
                _after(0, lambda d=dev, o=ok: set_com_status(d, o))
                _after(0, lambda d=dev, o=ok, n=names[dev], f=first:
                       _log(f"{d}: {'connected' if o else 'not found'} ('{n}')"
                            + ("" if f else f" — {'plugged in' if o else 'disconnected'}")))
            _after(_DEV_POLL_MS, _device_status_once)
        threading.Thread(target=_work, daemon=True).start()

    def _device_status_start():
        if state.get("dev_polling"): return
        state["dev_polling"] = True
        _device_status_once()

    # Camera frames — live feed from OpenCV
    cam_cfg = _load_cam_cfg()
    cam_frame = tk.Frame(right_panel, bg="black")
    cam_frame.grid(row=0, column=0, sticky="new", pady=(0, 3))
    _cam_feeds = []  # track for cleanup
    cam_labels = {}       # cam_id -> preview Label
    cam_feeds_by_id = {}  # cam_id -> CameraFeed (only when a live feed is running)
    cam_default_text = {}  # cam_id -> the label's placeholder text


    def _open_camera_popup(e, cam_id):
        dlg = tk.Toplevel(parent)
        dlg.withdraw()
        dlg.title(f"Camera {cam_id} Configuration")
        dlg.configure(bg="#222")
        dlg.transient(parent)
        dlg.resizable(False, False)

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
        lf = tk.LabelFrame(dlg, text=f"Camera {cam_id}", bg="#222", fg="#e8a000", font=("Arial", _fs(10), "bold"))
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

        # Live preview. Choosing between "Camera 0" and "Camera 1" from a
        # dropdown is guesswork on a rig with two identical USB cameras --
        # the picture is the only thing that says which one is which.
        _PREV_W, _PREV_H = 320, 240
        lf2 = tk.LabelFrame(dlg, text="Preview", bg="#222", fg="#e8a000", font=("Arial", _fs(10), "bold"))
        lf2.pack(fill="x", padx=10, pady=5)
        prev_box = tk.Frame(lf2, bg="#111", width=_PREV_W, height=_PREV_H, bd=1, relief="solid")
        prev_box.pack_propagate(False)
        prev_box.pack(padx=6, pady=6)
        prev_lbl = tk.Label(prev_box, text="—", bg="#111", fg="#666", font=("Arial", _fs(10)))
        prev_lbl.pack(fill="both", expand=True)

        preview = {"feed": None}

        def _stop_preview():
            feed, preview["feed"] = preview["feed"], None
            if feed is not None:
                try: feed.stop()
                except Exception: pass

        def _start_preview(*_a):
            """(Re)open the preview for whatever the two dropdowns now say."""
            _stop_preview()
            prev_lbl.config(image="", text="", fg="#666"); prev_lbl.image = None
            d_sel, r_sel = cmb_c.current(), cmb_r.current()
            idx = cam_indices[d_sel] if d_sel > 0 else -1
            if idx < 0:
                prev_lbl.config(text="Camera disabled"); return
            if not (_cv2_ok and _pil_ok):
                prev_lbl.config(text="Preview unavailable\n(OpenCV or Pillow missing)", fg="#ff9800"); return
            w, h = resolutions[r_sel][1], resolutions[r_sel][2]
            prev_lbl.config(text="Opening camera…", fg="#e8a000")
            feed = CameraFeed(prev_lbl, idx, display_w=_PREV_W, display_h=_PREV_H, width=w, height=h)
            preview["feed"] = feed
            feed.start()

        cmb_c.bind("<<ComboboxSelected>>", _start_preview)
        cmb_r.bind("<<ComboboxSelected>>", _start_preview)

        # Active Dataset config (vision_config.json)
        lf3 = tk.LabelFrame(dlg, text="Active Vision Dataset (Current Part)", bg="#222", fg="#e8a000", font=("Arial", _fs(10), "bold"))
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
                
            _stop_preview()
            dlg.destroy()
            
            # Reload page to apply changes
            try: parent.winfo_toplevel().event_generate("<<NavigateHome>>")
            except: pass

        tk.Button(dlg, text="Save Settings", bg="#1b5e20", fg="white", font=("Arial", _fs(11), "bold"), bd=0, padx=20, pady=8, command=_save).pack(pady=15)

        def _close(_e=None):
            """Dismissed without saving. nav_camera stopped the page's own
            feeds to free the cameras for this dialog, so they have to be put
            back -- otherwise cancelling left both panels dead until the next
            navigation."""
            _stop_preview()
            for feed in _cam_feeds:
                try: feed.start()
                except Exception: pass
            try: dlg.grab_release()
            except Exception: pass
            dlg.destroy()
        dlg.protocol("WM_DELETE_WINDOW", _close)
        dlg.bind("<Escape>", _close)

        # Centred on the app window rather than the screen: they are the same
        # thing on a maximised single monitor and very much not on two.
        dlg.update_idletasks()
        w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
        top = parent.winfo_toplevel()
        x = top.winfo_rootx() + (top.winfo_width() - w) // 2
        y = top.winfo_rooty() + (top.winfo_height() - h) // 2
        x = max(0, min(x, dlg.winfo_screenwidth() - w))
        y = max(0, min(y, dlg.winfo_screenheight() - h))
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.deiconify()
        dlg.update_idletasks()
        # Windows places the window *frame* at the requested point, while every
        # measurement here is of the client area inside it, so the title bar and
        # border push the dialog down and right of where it was asked to go.
        # Measure that trim now the window is mapped, and centre the frame --
        # the whole window is what the eye judges as centred, title bar included.
        bx = max(0, dlg.winfo_rootx() - x)          # left border
        by = max(0, dlg.winfo_rooty() - y)          # title bar + top border
        fw, fh = w + 2 * bx, h + by + bx            # the frame, as the screen sees it
        x = top.winfo_rootx() + (top.winfo_width() - fw) // 2
        y = top.winfo_rooty() + (top.winfo_height() - fh) // 2
        x = max(0, min(x, dlg.winfo_screenwidth() - fw))
        y = max(0, min(y, dlg.winfo_screenheight() - fh))
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.grab_set()
        _start_preview()

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
                       bg="#1a1a1a", fg="#555", font=("Arial", _fs(10), "bold"), cursor="hand2")
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
            # Navigating away is not "closing the program", so this only drops
            # the hook -- it does not print an END.
            _ACTIVE["close_out"] = None
            for feed in _cam_feeds:
                feed.stop()
            state["input_polling"] = False
            state["dev_polling"] = False
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
    pi = tk.Frame(pf, bg="black", padx=8, pady=3)
    pi.pack(fill="both", expand=True)
    for col in range(8): pi.columnconfigure(col, weight=1 if col % 2 != 0 else 0)
    def _lbl(parent, text): return tk.Label(parent, text=text, bg="black", fg="#999", font=("Arial", _fs(11)))
    def _ent(parent, w=13, editable=True, fg="white", size=_fs(12)):
        st = "normal" if editable else "readonly"
        e = tk.Entry(parent, bg="black" if editable else "#0d0d0d", fg=fg, font=("Arial", size), insertbackground="white", bd=1, relief="solid", width=w, highlightbackground="#444", highlightcolor="#888", highlightthickness=1, readonlybackground="#0d0d0d", state=st)
        return e

    _lbl(pi, "Part No").grid(row=0, column=0, sticky="w", pady=4); ent_pno = _ent(pi, w=15, editable=False); ent_pno.grid(row=0, column=1, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "EMP ID").grid(row=0, column=4, sticky="w", padx=(10, 4)); ent_emp = _ent(pi, w=7, editable=True); ent_emp.grid(row=0, column=5, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "Part Name").grid(row=1, column=0, sticky="w", pady=4); ent_pname = _ent(pi, w=7, editable=False); ent_pname.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "Customer").grid(row=1, column=4, sticky="w", padx=(10, 4)); ent_cust = _ent(pi, w=7, editable=False); ent_cust.grid(row=1, column=5, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "Model").grid(row=2, column=0, sticky="w", pady=4); ent_model = _ent(pi, w=7, editable=False); ent_model.grid(row=2, column=1, sticky="ew", padx=5)
    _lbl(pi, "ALC").grid(row=2, column=2, sticky="w", padx=(8, 4)); ent_alc = _ent(pi, w=5, editable=False); ent_alc.grid(row=2, column=3, sticky="ew", padx=5)
    # The full lot number is on the header and in the results grid; this box
    # carries the three character date code out of DAY/MONTH/YEAR CODE.txt,
    # which neither of those shows.
    _lbl(pi, "Lot Code").grid(row=2, column=4, sticky="w", padx=(8, 4)); ent_lot = _ent(pi, w=7, editable=False); ent_lot.grid(row=2, column=5, columnspan=2, sticky="ew", padx=5)
    _lbl(pi, "Vendor").grid(row=3, column=0, sticky="w", pady=4); ent_vendor = _ent(pi, w=7, editable=False); ent_vendor.grid(row=3, column=1, sticky="ew", padx=5)
    _lbl(pi, "EO No").grid(row=3, column=2, sticky="w", padx=(8, 4)); ent_eo = _ent(pi, w=7, editable=False); ent_eo.grid(row=3, column=3, sticky="ew", padx=5)
    _lbl(pi, "Machine").grid(row=3, column=4, sticky="w", padx=(8, 4)); ent_machine = _ent(pi, w=7, editable=False); ent_machine.grid(row=3, column=5, sticky="ew", padx=5)
    _lbl(pi, "JIG Scan").grid(row=4, column=0, sticky="w", pady=4); ent_jig = _ent(pi, w=15, editable=False); ent_jig.grid(row=4, column=1, columnspan=3, sticky="ew", padx=5)
    _lbl(pi, "Test Type").grid(row=4, column=4, sticky="w", padx=(8, 4)); ent_testtype = _ent(pi, w=7, editable=False); ent_testtype.grid(row=4, column=5, sticky="ew", padx=5)

    # Both buttons sit with the Part No / JIG fields they act on, START
    # stacked directly above NEXT PART so the two actions of a cycle read
    # top to bottom in one place. Their commands are wired further down,
    # once _trigger_test() and _next_part() exist.
    btn_start = tk.Button(pi, text="▶  START TEST", bg="#1a1a1a", fg="#444", font=("Arial", _fs(11), "bold"), bd=0, padx=10, pady=5, cursor="hand2", activebackground="#2e7d32", activeforeground="white")
    btn_start.grid(row=3, column=6, columnspan=2, sticky="ew", padx=(10, 0), pady=(0, 4))
    btn_next_part = tk.Button(pi, text="»  NEXT PART", bg="#0d47a1", fg="white", font=("Arial", _fs(10), "bold"), bd=0, padx=10, pady=4, cursor="hand2", activebackground="#1565c0", activeforeground="white")
    btn_next_part.grid(row=4, column=6, columnspan=2, sticky="ew", padx=(10, 0))
    
    def _fill_ro(entry, val):
        entry.config(state="normal"); entry.delete(0, "end"); entry.insert(0, str(val) if val else ""); entry.config(state="readonly")
    _fill_ro(ent_machine, cfg["machine_id"])

    cf = ttk.LabelFrame(row0, text="Count", style="TC.TLabelframe")
    cf.grid(row=0, column=1, sticky="nsew")
    ci = tk.Frame(cf, bg="black", padx=8, pady=5)
    ci.pack(fill="both", expand=True)
    ci.columnconfigure(1, weight=1); ci.columnconfigure(3, weight=1)
    _lbl(ci, "Total").grid(row=0, column=0, sticky="w", pady=5); cnt_total = _ent(ci, w=5, editable=False); cnt_total.grid(row=0, column=1, sticky="ew", padx=5)
    _lbl(ci, "NG").grid(row=0, column=2, sticky="w", padx=5); cnt_ng = _ent(ci, w=5, editable=False, fg="#ff5555"); cnt_ng.grid(row=0, column=3, sticky="ew", padx=5)
    _lbl(ci, "OK").grid(row=1, column=0, sticky="w", pady=5); cnt_ok = _ent(ci, w=5, editable=False, fg="#76ff03"); cnt_ok.grid(row=1, column=1, sticky="ew", padx=5)
    _lbl(ci, "NG%").grid(row=1, column=2, sticky="w", padx=5); cnt_ng_pct = _ent(ci, w=5, editable=False, fg="#ff5555"); cnt_ng_pct.grid(row=1, column=3, sticky="ew", padx=5)
    _lbl(ci, "PPM").grid(row=2, column=0, sticky="w", pady=5); cnt_ppm = _ent(ci, w=5, editable=False, fg="#ff9800"); cnt_ppm.grid(row=2, column=1, sticky="ew", padx=5)
    _lbl(ci, "CT (s)").grid(row=2, column=2, sticky="w", padx=5); cnt_ct = _ent(ci, w=5, editable=False, fg="#4fc3f7"); cnt_ct.grid(row=2, column=3, sticky="ew", padx=5)
    # Typed by the operator, not measured: how many good parts make one lot.
    # Asked for once per part load, and counted towards from zero each time,
    # so the page says so when the box in front of them is full -- which is
    # what the running mean cycle time used to occupy this row doing: a number
    # nobody acted on, next to the live CT that they do.
    _lbl(ci, "Lot Qty").grid(row=3, column=0, sticky="w", pady=5); ent_lot_qty = _ent(ci, w=5, editable=True); ent_lot_qty.grid(row=3, column=1, sticky="ew", padx=5)
    # How full the box in front of the operator is, which none of the counts
    # above answer: those are the day's totals for the part, and a box starts
    # over on every part load. Shares the Lot Qty row deliberately -- the
    # figure it counts towards is the one sitting next to it.
    _lbl(ci, "In Box").grid(row=3, column=2, sticky="w", padx=5); cnt_batch = _ent(ci, w=5, editable=False, fg="#76ff03"); cnt_batch.grid(row=3, column=3, sticky="ew", padx=5)

    # No login on this one, unlike Scan required: it decides whether a box
    # gets its own label, not whether a part ships unverified, and the person
    # who knows if this box needs one is the operator packing it.
    lot_label_var = tk.BooleanVar(value=cfg.get("lot_label_enabled", True))
    tk.Checkbutton(ci, text="Print lot label", variable=lot_label_var,
                   bg="black", fg="#888", font=("Arial", _fs(8)), selectcolor="#1a1a1a",
                   activebackground="black", activeforeground="white",
                   highlightthickness=0, bd=0, cursor="hand2", anchor="w",
                   command=lambda: _toggle_lot_label()).grid(
        row=4, column=0, columnspan=4, sticky="w", pady=(2, 0))

    def _update_counts():
        t = state["total"]; o = state["ok"]; n = state["ng"]
        pct = f"{(n/t*100):.1f}%" if t > 0 else "0.0%"
        ppm = f"{int(n/t*1000000)}" if t > 0 else "0"
        # Cycle time is measured live, not stored -- testmaster keeps no
        # duration column, so unlike the counts above (which are read back
        # from today's rows) it only covers the tests run since the current
        # part was loaded. "—" until the first one finishes.
        ct = f"{state['ct_last']:.1f}" if state["ct_last"] is not None else "—"
        # "6/10" once a lot quantity is typed, plain "6" before then: the
        # target is the operator's to set, and a denominator invented here
        # would be a box size nobody chose.
        bq = _lot_qty()
        # batch_shown holds a finished box at its full count until the next
        # part goes into the new one. Without it the panel drops to 0 the
        # instant the lot dialog opens, so the operator reads "0/10" behind a
        # dialog telling them they have ten.
        in_box = state["batch_ok"] if state["batch_shown"] is None else state["batch_shown"]
        box = f"{in_box}/{bq}" if bq > 0 else str(in_box)
        for entry, val in [(cnt_total, str(t)), (cnt_ok, str(o)), (cnt_ng, str(n)), (cnt_ng_pct, pct), (cnt_ppm, ppm), (cnt_ct, ct), (cnt_batch, box)]:
            entry.config(state="normal"); entry.delete(0, "end"); entry.insert(0, val); entry.config(state="readonly")

    def _lot_qty() -> int:
        """The typed lot quantity, or 0 when the box is empty or not a
        number -- which is the off switch for the announcement below."""
        try: return int(ent_lot_qty.get().strip())
        except (AttributeError, TypeError, ValueError): return 0

    def _toggle_lot_label():
        """Turn the lot (box) label on or off. Deliberately not behind a login.

        Persisted the same way the scan setting is, so the choice survives a
        restart rather than quietly coming back on at the start of a shift.
        """
        want = lot_label_var.get()
        cfg["lot_label_enabled"] = want
        try:
            _save_cfg_key("lot_label_enabled", want)
        except Exception as ex:
            _log(f"Could not save the lot label setting: {ex}")
        _log(f"Lot label printing {'ENABLED' if want else 'DISABLED'}.")

    def _start_batch(reason: str):
        """Open a new batch -- one box being filled -- counting from zero.

        A batch is not the day's output for a part. Loading a part opens one,
        including reloading a part that already ran earlier in the shift: that
        is a fresh box, not a continuation of the one packed before the
        operator switched away. Closing off a full box opens the next.
        """
        state["batch_ok"] = 0
        state["batch_shown"] = None
        state["batch_reason"] = reason
        _update_counts()

    def _count_pass_into_lot():
        """Count one good part into the open batch, and announce a full box.

        Counted here rather than off state["ok"], which is the whole day's OK
        total for the part read back from testmaster on every load. A day
        total cannot start a second batch of the same part: switching away and
        back would carry the first box's parts into the second, and any lot
        quantity that did not divide the running total evenly would then trip
        the announcement partway through a box.
        """
        state["batch_ok"] += 1
        state["batch_shown"] = None
        _update_counts()
        if state["batch_ok"] == 1:
            # Numbered on the first part into it rather than when it opened.
            # Opening one costs nothing and happens on every part load and
            # every full box, so numbering there burnt a number on batches
            # nothing was ever packed under -- a part loaded and swapped again
            # untested, or the empty batch a full box leaves behind when the
            # operator changes part instead of carrying on.
            state["batch_no"] += 1
            _log(f"Batch {state['batch_no']} started "
                 f"({state.get('batch_reason') or 'new lot'}).")
        qty = _lot_qty()
        if qty <= 0 or state["batch_ok"] < qty: return
        count = state["batch_ok"]
        _log(f"Lot quantity reached -- batch {state['batch_no']} full ({count} OK).")
        _show_lot_dialog(count)
        # The box just closed is counted and labelled; whatever is tested next
        # goes into the following one. The panel keeps showing the full box
        # until that next part arrives -- see batch_shown in _update_counts.
        _start_batch(f"previous batch of {count} complete")
        state["batch_shown"] = count
        _update_counts()

    def _show_lot_dialog(count: int):
        """The lot announcement, as a dialog that matches the console rather
        than a stock grey messagebox -- it lands on a dark screen the operator
        is watching from a step back, so it is built the size and contrast of
        the page's own verdict panel.

        Modal on purpose: the next test cannot start until it is acknowledged,
        which is the whole point of stopping to close off a lot.
        """
        top = parent.winfo_toplevel()
        dlg = tk.Toplevel(top)
        dlg.withdraw()
        dlg.title("Lot Complete")
        dlg.configure(bg="#111")
        dlg.resizable(False, False)
        dlg.transient(top)

        # A green cap, the same green a PASS verdict uses, so the dialog reads
        # as good news before a word of it is read.
        tk.Frame(dlg, bg="#1b5e20", height=6).pack(fill="x")
        body = tk.Frame(dlg, bg="#111", padx=44, pady=26)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="\u2714", bg="#111", fg="#76ff03",
                 font=("Arial", _fs(40))).pack()
        tk.Label(body, text="Lot quantity reached!", bg="#111", fg="white",
                 font=("Arial", _fs(20), "bold")).pack(pady=(8, 0))

        # What the box label will carry, taken now: the dialog is modal, so
        # nothing can move on underneath it, and reading it here keeps the
        # print path off the live state entirely.
        lot_info = dict(
            pno=state["pno"], model=state["model"], alc=state["alc"],
            vendor_code=state["vendor_code"], eo_number=state["eo_number"],
            lot_no=state.get("lot_no") or "", qty=_lot_qty(), count=count,
            emp=ent_emp.get().strip(), machine_id=cfg["machine_id"],
        )

        # The printer line is sized for its longest wording up front, inside a
        # strut of that width. The dialog measures itself once, before the
        # probe has answered, so a line that grew afterwards would be clipped
        # by a window already sized for the "Checking..." it replaced.
        _prn_font = tkfont.Font(family="Arial", size=_fs(9))
        _prn_msgs = (
            "Lot label printing is off",
            f"Checking {_LOT_PRINTER_NAME}…",
            f"{_LOT_PRINTER_NAME} ready — the lot label prints when you press OK",
            f"{_LOT_PRINTER_NAME} not available — no lot label will print",
        )
        prn_strut = tk.Frame(body, bg="#111",
                             width=max(_prn_font.measure(m) for m in _prn_msgs),
                             height=_prn_font.metrics("linespace"))
        prn_strut.pack(pady=(12, 0))
        prn_strut.pack_propagate(False)
        prn_lbl = tk.Label(prn_strut, text="", bg="#111", fg="#666", font=_prn_font)
        prn_lbl.pack(fill="both", expand=True)

        def _paint_printer(text, fg):
            try:
                if prn_lbl.winfo_exists(): prn_lbl.config(text=text, fg=fg)
            except Exception: pass

        # None until the probe answers, so an OK clicked before it lands asks
        # again on the print thread instead of reading "not ready" off a check
        # that had not finished.
        printer = {"ready": None}

        if not lot_label_var.get():
            _paint_printer("Lot label printing is off", "#666")
        else:
            _paint_printer(f"Checking {_LOT_PRINTER_NAME}…", "#666")

            def _probe():
                ok = _printer_online(_LOT_PRINTER_NAME)
                printer["ready"] = ok
                _after(0, lambda o=ok: _paint_printer(
                    f"{_LOT_PRINTER_NAME} ready — the lot label prints when you press OK"
                    if o else
                    f"{_LOT_PRINTER_NAME} not available — no lot label will print",
                    "#76ff03" if o else "#ff9800"))
            threading.Thread(target=_probe, daemon=True).start()

        def _print_lot_now():
            """Runs off the OK button, on its own thread: the availability
            re-check and the spooler write both touch Windows, and the operator
            should not be looking at a frozen dialog while they do."""
            if not lot_label_var.get():
                _log("Lot label not printed — lot label printing is switched off.")
                return

            def _work():
                ready = printer["ready"]
                if ready is None:
                    ready = _printer_online(_LOT_PRINTER_NAME)
                if not ready:
                    _after(0, lambda: _log(f"Lot label NOT printed — "
                                           f"'{_LOT_PRINTER_NAME}' is not available."))
                    return
                sent = _print_lot_label(**lot_info)
                _after(0, lambda ok=sent: _log(
                    f"Lot label sent to {_LOT_PRINTER_NAME} "
                    f"(qty {lot_info['qty']}, part {lot_info['pno']})." if ok else
                    "Lot label FAILED to print — check LOTPRN.prn and the printer."))
            threading.Thread(target=_work, daemon=True).start()

        # Tk's Button class binding already fires the command on <space>, and
        # the dialog binds <space> too, so an acknowledgement by keyboard
        # arrives twice. Harmless when all it did was close the window; not
        # harmless now that it prints a label.
        done = {"v": False}

        def _close(_e=None, do_print=False):
            if done["v"]: return
            done["v"] = True
            try: dlg.grab_release()
            except Exception: pass
            dlg.destroy()
            if do_print:
                _print_lot_now()
            elif lot_label_var.get():
                # Dismissed rather than acknowledged. Said out loud, because a
                # box that silently never got its label is found at the next
                # station, not at this one.
                _log("Lot dialog dismissed — lot label not printed.")
            # The grab took the keyboard off the scan entry that the PASS had
            # just focused, and a wedge scanner types wherever the focus is --
            # so hand it back, or the scan after a lot would land nowhere.
            if state.get("awaiting_scan"): _show_scan_entry()

        def _ok(_e=None):
            _close(do_print=True)

        btn = tk.Button(body, text="OK", bg="#1b5e20", fg="white",
                        font=("Arial", _fs(13), "bold"), bd=0, padx=48, pady=9,
                        cursor="hand2", activebackground="#2e7d32",
                        activeforeground="white", command=_ok)
        btn.pack(pady=(22, 0))
        # OK is what releases the label, so only the keys that mean OK print.
        # Escape and the window X stay a way out that does not.
        dlg.protocol("WM_DELETE_WINDOW", _close)
        for key in ("<Return>", "<KP_Enter>", "<space>"):
            dlg.bind(key, _ok)
        dlg.bind("<Escape>", _close)

        # Centred on the app window, not the screen -- the same thing on one
        # maximised monitor and very much not on two. Measured twice because
        # Windows places the window frame at the requested point while every
        # size here is of the client area inside it, so the title bar would
        # otherwise push the dialog down and right of centre.
        dlg.update_idletasks()
        w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
        def _place(fw, fh):
            x = top.winfo_rootx() + (top.winfo_width() - fw) // 2
            y = top.winfo_rooty() + (top.winfo_height() - fh) // 3
            x = max(0, min(x, dlg.winfo_screenwidth() - fw))
            y = max(0, min(y, dlg.winfo_screenheight() - fh))
            dlg.geometry(f"{w}x{h}+{x}+{y}")
            return x, y
        x, y = _place(w, h)
        dlg.deiconify()
        dlg.update_idletasks()
        bx = max(0, dlg.winfo_rootx() - x)
        by = max(0, dlg.winfo_rooty() - y)
        _place(w + 2 * bx, h + by + bx)

        btn.focus_set()
        try: dlg.grab_set()
        except Exception: pass

    shf = tk.Frame(left_area, bg="black")
    shf.pack(fill="x", pady=(4, 1))
    tk.Label(shf, text="Inspection Specification", bg="black", fg="white", font=("Arial", _fs(10), "bold")).pack(side="left")
    spec_status_lbl = tk.Label(shf, text="[ No part loaded ]", bg="black", fg="#444", font=("Arial", _fs(9)))
    spec_status_lbl.pack(side="left", padx=10)
    cols_spec = ("TEST", "CH", "APPLIED VOLTS (V)", "TEST TIME (S)", "MIN", "MAX")
    # One channel's specs are three rows -- IR, ACW, Contact -- and the grid
    # is sized to show exactly that block, scrolling to whichever channel the
    # test is on. An eight-channel part used to lay all 24 rows in a box that
    # showed five, so the spec actually being applied was usually out of view.
    _SPEC_ROWS_PER_CH = 3
    tree_spec = ttk.Treeview(left_area, columns=cols_spec, show="headings", height=_SPEC_ROWS_PER_CH, style="Spec.Treeview")
    spec_widths = {"TEST": 160, "CH": 45, "APPLIED VOLTS (V)": 130, "TEST TIME (S)": 110, "MIN": 80, "MAX": 80}
    for col in cols_spec: tree_spec.heading(col, text=col); tree_spec.column(col, anchor="center", width=spec_widths.get(col, 90))
    tree_spec.tag_configure("ir", background="#0d1a0d", foreground="#8bc34a")
    tree_spec.tag_configure("acw", background="#0d0d1a", foreground="#64b5f6")
    tree_spec.tag_configure("contact", background="#1a1a0d", foreground="#ffd54f")
    tree_spec.pack(fill="x")

    def _spec_focus(ch: int):
        """Scroll the spec grid to one channel's block and highlight it.

        Must run on the UI thread -- the test sequence calls it through
        _after() like every other display update.
        """
        items = tree_spec.get_children()
        first = (ch - 1) * _SPEC_ROWS_PER_CH
        if not items or ch < 1 or first >= len(items): return
        tree_spec.yview_moveto(first / len(items))
        tree_spec.selection_set(items[first:first + _SPEC_ROWS_PER_CH])

    tk.Label(left_area, text="Testing", bg="black", fg="white", font=("Arial", _fs(10), "bold")).pack(fill="x", pady=(4, 1))
    # Outer white border, the same 1px padded-wrapper trick the verdict and
    # scan boxes use -- without it this table has no outline of its own and
    # runs straight into the black background, unlike the treeviews above and
    # below it.
    test_outer = tk.Frame(left_area, bg="white", padx=1, pady=1)
    test_outer.pack(fill="x")
    test_frame = tk.Frame(test_outer, bg="black")
    test_frame.pack(fill="both", expand=True)
    MAX_CH = 8
    ch_header = ["TEST", "UNIT"] + [f"CH{i}" for i in range(1, MAX_CH + 1)] + ["RESULT"]
    for i in range(len(ch_header)): test_frame.columnconfigure(i, weight=1)
    for i, h in enumerate(ch_header): tk.Label(test_frame, text=h, bg="#1a1a1a", fg="white", font=("Arial", _fs(10), "bold"), bd=1, relief="solid", pady=5).grid(row=0, column=i, sticky="nsew")
    test_rows_def = [("IR", "Insulation (IR)", "MΩ"), ("ACW", "Withstand (ACW)", "mA"), ("Contact", "Contact", "—")]
    result_rows = {}
    for r_idx, (key, name, unit) in enumerate(test_rows_def, start=1):
        tk.Label(test_frame, text=name, bg="#111", fg="white", font=("Arial", _fs(10)), bd=1, relief="solid", pady=6).grid(row=r_idx, column=0, sticky="nsew")
        tk.Label(test_frame, text=unit, bg="#111", fg="#ffcc00", font=("Arial", _fs(10), "bold"), bd=1, relief="solid").grid(row=r_idx, column=1, sticky="nsew")
        row_cells = []
        for ch_i in range(MAX_CH):
            # Bold, like the RESULT cell at the end of the row and the UNIT at
            # the start of it. These are the measured numbers the operator
            # reads across from a step back, and they were the only thing in
            # the row set lighter than the labels around them.
            lbl = tk.Label(test_frame, text="—", bg="#0d0d0d", fg="#333", font=("Arial", _fs(11), "bold"), bd=1, relief="solid", pady=6)
            lbl.grid(row=r_idx, column=2 + ch_i, sticky="nsew")
            row_cells.append(lbl)
        res_lbl = tk.Label(test_frame, text="—", bg="#0d0d0d", fg="#333", font=("Arial", _fs(11), "bold"), bd=1, relief="solid")
        res_lbl.grid(row=r_idx, column=2 + MAX_CH, sticky="nsew")
        result_rows[key] = {"cells": row_cells, "result": res_lbl}

    def _reset_test_display():
        for key in result_rows:
            for cell in result_rows[key]["cells"]: cell.config(text="—", bg="#0d0d0d", fg="#333")
            result_rows[key]["result"].config(text="—", bg="#0d0d0d", fg="#333")
        _set_verdict("READY", "#1a1a1a", "#555")
        _spec_focus(1)
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
    scan_outer.pack(fill="x", pady=(4, 2))
    scan_lbl = tk.Label(scan_outer, text="Enter Part Number + Employee ID, then press ENTER or START", bg="#001830", fg="#555", font=("Arial", _fs(11), "bold"), pady=5)
    scan_lbl.pack(fill="both", expand=True)

    tk.Label(left_area, text="Today's PASS Records", bg="black", fg="white", font=("Arial", _fs(12), "bold")).pack(fill="x", pady=(3, 1))
    # Identity first (lot, part, who, when), verdicts last -- the four result
    # columns are what the operator reads across to, so they sit together at
    # the right-hand end rather than split by EMP/TIME.
    lot_cols = ("#", "LOT NO", "ALC", "EMP", "TIME", "CAM1", "CAM2", "RESULT", "SCAN")
    tree_lot = ttk.Treeview(left_area, columns=lot_cols, show="headings", height=4, style="Lot.Treeview")
    lot_widths = {"#": 40, "LOT NO": 200, "ALC": 80, "RESULT": 80, "SCAN": 70,
                  "CAM1": 70, "CAM2": 70, "EMP": 85, "TIME": 85}
    for col in lot_cols: tree_lot.heading(col, text=col); tree_lot.column(col, anchor="center", width=lot_widths.get(col, 70))

    # START now lives in Product Info above NEXT PART, so the whole leftover
    # height of this column goes to the records table.
    tree_lot.pack(fill="both", expand=True)

    bottom = tk.Frame(content, bg="black", height=_px(128))
    bottom.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(4, 0))
    bottom.grid_propagate(False)
    bottom.columnconfigure(0, weight=0)                # I/O: only as wide as its indicator grid
    bottom.columnconfigure(1, weight=3, minsize=200)   # Label Scan Result
    bottom.columnconfigure(2, weight=2, minsize=260)   # Log
    bottom.rowconfigure(0, weight=1)
    io_lf = ttk.LabelFrame(bottom, text="PLC I/O Channel Status", style="TC.TLabelframe")
    io_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    io_inner = tk.Frame(io_lf, bg="black", padx=4, pady=3); io_inner.pack(fill="both", expand=True)

    # Cell and row-label widths are shared by every row so the M coils, the X
    # inputs and the channel-number header stay in one vertical grid. A cell is
    # exactly wide enough for its "M29"/"X20" text.
    _IO_CELL_W, _IO_LBL_W, _IO_GAP = 3, 9, 6

    # Off = flat near-black, blending into the panel like an unlit bulb.
    # On = a solid, vivid fill with dark text -- meant to visibly pop, not
    # just shift to a slightly different shade of dark. Relays (M coils) and
    # acks (X inputs) keep their own fill colors in both states -- green-family
    # for relays, amber-family for acks -- so the two stay visually separate
    # categories even when both are off, not just two shades of "off".
    #
    # The text is white in both states. It used to darken with the fill, which
    # meant an unlit cell hid which coil it was: the panel only told you what
    # you were looking at once it lit up, and reading M32 off a dark cell is
    # exactly what you want to do when it is NOT firing. State is carried by
    # the fill, which is what the eye picks up across the room anyway.
    _IO_OFF_BG,     _IO_OFF_FG     = "#0d0d0d", "#ffffff"    # relays, off
    _IO_ON_BG,      _IO_ON_FG      = "#00e676", "#003d14"    # relays, on (vivid green)
    _IO_ACK_OFF_BG, _IO_ACK_OFF_FG = "#141008", "#ffffff"    # acks, off (dark amber tint)
    _IO_ACK_ON_BG,  _IO_ACK_ON_FG  = "#ffea00", "#3d3300"    # acks, on (vivid amber)

    # ── ROW 0: what each bank of eight is ──
    # The cells say M32 and X22; without this they do not say which of the
    # two banks of eight they belong to, so the panel had to be read against
    # the PLC map to know whether a lit cell was a contact relay or an HV one.
    # Placed from the cells' own measured positions rather than packed to a
    # width in characters: Tk measures `width` in characters of the widget's
    # own font, and this row's font is not the cells' font, so any character
    # count that lines up is a coincidence waiting for a font change to break.
    # _align_bank_captions() below does it off the real geometry, once.
    grp_row = tk.Frame(io_inner, bg="black", height=_px(15)); grp_row.pack(fill="x")
    grp_row.pack_propagate(False)
    _CAP = {"bg": "black", "fg": "#9a9a9a", "font": ("Arial", _fs(7), "bold")}
    cap_contact = tk.Label(grp_row, text="CONTACT", **_CAP)
    cap_hv = tk.Label(grp_row, text="IR / ACW", **_CAP)

    # ── ROW 1: channel-number header, aligned with the M/X columns below ──
    # so a lit cell reads as "channel N", not "go look up what M32 means".
    # Bright enough to actually be read: at #555 on black these were the one
    # thing on the panel that answered "which channel is that?", and they were
    # the dimmest thing on it.
    hdr_row = tk.Frame(io_inner, bg="black"); hdr_row.pack(anchor="w")
    tk.Label(hdr_row, text="CH #:", bg="black", fg="#cfcfcf", font=("Arial", _fs(7), "bold"), width=_IO_LBL_W, anchor="w").pack(side="left")
    tk.Label(hdr_row, text="", bg="black", width=_IO_CELL_W).pack(side="left", padx=(0, _IO_GAP))  # spacer over Safety/ACK cell
    for bank in range(2):
        for ch in range(1, 9):
            tk.Label(hdr_row, text=str(ch), bg="black", fg="#cfcfcf", font=("Arial", _fs(7), "bold"), width=_IO_CELL_W).pack(side="left", padx=1)
        if bank == 0:
            tk.Frame(hdr_row, bg="black", width=_IO_GAP).pack(side="left")

    # ── ROW 1: PLC Outputs (M Coils) ──
    out_row = tk.Frame(io_inner, bg="black"); out_row.pack(anchor="w", pady=(2, 5))
    tk.Label(out_row, text="OUT (M):", bg="black", fg="#777", font=("Arial", _fs(8), "bold"), width=_IO_LBL_W, anchor="w").pack(side="left")

    # Safety Relay
    safety_lbl = tk.Label(out_row, text="M28", bg=_IO_OFF_BG, fg=_IO_OFF_FG, font=("Arial", _fs(7), "bold"), bd=1, relief="solid", width=_IO_CELL_W)
    safety_lbl.pack(side="left", padx=(0, _IO_GAP))

    # Contact Relays
    io_contact_labels = []
    for i in range(1, 9):
        lbl = tk.Label(out_row, text=f"M{29+i}", bg=_IO_OFF_BG, fg=_IO_OFF_FG, font=("Arial", _fs(7)), bd=1, relief="solid", width=_IO_CELL_W)
        lbl.pack(side="left", padx=1)
        io_contact_labels.append(lbl)

    tk.Frame(out_row, bg="black", width=_IO_GAP).pack(side="left")

    # HV Relays
    io_ir_acw_labels = []
    for i in range(1, 9):
        lbl = tk.Label(out_row, text=f"M{19+i}", bg=_IO_OFF_BG, fg=_IO_OFF_FG, font=("Arial", _fs(7)), bd=1, relief="solid", width=_IO_CELL_W)
        lbl.pack(side="left", padx=1)
        io_ir_acw_labels.append(lbl)

    # ── ROW 2: PLC Inputs (X Pins) ──
    in_row = tk.Frame(io_inner, bg="black"); in_row.pack(anchor="w", pady=(0, 2))
    tk.Label(in_row, text="IN (X):", bg="black", fg="#777", font=("Arial", _fs(8), "bold"), width=_IO_LBL_W, anchor="w").pack(side="left")

    # Safety ACK
    x4_lbl = tk.Label(in_row, text="X4", bg=_IO_ACK_OFF_BG, fg=_IO_ACK_OFF_FG, font=("Arial", _fs(7), "bold"), bd=1, relief="solid", width=_IO_CELL_W)
    x4_lbl.pack(side="left", padx=(0, _IO_GAP))

    # The machine-wide inputs, in X order. None of these is per-channel --
    # unlike X20-X27 further along, they sit above the contact coils only
    # because that is where the row has room, so they are ordered to read as a
    # panel rather than to pair with whichever M coil is above each one.
    #
    #   X0  physical START button -- the idle poll reads it to launch a test
    #   X1  physical NG Reset button
    #   X2  contact OK (one global signal, not per-channel)
    #   X3  rework select -- drives the REWORK badge and which barcode
    #       template gets printed, so it belongs on the panel with the rest of
    #       the inputs rather than only behind a blinking label
    x0_lbl = tk.Label(in_row, text="X0", bg=_IO_ACK_OFF_BG, fg=_IO_ACK_OFF_FG, font=("Arial", _fs(7), "bold"), bd=1, relief="solid", width=_IO_CELL_W)
    x0_lbl.pack(side="left", padx=1)

    x1_lbl = tk.Label(in_row, text="X1", bg=_IO_ACK_OFF_BG, fg=_IO_ACK_OFF_FG, font=("Arial", _fs(7), "bold"), bd=1, relief="solid", width=_IO_CELL_W)
    x1_lbl.pack(side="left", padx=1)

    x2_lbl = tk.Label(in_row, text="X2", bg=_IO_ACK_OFF_BG, fg=_IO_ACK_OFF_FG, font=("Arial", _fs(7), "bold"), bd=1, relief="solid", width=_IO_CELL_W)
    x2_lbl.pack(side="left", padx=1)

    x3_lbl = tk.Label(in_row, text="X3", bg=_IO_ACK_OFF_BG, fg=_IO_ACK_OFF_FG, font=("Arial", _fs(7), "bold"), bd=1, relief="solid", width=_IO_CELL_W)
    x3_lbl.pack(side="left", padx=1)

    # X4 and X0-X3 are machine-wide signals that happen to sit under channel
    # columns 1-4, which reads as "X0 is channel 1" and is the one place the
    # CH # header lies. The dead cells under M34-M37 are the natural place to
    # say so, and cost nothing: they were empty padding.
    tk.Label(in_row, text="← not per-channel", bg="black", fg="#888",
             font=("Arial", _fs(6)), anchor="w",
             width=_IO_CELL_W * 4 + 4).pack(side="left", padx=1)

    tk.Frame(in_row, bg="black", width=_IO_GAP).pack(side="left")

    # HV ACKs (aligns under M20-M27)
    io_in_labels = []
    for i in range(1, 9):
        lbl = tk.Label(in_row, text=f"X{19+i}", bg=_IO_ACK_OFF_BG, fg=_IO_ACK_OFF_FG, font=("Arial", _fs(7)), bd=1, relief="solid", width=_IO_CELL_W)
        lbl.pack(side="left", padx=1)
        io_in_labels.append(lbl)

    def _align_bank_captions():
        """Sit each bank caption exactly over the eight cells it names.

        grp_row and out_row are both packed to the full width of io_inner, so
        a cell's x inside out_row is the same x inside grp_row.
        """
        try:
            io_inner.update_idletasks()
            for cap, cells in ((cap_contact, io_contact_labels),
                               (cap_hv, io_ir_acw_labels)):
                x0 = cells[0].winfo_x()
                cap.place(x=x0, y=0, relheight=1.0,
                          width=cells[-1].winfo_x() + cells[-1].winfo_width() - x0)
        except Exception: pass
    io_inner.after(0, _align_bank_captions)

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

    def _set_x0_indicator(active):
        try:
            if x0_lbl.winfo_exists(): x0_lbl.config(bg=_IO_ACK_ON_BG if active else _IO_ACK_OFF_BG, fg=_IO_ACK_ON_FG if active else _IO_ACK_OFF_FG)
        except Exception: pass

    def _set_x1_indicator(active):
        try:
            if x1_lbl.winfo_exists(): x1_lbl.config(bg=_IO_ACK_ON_BG if active else _IO_ACK_OFF_BG, fg=_IO_ACK_ON_FG if active else _IO_ACK_OFF_FG)
        except Exception: pass

    def _set_x2_indicator(active):
        try:
            if x2_lbl.winfo_exists(): x2_lbl.config(bg=_IO_ACK_ON_BG if active else _IO_ACK_OFF_BG, fg=_IO_ACK_ON_FG if active else _IO_ACK_OFF_FG)
        except Exception: pass

    def _set_x3_indicator(active):
        try:
            if x3_lbl.winfo_exists(): x3_lbl.config(bg=_IO_ACK_ON_BG if active else _IO_ACK_OFF_BG, fg=_IO_ACK_ON_FG if active else _IO_ACK_OFF_FG)
        except Exception: pass

    def _set_x4_indicator(active):
        try:
            if x4_lbl.winfo_exists(): x4_lbl.config(bg=_IO_ACK_ON_BG if active else _IO_ACK_OFF_BG, fg=_IO_ACK_ON_FG if active else _IO_ACK_OFF_FG)
        except Exception: pass

    _rework_blink = {"active": False, "on": False}
    _REWORK_IDLE_BG, _REWORK_IDLE_FG = "#2a2a2a", "#555"
    _REWORK_ON_BG,   _REWORK_ON_FG   = "#ff9100", "black"

    def _rework_blink_tick():
        if not _rework_blink["active"]:
            try: rework_lbl.config(bg=_REWORK_IDLE_BG, fg=_REWORK_IDLE_FG)
            except Exception: pass
            return
        _rework_blink["on"] = not _rework_blink["on"]
        try:
            if _rework_blink["on"]: rework_lbl.config(bg=_REWORK_ON_BG, fg=_REWORK_ON_FG)
            else: rework_lbl.config(bg=_REWORK_IDLE_BG, fg=_REWORK_IDLE_FG)
        except Exception: pass
        _after(500, _rework_blink_tick)

    def _set_rework_active(active: bool):
        """X3 (rework select) is high -- this cable is a rework part, not a
        fresh one. Drives the blinking badge and, at test time, which barcode
        template gets printed (plain vs. the R-suffixed rework template).
        """
        was_active = _rework_blink["active"]
        state["is_rework"] = active
        _set_x3_indicator(active)
        _rework_blink["active"] = active
        if active and not was_active:
            _rework_blink["on"] = False
            _after(0, _rework_blink_tick)
        elif not active:
            _after(0, lambda: rework_lbl.config(bg=_REWORK_IDLE_BG, fg=_REWORK_IDLE_FG))

    def _clear_all_io_indicators():
        """Force every per-channel output/ack indicator back to its resting
        (off) look immediately, instead of waiting for the background poll
        loop to notice the PLC is idle -- that gap is exactly the window
        where a just-finished test still shows stale "glowing" pins, most
        visibly after a PASS since polling doesn't resume until the operator
        scans the label.

        X2 and X4 are cleared with them -- both are test-time feedback and go
        low once the coils drop. X3 is deliberately left alone: it reports the
        position of the operator's rework selector, not anything the test
        drives, so blanking it would claim the switch had moved. X0/X1 are not
        here either -- _input_poll_stop already blanks the two button cells the
        moment it stops reading them, which is before the test starts.
        """
        for i in range(8):
            _after(0, lambda idx=i: (_set_io(io_contact_labels, idx, False),
                                      _set_io(io_ir_acw_labels, idx, False),
                                      _set_io(io_in_labels, idx, False)))
        _after(0, lambda: (_set_x2_indicator(False), _set_x4_indicator(False)))
    scan_lf = ttk.LabelFrame(bottom, text="Label Scan Result", style="TC.TLabelframe")
    scan_lf.grid(row=0, column=1, sticky="nsew", padx=(0, 4))
    scan_inner = tk.Frame(scan_lf, bg="black", padx=6, pady=4); scan_inner.pack(fill="both", expand=True)

    scan_head = tk.Frame(scan_inner, bg="black")
    scan_head.pack(fill="x")
    scan_verdict_lbl = tk.Label(scan_head, text="—", bg="black", fg="#555",
                                font=("Arial", _fs(11), "bold"), anchor="w")
    scan_verdict_lbl.pack(side="left")

    # Turning verification off lets parts ship without their printed label
    # ever being checked, so it is a supervisor decision, not an operator one:
    # the toggle asks for a login and puts itself back if that is refused.
    scan_req_var = tk.BooleanVar(value=cfg.get("scan_enabled", True))
    tk.Checkbutton(scan_head, text="Scan required", variable=scan_req_var,
                   bg="black", fg="#888", font=("Arial", _fs(8)), selectcolor="#1a1a1a",
                   activebackground="black", activeforeground="white",
                   highlightthickness=0, bd=0, cursor="hand2",
                   command=lambda: _toggle_scan_required()).pack(side="right")

    # The operator never has to click anywhere -- after a PASS this entry
    # gets keyboard focus directly, so a keyboard-wedge scanner's trigger
    # pull types the code straight in here and its own Enter submits it.
    ent_scan = _ent(scan_inner, w=16, editable=False, size=_fs(10))
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
                             font=("Consolas", _fs(8)), anchor="nw", justify="left", wraplength=300)
    scan_data_lbl.pack(fill="both", expand=True, pady=(2, 0))

    def _set_scan_box(verdict: str, raw: str = ""):
        """verdict: "OK" | "NG" | "DUP" | "" (idle)."""
        colors = {"OK": ("✅  OK", "#76ff03"), "NG": ("❌  NG", "#ff5555"),
                  "DUP": ("⚠  Duplicate label", "#ff9800")}
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

    def _set_awaiting_scan(on: bool):
        """Hold the next test until the printed label has been scanned.

        A PASS with "Scan required" checked left the physical START button
        dead -- the input poll stays off until the scan lands -- but the
        on-screen button was handed straight back, so a click started the
        next part with the previous label never verified. Both routes are
        now gated on the same flag.
        """
        state["awaiting_scan"] = on
        try:
            if not btn_start.winfo_exists(): return
            if on:
                btn_start.config(state="disabled", bg="#4a3800", fg="#ffcc00", text="⤷  SCAN LABEL TO CONTINUE")
            elif not state["test_running"]:
                btn_start.config(state="normal", bg="#1b5e20", fg="white", text="▶  START TEST")
        except Exception: pass

    def _reset_scan_box():
        """Put the box back to idle once the operator has had a moment to read
        the verdict. The verdict is not lost by clearing it -- by this point it
        is stamped on the record and shown in the SCAN column -- so the next
        part starts from a clean box instead of the previous part's result."""
        _lock_scan_entry(); _set_scan_box("")

    def _reset_for_next_part():
        """Put the whole page back to READY once the verdict and its scan
        result have had three seconds on screen.

        Clearing the scan box alone left the channel table, the verdict panel
        and the lot/cycle strip still showing the finished part, so the next
        operator walked up to a panel that looked like a live result. Nothing
        is lost by clearing it -- the record is already written and the row is
        in Today's PASS Records. Skipped when the next test has already
        started, or when a scan is still outstanding: neither should have its
        display pulled out from under it."""
        if state["test_running"] or state.get("awaiting_scan"): return
        _reset_scan_box()
        _reset_test_display()
        try:
            if scan_lbl.winfo_exists():
                scan_lbl.config(text="Enter Part Number + Employee ID, then press ENTER or START",
                                bg="#001830", fg="#555")
        except Exception: pass

    def _fit_scan_wrap(event):
        # wraplength is in pixels and has to follow the panel, or a long code
        # spills past the edge instead of wrapping inside it.
        try:
            if scan_data_lbl.winfo_exists(): scan_data_lbl.config(wraplength=max(event.width - 16, 80))
        except Exception: pass
    scan_inner.bind("<Configure>", _fit_scan_wrap)

    log_lf = ttk.LabelFrame(bottom, text="Log", style="TC.TLabelframe")
    log_lf.grid(row=0, column=2, sticky="nsew")
    log_txt = tk.Text(log_lf, bg="black", fg="#aaa", font=("Consolas", _fs(8)), bd=0, height=5, width=1)
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

    def _toggle_scan_required():
        """Enable/disable label scan verification, behind a login.

        Reverting the variable on refusal matters: Checkbutton has already
        flipped it by the time this runs, so without that the box would show a
        setting that was never applied.
        """
        want = scan_req_var.get()
        if state["test_running"]:
            scan_req_var.set(not want)
            _log("Test in progress — finish it before changing the scan setting.")
            return
        if not auth.show_login(parent.winfo_toplevel(),
                               title="Label Scan Setting", page="label_scan_toggle"):
            scan_req_var.set(not want)
            _log("Label scan setting unchanged (login cancelled or failed).")
            return
        cfg["scan_enabled"] = want
        try:
            _save_cfg_key("scan_enabled", want)
        except Exception as ex:
            _log(f"Could not save the label scan setting: {ex}")
        # The idle text of the box spells out which mode it is in.
        if not want:
            # Turning the requirement off while a PASS is still waiting for
            # its label is that scan's answer, so close the part out the way
            # a scan would. Dropping the gate alone left the page showing the
            # finished part's PASS and the input poll still stopped -- the
            # physical START button stays dead until something restarts it,
            # and nothing else on this path does.
            was_awaiting = state.get("awaiting_scan")
            _lock_scan_entry(); _set_awaiting_scan(False)
            if was_awaiting:
                _reset_for_next_part(); _input_poll_start()
        _set_scan_box("")
        _log(f"Label scan {'ENABLED' if want else 'DISABLED'} — "
             f"{'required' if want else 'not required'} after a PASS.")

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
                # The code is the day's, not the part's, so it is known before
                # anything is tested. Filling it only at the end of a run left
                # the box empty for the whole of the first part, which is when
                # somebody setting the line up wants to read it.
                _fill_ro(ent_lot, _lot_3_letters())
                cur.execute("SELECT testname, chsel AS channel, appvol, testtime, min, max FROM settingspec WHERE pno=%s", (pno,))
                rows = cur.fetchall()
            spec_ir = {}; spec_acw = {}
            for r in rows:
                tn = str(r.get("testname", "")).strip()
                ch = int(r.get("chsel", r.get("channel", 1)) or 1)
                # A row that names neither test is not one of these two and is
                # skipped, rather than being filed under whichever came last.
                if "Insulation" in tn or tn.upper() == "IR": into = spec_ir
                elif "Withstand" in tn or tn.upper() == "ACW": into = spec_acw
                else: continue
                into[ch] = {f: _spec_number(r.get(f)) for f in _SPEC_FIELDS}
                into[ch]["raw"] = {f: r.get(f) for f in _SPEC_FIELDS}
            state["spec_ir"] = spec_ir; state["spec_acw"] = spec_acw
            tree_spec.delete(*tree_spec.get_children())
            for ch in range(1, channel + 1):
                for test_key, tag, sp in [("Insulation Test", "ir", spec_ir.get(ch, {})), ("Withstand Test", "acw", spec_acw.get(ch, {}))]:
                    # Applied volts is a whole number on the spec sheet, but the
                    # column is read out of the DB as a float, which put it in
                    # the grid as "500.0".
                    appvol = f"{sp['appvol']:.0f}" if sp.get("appvol") is not None else "—"
                    cells = [sp.get(f) for f in ("testtime", "min", "max")]
                    cells = ["—" if c is None else c for c in cells]
                    tree_spec.insert("", "end", tags=(tag,), values=(test_key, str(ch), appvol, *cells))
                tree_spec.insert("", "end", tags=("contact",), values=("Contact Test", str(ch), "—", "—", "—", "—"))
            _spec_focus(1)
            spec_status_lbl.config(text=f"[ {channel} channel(s) loaded ]", fg="#4caf50")
            _log(f"Specs loaded for {pno} ({channel} ch)")
            return True
        except Exception as ex:
            messagebox.showerror("DB Error", str(ex))
            _log(f"DB Error: {ex}"); return False

    def _load_today_pass(pno=None):
        """Today's PASS records for one part, and the Count box to match.

        Pass a part number to scope both to that part; with none (no part
        loaded yet) it shows the whole day. The verdict is read from
        testmaster.result -- testresult only carries the per-channel
        measurements (ir_result / acw_result / contact_result) and has no
        'result' column at all, so the old join both failed outright and, had
        the column existed, would have listed every lot once per channel.
        """
        tree_lot.delete(*tree_lot.get_children())
        # Parameterised, not interpolated -- a part number reaches this from an
        # operator-typed field.
        where_pno = " AND pno=%s" if pno else ""
        args = (pno,) if pno else ()
        rows = []
        try:
            with db.get_cursor() as cur:
                cur.execute("SELECT lotno, alc, result, scanresult, cam1result, cam2result, empcode, time FROM testmaster "
                            "WHERE result='PASS' AND DATE(date)=CURDATE()" + where_pno +
                            " ORDER BY time DESC", args)
                rows = cur.fetchall()
        except Exception as ex:
            _log(f"Today's PASS records: load failed ({ex})")
        ok = len(rows)
        ng = 0
        try:
            with db.get_cursor() as cur2:
                cur2.execute("SELECT COUNT(*) FROM testmaster "
                             "WHERE result='FAIL' AND DATE(date)=CURDATE()" + where_pno, args)
                ng = cur2.fetchone()[0] or 0
        except Exception as ex:
            _log(f"Today's NG count: load failed ({ex})")
        state["total"] = ok + ng; state["ok"] = ok; state["ng"] = ng; _after(0, _update_counts)
        for idx, row in enumerate(rows, start=1):
            # row order is lotno, alc, result, scanresult, cam1, cam2, emp, time
            tree_lot.insert("", "end", values=(len(rows) - idx + 1, row[0], row[1], row[6], row[7],
                                              row[4] or "—", row[5] or "—",
                                              row[2] or "—", row[3] or "—"))

    _VISION_IMG_DIR = os.path.join(os.path.dirname(__file__), "vision_captures")

    # Saved at OpenCV's default the 640x480 pass image is ~64 KB, and a
    # station writes one per PASS all shift, every shift, for as long as the
    # records are kept. Quality 80 with an optimized Huffman table halves that
    # -- ~33 KB -- for 41 dB PSNR against the source frame, which on a boxed
    # overlay whose whole job is to show where the match was and what it
    # scored is a difference nobody will see.
    _VISION_JPEG_QUALITY = 80

    def _save_vision_pass_image(lot_no: str) -> str:
        """If vision passed on this cycle, save the judged (boxed) frame to
        vision_captures/<yyyy>/<mm>/<dd>/<lotno>.jpg and return its path,
        else None.

        One folder per day, nested under its month and year. A station saves
        an image per PASS all shift, so a flat directory reached tens of
        thousands of files inside a year -- slow to open, and with no way to
        archive or clear down a single day or month. Every level is numeric
        and zero padded, so the folders sort chronologically in any file
        browser and the same month of two years can never merge.

        The whole chain is created on the first save of the day; a day that
        produced no PASS leaves no empty folder behind.

        Each record stores its own path in testmaster.visionimg, so rows
        written before this keep pointing at wherever their image went and
        still preview; existing files are left exactly where they are.
        """
        result = state.get("last_vision_result")
        if result is None or result.judgement != "OK" or not _cv2_ok:
            return None
        frame = _annotate_vision_frame(result)
        if frame is None:
            return None
        try:
            now = datetime.datetime.now()
            day_dir = os.path.join(_VISION_IMG_DIR, now.strftime("%Y"),
                                   now.strftime("%m"), now.strftime("%d"))
            os.makedirs(day_dir, exist_ok=True)
            path = os.path.join(day_dir, f"{lot_no}.jpg")
            cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, _VISION_JPEG_QUALITY,
                                      cv2.IMWRITE_JPEG_OPTIMIZE, 1])
            _log(f"Vision pass image saved: {path} "
                 f"({os.path.getsize(path) / 1024:.0f} KB)")
            return path
        except Exception as ex:
            _log(f"Vision image save error: {ex}")
            return None

    def _save_result(lot_no: str, overall: str, ir_ch: dict, acw_ch: dict, contact_ch: dict, vision_img: str = None):
        try:
            with db.get_cursor(commit=True) as cur:
                now = datetime.datetime.now(); pno = state["pno"]; emp = ent_emp.get().strip()
                cur.execute("INSERT INTO testmaster (pno, pname, model, alc, channel, lotno, date, time, empcode, result, machine, visionimg, cam1result, cam2result) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (pno, state["pname"], state["model"], state["alc"], str(state["num_channels"]), lot_no, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), emp, overall, cfg["machine_id"], vision_img, state["cam_results"].get(1), state["cam_results"].get(2)))
                for ch in range(1, state["num_channels"] + 1):
                    cur.execute("INSERT INTO testresult (pno, lotno, channel, ir_volts, ir_resistance, ir_current, ir_result, acw_volts, acw_current, acw_result, contact_result) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (pno, lot_no, str(ch), str(ir_ch.get(ch, {}).get("appvol", "")), _meas_db(ir_ch.get(ch, {}).get("value")), "0.01", ir_ch.get(ch, {}).get("result", ""), str(acw_ch.get(ch, {}).get("appvol", "")), _meas_db(acw_ch.get(ch, {}).get("value")), acw_ch.get(ch, {}).get("result", ""), contact_ch.get(ch, {}).get("result", "")))
            _log(f"Saved {overall} → {lot_no}")
        except Exception as ex:
            # The part has already been tested and its label may already be
            # printed, so there is nothing to undo -- but the operator has to
            # know the run left no record, while they still have the part.
            _log(f"Save error: {ex}")
            _after(0, lambda e=ex, l=lot_no, o=overall: messagebox.showerror(
                "Result NOT Saved",
                f"Lot {l} tested {o}, but the result could not be written to "
                f"the database.\n\n{e}\n\n"
                "There is no record of this part. Note the lot number and its "
                "verdict now, and tell your supervisor before carrying on."))

    def _update_scan_result(lot_no: str, scan_res: str):
        try:
            with db.get_cursor(commit=True) as cur:
                # Scoped by part too: another part can hold the same lot string
                # today, and stamping its row with this scan's verdict would
                # quietly corrupt that part's record.
                cur.execute("UPDATE testmaster SET scanresult=%s WHERE pno=%s AND lotno=%s",
                            (scan_res, state["pno"], lot_no))
        except Exception as ex: _log(f"Scan update error: {ex}")

    def _duplicate_check(scanned: str):
        """(lot this label belongs to if already scanned, is this lot scanned).

        The second flag decides whether a duplicate can be recorded: it says
        whether the row for the lot on the bench right now already holds a
        verdict of its own.

        Covers both ways an operator can present a used label: triggering the
        scanner twice on the current one, and picking an earlier part's label
        up off the bench. Matching reuses _scan_lot_ok against each candidate,
        so it reads a label exactly the way verification does.

        Scoped to this part, and it has to be: the lot sequence restarts at 1
        per part, so another part's run today can hold the very same lot string
        and would otherwise read as a duplicate of this one.
        """
        try:
            with db.get_cursor() as cur:
                cur.execute("SELECT lotno FROM testmaster WHERE pno=%s AND DATE(date)=CURDATE() "
                            "AND scanresult IS NOT NULL AND scanresult<>'' ORDER BY time DESC",
                            (state["pno"],))
                rows = cur.fetchall()
        except Exception as ex:
            # Can't prove it's a duplicate, so don't claim it is -- fall through
            # to the normal OK/NG comparison rather than blocking a good part.
            _log(f"Duplicate check failed: {ex}"); return "", False
        done = {row[0] for row in rows if row[0]}
        dup = next((lot for lot in done if _scan_lot_ok(scanned, lot)), "")
        return dup, state["lot_no"] in done

    def _validate_employee(empno: str) -> bool:
        emp_file = os.path.join(os.path.dirname(__file__), "emp.txt")
        try: return empno in open(emp_file).read()
        except FileNotFoundError: return True

    def _plc_open() -> bool:
        """Open the PLC Modbus port, or keep the one already open.

        A handle that is open is handed back as it is. The phases of a cycle
        call this one after another, and tearing a working connection down to
        build the same one again cost a close, an open and 50ms each time --
        on the adapter this code already knows drops transactions when a port
        is reopened shortly after being closed. A handle that dies is closed
        by the read or write that discovers it, so the next call opens afresh.
        """
        if not _modbus_ok: return False
        if plc.is_open:
            set_com_status("IO Ctrl", True)
            return True
        ok = plc.open()
        if not ok: _log("PLC: could not open Modbus RTU port"); set_com_status("IO Ctrl", False)
        else: set_com_status("IO Ctrl", True)
        return ok

    def _wait_x2_low(ctx: str, timeout: float = 2.0, poll: float = 0.02) -> bool:
        """Wait for X2 (Contact OK) to fall after a channel coil is dropped.

        X2 is one global signal shared by all eight channels, not one per
        channel, so a channel's verdict is only its own if the previous
        channel's contact has cleared before this one is energised. A blind
        sleep never proved that: a coil whose OFF write never landed, or a jig
        that keeps holding continuity, leaves X2 high and the next channel
        then reads the last one's contact as its own -- which is how one
        seated cable can carry every remaining channel to PASS.

        Polls until X2 reads Low and returns True, or gives up after `timeout`
        and returns False. The caller decides what a stuck X2 means; here it
        is only reported, never judged.
        """
        deadline = time.time() + timeout
        while True:
            if not plc.is_contact_ok():
                _after(0, lambda: _set_x2_indicator(False))
                return True
            if time.time() >= deadline:
                _after(0, lambda: _set_x2_indicator(True))
                _log(f"{ctx}: X2 (Contact OK) is still High {timeout:.1f}s after the coil was dropped.")
                return False
            time.sleep(poll)

    def _wait_x2_high(ctx: str, timeout: float = 0.5, poll: float = 0.02) -> bool:
        """Wait for X2 (Contact OK) to rise after a channel coil is energised.

        The mirror of _wait_x2_low, and here for the same reason it is: a coil
        write returning does not mean the relay has closed, and the fixed 0.5s
        that used to stand here never proved it had -- it only waited long
        enough to be fairly sure, then took one sample.

        `timeout` is that same 0.5s, so no channel can ever wait longer than it
        did before. A contact that is there answers in a few tens of
        milliseconds and the phase moves on; one that is not still takes the
        full 0.5s and reads exactly the NG it read before. Faster or equal,
        never slower, and the verdict is unchanged either way.

        Two consecutive High reads, not one. A closing relay bounces, and
        unlike the falling edge -- where an early answer is caught out by the
        next channel reading its own contact -- an early High here would pass
        a channel outright. The confirming read costs one Modbus round trip
        against the 0.5s sample it replaces.
        """
        deadline = time.time() + timeout
        seen = 0
        while True:
            if plc.is_contact_ok():
                seen += 1
                if seen >= 2:
                    _after(0, lambda: _set_x2_indicator(True))
                    return True
            else:
                seen = 0
            if time.time() >= deadline:
                _after(0, lambda: _set_x2_indicator(False))
                if seen:
                    _log(f"{ctx}: X2 (Contact OK) would not hold High for two reads.")
                return False
            time.sleep(poll)

    def _run_contact_test(n_ch: int) -> tuple:
        """Contact test via PLC — set each channel coil, read acknowledge input."""
        _log("Contact Test → PLC Modbus (M coils / X inputs)")
        if not _plc_open():
            _log("CRITICAL: PLC Modbus port blocked or disconnected!")
            return False, {ch: {"result": "FAIL"} for ch in range(1, n_ch + 1)}
        # Ensure safety relay is in Contact Test mode
        _log("M28 (Safety Relay) -> ON (Contact Mode)")
        moved = plc.is_hv_mode is not False
        plc.safety_relay_to_contact()
        _after(0, lambda: _set_safety_indicator(True))
        if moved: time.sleep(_RELAY_SETTLE_S)
        x4_ack = plc.read_input(_PLC_SAFETY_ACK)
        _log(f"X4 (Safety ACK): {'OK' if x4_ack else 'NO ACK!'}")
        _after(0, lambda a=x4_ack: _set_x4_indicator(a))
        contact_res = {}; all_pass = True
        for ch in range(1, n_ch + 1):
            _log(f"Contact Test: Testing CH{ch}...")
            _after(0, lambda c=ch: _spec_focus(c))
            # Turn ON channel coil
            _log(f"CH{ch} -> ON")
            plc.set_channel(ch, True)
            _after(0, lambda c=ch-1: _set_io(io_contact_labels, c, True))
            # The wait and the reading are one act: _wait_x2_high returns as
            # soon as X2 is up and holding, and False if it never was inside
            # the 0.5s this used to spend before sampling once.
            # Note: X20-X27 are hardware-linked to IR/ACW relays only, so we do not check them here.
            x2_passed = _wait_x2_high(f"CH{ch} -> ON")
            _log(f"X2 (Contact OK): {'OK (High)' if x2_passed else 'NG (Low)'}")
            _after(0, lambda a=x2_passed: _set_x2_indicator(a))
            passed = x2_passed
            
            contact_res[ch] = {"result": "PASS" if passed else "FAIL"}
            if not passed:
                all_pass = False
                _log(f"Contact (CH{ch}): Failed — X2 (Contact OK) went Low!")
            _after(0, lambda c=ch-1, p=passed: _set_cell("Contact", c, "OK" if p else "NG", p))
            # Turn OFF the channel coil and confirm X2 actually falls before
            # the next channel goes up. Waiting a fixed 0.5s here only assumed
            # it had; every channel after a coil that failed to drop was then
            # reading this channel's contact instead of its own.
            _log(f"CH{ch} -> OFF")
            if not plc.set_channel(ch, False):
                _log(f"CH{ch}: coil OFF write was refused by the PLC.")
            _after(0, lambda c=ch-1: _set_io(io_contact_labels, c, False))
            if not _wait_x2_low(f"CH{ch} -> OFF"):
                # This channel's own reading stands -- it was taken with the
                # coil up. What cannot stand is every channel after it, so
                # mark those unjudged rather than pass them on a stale X2.
                all_pass = False
                for rest in range(ch + 1, n_ch + 1):
                    contact_res[rest] = {"result": "FAIL"}
                    _after(0, lambda c=rest-1: _set_cell("Contact", c, "NG", False))
                _log("Contact: aborting — X2 will not clear, so no later channel can be judged on its own.")
                break
        plc.close()
        _after(0, lambda p=all_pass: _set_row_result("Contact", p))
        _log(f"Contact: {'PASS' if all_pass else 'FAIL'}"); return all_pass, contact_res

    def _run_contact_boundary_check(n_ch: int) -> str:
        """Pre-test jig check on the part's channel boundary.

        Driving CH1 alone only proved *something* was in the jig. Driving the
        part's highest channel proves the whole harness is seated, and driving
        the one past it proves nothing extra is bridging -- a wrong cable or
        wrong jig that shares the first conductors answers CH1 exactly like
        the right one does.

        Returns "OK", "NOT_SEATED" (the part's last channel gave no contact),
        "STUCK" (X2 never fell again after that channel was switched off, so
        the channel above it cannot be judged on its own reading),
        "EXTRA" (the channel past it answered when this part has no conductor
        there) or "PLC" (port unreachable).
        """
        last = max(1, min(n_ch, MAX_CH))
        nxt = last + 1 if last < MAX_CH else None
        _log(f"Contact boundary check → CH{last} expect OK" +
             (f", CH{nxt} expect NG" if nxt else f" (CH{last} is the last channel — nothing above it to probe)"))
        if not _plc_open():
            _log("CRITICAL: PLC Modbus port blocked or disconnected!")
            return "PLC"

        # 1) Turn on Safety Relay and confirm X4
        _log("M28 (Safety Relay) -> ON (Contact Mode)")
        moved = plc.is_hv_mode is not False
        plc.safety_relay_to_contact()
        if moved: time.sleep(_RELAY_SETTLE_S)
        x4_ack = plc.read_input(_PLC_SAFETY_ACK)
        _log(f"X4 (Safety ACK): {'OK (High)' if x4_ack else 'NO ACK! (Low)'}")
        _after(0, lambda a=x4_ack: _set_x4_indicator(a))

        def _probe(ch: int) -> tuple:
            """Drive one contact channel, read X2, then put the coil back.

            Returns (contact, cleared): whether X2 was High with the coil up,
            and whether it fell again once the coil was dropped. The second
            half is what makes the *next* probe's reading its own -- X2 is one
            signal shared by every channel, so a probe that starts while the
            last channel's contact is still up reads that contact, not its own.
            """
            idx = ch - 1
            plc.set_channel(ch, True)
            _after(0, lambda i=idx: _set_io(io_contact_labels, i, True))
            # The channel expected to make contact answers in milliseconds;
            # the one probed to prove it does not still costs the same 0.5s
            # this slept unconditionally.
            x2 = _wait_x2_high(f"CH{ch} -> ON")
            ack = plc.read_channel_ack(ch)
            _after(0, lambda i=idx, a=ack: _set_io(io_in_labels, i, a))
            _after(0, lambda a=x2: _set_x2_indicator(a))
            if not plc.set_channel(ch, False):
                _log(f"CH{ch}: coil OFF write was refused by the PLC.")
            _after(0, lambda i=idx: _set_io(io_contact_labels, i, False))
            return x2, _wait_x2_low(f"CH{ch} -> OFF")

        # 2) The part's own last channel must make contact.
        _after(0, lambda c=last: _spec_focus(c))
        seated, cleared = _probe(last)
        if not seated:
            _log(f"CH{last} contact: NG — X2 (Contact OK) is Low. Cable not seated.")
            plc.close()
            return "NOT_SEATED"
        _log(f"CH{last} contact: OK — X2 is High (cable in jig)")
        if not cleared:
            # Probing CH last+1 on an X2 that never came down would only read
            # CH last's contact again and call a good part a wrong cable. The
            # fixture is what is wrong, so say that instead of blaming the cable.
            _log(f"CH{last} contact: X2 never returned Low — CH{last + 1} cannot be judged.")
            plc.close()
            return "STUCK"

        # 3) One past the part's channels must NOT. An answer there means a
        #    conductor exists where this part has none.
        if nxt is None:
            _log(f"CH{last + 1} probe skipped — the fixture has only {MAX_CH} channels")
        else:
            extra, _ = _probe(nxt)
            if extra:
                _log(f"CH{nxt} contact: NG — X2 is High, but this part has only {last} channels. Wrong cable or wrong jig.")
                plc.close()
                return "EXTRA"
            _log(f"CH{nxt} contact: OK — X2 is Low, as expected for a {last}-channel part")

        # 4) Turn off safety relay M28 and ensure no X4 feedback is received
        _log("M28 (Safety Relay) -> OFF (Preparing for HV Mode)")
        moved = plc.is_hv_mode is not True
        plc.safety_relay_to_hv()
        _after(0, lambda: _set_safety_indicator(False))
        if moved: time.sleep(_RELAY_SETTLE_S)
        x4_off = plc.read_input(_PLC_SAFETY_ACK)
        _log(f"X4 (Safety ACK): {'Still ON! (WARNING)' if x4_off else 'OFF (Low - OK)'}")
        _after(0, lambda a=x4_off: _set_x4_indicator(a))

        plc.close()
        return "OK"

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



    def _refuse_unspecified(test: str, ch: int, missing: list, upto: int,
                            into: dict, row: str, spec: dict = None,
                            one_channel: bool = False):
        """Say which fields are blank, and mark the channels not tested.

        No voltage has been applied at the point this is called and none will
        be. The channels are recorded NOSPEC rather than FAIL: a part is not
        faulty because nobody filled in its spec, and calling it a failure
        would hide the thing that actually needs doing.
        """
        _log(f"{test}: CH{ch} cannot be tested --")
        for f in missing:
            _log(f"    {_spec_field_detail(spec, f)}")
        _log(f"{test}: REFUSING to test. Correct it in Model Settings for every "
             f"channel, then reload the part.")
        first = ch if one_channel else 1
        for c in range(first, upto + 1):
            into[c] = {"appvol": None, "value": None, "result": _NO_LIMIT_RESULT}
            _after(0, lambda i=c-1: _set_cell(row, i, _NO_SPEC_TEXT, False))

    def _log_reading(label: str, rd, lo, hi, unit: str):
        """Say what was measured, who judged it, and what it was judged against.

        The console used to log the number alone. The instrument was
        failing channels this log called a pass and there was nothing in it
        to show the two had ever disagreed, so the line now carries both
        verdicts and the window each was applied to.

        The instrument's reply is logged verbatim under it. Everything above
        is this console's reading of that one line -- which field it took the
        number from, which word it read as a verdict -- and when any of that
        looks wrong, the reply is the only thing that settles it. It used to
        go to stdout alone, which the windowed build discards, so answering
        the question meant rebuilding with --console first.
        """
        if rd.raw:
            _log(f"{label}: MEAS? -> {rd.raw}")
        if rd.value is None:
            _log(f"{label}: NO READING from HiPot -- comms fault, not a measurement")
            return
        shown = _meas_text(rd.value, ".3f" if unit == "mA" else ".0f")
        window = "NO LIMITS SET for this part" if lo is None or hi is None else f"{lo:g}..{hi:g} {unit}"
        said = rd.verdict if rd.verdict else "no verdict in its reply"
        _log(f"{label}: {shown} {unit} | instrument says {said} | spec {window}")
        if not rd.limits_set:
            _log(f"{label}: WARNING -- instrument is NOT judging against this part's limits")

    def _run_ir_test(n_ch: int) -> tuple:
        _log("IR Test → MANU:EDIT:MODE IR | FUNC:TEST ON | MEAS?")
        if not _serial_ok or not hipot.open():
            _log("CRITICAL: HiPot not connected or port blocked!")
            set_com_status("HiPot", False)
            return False, {ch: {"result": "FAIL"} for ch in range(1, n_ch + 1)}
        if not _plc_open():
            _log("CRITICAL: PLC Modbus port blocked or disconnected!")
            return False, {ch: {"result": "FAIL"} for ch in range(1, n_ch + 1)}
            
        set_com_status("HiPot", True)
        # plc.is_open, not _plc_open(): the guard above already opened the
        # port, and there is nothing here that could have closed it since.
        if plc.is_open:
            _log("M28 (Safety Relay) -> OFF (HV Mode)")
            moved = plc.is_hv_mode is not True
            plc.safety_relay_to_hv()
            _after(0, lambda: _set_safety_indicator(False))
            if moved: time.sleep(_RELAY_SETTLE_S)
            x4_ack = plc.read_input(_PLC_SAFETY_ACK)
            _log(f"X4 (Safety ACK): {'OK' if x4_ack else 'NO ACK!'}")
            _after(0, lambda a=x4_ack: _set_x4_indicator(a))
            
        all_pass = True; ir_res = {}
        if state.get("testmode", "Combined").strip().lower() == "combined":
            _log("IR Test: Testing all channels (Combined)...")
            if plc.is_open:
                plc.set_all_channels(n_ch, True)
                for i in range(n_ch): _after(0, lambda idx=i: _set_io(io_ir_acw_labels, idx, True))
                # Bounded at the 0.5s this used to sleep flat, so a rack of
                # relays that is up returns at once and one that is not costs
                # no more than before. The per-channel reads below still decide
                # the verdict; this only stops them being taken too early.
                plc.confirm_channels_on(n_ch)
                # X20-X27 are one unbroken run, so every channel's
                # acknowledgement arrives in a single read. Asking per channel
                # read all eight inputs eight times to pick one bit out of each.
                acks = plc.read_all_acks(n_ch)
                for ch in range(1, n_ch + 1):
                    ack = acks.get(ch, False)
                    _after(0, lambda c=ch-1, a=ack: _set_io(io_in_labels, c, a))
                    if not ack:
                        _log(f"IR (Combined): Channel {ch} ACK failed!")
                        all_pass = False
            s0 = state["spec_ir"].get(1, {})
            # Combined mode drives the instrument from CH1, so CH1 is the row
            # that has to be complete before any voltage is applied at all.
            missing = _spec_missing(s0)
            if missing:
                _refuse_unspecified("IR", 1, missing, n_ch, ir_res, "IR", s0)
                all_pass = False
                if plc.is_open:
                    plc.set_all_channels(n_ch, False)
                    for i in range(n_ch): _after(0, lambda idx=i: (_set_io(io_ir_acw_labels, idx, False), _set_io(io_in_labels, idx, False)))
                hipot.close()
                if plc.is_open: plc.close()
                _after(0, lambda: _set_row_result("IR", False))
                return False, ir_res
            v_kv = float(s0["appvol"]) / 1000.0; t_s = float(s0["testtime"]); v_min = s0["min"]; v_max = s0["max"]
            _log(f"IR: commanding {s0['appvol']:.0f} V ({v_kv:.4f} kV) for {t_s:.1f}s")
            rd = hipot.run_ir_test(v_kv, t_s, v_min, v_max)
            ir_val = rd.value
            _log_reading("IR (Combined)", rd, v_min, v_max, "MOhm")
            for ch in range(1, n_ch + 1):
                s = state["spec_ir"].get(ch, {}); passed = _channel_passed(rd, s.get("min"), s.get("max"))
                if not passed: all_pass = False
                ir_res[ch] = {"appvol": s0["appvol"], "value": ir_val, "result": _chan_result(rd, s, passed)}
                _after(0, lambda c=ch-1, v=_meas_text(ir_val, ".0f"), p=passed: _set_cell("IR", c, v, p))
            if plc.is_open:
                plc.set_all_channels(n_ch, False)
                for i in range(n_ch): _after(0, lambda idx=i: (_set_io(io_ir_acw_labels, idx, False), _set_io(io_in_labels, idx, False)))
            _log(f"IR (Combined): {_meas_text(ir_val, '.0f')} MΩ — {'PASS' if all_pass else 'FAIL'}")
        else:
            for ch in range(1, n_ch + 1):
                _log(f"IR Test: Testing CH{ch}...")
                _after(0, lambda c=ch: _spec_focus(c))
                ack_ok = True
                if plc.is_open:
                    _log(f"CH{ch} -> ON")
                    plc.set_channel(ch, True)
                    _after(0, lambda idx=ch-1: _set_io(io_ir_acw_labels, idx, True))
                    # Capped at the 0.5s this replaced, so a relay that comes
                    # up answers immediately and one that does not fails no
                    # later than it did. Worth the most here: Individual mode
                    # pays this settle once per channel, twice per cycle.
                    ack_ok = plc.confirm_channel_on(ch)
                    _after(0, lambda idx=ch-1, a=ack_ok: _set_io(io_in_labels, idx, a))
                    if not ack_ok:
                        _log(f"IR (Individual): Channel {ch} ACK failed!")
                        all_pass = False
                s = state["spec_ir"].get(ch, {})
                missing = _spec_missing(s)
                if missing:
                    _refuse_unspecified("IR", ch, missing, ch, ir_res, "IR", s, one_channel=True)
                    all_pass = False
                    if plc.is_open:
                        plc.set_channel(ch, False)
                        _after(0, lambda idx=ch-1: (_set_io(io_ir_acw_labels, idx, False), _set_io(io_in_labels, idx, False)))
                    continue
                v_kv = float(s["appvol"]) / 1000.0; t_s = float(s["testtime"]); v_min = s["min"]; v_max = s["max"]
                _log(f"IR CH{ch}: commanding {s['appvol']:.0f} V ({v_kv:.4f} kV) for {t_s:.1f}s")
                rd = hipot.run_ir_test(v_kv, t_s, v_min, v_max)
                ir_val = rd.value
                _log_reading(f"IR CH{ch}", rd, v_min, v_max, "MOhm")
                passed = _channel_passed(rd, v_min, v_max)
                if not passed or not ack_ok: all_pass = False
                ir_res[ch] = {"appvol": s["appvol"], "value": ir_val, "result": _chan_result(rd, s, passed and ack_ok)}
                _after(0, lambda c=ch-1, v=_meas_text(ir_val, ".0f"), p=(passed and ack_ok): _set_cell("IR", c, v, p))
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
            
        # See _run_ir_test: the port is already open, and asking for it again
        # here says nothing the guard above has not already settled.
        if plc.is_open:
            _log("M28 (Safety Relay) -> OFF (HV Mode)")
            moved = plc.is_hv_mode is not True
            plc.safety_relay_to_hv()
            _after(0, lambda: _set_safety_indicator(False))
            if moved: time.sleep(_RELAY_SETTLE_S)
            x4_ack = plc.read_input(_PLC_SAFETY_ACK)
            _log(f"X4 (Safety ACK): {'OK' if x4_ack else 'NO ACK!'}")
            _after(0, lambda a=x4_ack: _set_x4_indicator(a))
            
        all_pass = True; acw_res = {}
        if state.get("testmode", "Combined").strip().lower() == "combined":
            _log("ACW Test: Testing all channels (Combined)...")
            if plc.is_open:
                plc.set_all_channels(n_ch, True)
                for i in range(n_ch): _after(0, lambda idx=i: _set_io(io_ir_acw_labels, idx, True))
                # Bounded at the 0.5s this used to sleep flat, so a rack of
                # relays that is up returns at once and one that is not costs
                # no more than before. The per-channel reads below still decide
                # the verdict; this only stops them being taken too early.
                plc.confirm_channels_on(n_ch)
                # X20-X27 are one unbroken run, so every channel's
                # acknowledgement arrives in a single read. Asking per channel
                # read all eight inputs eight times to pick one bit out of each.
                acks = plc.read_all_acks(n_ch)
                for ch in range(1, n_ch + 1):
                    ack = acks.get(ch, False)
                    _after(0, lambda c=ch-1, a=ack: _set_io(io_in_labels, c, a))
                    if not ack:
                        _log(f"ACW (Combined): Channel {ch} ACK failed!")
                        all_pass = False
            s0 = state["spec_acw"].get(1, {})
            # See _run_ir_test: CH1 drives the instrument in combined mode.
            missing = _spec_missing(s0)
            if missing:
                _refuse_unspecified("ACW", 1, missing, n_ch, acw_res, "ACW", s0)
                all_pass = False
                if plc.is_open:
                    plc.set_all_channels(n_ch, False)
                    for i in range(n_ch): _after(0, lambda idx=i: (_set_io(io_ir_acw_labels, idx, False), _set_io(io_in_labels, idx, False)))
                hipot.close()
                if plc.is_open: plc.close()
                _after(0, lambda: _set_row_result("ACW", False))
                return False, acw_res
            v_kv = float(s0["appvol"]) / 1000.0; t_s = float(s0["testtime"]); v_min = s0["min"]; v_max = s0["max"]
            _log(f"ACW: commanding {s0['appvol']:.0f} V ({v_kv:.4f} kV) for {t_s:.1f}s")
            rd = hipot.run_acw_test(v_kv, t_s, v_min, v_max)
            acw_val = rd.value
            _log_reading("ACW (Combined)", rd, v_min, v_max, "mA")
            for ch in range(1, n_ch + 1):
                s = state["spec_acw"].get(ch, {}); passed = _channel_passed(rd, s.get("min"), s.get("max"))
                if not passed: all_pass = False
                acw_res[ch] = {"appvol": s0["appvol"], "value": acw_val, "result": _chan_result(rd, s, passed)}
                _after(0, lambda c=ch-1, v=_meas_text(acw_val, ".3f"), p=passed: _set_cell("ACW", c, v, p))
            if plc.is_open:
                plc.set_all_channels(n_ch, False)
                for i in range(n_ch): _after(0, lambda idx=i: (_set_io(io_ir_acw_labels, idx, False), _set_io(io_in_labels, idx, False)))
            _log(f"ACW (Combined): {_meas_text(acw_val, '.3f')} mA — {'PASS' if all_pass else 'FAIL'}")
        else:
            for ch in range(1, n_ch + 1):
                _log(f"ACW Test: Testing CH{ch}...")
                _after(0, lambda c=ch: _spec_focus(c))
                ack_ok = True
                if plc.is_open:
                    _log(f"CH{ch} -> ON")
                    plc.set_channel(ch, True)
                    _after(0, lambda idx=ch-1: _set_io(io_ir_acw_labels, idx, True))
                    # Capped at the 0.5s this replaced, so a relay that comes
                    # up answers immediately and one that does not fails no
                    # later than it did. Worth the most here: Individual mode
                    # pays this settle once per channel, twice per cycle.
                    ack_ok = plc.confirm_channel_on(ch)
                    _after(0, lambda idx=ch-1, a=ack_ok: _set_io(io_in_labels, idx, a))
                    if not ack_ok:
                        _log(f"ACW (Individual): Channel {ch} ACK failed!")
                        all_pass = False
                s = state["spec_acw"].get(ch, {})
                missing = _spec_missing(s)
                if missing:
                    _refuse_unspecified("ACW", ch, missing, ch, acw_res, "ACW", s, one_channel=True)
                    all_pass = False
                    if plc.is_open:
                        plc.set_channel(ch, False)
                        _after(0, lambda idx=ch-1: (_set_io(io_ir_acw_labels, idx, False), _set_io(io_in_labels, idx, False)))
                    continue
                v_kv = float(s["appvol"]) / 1000.0; t_s = float(s["testtime"]); v_min = s["min"]; v_max = s["max"]
                _log(f"ACW CH{ch}: commanding {s['appvol']:.0f} V ({v_kv:.4f} kV) for {t_s:.1f}s")
                rd = hipot.run_acw_test(v_kv, t_s, v_min, v_max)
                acw_val = rd.value
                _log_reading(f"ACW CH{ch}", rd, v_min, v_max, "mA")
                passed = _channel_passed(rd, v_min, v_max)
                if not passed or not ack_ok: all_pass = False
                acw_res[ch] = {"appvol": s["appvol"], "value": acw_val, "result": _chan_result(rd, s, passed and ack_ok)}
                _after(0, lambda c=ch-1, v=_meas_text(acw_val, ".3f"), p=(passed and ack_ok): _set_cell("ACW", c, v, p))
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
            moved = plc.is_hv_mode is not False
            plc.safety_relay_to_contact()
            if moved: time.sleep(_RELAY_SETTLE_S)
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
        state["test_running"] = True; state["start_time"] = datetime.datetime.now(); state["flag"] = True; state["last_vision_result"] = None; state["cam_results"] = {1: None, 2: None}
        _after(0, lambda: btn_start.config(state="disabled", bg="#555", text="TESTING...")); _after(0, _reset_test_display); _after(0, lambda: _set_verdict("TESTING", "#0033aa", "white")); _after(0, lambda: scan_lbl.config(text="⏳  Test in progress...", bg="#001830", fg="#e8a000")); _after(0, _lock_scan_entry)
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
        vision_failed = []   # every enabled camera that did not come back OK
        if vision_ctrl:
            vision_ctrl.reload_config()

            if not vision_ctrl.config.get("vision_enabled", True):
                # Off in Vision Settings means the cycle skips vision, not that
                # every part fails it. inspect() reports a disabled engine as
                # ERROR, and that ERROR used to land in vision_failed and NG the
                # part before the electrical tests even ran -- so the switch
                # read as "fail everything" instead of "skip".
                _log("Vision disabled in settings — skipping vision verification.")
            elif not vision_ctrl.has_model(state["pno"]):
                _log(f"Vision WARNING: No vision model configured for part '{state['pno']}'. Skipping vision.")
            else:
                _after(0, lambda: scan_lbl.config(text="👁  Vision Verification...", bg="#001830", fg="#e8a000"))
                # Each enabled camera is inspected in turn against the part's
                # one taught model, so the record can say which camera saw the
                # part. The configured camera_source stays the "primary": it
                # is the result that drives the saved pass image, exactly as
                # before, so nothing downstream changes shape.
                primary = 2 if vision_ctrl.config.get("camera_source", "cam1") == "cam2" else 1
                cams = _load_cam_cfg()
                for cid in (1, 2):
                    if not cams.get(f"cam{cid}_enabled"):
                        state["cam_results"][cid] = None
                        continue
                    frame = camera.grab(cams[f"cam{cid}_index"],
                                        cams[f"cam{cid}_width"], cams[f"cam{cid}_height"])
                    if frame is None:
                        state["cam_results"][cid] = "ERROR"
                        _log(f"Vision CAM{cid} ERROR: no frame from the camera")
                        vision_failed.append(cid)
                        continue
                    r = vision_ctrl.inspect(state["pno"], frame=frame)
                    state["cam_results"][cid] = r.judgement
                    _after(0, lambda res=r, c=cid: _show_vision_frame(res, c))
                    if cid == primary:
                        state["vision_result"] = r.judgement
                        state["last_vision_result"] = r
                    if r.judgement == "ERROR":
                        _log(f"Vision CAM{cid} ERROR: {r.error}")
                        vision_failed.append(cid)
                    elif not r.ok:
                        _log(f"Vision CAM{cid} NG: score={r.match_score:.4f}")
                        vision_failed.append(cid)
                    else:
                        _log(f"Vision CAM{cid} OK: score={r.match_score:.4f} in {r.processing_time_ms}ms")
        else:
            _log("Vision skipped (not initialized/disabled). Proceeding with electrical tests.")
        # --- END VISION VERIFICATION ---

        # Vision is part of the verdict, not just a line in the log and a
        # column in the record: a part the cameras did not pass used to ship
        # as a PASS so long as the electrical tests passed. The cycle ends
        # here -- there is nothing to learn from putting 1kV through a part
        # vision says is not the part.
        if vision_failed:
            failed_cams = ", ".join(f"CAM{cid}" for cid in vision_failed)
            _log(f"Vision failed on {failed_cams} — NG, electrical tests skipped")
            state["flag"] = False
            _finish_test("FAIL", {}, {}, {}, fail_banner=f"❌  NG — vision failed on {failed_cams}")
            return

        _after(0, lambda: scan_lbl.config(text=f"Checking contact (CH{min(n_ch, MAX_CH)}"
                                               + (f" / CH{min(n_ch, MAX_CH) + 1})..." if min(n_ch, MAX_CH) < MAX_CH else ")..."),
                                          bg="#001830", fg="#e8a000"))
        if _modbus_ok:
            verdict = _run_contact_boundary_check(n_ch)
            if verdict != "OK":
                # Each failure gets its own wording: "not seated" and "wrong
                # cable/jig" need different things done to the fixture, and
                # one generic message had the operator re-seating a cable
                # that was never the right one.
                if verdict == "EXTRA":
                    title, popup = "Wrong Cable / JIG", (f"Contact found on CH{min(n_ch, MAX_CH) + 1}, but this part has only "
                                                         f"{min(n_ch, MAX_CH)} channels.\n\n"
                                                         "Wrong cable or wrong JIG — please check.")
                    banner = "❌  Extra channel detected — wrong cable or JIG"
                elif verdict == "NOT_SEATED":
                    title, popup = "Contact", (f"No contact on CH{min(n_ch, MAX_CH)}.\n\n"
                                               "The cable is not fully seated. Please check the jig.")
                    banner = "❌  Contact NOT OK — check and retry"
                elif verdict == "STUCK":
                    title, popup = "Contact Signal Stuck", (f"X2 (Contact OK) stayed High after "
                                                            f"CH{min(n_ch, MAX_CH)} was switched off.\n\n"
                                                            "A channel relay is not dropping out, or the jig is still "
                                                            "holding continuity. Check the fixture — this is not a "
                                                            "fault with the cable.")
                    banner = "❌  X2 stuck High — check the JIG, not the cable"
                else:
                    title, popup = "PLC", "PLC Modbus port blocked or disconnected."
                    banner = "❌  PLC not reachable — check the connection"
                _log(f"Contact boundary check failed ({verdict}) — aborting")
                _after(0, lambda t=title, m=popup: messagebox.showwarning(t, m)); _after(0, lambda: _set_verdict("READY", "#1a1a1a", "#555")); _after(0, lambda b=banner: scan_lbl.config(text=b, bg="#220000", fg="#ff5555"))
                _clear_all_io_indicators()
                state["test_running"] = False; _after(0, lambda: btn_start.config(state="normal", bg="#1b5e20", fg="white", text="▶  START TEST")); _after(0, _input_poll_start); return
        _after(0, lambda: scan_lbl.config(text="⚡  IR Testing (Insulation Resistance)...", bg="#001830", fg="#e8a000")); ir_pass, ir_ch = _run_ir_test(n_ch)
        if not ir_pass: state["flag"] = False; _finish_test("FAIL", ir_ch, {}, {}); return
        _after(0, lambda: scan_lbl.config(text="⚡  ACW Testing (Withstand Voltage)…", bg="#001830", fg="#e8a000")); acw_pass, acw_ch = _run_acw_test(n_ch)
        if not acw_pass: state["flag"] = False; _finish_test("FAIL", ir_ch, acw_ch, {}); return
        _after(0, lambda: scan_lbl.config(text="🔗  Contact Testing…", bg="#001830", fg="#e8a000")); contact_pass, contact_ch = _run_contact_test(n_ch)
        overall = "PASS" if (ir_pass and acw_pass and contact_pass) else "FAIL"
        state["flag"] = (overall == "PASS"); _finish_test(overall, ir_ch, acw_ch, contact_ch)

    def _finish_test(overall: str, ir_ch: dict, acw_ch: dict, contact_ch: dict, fail_banner: str = None):
        _clear_all_io_indicators()
        if _plc_open():
            _log("Resetting all PLC pins (Contact + IR/ACW + Safety Relay)...")
            plc.reset_all_channels()
            plc.safety_relay_to_hv() # Resets M28 to False (default state)
            plc.close()
        _after(0, lambda: _set_safety_indicator(False))  # match the physical reset above
            
        pno = state["pno"]; lot_no = _generate_lot_number(pno, cfg["machine_id"]); state["lot_no"] = lot_no; state["labelstr"] = lot_no
        elapsed = (datetime.datetime.now() - state["start_time"]).total_seconds() if state["start_time"] else None
        elapsed_str = f"{elapsed:.1f}" if elapsed is not None else "—"
        # Cycle time == this test's duration (START to verdict), which is what
        # the sidebar strip and the Count box's CT both show.
        if elapsed is not None:
            state["ct_last"] = elapsed
        state["total"] += 1; state["ok" if overall == "PASS" else "ng"] += 1
        _after(0, _update_counts)
        # Queued, not called here: this runs on the test thread and the
        # announcement is a modal dialog.
        if overall == "PASS": _after(0, _count_pass_into_lot)
        _after(0, lambda l=lot_no: lot_lbl.config(text=l)); _after(0, lambda e=elapsed_str: elapsed_lbl.config(text=e)); _after(0, lambda c=_lot_3_letters(): _fill_ro(ent_lot, c))
        vision_img_path = _save_vision_pass_image(lot_no)
        _save_result(lot_no, overall, ir_ch, acw_ch, contact_ch, vision_img_path)
        if overall == "PASS":
            _after(0, lambda: _set_verdict("PASS", "#1b5e20", "white")); _after(0, lambda: scan_lbl.config(text="✅  PASS — Scan the printed barcode label", bg="#0a2200", fg="#76ff03")); _play_wav("OK.WAV"); blink_stop()
            threading.Thread(target=_print_barcode_label,
                             args=(pno, state["alc"], state["model"], state["vendor_code"],
                                   state["eo_number"], lot_no, cfg["machine_id"],
                                   state.get("is_rework", False)),
                             kwargs={"num_channels": state["num_channels"],
                                     "ir_ch": ir_ch, "acw_ch": acw_ch},
                             daemon=True).start()
            if cfg.get("scan_enabled", True):
                state["awaiting_scan"] = True
                # Focus immediately, not after a delay: printers eject a label
                # fast enough that a delay left the entry still readonly when
                # the operator's actual scan arrived, dropping it silently and
                # leaving the box showing the previous part's result -- which
                # reads exactly like results lagging one part behind.
                _after(0, _show_scan_entry)
            else:
                _after(0, lambda: _set_scan_box(""))
                _after(500, _input_poll_start)
                _after(3000, _reset_for_next_part)
        else:
            _after(0, lambda: _set_verdict("FAIL", "#b71c1c", "white")); _after(0, lambda b=fail_banner or "❌  FAIL — Check cable and retry": scan_lbl.config(text=b, bg="#220000", fg="#ff5555")); _play_wav("NG.WAV"); blink_start()
        _after(0, lambda p=pno: _load_today_pass(p)); _log(f"── Test Complete: {overall} | Lot: {lot_no} | Time: {elapsed_str}s ──")
        state["test_running"] = False; _after(0, lambda: btn_start.config(state="normal", bg="#1b5e20" if overall == "PASS" else "#b71c1c", fg="white", text="▶  START TEST"))
        # Queued after the restore above, so the gate has the last word.
        if state.get("awaiting_scan"): _after(0, lambda: _set_awaiting_scan(True))
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
        dup_lot, cur_done = _duplicate_check(scanned)
        if dup_lot:
            _log(f"Scan verify: duplicate label — lot {dup_lot} was already scanned")
            _set_scan_box("DUP", scanned)
            if not cur_done:
                # An older label was presented for a lot that has no verdict
                # yet, so record what happened. Skipped when this lot has
                # already been scanned -- there the row holds a real verdict
                # and a duplicate must not overwrite it.
                _update_scan_result(state["lot_no"], "DUP")
                _after(0, lambda p=state["pno"]: _load_today_pass(p))
            _set_awaiting_scan(False)
            _after(3000, _reset_for_next_part); _after(3100, _input_poll_start)
            return
        if _scan_lot_ok(scanned, labelstr): res_str = "OK"; _log(f"Scan verify: OK ({_fmt_scan(scanned)})")
        else: res_str = "NG"; _log(f"Scan verify: NG (expected '{labelstr}', got '{_fmt_scan(scanned)}')")
        _set_scan_box(res_str, scanned)
        _update_scan_result(state["lot_no"], res_str)
        # Today's PASS Records was drawn when the test finished, before this
        # scan existed, so its SCAN column still reads "—" for this lot.
        # Refresh it now the row is stamped rather than leaving it stale until
        # the next test completes. _update_scan_result has already committed --
        # _after(0, ...) runs after this callback returns -- so the reload sees
        # the new verdict.
        _after(0, lambda p=state["pno"]: _load_today_pass(p))
        _set_awaiting_scan(False)
        _after(3000, _reset_for_next_part); _after(3100, _input_poll_start)
    ent_scan.bind("<Return>", _on_scan_enter)

    # Gap between poll ticks. A tick is two transactions on an already-open
    # port -- roughly 80ms of wire time -- so this is what sets how far behind
    # a pin the panel runs, and 150ms reads as live to the eye.
    _IO_POLL_MS = 150

    def _input_poll_once():
        if not state.get("input_polling"): return
        if state["test_running"] or not state["pno"]: _after(500, _input_poll_once); return
        def _poll():
            pressed = _update_io_display()
            if pressed: _log("START button pressed (PLC X0)"); _after(0, _trigger_test)
            else: _after(_IO_POLL_MS, _input_poll_once)
        threading.Thread(target=_poll, daemon=True).start()
    def _input_poll_start():
        if not _modbus_ok or state.get("input_polling"): return
        state["input_polling"] = True; _input_poll_once()
    def _input_poll_stop():
        """Stop reading the inputs, blank the two button cells and hand the
        port back.

        X0/X1 are momentary: the poll tick that sees START pressed is the one
        that stops itself to run the test, so leaving the cell as-read would
        show the button held down for the whole cycle.

        Closing here is what releases the port, since the loop now holds it
        open between ticks -- the test sequence and the other pages open it
        for themselves straight after this returns.
        """
        state["input_polling"] = False
        _after(0, lambda: (_set_x0_indicator(False), _set_x1_indicator(False)))
        try: plc.close()
        except Exception: pass

    def _poll_plc_open() -> bool:
        """Open the port for the polling loop and leave it open between ticks.

        Every tick used to be bracketed by a USB-serial open and close. That is
        the same reopen-shortly-after-close pattern this adapter was already
        known to drop transactions on, and it cost more time than the reads it
        wrapped. Holding the handle removes both problems; _input_poll_stop
        gives the port up whenever anything else needs it.
        """
        # A tick already in flight can reach here just after _input_poll_stop
        # closed the port for the test sequence. Without this guard it would
        # reopen the handle underneath the test about to claim it.
        if not _modbus_ok or not state.get("input_polling"): return False
        if plc.is_open: return True
        ok = plc.open()
        # Logged on change only. At this poll rate an unplugged PLC would
        # otherwise write several identical lines a second into the log.
        if state.get("poll_port_ok") != ok:
            state["poll_port_ok"] = ok
            _after(0, lambda o=ok: set_com_status("IO Ctrl", o))
            if not ok: _after(0, lambda: _log("PLC: could not open Modbus port"))
        return ok
    def _update_io_display() -> bool:
        """Refresh every I/O indicator from the PLC and report whether the
        physical START button (X0) is pressed.

        Two transactions, inputs first, on a port the loop keeps open.

        X0-X27 are one unbroken run of discrete inputs and M20-M37 one
        unbroken run of coils, so a single FC02 of 24 bits carries the START
        button, X1-X4 and all eight channel acks, and a single FC01 of 18 bits
        carries the HV relays, the safety relay and the contact relays. That
        replaces five transactions wrapped in an open/close: at 9600 baud with
        ASCII framing each transaction is ~35ms on the wire and the port
        open/close cost as much again, so X2 -- read last of the five -- was
        already a quarter-second stale before the poll gap was added to it.

        The X indicators are painted before the coil read rather than after it,
        so the pins an operator actually watches are as fresh as the link
        allows.
        """
        if not _poll_plc_open(): return False
        pressed = False
        try:
            x = plc.read_inputs_bulk(_PLC_X_BASE, _PLC_X_COUNT, strict=True)
            if x is None:
                # The PLC would not serve the wide read. Fall back to the two
                # narrow ones for this tick rather than blanking the panel --
                # X10-X17 are not wired to anything, so the gap is padding.
                x = (list(plc.read_inputs_bulk(_PLC_X_BASE, 8)) + [False] * 8 +
                     list(plc.read_inputs_bulk(_PLC_ACK_BASE, 8)))
            pressed = x[0]
            x1, x2, x3, x4 = x[1], x[2], x[3], x[4]
            acks = x[16:24]

            def _paint_inputs(p=pressed, a1=x1, a2=x2, a3=x3, a4=x4, ak=acks):
                _set_x0_indicator(p); _set_x1_indicator(a1); _set_x2_indicator(a2)
                _set_rework_active(a3); _set_x4_indicator(a4)
                for i, bit in enumerate(ak): _set_io(io_in_labels, i, bit)
            _after(0, _paint_inputs)

            # A test or a page change can land between the two reads. The coils
            # only mirror what this program just commanded, so give the port up
            # now rather than holding it for a picture nobody is waiting on.
            if not state.get("input_polling"): return pressed

            m = plc.read_coils_bulk(_PLC_M_BASE, _PLC_M_COUNT, strict=True)
            if m is None:
                m = (list(plc.read_coils_bulk(_PLC_M_BASE, 8)) + [False] * 2 +
                     list(plc.read_coils_bulk(_PLC_CONTACT_COILS[1], 8)))

            def _paint_coils(bits=m):
                _set_safety_indicator(bits[8])                     # M28
                for i in range(8):
                    _set_io(io_ir_acw_labels, i, bits[i])          # M20-M27
                    _set_io(io_contact_labels, i, bits[10 + i])    # M30-M37
            _after(0, _paint_coils)
        except Exception: pass
        return pressed

    def _db_state() -> tuple:
        """(reachable, newest date this machine has already tested on).

        One query answers both station-level questions, so START probes the
        database and reads its own clock history in a single round trip.

        MAX(STR_TO_DATE(...)) rather than MAX(date) because the column is a
        VARCHAR: a row written in some other date format would otherwise sort
        above every real one and read as a date from the future. STR_TO_DATE
        gives NULL for anything that does not match and MAX skips the NULLs,
        so unrecognised rows are ignored instead of trusted.

        The history is scoped to this machine. Another station's clock being
        wrong is that station's problem, and letting it stop this line would
        turn one bad PC into an idle shop floor. Reachability is not scoped to
        anything -- the database is either there or it is not.
        """
        try:
            with db.get_cursor() as cur:
                # The format goes in as a parameter, not inline: the driver
                # does not unescape %% here, so an inline format string
                # reaches MySQL literally, matches no date at all, and
                # quietly turns the clock check into a no-op.
                cur.execute("SELECT MAX(STR_TO_DATE(date, %s)) "
                            "FROM testmaster WHERE machine = %s",
                            ("%Y-%m-%d", cfg["machine_id"]))
                row = cur.fetchone()
        except Exception as ex:
            _log(f"Database unreachable: {ex}")
            return False, None
        newest = row[0] if row else None
        if isinstance(newest, datetime.datetime): newest = newest.date()
        return True, newest

    def _station_checks_ok() -> bool:
        """The two gates that are the station's problem, not the operator's.

        Both refuse the run rather than warn, because in both cases the part
        would have to be tested again afterwards: a run with no database is
        never recorded, and a run under a clock that has gone back is recorded
        under a lot number that is already on somebody else's label.
        """
        reachable, newest = _db_state()
        if not reachable:
            _log("TEST REFUSED: database unreachable -- the result could not be saved.")
            _after(0, lambda: messagebox.showerror(
                "Database Unreachable",
                "This test is blocked because the database cannot be reached.\n\n"
                "A part tested now would not be recorded at all, and its label "
                "would carry a duplicate lot number, so it would have to be "
                "tested again once the database is back.\n\n"
                "Check the database server and the network connection, then "
                "start the test again."))
            return False
        today = datetime.date.today()
        if newest is not None and today < newest:
            # Every lot number starts with the system date and continues from
            # the highest already issued that day, so a clock that has gone
            # backwards re-issues numbers that are already on printed labels.
            # Testing again on the same date is ordinary production; only an
            # earlier date is refused.
            _log(f"TEST REFUSED: system date {today:%d/%m/%Y} is before the last test "
                 f"on this machine ({newest:%d/%m/%Y}) -- check the PC date.")
            _after(0, lambda t=today, n=newest: messagebox.showerror(
                "Check the Date",
                f"The system date is {t:%d/%m/%Y}, but this machine has already "
                f"tested parts on {n:%d/%m/%Y}.\n\n"
                "Testing is blocked because the lot number is built from the "
                "date: running now would issue lot numbers that are already on "
                "printed labels.\n\n"
                "Correct the date and time on this PC, then start the test again."))
            return False
        return True

    def _trigger_test():
        if state["test_running"]: return
        if state.get("awaiting_scan"):
            _log("Scan the printed label before testing the next part.")
            messagebox.showwarning("Scan Required", "Scan the printed barcode label for the last part before starting the next test.")
            _show_scan_entry()   # focus lands on the entry as the dialog closes
            return
        if not state["pno"]: _log("No part number loaded."); return
        if not ent_emp.get().strip(): _after(0, lambda: messagebox.showwarning("Validation", "Enter Employee ID before testing.")); return
        if _lot_qty() <= 0:
            # Without it the lot announcement never fires, so the operator has
            # no cue to close off a box -- which is only noticed at the end of
            # a lot, too late. Ask for it up front instead.
            _after(0, lambda: messagebox.showwarning("Validation", "Enter the Lot Qty (how many good parts make one lot) before testing."))
            _after(0, lambda: (ent_lot_qty.focus_set(), ent_lot_qty.select_range(0, "end")))
            return
        # Last gate before the run: the others are fields the operator can
        # fix on the spot, these are the station's database and clock.
        if not _station_checks_ok(): return
        _input_poll_stop(); _reset_test_display(); threading.Thread(target=_run_test_sequence, daemon=True).start()
    btn_start.config(command=lambda: _trigger_test())
    # ENTER here moves to START, it does not press it. A test begins only on a
    # deliberate act -- clicking START, or the physical button pulling X0 high
    # -- so that typing the last digit of a quantity can never set the machine
    # running on a part the operator has not finished loading.
    # The "In Box" target follows the box as it is typed: an operator who
    # mistypes 100 for 10 should see it next to the count, not discover it a
    # box later.
    ent_lot_qty.bind("<KeyRelease>", lambda e: _update_counts())
    ent_lot_qty.bind("<Return>", lambda e: btn_start.focus_set())

    def _print_marker(marker: str, pno: str):
        """Send a START/END marker label off the UI thread -- printing blocks
        for as long as the spooler takes, and this runs while the operator is
        mid-flow loading or releasing a part."""
        _log(f"{marker} label -> {pno}")
        threading.Thread(target=_print_marker_label,
                         args=(pno, marker, cfg["machine_id"]), daemon=True).start()

    def _close_out_run() -> bool:
        """END for the part still loaded when the program closes. Prints on
        this thread -- see close_out_run() -- and clears the part so a second
        call can't put a duplicate END on the roll.

        Returns False to call the shutdown off, which is what a part-filled
        box gets here: closing the program abandons it exactly as a part
        change does, and the operator is as able to press the window X by
        mistake as they are Next Part. Asked before the END prints, since
        that is the point the run is closed off.

        The dialog works here only because main.py asks on WM_DELETE_WINDOW,
        with the root still alive and its mainloop still running -- a nested
        event loop has something to nest in. There is no equivalent on a kill
        or a power cut, and a box open at one of those is simply lost.
        """
        if not state["pno"]: return True
        if not _confirm_short_box("Closing now leaves this box without a lot label.",
                                  "Close anyway"):
            return False
        _log(f"END label -> {state['pno']} (program closing)")
        _print_marker_label(state["pno"], "END", cfg["machine_id"])
        state["pno"] = None
        return True
    _ACTIVE["close_out"] = _close_out_run

    def _clear_part_fields():
        """Reset everything that belongs to one part -- the part/JIG entries,
        the master data loaded from them, the specs and the per-cycle test
        display -- leaving the employee login and the day's records alone."""
        ent_pno.config(state="normal"); ent_pno.delete(0, "end"); ent_pno.config(state="readonly", bg="#0d0d0d")
        ent_jig.config(state="normal"); ent_jig.delete(0, "end"); ent_jig.config(state="readonly", bg="#0d0d0d")
        for e in [ent_pname, ent_cust, ent_model, ent_alc, ent_vendor, ent_eo, ent_lot, ent_testtype]: e.config(state="normal"); e.delete(0, "end"); e.config(state="readonly")
        tree_spec.delete(*tree_spec.get_children()); _reset_test_display()
        spec_status_lbl.config(text="[ No part loaded ]", fg="#444"); _lock_scan_entry(); _set_awaiting_scan(False); _set_scan_box("")
        # The lot quantity goes with the part, not with the station. Leaving
        # the last one in the box let the next part inherit a box size nobody
        # chose for it, and the part after that inherit it again -- so it is
        # emptied here and asked for again on the next load.
        ent_lot_qty.delete(0, "end")
        state.update({"pno": None, "num_channels": 0, "spec_ir": {}, "spec_acw": {}, "lot_no": "", "labelstr": "", "flag": True, "last_vision_result": None,
                      "ct_last": None, "batch_ok": 0, "batch_shown": None})
        _update_counts()
        btn_start.config(bg="#1a1a1a", fg="#444")

    def _confirm_short_box(detail: str, go_text: str) -> bool:
        """Ask before a box that is not full is abandoned. True to go ahead.

        Asked on a part change and again on program close -- the two ways a
        part-filled box is left behind. `detail` says which, and `go_text` is
        what the go-ahead button reads.

        Nothing already recorded is at stake -- every part counted into the
        box has its testmaster row and its own barcode label, and still counts
        in the day's totals. What is lost is the box: its count, and the lot
        label it never gets. That is worth a deliberate press rather than the
        silent discard a stray Next Part used to be.

        Silent when there is nothing to be short of: no lot quantity typed, or
        no part counted into the box yet.
        """
        qty = _lot_qty()
        done = state["batch_ok"]
        if qty <= 0 or done <= 0 or done >= qty: return True

        top = parent.winfo_toplevel()
        dlg = tk.Toplevel(top)
        dlg.withdraw()
        dlg.title("Box Not Full")
        dlg.configure(bg="#111")
        dlg.resizable(False, False)
        dlg.transient(top)

        # Amber, where the lot dialog is green: the same box, stopped early.
        tk.Frame(dlg, bg="#e8a000", height=6).pack(fill="x")
        body = tk.Frame(dlg, bg="#111", padx=44, pady=26)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="⚠", bg="#111", fg="#e8a000",
                 font=("Arial", _fs(40))).pack()
        tk.Label(body, text="Box not full", bg="#111", fg="white",
                 font=("Arial", _fs(20), "bold")).pack(pady=(8, 0))
        tk.Label(body, text=f"Batch {state['batch_no']} — part {state['pno'] or '?'}\n"
                            f"{done} of {qty} tested.",
                 bg="#111", fg="#ccc", font=("Arial", _fs(12)),
                 justify="center").pack(pady=(10, 0))
        tk.Label(body, text=detail,
                 bg="#111", fg="#888", font=("Arial", _fs(9))).pack(pady=(10, 0))

        # Guarded like the lot dialog's: every way out lands here, and
        # destroying an already destroyed window raises.
        answer = {"go": False, "done": False}

        def _finish(go):
            if answer["done"]: return
            answer["done"] = True
            answer["go"] = go
            try: dlg.grab_release()
            except Exception: pass
            dlg.destroy()

        btns = tk.Frame(body, bg="#111")
        btns.pack(pady=(22, 0))
        btn_cancel = tk.Button(btns, text="Cancel", bg="#1a1a1a", fg="#ccc",
                               font=("Arial", _fs(13), "bold"), bd=0, padx=30, pady=9,
                               cursor="hand2", activebackground="#2a2a2a",
                               activeforeground="white", command=lambda: _finish(False))
        btn_cancel.pack(side="left", padx=6)
        tk.Button(btns, text=go_text, bg="#b71c1c", fg="white",
                  font=("Arial", _fs(13), "bold"), bd=0, padx=30, pady=9,
                  cursor="hand2", activebackground="#d32f2f",
                  activeforeground="white", command=lambda: _finish(True)).pack(side="left", padx=6)

        # Escape and the window X mean Cancel, and so does ENTER: keeping the
        # box open is the recoverable answer, and this dialog appears when the
        # operator may have pressed Next Part, or the window X, by mistake.
        # <space> is left to
        # Tk's own button binding so a focused button is not fired twice.
        dlg.protocol("WM_DELETE_WINDOW", lambda: _finish(False))
        dlg.bind("<Escape>", lambda e: _finish(False))
        for key in ("<Return>", "<KP_Enter>"):
            dlg.bind(key, lambda e: _finish(False))

        # Measured twice, as the lot dialog is: Windows places the frame at
        # the requested point while these sizes are of the client area inside.
        dlg.update_idletasks()
        w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()

        def _place(fw, fh):
            x = top.winfo_rootx() + (top.winfo_width() - fw) // 2
            y = top.winfo_rooty() + (top.winfo_height() - fh) // 3
            x = max(0, min(x, dlg.winfo_screenwidth() - fw))
            y = max(0, min(y, dlg.winfo_screenheight() - fh))
            dlg.geometry(f"{w}x{h}+{x}+{y}")
            return x, y
        x, y = _place(w, h)
        dlg.deiconify()
        dlg.update_idletasks()
        bx = max(0, dlg.winfo_rootx() - x)
        by = max(0, dlg.winfo_rooty() - y)
        _place(w + 2 * bx, h + by + bx)

        btn_cancel.focus_set()
        try: dlg.grab_set()
        except Exception: pass
        # Blocks, unlike the lot dialog: the caller is mid part change and
        # needs the answer before it releases anything.
        top.wait_window(dlg)
        return answer["go"]

    def _next_part():
        """Switch to a different part without ending the operator's session.

        Only the part is released: the employee stays validated, so the
        operator just types the new part number and rescans its JIG. The
        records panel widens back to the whole day until the new part loads,
        at which point it narrows to that part.
        """
        if state["test_running"]:
            _log("Test in progress — finish it before changing part."); return
        # Asked first, while everything is still recoverable: the END marker
        # below and _clear_part_fields are both one way.
        if not _confirm_short_box("Changing part closes this box without a lot label.",
                                  "Change part"):
            _log("Part change cancelled — the box is still open."); return
        # Read before _clear_part_fields() zeroes them, so the log can say what
        # was in the box that just went unlabelled.
        short_of = (state["batch_ok"], _lot_qty(), state["batch_no"])
        # Has to happen before _clear_part_fields() wipes state["pno"]. The
        # guard also covers _on_jig_enter's failure path, which calls this with
        # no part ever loaded -- there is nothing to close out there.
        if state["pno"]: _print_marker("END", state["pno"])
        _input_poll_stop()
        _clear_part_fields()
        done, qty, batch = short_of
        if qty > 0 and 0 < done < qty:
            _log(f"Batch {batch} closed short — {done} of {qty}, no lot label.")
        emp = ent_emp.get().strip()
        if not emp:
            ent_emp.config(state="normal", bg="black"); ent_emp.focus_set()
            _log("Enter Employee ID first."); return
        ent_pno.config(state="normal", bg="black"); ent_pno.focus_set()
        _load_today_pass()
        _log("Ready for the next part — enter the new Part Number.")

    btn_next_part.config(command=_next_part)

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

    def _show_vision_frame(result, cam_id=None):
        """Paint the frame vision judged, with the detected match boxed on it,
        into that camera's preview panel — so the operator sees *what* the
        matcher found, not just a score. Reverts to the live feed a few
        seconds later.
        """
        if not (_cv2_ok and _pil_ok) or result.frame is None or not vision_ctrl:
            return
        if cam_id is None:
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

    def _announce_part_loaded(pno: str):
        """Say the part is loaded, and warn if no vision model is taught for it.

        This used to inspect the part here as well, a full ~1.5s capture and
        match at JIG-scan time. Vision belongs to the cycle: it now runs once,
        after START, where its verdict counts. Checking a part the operator has
        not started testing yet only told them something the cycle would say
        again a moment later, off a frame taken before the part was settled.
        """
        base = f"Part '{pno}' loaded ({state['num_channels']} ch)"

        def _paint(suffix, fg, bg="#001830"):
            scan_lbl.config(text=f"{base} — {suffix}", bg=bg, fg=fg)

        if not vision_ctrl:
            _paint("Ready", "#4caf50"); return

        vision_ctrl.reload_config()
        if not vision_ctrl.config.get("vision_enabled", True):
            # Nothing to warn about while vision is switched off -- the cycle
            # will not run it, taught model or not.
            _paint("Ready", "#4caf50"); return
        if not vision_ctrl.has_model(pno):
            _log(f"Vision WARNING: No vision model configured for part '{pno}'.")
            _paint("NO VISION MODEL", "#e8a000"); return

        _paint("Ready", "#4caf50")

    def _on_jig_enter(event=None):
        # A validated JIG entry is readonly, but readonly is not unfocusable --
        # ENTER pressed in it again would reload the part underneath the
        # operator, putting a second START on the marker roll and, worse now,
        # restarting the batch halfway through the box they are packing.
        if state["pno"]: return
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
            _load_today_pass(pno); btn_start.config(bg="#1b5e20", fg="white")
            # A loaded part is a new box to fill, even one that ran earlier in
            # the shift -- the operator packed and closed that one before they
            # switched away.
            _start_batch(f"part {pno}")
            _print_marker("START", pno)
            _announce_part_loaded(pno)
            # Focus goes to Lot Qty rather than START: releasing the last part
            # emptied it, so it is the only field the operator still has to
            # fill, and _trigger_test refuses to run without it -- which is
            # what asks for a box size once per part rather than once a shift.
            # ENTER moves on to START without pressing it: starting the test
            # stays a separate, deliberate act.
            ent_lot_qty.focus_set()
            _after(500, _input_poll_start)
        else:
            # An unknown part number is a typo, not the end of the shift --
            # release just the part and ask for it again, rather than logging
            # the operator out and wiping the day's records off the panel.
            btn_start.config(bg="#1a1a1a", fg="#444"); _next_part()
    ent_jig.bind("<Return>", _on_jig_enter)

    _load_today_pass(); _log("System ready. Enter Employee ID and press ENTER.")
    set_com_status("HiPot", False); set_com_status("IO Ctrl", False); set_com_status("Scanner", False); set_com_status("Printer", False)
    _device_status_start()
    ent_emp.focus_set()
