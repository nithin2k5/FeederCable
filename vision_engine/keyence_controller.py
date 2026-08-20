import socket
import time
import json
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class VisionResult:
    ok: bool
    judgement: str
    program: str
    part_number: str
    processing_time_ms: int
    image_available: bool
    error: Optional[str] = None

class KeyenceVisionController:
    """
    Controller for KEYENCE IV2/IV3 series Vision Sensors.
    Uses official non-procedural TCP/IP commands.
    """
    def __init__(self, config_path="keyence_config.json"):
        self.config_path = config_path
        self.ip_address = "192.168.0.10"
        self.port = 8500
        self.timeout_ms = 2000
        self.program_mapping = {}
        self.sock = None
        self.connected = False
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    cfg = json.load(f)
                    self.ip_address = cfg.get("ip_address", self.ip_address)
                    self.port = cfg.get("port", self.port)
                    self.timeout_ms = cfg.get("timeout_ms", self.timeout_ms)
                    self.program_mapping = cfg.get("program_mapping", self.program_mapping)
            except Exception as e:
                print(f"Error loading keyence config: {e}")

    def save_config(self):
        cfg = {
            "device_type": "KEYENCE_IV4",
            "ip_address": self.ip_address,
            "port": self.port,
            "communication_mode": "TCP/IP Non-Procedural",
            "timeout_ms": self.timeout_ms,
            "program_mapping": self.program_mapping
        }
        with open(self.config_path, "w") as f:
            json.dump(cfg, f, indent=4)

    def connect(self) -> bool:
        if self.connected:
            return True
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout_ms / 1000.0)
            self.sock.connect((self.ip_address, self.port))
            self.connected = True
            return True
        except Exception:
            self.connected = False
            self.sock = None
            return False

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.connected = False
        self.sock = None

    def _send_command(self, cmd: str) -> str:
        if not self.connected or not self.sock:
            raise ConnectionError("Not connected to Keyence device")
        
        # Keyence commands are typically terminated with CR (\r)
        self.sock.sendall((cmd + "\r").encode('ascii'))
        
        response = b""
        while True:
            chunk = self.sock.recv(1024)
            if not chunk:
                break
            response += chunk
            if b"\r" in chunk:
                break
        
        return response.decode('ascii').strip()

    def select_program(self, part_number: str) -> bool:
        """Switch to the appropriate KEYENCE program (PW command)"""
        if part_number not in self.program_mapping:
            return False # Program mapping missing
            
        prog_str = self.program_mapping[part_number]
        # Command: PW,<program_no> (e.g. PW,001)
        try:
            prog_num = int(prog_str)
            cmd = f"PW,{prog_num:03d}"
            resp = self._send_command(cmd)
            # Typically returns PW,OK
            return "OK" in resp
        except Exception:
            return False

    def trigger_inspection(self, part_number: str, program_str: str) -> VisionResult:
        """Trigger inspection using T3 command and parse result"""
        start_time = time.time()
        try:
            # T3 triggers and returns the overall judgement and tool results
            resp = self._send_command("T3")
            processing_time = int((time.time() - start_time) * 1000)
            
            # Response format depends on exact config, but generally starts with T3,OK or T3,NG
            parts = resp.split(",")
            if len(parts) >= 2 and parts[1] == "OK":
                return VisionResult(
                    ok=True,
                    judgement="OK",
                    program=program_str,
                    part_number=part_number,
                    processing_time_ms=processing_time,
                    image_available=False,
                    error=None
                )
            else:
                return VisionResult(
                    ok=False,
                    judgement="NG",
                    program=program_str,
                    part_number=part_number,
                    processing_time_ms=processing_time,
                    image_available=False,
                    error="Part failed visual inspection"
                )
        except Exception as e:
            return VisionResult(
                ok=False,
                judgement="ERROR",
                program=program_str,
                part_number=part_number,
                processing_time_ms=int((time.time() - start_time) * 1000),
                image_available=False,
                error=f"Communication error: {str(e)}"
            )

    def get_status(self) -> str:
        """Get device status"""
        if not self.connected:
            return "OFFLINE"
        try:
            # Simple check, read current program
            resp = self._send_command("PR")
            if resp:
                return "CONNECTED"
            return "OFFLINE"
        except:
            self.disconnect()
            return "ERROR"
