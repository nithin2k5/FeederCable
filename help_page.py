"""
help_page.py
============
Operator manual for the Feeder Cable EOL Tester.

Laid out as a manual rather than a single sheet of notes: a contents list
on the left, a scrolling chapter on the right, and a search box that
filters the contents. Each chapter is data -- a list of typed blocks --
so adding to the manual means adding entries to CHAPTERS, not writing
more widget code.
"""
import tkinter as tk
from tkinter import ttk

# ── Palette, shared with the rest of the application ─────────────────────────
BG, PANEL, HEADER = "#000000", "#0d0d0d", "#161616"
LINE, TXT, DIM, ACCENT = "#2b2b2b", "#e8e8e8", "#8a8a8a", "#e8a000"
GREEN, BLUE, RED = "#76ff03", "#4fc3f7", "#ff5555"


# ── The manual itself ────────────────────────────────────────────────────────
# Block types the renderer understands:
#   ("h",     text)                 section heading inside a chapter
#   ("p",     text)                 paragraph
#   ("steps", [text, ...])          numbered procedure
#   ("bul",   [text, ...])          bullet list
#   ("kv",    [(term, text), ...])  definition list
#   ("tbl",   [headers], [rows])    table
#   ("note",  text)                 informational callout
#   ("warn",  text)                 warning callout

