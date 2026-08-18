"""
contact_page.py
===============
Contact information page for the Feeder Cable EOL Tester application.
"""
import tkinter as tk


def render(parent):
    """Render the Contact page."""
    content = tk.Frame(parent, bg="black")
    content.pack(fill="both", expand=True, padx=20, pady=20)

    tk.Label(content, text="Contact Information", bg="black", fg="white",
             font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 16))

    contacts = [
        ("Company",    "Nice Automation Pvt. Ltd."),
        ("Address",    "Bangalore, Karnataka, India"),
        ("Phone",      "+91-XXXX-XXXXXX"),
        ("Email",      "support@niceautomation.com"),
        ("Website",    "www.niceautomation.com"),
    ]

    info_frame = tk.LabelFrame(content, text="  Support  ", bg="black", fg="#e8a000",
                               font=("Arial", 11, "bold"), bd=1, relief="solid",
                               highlightbackground="#333", highlightthickness=1,
                               padx=16, pady=12)
    info_frame.pack(fill="x", pady=(0, 12))

    for i, (label, value) in enumerate(contacts):
        row = tk.Frame(info_frame, bg="black")
        row.pack(fill="x", pady=4)
        tk.Label(row, text=f"{label}:", bg="black", fg="#999", font=("Arial", 10, "bold"),
                 width=12, anchor="w").pack(side="left")
        tk.Label(row, text=value, bg="black", fg="white", font=("Arial", 10),
                 anchor="w").pack(side="left", padx=8)

    # Developer info
    dev_frame = tk.LabelFrame(content, text="  Developer  ", bg="black", fg="#e8a000",
                              font=("Arial", 11, "bold"), bd=1, relief="solid",
                              highlightbackground="#333", highlightthickness=1,
                              padx=16, pady=12)
    dev_frame.pack(fill="x", pady=(0, 12))

    dev_contacts = [
        ("Name",       "—"),
        ("Email",      "—"),
        ("Phone",      "—"),
    ]

    for label, value in dev_contacts:
        row = tk.Frame(dev_frame, bg="black")
        row.pack(fill="x", pady=4)
        tk.Label(row, text=f"{label}:", bg="black", fg="#999", font=("Arial", 10, "bold"),
                 width=12, anchor="w").pack(side="left")
        tk.Label(row, text=value, bg="black", fg="white", font=("Arial", 10),
                 anchor="w").pack(side="left", padx=8)

    # App info
    app_frame = tk.LabelFrame(content, text="  Application  ", bg="black", fg="#e8a000",
                              font=("Arial", 11, "bold"), bd=1, relief="solid",
                              highlightbackground="#333", highlightthickness=1,
                              padx=16, pady=12)
    app_frame.pack(fill="x")

    app_info = [
        ("Application", "Feeder Cable EOL Tester"),
        ("Version",     "2.0 (Python)"),
        ("Platform",    "Windows / Tkinter"),
    ]

    for label, value in app_info:
        row = tk.Frame(app_frame, bg="black")
        row.pack(fill="x", pady=4)
        tk.Label(row, text=f"{label}:", bg="black", fg="#999", font=("Arial", 10, "bold"),
                 width=12, anchor="w").pack(side="left")
        tk.Label(row, text=value, bg="black", fg="white", font=("Arial", 10),
                 anchor="w").pack(side="left", padx=8)
