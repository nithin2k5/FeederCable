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

    def section(title, rows):
        """One bordered block of caption/value rows.

        All three blocks on this page are the same shape, so they are built
        the same way -- the address is the only value long enough to need
        wrapping, and it wraps rather than pushing the page wide.
        """
        frame = tk.LabelFrame(content, text=f"  {title}  ", bg="black", fg="#e8a000",
                              font=("Arial", 11, "bold"), bd=1, relief="solid",
                              highlightbackground="#333", highlightthickness=1,
                              padx=16, pady=12)
        frame.pack(fill="x", pady=(0, 12))
        for label, value in rows:
            row = tk.Frame(frame, bg="black")
            row.pack(fill="x", pady=4)
            tk.Label(row, text=f"{label}:", bg="black", fg="#999",
                     font=("Arial", 10, "bold"), width=12, anchor="w").pack(side="left")
            tk.Label(row, text=value, bg="black", fg="white", font=("Arial", 10),
                     anchor="w", justify="left", wraplength=900).pack(side="left", padx=8)
        return frame

    # The website row is gone: the address that was there belonged to a
    # different company name and has no replacement.
    section("Support", [
        ("Name",        "Venkaiah Alla"),
        ("Company",     "Nice Computer Education & Software Solutions"),
        ("Address",     "8-30-32/2, Revenue ward No.8, Vaikuntapuram, Kavali, "
                        "Sri Potti Sriramulu Nellore, Andhra Pradesh, 525201"),
        ("Phone",       "+91 93467 40314"),
        ("Email",       "niceavr@gmail.com"),
    ])

    section("Developer", [
        ("Name",        "\u2014"),
        ("Email",       "koppisettinithin.dev@gmail.com"),
        ("Phone",       "+91 93982 25082"),
    ])

    section("Application", [
        ("Application", "Feeder Cable EOL Tester"),
        ("Version",     "2.0 (Python)"),
        ("Platform",    "Windows / Tkinter"),
    ])