CHAPTERS = [
("About This Machine", [
    ("p", "The Feeder Cable EOL (end-of-line) tester checks a finished feeder "
          "cable before it leaves the line. One cable is clamped into a jig, and "
          "the machine proves four things about it in one cycle: that it is the "
          "right cable, that its insulation holds, that it withstands high "
          "voltage, and that every conductor is continuous."),
    ("h", "What one cycle does"),
    ("steps", [
        "Vision check — each enabled camera compares the cable against the taught model for this part.",
        "Contact check — proves the cable is fully seated in the jig and that it is the right cable.",
        "IR test — insulation resistance, measured in megohms (MΩ).",
        "ACW test — AC withstand voltage, leakage measured in milliamps (mA).",
        "Contact test — continuity, channel by channel.",
        "Verdict — PASS prints a label to be scanned back; FAIL asks for the cable to be checked.",
    ]),
    ("p", "A cycle takes only as long as the specs for that part demand. The "
          "Count box on the Test Console shows the last cycle time and the "
          "running average for the part currently loaded."),
    ("warn", "This machine applies high voltage during the IR and ACW steps. "
             "Never touch the cable, the jig or the fixture wiring while a test "
             "is running. Wait for the verdict."),
]),

("Before You Start", [
    ("h", "Check the machine is talking to its devices"),
    ("p", "The COM Status box at the bottom of the sidebar has one pill per "
          "device. A lit pill means the machine can reach that device."),
    ("kv", [
        ("HiPot", "The high-voltage tester. Lights when the IR/ACW sequence opens its serial port."),
        ("IO Ctrl", "The PLC. Lights when the Modbus port opens. If it stays dark, no test can run."),
        ("Scanner", "The barcode scanner. Checked against Windows' device list every ten seconds."),
        ("Printer", "The label printer, EOLPRINTER. Checked the same way, against the installed printers."),
    ]),
    ("note", "Scanner and Printer are found by name. If either stays dark while "
             "the device is plainly plugged in, the log line names the exact "
             "string the machine searched for — compare it against Windows "
             "Settings, Printers & scanners, or Device Manager."),
    ("h", "Sign in"),
    ("p", "Type your Employee ID into the EMP ID field and press ENTER. The ID "
          "is checked against the machine's employee list, and it is stamped on "
          "every record the shift produces. A test will not start without one."),
]),

("Loading a Part", [
    ("steps", [
        "Type the Part Number into the Part No field and press ENTER.",
        "Scan the JIG label. The machine checks it before accepting the part.",
        "The specs for the part load from the database and appear in Inspection Specification.",
        "A START marker label prints, opening the run for that part.",
    ]),
    ("h", "What the JIG check enforces"),
    ("bul", [
        "The JIG label must end with the letter J.",
        "Everything before that J must match the Part Number exactly.",
    ]),
    ("p", "So part FC-2291 is only accepted with jig FC-2291J. Anything else is "
          "refused and the field clears for another scan. This is what stops a "
          "cable being tested against another part's fixture."),
    ("h", "Changing parts"),
    ("p", "Press NEXT PART. An END marker label prints for the part being "
          "released, the part fields and the test display clear, and the machine "
          "waits for the new Part Number. Your employee login and the day's "
          "records stay as they are. Closing the program also prints the END "
          "marker for whatever part is still loaded."),
]),

("Running a Test", [
    ("p", "Press the physical START button, or START TEST on screen. Both do the "
          "same thing. The button is dead while a test is running and while a "
          "printed label is waiting to be scanned."),
    ("h", "The sequence, in order"),
    ("kv", [
        ("1. Rework check",
         "X3 is read fresh for this cycle. High means this cable is a rework part, "
         "and the rework barcode template will be printed at the end."),
        ("2. Vision",
         "Each enabled camera is inspected against the part's taught model. The "
         "verdicts are recorded per camera as CAM1 and CAM2."),
        ("3. Contact check",
         "The safety relay goes to contact mode. The part's highest channel must "
         "make contact, and the channel one past it must not. Both together prove "
         "the whole harness is seated and that nothing extra is bridging."),
        ("4. IR test",
         "The safety relay switches to high-voltage mode and insulation resistance "
         "is measured against the spec for each channel."),
        ("5. ACW test",
         "Withstand voltage is applied and the leakage current measured."),
        ("6. Contact test",
         "Back in contact mode, each channel is energised in turn and its "
         "continuity confirmed."),
        ("7. Verdict",
         "All three electrical tests must pass for the cycle to pass."),
    ]),
    ("h", "Combined and Single test modes"),
    ("p", "A part is configured for one or the other in Model Settings. In "
          "Combined mode the IR and ACW steps energise every channel at once and "
          "take a single reading. In Single mode each channel is tested on its "
          "own, one reading per channel. The contact test always runs channel by "
          "channel in both modes."),
    ("h", "If a test is stopped early"),
    ("p", "The contact check stops the cycle before any high voltage is applied, "
          "and says which fault it found:"),
    ("tbl", ["Message", "What it means", "What to do"], [
        ["Contact NOT OK", "No contact on the part's last channel", "Re-seat the cable fully in the jig and retry"],
        ["Wrong Cable / JIG", "A conductor answered on a channel this part does not have", "Wrong cable or wrong jig — check both"],
        ["PLC not reachable", "The Modbus port could not be opened", "Check the IO Ctrl pill and the PLC cable"],
    ]),
]),

("Reading the Screen", [
    ("h", "Test Console, left to right and top to bottom"),
    ("kv", [
        ("Product Info", "The part currently loaded, the employee signed in, the lot number of the last test, and the machine ID."),
        ("Count", "Today's totals for this part: Total, OK, NG, NG%, PPM and the last cycle time, then the Lot Qty that decides when a box is full and the Print lot label tick that decides whether it gets a label."),
        ("Inspection Specification", "The specs being applied, three rows for one channel — insulation, withstand, contact. The grid follows the test: it scrolls to whichever channel is being measured and highlights it."),
        ("Testing", "The live results table. One column per channel, one row per test, and a RESULT column for the row."),
        ("Verdict panel", "READY, TESTING, PASS or FAIL, in large type on the right."),
        ("Today's PASS Records", "Every lot this part has produced today, with its scan verdict and per-camera vision results."),
        ("PLC I/O Channel Status", "The live state of the PLC's coils and inputs."),
        ("Label Scan Result", "The verdict of the last barcode scan, and the Scan required setting."),
        ("Log", "A running account of what the machine is doing. The first place to look when something is not behaving."),
    ]),
    ("h", "The REWORK badge"),
    ("p", "Blinks amber while X3 is high. It means the next label will be printed "
          "from the rework template rather than the regular one."),
]),

("Labels and Scanning", [
    ("h", "The lot number"),
    ("p", "Every passing cable gets a lot number of the form "
          "yymmdd I m A2A nnnn — the date, the machine, and a four-digit serial. "
          "The serial belongs to the part: each part starts again at 0001 every "
          "day, so a test is identified by the part number and lot number "
          "together."),
    ("h", "Scanning the label back"),
    ("p", "When Scan required is ticked, a PASS is not finished until its printed "
          "label has been scanned. The START button is held — it reads SCAN LABEL "
          "TO CONTINUE — and the scan entry takes focus by itself, so pulling the "
          "scanner trigger is all that is needed."),
    ("tbl", ["Verdict", "Meaning"], [
        ["OK", "The scanned code matches the label just printed"],
        ["NG", "The code does not match — wrong label presented"],
        ["DUP", "This label was already scanned for an earlier lot"],
    ]),
    ("note", "Scan required is a supervisor setting: turning it off asks for a "
             "login. Unticked, a PASS finishes as soon as the label prints."),

    ("h", "Label templates"),
    ("p", "Every label is a PRN file — the printer's own command language — with "
          "@placeholders@ standing in for the values that change from one label "
          "to the next. The machine substitutes them just before printing, so a "
          "label can be redrawn in the label designer without touching the "
          "software, as long as the @names@ are kept."),
    ("kv", [
        ("Part label", "One per PASS, on EOLPRINTER. The template is the PRN file chosen for the part in Model Settings; the rework version is the same file name with R before the extension. TEMPPRN.prn is used if neither is found."),
        ("Lot label", "One per box, on LOTPRINTER, from LOTPRN.prn. It prints when OK is pressed on the lot dialog, and only while Print lot label is ticked."),
        ("Marker labels", "The START and END labels that bracket a part's run, from MARKER.prn. Their text is generated by the machine, so that file holds only the stock setup and a single @body@ placeholder."),
    ]),

    ("h", "Part label placeholders"),
    ("tbl", ["Placeholder", "Replaced with"], [
        ["@partNumber@", "The part number being tested"],
        ["@modelName@", "The model name, from Model Settings"],
        ["@alcCode@", "The ALC code"],
        ["@vendorCode@", "The vendor code"],
        ["@eoNumber@", "The EO number"],
        ["@lotNo@", "The lot number of this test"],
        ["@traceabilityCode@", "The lot number again, under the name some templates use for it"],
        ["@irValues@", "The measured insulation resistance of every channel, CH1 first, comma separated — 1204,1198,1211 for a three-channel part"],
        ["@acwValues@", "The measured withstand current of every channel the same way, to two decimals — 0.12,0.50,1.00"],
        ["@machineID_NoAlphabet@", "The machine ID with its leading letters removed — PB1 becomes 1"],
        ["@ddMMyy@", "The date the label was printed, six digits"],
        ["@HH:mm:ss@", "The time the label was printed"],
    ]),
    ("note", "@irValues@ and @acwValues@ hold every channel in one field, "
             "because the number of channels changes from part to part. The "
             "values are in channel order and a channel with no reading leaves "
             "its slot empty, so the third value is CH3 whatever else happened."),

    ("h", "Lot label placeholders"),
    ("p", "LOTPRN.prn takes all of the above except @traceabilityCode@, "
          "@irValues@ and @acwValues@ — which belong to one cable, not a box — "
          "and adds the five below. The file lists the whole set in its own "
          "comments as well, next to the layout."),
    ("tbl", ["Placeholder", "Replaced with"], [
        ["@lotQty@", "The Lot Qty typed on the Test Console — how many good parts make one box"],
        ["@lotCount@", "The running OK count that reached it, so the second box of 50 reads QTY 50 and COUNT 100"],
        ["@empCode@", "The employee ID signed in when the box was closed"],
        ["@machineID@", "The machine ID as it is, letters and all"],
        ["@dd/MM/yy@", "The date with separators, rather than the six digits of @ddMMyy@"],
    ]),
    ("note", "A placeholder the template does not use is simply left alone. A "
             "misspelled one prints as itself — so a label that comes out reading "
             "@partNumber@ instead of the part number is a typo in the template, "
             "not a fault on the machine."),
]),

("PLC Signals", [
    ("p", "The PLC I/O Channel Status panel shows these live. A lit cell is a "
          "signal that is currently high."),
    ("h", "Outputs — M coils"),
    ("tbl", ["Coil", "Purpose"], [
        ["M28", "Safety relay. ON = contact mode (low voltage); OFF = high-voltage mode"],
        ["M30 – M37", "Contact test relays, channels 1 to 8"],
        ["M20 – M27", "IR and ACW relays, channels 1 to 8"],
    ]),
    ("h", "Inputs — X pins"),
    ("tbl", ["Input", "Purpose"], [
        ["X0", "Physical START button"],
        ["X1", "NG reset"],
        ["X2", "Contact OK — high when the jig has continuity on the energised channel"],
        ["X3", "Rework select — high marks this cable as a rework part"],
        ["X4", "Safety relay acknowledge, the feedback for M28"],
        ["X20 – X27", "Channel acknowledge, channels 1 to 8"],
    ]),
    ("note", "X20 to X27 are wired to the IR and ACW relays in hardware, which is "
             "why the contact test judges continuity from X2 alone."),
]),

("Devices and COM Ports", [
    ("kv", [
        ("HiPot tester", "SCPI commands over RS-232. Runs the IR and ACW measurements."),
        ("PLC / IO controller", "Modbus RTU over serial. Drives the relays and reads the inputs."),
        ("Barcode scanner", "A keyboard-wedge HID device: it types the code and presses Enter itself, so nothing needs clicking first."),
        ("Label printer", "A thermal printer named EOLPRINTER, fed raw PRN templates. The part label and the START/END markers go here."),
        ("Lot label printer", "A second thermal printer named LOTPRINTER, on its own stock, for the one label per box. The lot dialog says whether Windows can see it before anything is printed."),
    ]),
    ("p", "Ports and baud rates live on the COM Setting page, along with the "
          "machine ID that appears in every lot number. That page can also test a "
          "port on its own, which is the quickest way to tell a dead device from "
          "a wrong port."),
    ("warn", "Only one program can hold a serial port at a time. If a manual port "
             "test is left open on the COM Setting page, the test console cannot "
             "reach the same device."),
]),

("Model Settings", [
    ("p", "Model Settings is where a part and its test specification are defined. "
          "It asks for a login."),
    ("steps", [
        "Press NEW. The mode chip turns green and the fields unlock.",
        "Fill in the part number, names, vendor and EO codes, and the ALC.",
        "Choose the number of channels, the label template, the machine and the test mode.",
        "For each channel, enter the IR and ACW rows: applied volts, test time, and the spec minimum and maximum.",
        "Press SAVE.",
    ]),
    ("p", "The channel tabs under Test Specification appear to match the channel "
          "count. Every channel must have all four values filled for both rows "
          "before the part will save."),
    ("p", "Selecting a row in Saved Parts loads that part for editing — the chip "
          "turns blue and UPDATE and DELETE become available. CANCEL returns the "
          "form to read-only without changing anything."),
]),

("Cameras and Vision", [
    ("p", "Two cameras can be fitted. Each enabled camera is inspected on every "
          "cycle against the one model taught for the part, and both verdicts are "
          "stored with the record as CAM1 and CAM2."),
    ("h", "Configuring a camera"),
    ("steps", [
        "Click the camera panel on the right of the Test Console.",
        "Pick the device from the dropdown. The preview shows what that camera sees, which is the only reliable way to tell two identical cameras apart.",
        "Pick a resolution. The preview re-opens to match.",
        "Optionally map a vision dataset to the part currently loaded.",
        "Press Save Settings.",
    ]),
    ("note", "Closing the dialog without saving restores the live panels. While "
             "the dialog is open the camera belongs to the preview, so the panels "
             "behind it pause."),
    ("p", "Teaching and tuning the models themselves is done on the Vision "
          "Settings page."),
]),

("Report", [
    ("p", "Every cycle is written to the database as it finishes: the part, lot "
          "number, date and time, employee, overall verdict, per-camera vision "
          "results, and the per-channel readings for each test."),
    ("p", "Today's PASS Records on the Test Console shows the current part's runs "
          "for today. The Report page is the full history, for any part and "
          "any date."),
]),

("Troubleshooting", [
    ("tbl", ["What you see", "What it means", "What to do"], [
        ["IO Ctrl pill dark", "The Modbus port will not open", "Check the cable and the port setting; make sure no other page is holding the port"],
        ["\"Contact NOT OK\"", "The last channel has no continuity", "Re-seat the cable fully and retry"],
        ["\"Wrong Cable / JIG\"", "A channel answered that this part does not have", "Wrong cable or wrong jig in the fixture"],
        ["JIG error on scan", "The jig label does not end in J, or does not match the part", "Fit the correct jig for this part"],
        ["\"Employee number not found\"", "The ID is not in the employee list", "Check the ID; ask a supervisor to add it"],
        ["START does nothing", "A printed label is waiting to be scanned", "Scan the label; the button says so while it is held"],
        ["Scan reads NG", "The code does not match the label just printed", "Make sure you are scanning the label for this cable"],
        ["Scan reads DUP", "That label has already been scanned", "Find the correct label for this cable"],
        ["Vision says no model", "No vision model is taught for this part", "Teach one on the Vision Settings page, or the step is skipped"],
        ["Camera unavailable", "The camera could not be opened", "Check it is plugged in and not held by another program"],
        ["Printer pill dark", "EOLPRINTER is missing or set offline", "Check Printers & scanners in Windows"],
    ]),
    ("p", "The Log panel records each step as it happens, including the exact "
          "values read from the PLC. When a fault is not obvious, read the log "
          "from the line that says Test Started."),
]),

("Safety", [
    ("warn", "The IR and ACW steps apply high voltage to the cable under test. "
             "Treat the jig as live from the moment START is pressed until the "
             "verdict appears."),
    ("bul", [
        "Never touch the cable, the jig, or the fixture wiring during a test.",
        "Load and unload cables only when the verdict panel reads READY, PASS or FAIL.",
        "The safety relay must acknowledge before high voltage is applied; if X4 does not follow M28, stop and call maintenance.",
        "Do not defeat or bypass the jig interlocks.",
        "Report any smell of burning, arcing sound, or visible damage to the fixture immediately.",
    ]),
]),
]


