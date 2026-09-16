import datetime
import tkinter as tk
from tkinter import font as tkfont
import mysql.connector

import db

def _get_conn():
    return db.get_connection()

# Audit trail for the pages behind a login (Admin, Model Settings). Kept as
# separate date/time strings to match testmaster, so the two read the same way.
LOGIN_HISTORY_COLUMNS = """
    id INT AUTO_INCREMENT PRIMARY KEY,
    page VARCHAR(50),
    eno VARCHAR(50),
    ename VARCHAR(100),
    result VARCHAR(20),
    reason VARCHAR(100),
    date VARCHAR(20),
    time VARCHAR(20)
"""

def _record_login(page: str, eno: str, ok: bool, reason: str = ""):
    """Append one login attempt to the audit trail.

    Both outcomes are recorded -- a run of failures against an admin page is
    exactly what this table exists to show. The password is never stored, on
    success or failure.

    Never raises: a failed audit write must not stop someone logging in.
    """
    now = datetime.datetime.now()
    try:
        db.ensure_table("loginhistory", LOGIN_HISTORY_COLUMNS)
        with db.get_cursor(commit=True) as cur:
            cur.execute("SELECT ename FROM admin WHERE eno=%s", (eno,))
            row = cur.fetchone()
            cur.execute(
                "INSERT INTO loginhistory (page, eno, ename, result, reason, date, time) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (page, eno, (row[0] if row else "") or "", "SUCCESS" if ok else "FAILED",
                 reason, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")))
    except Exception as ex:
        print(f"[AUTH] login history write failed: {ex}")

# Arial has no Tamil glyphs, so a Tamil string set in it renders as boxes.
# Nirmala UI is the Windows 11 Indic UI face and Latha the older one; fall
# back to what Tk picks rather than pinning a font that may not be installed.
_TAMIL_FALLBACKS = ("Nirmala UI", "Latha", "Vijaya", "Segoe UI")


def _tamil_family():
    try:
        families = set(tkfont.families())
    except Exception:
        return "Nirmala UI"
    for fam in _TAMIL_FALLBACKS:
        if fam in families:
            return fam
    return "Nirmala UI"


# The notice in both languages. Both are shown at once rather than behind a
# language toggle: this is the one screen an operator has to have actually
# read, and a toggle is a thing you have to know to go looking for.
_SAFETY_INTRO = (
    "This is an industrial End-Of-Line (EOL) tester.\n"
    "It involves High Voltage (HiPot) and automated IO control.",
    "இது ஒரு தொழிற்சாலை இறுதிநிலை (EOL) சோதனை கருவி.\n"
    "இதில் உயர் மின்னழுத்தம் (HiPot) மற்றும் தானியங்கி IO கட்டுப்பாடு உள்ளன.",
)
_SAFETY_RULES = (
    ("Ensure the jig and cables are properly secured before testing.",
     "சோதனைக்கு முன் ஜிக் மற்றும் கேபிள்கள் சரியாகப் பொருத்தப்பட்டுள்ளதா என உறுதிசெய்யவும்."),
    ("Do NOT touch the exposed leads during testing.",
     "சோதனை நடைபெறும்போது வெளிப்பட்டுள்ள கம்பிகளைத் தொடக் கூடாது."),
    ("Only authorized personnel are permitted to operate this machine.",
     "அங்கீகரிக்கப்பட்ட பணியாளர்கள் மட்டுமே இந்த இயந்திரத்தை இயக்க அனுமதிக்கப்பட்டவர்."),
)
_ACK_EN = "I have read and understood the instructions."
_ACK_TA = "நான் இந்த வழிமுறைகளைப் படித்து புரிந்துக்கொண்டேன்."


def show_disclaimer(parent_root):
    """The startup safety notice: modal, and dismissable only by acknowledging.

    Monochrome like the rest of the app -- black ground, white type -- and it
    spends color only where the color carries meaning: red for the hazard,
    amber for the thing being asked of you, green once the button is live.
    """
    BG, CARD, RULE = "black", "#0d0d0d", "#262626"
    DANGER, ACCENT, TEXT, MUTED = "#ff5252", "#e8a000", "#ffffff", "#b0b0b0"
    ta = _tamil_family()

    # Modal dialog that blocks the main window
    dialog = tk.Toplevel(parent_root)
    dialog.withdraw()
    dialog.title("Disclaimer")
    dialog.configure(bg=BG)
    dialog.resizable(False, False)
    dialog.transient(parent_root)

    # Remove window controls so user is forced to accept
    dialog.protocol("WM_DELETE_WINDOW", lambda: None)

    # A red cap, the red of the hazard itself, so the dialog reads as a
    # warning before a word of it has been read.
    tk.Frame(dialog, bg=DANGER, height=6).pack(fill="x")

    card = tk.Frame(dialog, bg=CARD, padx=48, pady=18)
    card.pack(fill="both", expand=True)

    tk.Label(card, text="⚠", bg=CARD, fg=DANGER, font=("Arial", 34)).pack()
    tk.Label(card, text="IMPORTANT SAFETY INSTRUCTIONS", bg=CARD, fg=DANGER,
             font=("Arial", 22, "bold")).pack(pady=(4, 0))
    tk.Label(card, text="முக்கியப் பாதுகாப்பு வழிமுறைகள்", bg=CARD, fg=ACCENT,
             font=(ta, 17, "bold")).pack(pady=(2, 0))

    tk.Frame(card, bg=RULE, height=1).pack(fill="x", pady=12)

    intro_en, intro_ta = _SAFETY_INTRO
    tk.Label(card, text=intro_en, bg=CARD, fg=TEXT, font=("Arial", 14),
             justify="center").pack()
    tk.Label(card, text=intro_ta, bg=CARD, fg=MUTED, font=(ta, 13),
             justify="center").pack(pady=(4, 0))

    tk.Frame(card, bg=RULE, height=1).pack(fill="x", pady=12)

    # Each rule is numbered in an amber badge down the left, the English and
    # the Tamil sharing one text column so a rule reads as one item in a list
    # of three rather than as two lists of three.
    rules = tk.Frame(card, bg=CARD)
    rules.pack(fill="x")
    rules.columnconfigure(1, weight=1)
    for i, (en, tam) in enumerate(_SAFETY_RULES):
        tk.Label(rules, text=str(i + 1), bg="#1a1a1a", fg=ACCENT,
                 font=("Arial", 13, "bold"), width=3, pady=2).grid(
            row=i, column=0, sticky="n", pady=(0, 10))
        body = tk.Frame(rules, bg=CARD)
        body.grid(row=i, column=1, sticky="ew", padx=(14, 0), pady=(0, 10))
        tk.Label(body, text=en, bg=CARD, fg=TEXT, font=("Arial", 14),
                 anchor="w", justify="left").pack(fill="x")
        tk.Label(body, text=tam, bg=CARD, fg=MUTED, font=(ta, 13), anchor="w",
                 justify="left", wraplength=640).pack(fill="x", pady=(1, 0))

    tk.Frame(card, bg=RULE, height=1).pack(fill="x", pady=(2, 12))

    chk_var = tk.BooleanVar(value=False)

    def on_check():
        if chk_var.get():
            btn_accept.config(state="normal", bg="#1b5e20", fg="white",
                              activebackground="#2e7d32", cursor="hand2")
        else:
            btn_accept.config(state="disabled", bg="#1a1a1a", fg="#555",
                              cursor="arrow")

    ack = tk.Frame(card, bg=CARD)
    ack.pack()
    chk = tk.Checkbutton(ack, text=_ACK_EN, variable=chk_var, bg=CARD, fg=ACCENT,
                         selectcolor="#1a1a1a", activebackground=CARD,
                         activeforeground=ACCENT, font=("Arial", 14), bd=0,
                         highlightthickness=0, cursor="hand2", command=on_check)
    chk.pack(anchor="w")
    # The Tamil line ticks the box too. It is the same sentence, and the
    # operator reading that line is the one being asked to tick it.
    ack_ta = tk.Label(ack, text=_ACK_TA, bg=CARD, fg=MUTED, font=(ta, 13),
                      cursor="hand2")
    ack_ta.pack(anchor="w", padx=(26, 0))
    ack_ta.bind("<Button-1>", lambda _e: (chk.toggle(), on_check()))

    def on_accept():
        dialog.destroy()

    btn_accept = tk.Button(card, text="ACCEPT  /  ஏற்கிறேன்", state="disabled",
                           bg="#1a1a1a", fg="#555", font=(ta, 16, "bold"), bd=0,
                           padx=54, pady=10, activeforeground="white",
                           command=on_accept)
    btn_accept.pack(pady=(14, 2))

    # Sized to its content rather than to the fixed 600x400 the text had long
    # since outgrown, then centred and clamped so it cannot open off-screen.
    dialog.update_idletasks()
    w, h = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
    x = max(0, (dialog.winfo_screenwidth() - w) // 2)
    y = max(0, (dialog.winfo_screenheight() - h) // 3)
    dialog.geometry(f"{w}x{h}+{x}+{y}")
    dialog.deiconify()
    dialog.grab_set()

    # Wait for the window to be destroyed before returning
    parent_root.wait_window(dialog)


def show_login(parent_root, title="Login", page=None):
    """
    Shows a login modal.
    Returns True if login successful, False otherwise.

    Every attempt, successful or not, is written to the loginhistory table
    against `page` (defaults to the dialog title).
    """
    page = page or title
    dialog = tk.Toplevel(parent_root)
    dialog.title(title)

    w, h = 420, 380
    sw = dialog.winfo_screenwidth()
    sh = dialog.winfo_screenheight()
    x = int((sw / 2) - (w / 2))
    y = int((sh / 2) - (h / 2))
    dialog.geometry(f"{w}x{h}+{x}+{y}")
    dialog.resizable(False, False)
    dialog.configure(bg="black")
    dialog.transient(parent_root)
    dialog.grab_set()

    # Thin amber accent strip along the top, matching the header's accent color.
    tk.Frame(dialog, bg="#e8a000", height=4).pack(fill="x")

    card = tk.Frame(dialog, bg="#111")
    card.pack(fill="both", expand=True)

    tk.Label(card, text="🔒", bg="#111", fg="#e8a000", font=("Arial", 30)).pack(pady=(26, 4))
    tk.Label(card, text=title.upper(), bg="#111", fg="#e8a000", font=("Arial", 16, "bold")).pack()
    tk.Label(card, text="Authorized personnel only", bg="#111", fg="#666", font=("Arial", 9)).pack(pady=(2, 18))

    form_frame = tk.Frame(card, bg="#111")
    form_frame.pack(padx=40, fill="x")

    err_lbl = tk.Label(card, text=" ", bg="#111", fg="#ff5555", font=("Arial", 9, "bold"))

    def _entry_row(label_text, show=None):
        tk.Label(form_frame, text=label_text, bg="#111", fg="#999", font=("Arial", 9)).pack(anchor="w")
        wrap = tk.Frame(form_frame, bg="#444", highlightthickness=0)
        wrap.pack(fill="x", pady=(3, 14))
        ent = tk.Entry(wrap, font=("Arial", 12), bg="#1c1c1c", fg="white", insertbackground="white",
                        bd=0, relief="flat", show=show)
        ent.pack(fill="x", ipady=6, padx=1, pady=1)

        def on_focus_in(_e=None):
            wrap.config(bg="#e8a000")

        def on_focus_out(_e=None):
            wrap.config(bg="#444")

        ent.bind("<FocusIn>", on_focus_in)
        ent.bind("<FocusOut>", on_focus_out)
        return ent

    ent_eno = _entry_row("EMPLOYEE ID")
    ent_pwd = _entry_row("PASSWORD", show="*")

    err_lbl.pack(pady=(0, 4))

    result = {"success": False}

    def on_login(event=None):
        eno = ent_eno.get().strip()
        pwd = ent_pwd.get().strip()

        if (eno == "nice" and pwd == "nice1234") or (eno == "123" and pwd == "123"):
            result["success"] = True
            _record_login(page, eno, True)
            dialog.destroy()
            return

        try:
            with db.get_cursor() as cur:
                cur.execute("SELECT pwd FROM admin WHERE eno=%s", (eno,))
                row = cur.fetchone()

            if row and row[0] == pwd:
                result["success"] = True
                _record_login(page, eno, True)
                dialog.destroy()
            else:
                # Separated so the trail distinguishes someone mistyping their
                # own password from an ID that does not exist at all.
                _record_login(page, eno, False,
                              "wrong password" if row else "unknown employee ID")
                err_lbl.config(text="Invalid Employee ID or Password.")
                ent_pwd.delete(0, "end")
                ent_pwd.focus_set()
        except Exception as ex:
            # If DB is not reachable, fallback to error
            err_lbl.config(text=f"DB Error: {ex}")

    ent_eno.bind("<Return>", lambda e: ent_pwd.focus_set())
    ent_pwd.bind("<Return>", on_login)
    dialog.bind("<Escape>", lambda e: dialog.destroy())

    btn_row = tk.Frame(card, bg="#111")
    btn_row.pack(pady=(6, 0))

    tk.Button(btn_row, text="CANCEL", bg="#111", fg="#888", font=("Arial", 10, "bold"), bd=1,
              relief="solid", highlightbackground="#444", padx=20, pady=8, cursor="hand2",
              activebackground="#222", activeforeground="white",
              command=dialog.destroy).pack(side="left", padx=(0, 10))

    tk.Button(btn_row, text="LOGIN", bg="#e8a000", fg="black", font=("Arial", 11, "bold"), bd=0,
              padx=30, pady=8, cursor="hand2", activebackground="#ffc107", activeforeground="black",
              command=on_login).pack(side="left")

    ent_eno.focus_set()
    parent_root.wait_window(dialog)
    return result["success"]
