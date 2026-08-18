"""
help_page.py
============
Help page for the Feeder Cable EOL Tester application.
Shows quick reference for the testing workflow, keyboard shortcuts,
and a link to the setup video.
"""
import tkinter as tk
from tkinter import ttk
import webbrowser


_SETUP_VIDEO_URL = "https://www.youtube.com/watch?v=BUtAW9CwS4M"


def render(parent):
    """Render the Help page."""
    content = tk.Frame(parent, bg="black")
    content.pack(fill="both", expand=True, padx=20, pady=10)

    # --- Quick Reference ---
    tk.Label(content, text="Quick Reference", bg="black", fg="white",
             font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 8))

    sections = [
        ("Testing Workflow", [
            "1.  Enter Part Number in the Part No field",
            "2.  Enter Employee ID in the EMP ID field",
            "3.  Press ENTER or click START TEST",
            "4.  System loads specs from database and validates employee",
            "5.  Connect cable to the jig — system checks connection",
            "6.  IR Test (Insulation Resistance) runs automatically",
            "7.  ACW Test (AC Withstand Voltage) runs automatically",
            "8.  Contact Test (Continuity) runs automatically",
            "9.  PASS → label prints, scan the barcode to verify",
            "10. FAIL → check cable and retry",
        ]),
        ("COM Port Devices", [
            "HiPot Tester  —  SCPI commands over RS-232 (IR & ACW tests)",
            "IO Controller —  Advantech ADAM module (contact test & jig I/O)",
            "Scanner       —  External barcode scanner for label verification",
            "Printer       —  Thermal label printer (raw PRN templates)",
        ]),
        ("Camera Feeds", [
            "Configure cameras via the Camera Settings page in the sidebar",
            "Camera feeds appear on the right panel of the Test Console",
            "Click a camera frame to navigate to Camera Settings",
        ]),
    ]

    for title, items in sections:
        lf = tk.LabelFrame(content, text=f"  {title}  ", bg="black", fg="#e8a000",
                           font=("Arial", 11, "bold"), bd=1, relief="solid",
                           highlightbackground="#333", highlightthickness=1,
                           padx=12, pady=8)
        lf.pack(fill="x", pady=(0, 10))

        for item in items:
            tk.Label(lf, text=item, bg="black", fg="#ccc", font=("Consolas", 9),
                     anchor="w").pack(fill="x", pady=1)

    # --- Setup Video Link ---
    link_frame = tk.Frame(content, bg="black")
    link_frame.pack(fill="x", pady=(10, 0))

    tk.Label(link_frame, text="Setup Video:", bg="black", fg="#999",
             font=("Arial", 10)).pack(side="left")

    link_lbl = tk.Label(link_frame, text=_SETUP_VIDEO_URL, bg="black", fg="#4fc3f7",
                        font=("Arial", 10, "underline"), cursor="hand2")
    link_lbl.pack(side="left", padx=6)
    link_lbl.bind("<Button-1>", lambda e: webbrowser.open(_SETUP_VIDEO_URL))