def render(parent):
    """Render the Help page as a two-pane manual."""
    content = tk.Frame(parent, bg=BG)
    content.pack(fill="both", expand=True, padx=8, pady=8)

    # ── Page header ──────────────────────────────────────────────────────────
    head = tk.Frame(content, bg=BG)
    head.pack(fill="x", pady=(0, 8))
    tk.Label(head, text="Operator Manual", bg=BG, fg=TXT,
             font=("Arial", 17, "bold")).pack(side="left")
    tk.Label(head, text="Feeder Cable EOL Tester", bg=BG, fg=DIM,
             font=("Arial", 10)).pack(side="left", padx=(12, 0), pady=(8, 0))

    body = tk.Frame(content, bg=BG)
    body.pack(fill="both", expand=True)

    # ── Contents, left ───────────────────────────────────────────────────────
    toc_outer = tk.Frame(body, bg=LINE, padx=1, pady=1, width=290)
    toc_outer.pack(side="left", fill="y")
    toc_outer.pack_propagate(False)

    toc_head = tk.Frame(toc_outer, bg=HEADER)
    toc_head.pack(fill="x")
    tk.Label(toc_head, text="Contents", bg=HEADER, fg=TXT,
             font=("Arial", 12, "bold"), padx=12, pady=8).pack(side="left")

    toc_body = tk.Frame(toc_outer, bg=PANEL)
    toc_body.pack(fill="both", expand=True)

    search_wrap = tk.Frame(toc_body, bg=PANEL, padx=8, pady=8)
    search_wrap.pack(fill="x")
    ent_search = tk.Entry(search_wrap, bg="#111", fg=TXT, font=("Arial", 11),
                          bd=0, relief="flat", insertbackground="white",
                          highlightbackground=LINE, highlightcolor=ACCENT,
                          highlightthickness=1)
    ent_search.pack(fill="x", ipady=4)
    ent_search.insert(0, "Search the manual…")

    toc_list = tk.Frame(toc_body, bg=PANEL)
    toc_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    # ── Chapter body, right ──────────────────────────────────────────────────
    page_outer = tk.Frame(body, bg=LINE, padx=1, pady=1)
    page_outer.pack(side="left", fill="both", expand=True, padx=(6, 0))

    page_head = tk.Frame(page_outer, bg=HEADER)
    page_head.pack(fill="x")
    title_lbl = tk.Label(page_head, text="", bg=HEADER, fg=TXT,
                         font=("Arial", 13, "bold"), padx=12, pady=8)
    title_lbl.pack(side="left")
    pos_lbl = tk.Label(page_head, text="", bg=HEADER, fg=DIM, font=("Arial", 10))
    pos_lbl.pack(side="right", padx=12)

    scroll_host = tk.Frame(page_outer, bg=PANEL)
    scroll_host.pack(fill="both", expand=True)
    canvas = tk.Canvas(scroll_host, bg=PANEL, highlightthickness=0, bd=0)
    vsb = ttk.Scrollbar(scroll_host, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(canvas, bg=PANEL)
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    # Text has to be told how wide it may run; Tk will not wrap on its own.
    # Every label that holds prose is tracked here and re-wrapped whenever the
    # pane changes width, so the manual reflows instead of being cut off.
    wrapped = []          # [(label, extra_indent), ...]

    def _on_canvas_resize(e):
        canvas.itemconfig(win_id, width=e.width)
        for lbl, indent in wrapped:
            try:
                lbl.config(wraplength=max(200, e.width - 48 - indent))
            except Exception:
                pass
    canvas.bind("<Configure>", _on_canvas_resize)

    # Scroll only while the pointer is over this page, so the binding does not
    # follow the operator to whatever page they open next.
    def _wheel(e):
        canvas.yview_scroll(-1 * int(e.delta / 120), "units")

    def _bind_wheel(_e=None):
        canvas.bind_all("<MouseWheel>", _wheel)

    def _unbind_wheel(_e=None):
        canvas.unbind_all("<MouseWheel>")
    canvas.bind("<Enter>", _bind_wheel)
    canvas.bind("<Leave>", _unbind_wheel)
    content.bind("<Destroy>", lambda e: e.widget == content and _unbind_wheel())

    # ── Block renderers ──────────────────────────────────────────────────────
    def _text(parent_, text, fg=TXT, font=("Arial", 12), indent=0, pady=(0, 0)):
        lbl = tk.Label(parent_, text=text, bg=parent_.cget("bg"), fg=fg,
                       font=font, justify="left", anchor="nw")
        lbl.pack(fill="x", padx=(indent, 0), pady=pady)
        wrapped.append((lbl, indent))
        return lbl

    def _callout(parent_, text, accent, tag):
        wrap = tk.Frame(parent_, bg=accent)
        wrap.pack(fill="x", pady=(10, 4))
        bodyf = tk.Frame(wrap, bg="#141414")
        bodyf.pack(fill="x", padx=(3, 0))
        tk.Label(bodyf, text=tag, bg="#141414", fg=accent,
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        lbl = tk.Label(bodyf, text=text, bg="#141414", fg=TXT,
                       font=("Arial", 12), justify="left", anchor="nw")
        lbl.pack(fill="x", padx=12, pady=(2, 10))
        wrapped.append((lbl, 30))

    def _table(parent_, headers, rows):
        outer = tk.Frame(parent_, bg=LINE)
        outer.pack(fill="x", pady=(8, 6))
        for c in range(len(headers)):
            outer.columnconfigure(c, weight=1 if c else 0, uniform="" if c == 0 else "tc")
        for c, h in enumerate(headers):
            tk.Label(outer, text=h, bg=HEADER, fg=TXT, font=("Arial", 11, "bold"),
                     anchor="w", padx=10, pady=6).grid(row=0, column=c, sticky="nsew",
                                                       padx=1, pady=1)
        for r, row in enumerate(rows, start=1):
            bg = "#101010" if r % 2 else "#151515"
            for c, cell in enumerate(row):
                lbl = tk.Label(outer, text=cell, bg=bg,
                               fg=TXT if c == 0 else DIM,
                               font=("Consolas", 11) if c == 0 else ("Arial", 11),
                               anchor="nw", justify="left", padx=10, pady=6)
                lbl.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                if c:
                    wrapped.append((lbl, 260 * len(headers)))

    def _render_chapter(idx):
        for w in inner.winfo_children():
            w.destroy()
        wrapped.clear()
        name, blocks = CHAPTERS[idx]
        title_lbl.config(text=name)
        pos_lbl.config(text=f"Chapter {idx + 1} of {len(CHAPTERS)}")

        pad = tk.Frame(inner, bg=PANEL, padx=20, pady=16)
        pad.pack(fill="both", expand=True)

        for block in blocks:
            kind = block[0]
            if kind == "h":
                _text(pad, block[1], fg=ACCENT, font=("Arial", 13, "bold"), pady=(16, 5))
            elif kind == "p":
                _text(pad, block[1], fg="#cfcfcf", pady=(0, 6))
            elif kind == "steps":
                for i, s in enumerate(block[1], start=1):
                    row = tk.Frame(pad, bg=PANEL)
                    row.pack(fill="x", pady=2)
                    tk.Label(row, text=f"{i}", bg="#1f1f1f", fg=ACCENT,
                             font=("Arial", 11, "bold"), width=3, pady=2).pack(side="left", anchor="n")
                    lbl = tk.Label(row, text=s, bg=PANEL, fg="#cfcfcf",
                                   font=("Arial", 12), justify="left", anchor="nw")
                    lbl.pack(side="left", fill="x", expand=True, padx=(10, 0))
                    wrapped.append((lbl, 70))
            elif kind == "bul":
                for s in block[1]:
                    row = tk.Frame(pad, bg=PANEL)
                    row.pack(fill="x", pady=2)
                    tk.Label(row, text="•", bg=PANEL, fg=ACCENT,
                             font=("Arial", 13, "bold")).pack(side="left", anchor="n")
                    lbl = tk.Label(row, text=s, bg=PANEL, fg="#cfcfcf",
                                   font=("Arial", 12), justify="left", anchor="nw")
                    lbl.pack(side="left", fill="x", expand=True, padx=(10, 0))
                    wrapped.append((lbl, 60))
            elif kind == "kv":
                for term, desc in block[1]:
                    row = tk.Frame(pad, bg=PANEL)
                    row.pack(fill="x", pady=3)
                    tk.Label(row, text=term, bg=PANEL, fg=BLUE,
                             font=("Arial", 11, "bold"), width=19, anchor="nw",
                             justify="left", wraplength=175).pack(side="left", anchor="n")
                    lbl = tk.Label(row, text=desc, bg=PANEL, fg="#cfcfcf",
                                   font=("Arial", 12), justify="left", anchor="nw")
                    lbl.pack(side="left", fill="x", expand=True, padx=(10, 0))
                    wrapped.append((lbl, 230))
            elif kind == "tbl":
                _table(pad, block[1], block[2])
            elif kind == "note":
                _callout(pad, block[1], BLUE, "NOTE")
            elif kind == "warn":
                _callout(pad, block[1], "#ff9100", "WARNING")

        canvas.yview_moveto(0)
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        _on_canvas_resize(type("E", (), {"width": canvas.winfo_width()})())

    # ── Contents list ────────────────────────────────────────────────────────
    current = {"idx": 0}
    toc_items = []

    def _select(idx):
        current["idx"] = idx
        for i, lbl in toc_items:
            on = i == idx
            lbl.config(bg="#1f1f1f" if on else PANEL,
                       fg=ACCENT if on else DIM,
                       font=("Arial", 11, "bold") if on else ("Arial", 11))
        _render_chapter(idx)

    def _build_toc(match=""):
        for w in toc_list.winfo_children():
            w.destroy()
        toc_items.clear()
        needle = match.strip().lower()
        shown = 0
        for i, (name, blocks) in enumerate(CHAPTERS):
            if needle and needle not in _chapter_text(name, blocks):
                continue
            shown += 1
            lbl = tk.Label(toc_list, text=f"{i + 1}.  {name}", bg=PANEL, fg=DIM,
                           font=("Arial", 11), anchor="w", padx=10, pady=7,
                           cursor="hand2")
            lbl.pack(fill="x", pady=1)
            lbl.bind("<Button-1>", lambda e, k=i: _select(k))
            toc_items.append((i, lbl))
        if needle and not shown:
            tk.Label(toc_list, text="Nothing found", bg=PANEL, fg="#555",
                     font=("Arial", 11, "italic"), pady=10).pack(fill="x")
        # Keep the open chapter highlighted when it survives the filter.
        for i, lbl in toc_items:
            if i == current["idx"]:
                lbl.config(bg="#1f1f1f", fg=ACCENT, font=("Arial", 11, "bold"))

    def _chapter_text(name, blocks):
        """Everything in a chapter as one lowercase string, for searching."""
        parts = [name]
        for b in blocks:
            for piece in b[1:]:
                if isinstance(piece, str):
                    parts.append(piece)
                elif isinstance(piece, (list, tuple)):
                    for item in piece:
                        if isinstance(item, str):
                            parts.append(item)
                        elif isinstance(item, (list, tuple)):
                            parts.extend(str(x) for x in item)
        return " ".join(parts).lower()

    # Placeholder that gets out of the way on the first click, and comes back
    # if the box is left empty -- otherwise an empty box looks broken.
    def _focus_search(_e=None):
        if ent_search.get() == "Search the manual…":
            ent_search.delete(0, "end")
            ent_search.config(fg=TXT)

    def _blur_search(_e=None):
        if not ent_search.get().strip():
            ent_search.delete(0, "end")
            ent_search.insert(0, "Search the manual…")
            ent_search.config(fg=DIM)

    def _on_search(_e=None):
        term = ent_search.get()
        _build_toc("" if term == "Search the manual…" else term)

    ent_search.config(fg=DIM)
    ent_search.bind("<FocusIn>", _focus_search)
    ent_search.bind("<FocusOut>", _blur_search)
    ent_search.bind("<KeyRelease>", _on_search)

    # ── Footer: move between chapters without going back to the list ─────────
    foot = tk.Frame(page_outer, bg=HEADER)
    foot.pack(fill="x")

    def _step(delta):
        nxt = current["idx"] + delta
        if 0 <= nxt < len(CHAPTERS):
            _select(nxt)

    for text, delta, side in (("‹  Previous", -1, "left"), ("Next  ›", 1, "right")):
        tk.Button(foot, text=text, bg="#222", fg=TXT, font=("Arial", 11, "bold"),
                  bd=0, padx=14, pady=6, cursor="hand2",
                  activebackground="#333", activeforeground=TXT,
                  command=lambda d=delta: _step(d)).pack(side=side, padx=10, pady=6)

    _build_toc()
    _select(0)
