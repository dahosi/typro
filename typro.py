#!/usr/bin/env python3
"""
Typro - An offline, keyboard-only typewriter for the Raspberry Pi.

Visual inspiration: Olympia SM3 (Italic typeface, 1956).
- Vintage cream "paper" background, black text, red dates.
- No mouse required: every action has a keyboard shortcut.
- Works fully offline. Saves notebooks as plain .typro files (JSON inside).

This is a single-file program written with Python's built-in Tkinter toolkit,
so it runs the same on macOS (for testing) and on Raspberry Pi OS.

Author: dahosi
Open-source project, released under the MIT License.
"""

# ---------------------------------------------------------------------------
# 1. IMPORTS  (all of these ship with Python - nothing to install)
# ---------------------------------------------------------------------------
import tkinter as tk                      # the core GUI toolkit
from tkinter import filedialog            # the "Save as / Open" file pickers
from tkinter import messagebox            # the small Yes/No/OK pop-up boxes
from tkinter import simpledialog          # the small "type a name" pop-up box
from tkinter import font as tkfont        # lets us inspect installed fonts
import json                               # turns our notebook into a text file
import datetime                           # gives us today's date
import os                                 # lets us read file names/paths
import sys                                # lets us exit cleanly on old Tk
import wave                               # writes the little key-click sound file
import struct                             # packs sound samples into bytes
import math                               # shapes the click's fade-out
import random                             # the click is a short burst of noise
import shutil                             # finds an audio player on Linux
import subprocess                         # plays the click (fixed file, no input)
import tempfile                           # where the generated click is stored


# ---------------------------------------------------------------------------
# 2. CONSTANTS  (settings you can tweak in one place)
# ---------------------------------------------------------------------------
APP_NAME      = "Typro"
FILE_EXT      = ".typro"                  # our own file type (it is just JSON)

# Palette - the brand colours of the project.
#   #b81106 #830a06 #1f140f #d4b9a5 #ad5e33 #a88b75 #cf845b #4c3126 #783c1d
PAPER_COLOR   = "#F5ECD7"                 # cream / yellowish vintage paper
DESK_COLOR    = "#4a2f24"                 # the brand background colour
DESK_GRAIN    = ["#4c3126", "#783c1d", "#3a241b"]   # subtle leather-grain specks
SHEET_SHADOW  = "#1f140f"                 # soft shadow cast by the paper (brand)
TEXT_COLOR    = "#1f140f"                 # near-black brand ink
DATE_COLOR    = "#b81106"                 # brand red, like a 2-colour ribbon
STATUS_BG     = "#1f140f"                 # dark strip at the bottom (brand)
STATUS_FG     = "#d4b9a5"                 # light tan text on the dark strip (brand)
HELP_FILL     = "#cf845b"                 # the round "?" button (brand terracotta)
HELP_FG       = "#1f140f"                 # text on the "?" button

# On-screen page layout (pixels).
OUTER_MARGIN  = 40                        # gap between the sheet and the window edge
SHEET_PADX    = 18                        # left/right margin inside the paper
SHEET_PADY    = 18                        # top/bottom margin inside the paper
MIN_FONT      = 7                         # smallest the type may shrink to
MAX_FONT      = 26                        # largest the type may grow to

# Preferred fonts, best first. We pick the first one your computer actually has.
# Courier Prime and TT2020 are free classic typewriter fonts (see README).
FONT_WISHLIST = ["Courier Prime", "TT2020", "Courier New", "Courier"]
FONT_SIZE     = 14

# Paper sizes.
#   cols/rows = the character grid of ONE page. These match the PDF exporter, so
#               the page breaks you see on screen are exactly where the PDF (and
#               a printout) will break.
#   pts       = the real page size in PDF points (1 point = 1/72 inch).
#   margin    = blank border in points around the PDF text.
#   pdf_font  = font size in points used in the exported PDF.
PAPER_SIZES = {
    "A4":    {"cols": 73, "rows": 49, "label": "A4 (210 x 297 mm)",
              "pts": (595.28, 841.89), "margin": 56.7, "pdf_font": 11},
    "3x4in": {"cols": 33, "rows": 20, "label": "3 x 4 inch card",
              "pts": (216.0, 288.0),   "margin": 18.0, "pdf_font": 9},
}

# Text colours expressed for PDF (red/green/blue, each 0.0 to 1.0).
PDF_RGB = {"black": (0.122, 0.078, 0.059), "red": (0.722, 0.067, 0.024)}

# The vintage cream paper colour (PAPER_COLOR = #F5ECD7) as a PDF fill colour,
# used when the user chooses a cream page background for the exported PDF.
PDF_CREAM = (0.961, 0.925, 0.843)

# The date format the user asked for: DD MON YYYY  ->  e.g. 31 MAY 2026
DATE_FORMAT = "%d %b %Y"

# The shortcut modifier key. macOS users expect Command; Windows / Raspberry Pi
# / Linux users expect Control. MOD is used to build the key bindings, MOD_LABEL
# is what we show in the help and status bar, and SHORTCUT_MASK lets the click
# sound ignore keys pressed as part of a shortcut.
if sys.platform == "darwin":
    MOD, MOD_LABEL, SHORTCUT_MASK = "Command", "Cmd", 0x8
else:
    MOD, MOD_LABEL, SHORTCUT_MASK = "Control", "Ctrl", 0x4


# ---------------------------------------------------------------------------
# 3. THE APPLICATION CLASS
#    A "class" is a blueprint. We build one Typro object from it (see bottom).
# ---------------------------------------------------------------------------
class Typro:

    def __init__(self, root):
        """Runs once when the app starts. Sets up the window and the state."""
        self.root = root

        # ---- In-memory data -------------------------------------------------
        # A "notebook" is a dictionary (a labelled box of values).
        # It holds its name, the chosen paper size, and a list of pages.
        # Each page is a list of "segments": pieces of text with a colour.
        self.notebook = self._blank_notebook("Untitled Notebook", "A4")
        self.file_path = None          # where this notebook lives on disk
        self.modified = False          # True if there are unsaved changes

        # ---- Pages (fixed-size sheets with automatic flow) ------------------
        # The whole document lives in ONE text box and flows continuously. We
        # show it one PAGE at a time: a page is `cols` characters wide and
        # `rows` lines tall (matching the chosen paper). When you fill a page,
        # typing continues on the next page automatically; you move between
        # pages with Ctrl+Left / Ctrl+Right.
        self.cols = PAPER_SIZES[self.notebook["paper_size"]]["cols"]
        self.rows = PAPER_SIZES[self.notebook["paper_size"]]["rows"]
        self.current_page = 0          # which page is in view (0 = first)
        self._text_window = None       # canvas id of the paper, once placed
        self._laying_out = False       # guard against re-entrant layout

        # The app opens in full screen (like a dedicated typewriter); F11 or
        # Esc toggles back to a window.
        self.fullscreen = True

        # ---- Key-click sound ------------------------------------------------
        # A short "clack" plays as you type. Toggle with Ctrl+B.
        self.sound_on = True
        self.sound_path = os.path.join(tempfile.gettempdir(), "typro_key.wav")
        self._sound_player = self._find_sound_player()   # how to play on this OS

        # ---- Choose the typewriter font ------------------------------------
        self.type_font = tkfont.Font(family=self._pick_font(), size=FONT_SIZE)

        # ---- Build the window ----------------------------------------------
        self._build_window()
        self._bind_shortcuts()
        self._load_notebook()
        self._refresh_status()

    # -----------------------------------------------------------------------
    # 3a. Small helpers
    # -----------------------------------------------------------------------
    def _blank_notebook(self, name, paper_size):
        """Return a fresh, empty notebook with one blank page."""
        return {
            "app": APP_NAME,
            "name": name,
            "paper_size": paper_size,
            "pages": [self._blank_page()],
        }

    def _blank_page(self):
        """A page is a list of text segments. A blank page has no segments."""
        return {"segments": []}

    def _pick_font(self):
        """Pick the first font from our wishlist that is installed."""
        installed = set(tkfont.families())
        for name in FONT_WISHLIST:
            if name in installed:
                return name
        return "Courier"   # last-resort fallback that exists everywhere

    def _set_window_icon(self):
        """Give the window/taskbar an app icon, using the files in img/.
        Best-effort: if an icon file is missing or the platform refuses it, the
        app simply keeps the default icon."""
        img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")
        # Windows prefers a .ico for the title bar and taskbar.
        if sys.platform.startswith("win"):
            ico = os.path.join(img_dir, "typewriter_icon.ico")
            if os.path.exists(ico):
                try:
                    self.root.iconbitmap(ico)
                except tk.TclError:
                    pass
        # A PNG icon works across platforms (Linux/Raspberry Pi taskbar, and the
        # window proxy icon). We keep a reference so it is not garbage-collected.
        png = os.path.join(img_dir, "typewriter_icon_128x128.png")
        if os.path.exists(png):
            try:
                self._app_icon = tk.PhotoImage(file=png)
                self.root.iconphoto(True, self._app_icon)
            except tk.TclError:
                pass

    # -----------------------------------------------------------------------
    # 3b. Building the visible window
    # -----------------------------------------------------------------------
    def _build_window(self):
        self.root.title(APP_NAME)
        self._set_window_icon()
        self.root.configure(bg=DESK_COLOR)
        self.root.geometry("900x680")          # the size if you leave fullscreen
        self.root.minsize(640, 480)
        self.root.attributes("-fullscreen", self.fullscreen)   # open fullscreen

        # The "desk" is a Canvas so we can paint a textured leather-brown
        # surface and draw the paper (with a shadow and chrome trim) on top.
        self.desk = tk.Canvas(self.root, bg=DESK_COLOR, highlightthickness=0, bd=0)
        self.desk.pack(fill="both", expand=True)

        # The "paper": a Text widget the user types into. It is sized to one
        # page (cols x rows) and placed on the desk by _layout(). We wrap on
        # whole words so text never gets cut mid-word.
        self.text = tk.Text(
            self.desk,
            width=self.cols, height=self.rows,
            wrap="word",
            font=self.type_font,
            bg=PAPER_COLOR,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,   # the blinking cursor colour
            padx=SHEET_PADX, pady=SHEET_PADY,
            relief="flat",
            borderwidth=0,
            undo=True,                     # enables Ctrl+Z / Ctrl+Y
            highlightthickness=0,
        )

        # Define the "date" style: any text tagged "date" turns red.
        self.text.tag_configure("date", foreground=DATE_COLOR)
        # The "pad" style marks invisible filler lines kept below your text so
        # that even a half-empty last page can be shown from its top. Filler is
        # never saved or exported.
        self.text.tag_configure("pad")

        # Whenever the user types, remember that there are unsaved changes.
        self.text.bind("<<Modified>>", self._on_text_modified)
        # After any key, keep the page that holds the cursor in view.
        self.text.bind("<KeyRelease>", self._update_pagination)
        # Play the key-click sound as keys go down.
        self.text.bind("<KeyPress>", self._play_click)

        # Re-lay-out the page whenever the window is resized.
        self.desk.bind("<Configure>", self._layout)

        # The status strip along the bottom.
        self.status = tk.Label(
            self.root, anchor="w", bg=STATUS_BG, fg=STATUS_FG,
            font=("Helvetica", 11), padx=12, pady=4,
        )
        self.status.pack(side="bottom", fill="x")

        # A floating round "?" button in the bottom-right corner that opens the
        # shortcuts help. It is a visible hint; the keyboard (Ctrl+/) still works.
        self._build_help_button(self.desk)

        self.text.focus_set()   # so the user can type immediately

    def _build_help_button(self, parent):
        """A small round brass '?' button, bottom-right, that opens Help."""
        size = 44
        btn = tk.Canvas(parent, width=size, height=size, bg=DESK_COLOR,
                        highlightthickness=0, bd=0, cursor="hand2")
        btn.create_oval(3, 3, size - 3, size - 3, fill=HELP_FILL, outline="")
        btn.create_text(size // 2, size // 2 - 1, text="?",
                        fill=HELP_FG, font=("Helvetica", 20, "bold"))
        btn.bind("<Button-1>", lambda e: self.show_help())
        btn.bind("<Enter>", lambda e: self._show_tip(btn, f"Shortcuts ({MOD_LABEL} + /)"))
        btn.bind("<Leave>", lambda e: self._hide_tip())
        btn.place(relx=1.0, rely=1.0, anchor="se", x=-18, y=-18)
        self._help_btn = btn
        self._tip = None

    def _show_tip(self, widget, message):
        """Tiny hover tooltip shown above a widget."""
        self._hide_tip()
        self._tip = tk.Toplevel(self.root)
        self._tip.wm_overrideredirect(True)         # no title bar
        x = widget.winfo_rootx() - 120
        y = widget.winfo_rooty() - 8
        self._tip.geometry(f"+{x}+{y}")
        tk.Label(self._tip, text=message, bg=STATUS_BG, fg=STATUS_FG,
                 font=("Helvetica", 10), padx=8, pady=3).pack()

    def _hide_tip(self):
        if getattr(self, "_tip", None) is not None:
            self._tip.destroy()
            self._tip = None

    # -----------------------------------------------------------------------
    # 3c. Keyboard shortcuts (the only way to drive the app - no mouse needed)
    # -----------------------------------------------------------------------
    def _bind_shortcuts(self):
        # MOD is "Command" on macOS and "Control" elsewhere, so the shortcuts
        # feel native on every platform.
        b = self.root.bind_all
        b(f"<{MOD}-n>",        lambda e: self.new_page())
        b(f"<{MOD}-N>",        lambda e: self.new_page())
        b(f"<{MOD}-Shift-N>",  lambda e: self.new_notebook())
        b(f"<{MOD}-s>",        lambda e: self.save())
        b(f"<{MOD}-Shift-S>",  lambda e: self.save_as())
        b(f"<{MOD}-o>",        lambda e: self.open_notebook())
        b(f"<{MOD}-d>",        lambda e: self.insert_date())
        b(f"<{MOD}-Delete>",   lambda e: self.delete_page())
        b(f"<{MOD}-BackSpace>", lambda e: self.delete_page())   # mac Delete key
        b(f"<{MOD}-Right>",    lambda e: self.next_page())
        b(f"<{MOD}-Left>",     lambda e: self.prev_page())
        b(f"<{MOD}-p>",        lambda e: self.export())          # "Print" -> PDF
        b(f"<{MOD}-e>",        lambda e: self.export())
        b(f"<{MOD}-Shift-P>",  lambda e: self.choose_paper_size())
        b(f"<{MOD}-b>",        lambda e: self.toggle_sound())
        b("<F11>",             lambda e: self.toggle_fullscreen())
        # Help: F1 works on the Raspberry Pi; on macOS the F-keys are taken by
        # the system, so the MOD+/ shortcut is reliable (the "?" button always
        # works too).
        b("<F1>",              lambda e: self.show_help())
        b(f"<{MOD}-slash>",    lambda e: self.show_help())
        # Esc leaves full screen (only from the typing area, so it does not
        # clash with Esc closing a pop-up window).
        self.text.bind("<Escape>", self._exit_fullscreen)
        b(f"<{MOD}-q>",        lambda e: self.quit_app())
        # When the window's close button is used, run our safe-quit routine.
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)

    # -----------------------------------------------------------------------
    # 3d. Converting between the typing area and our saved data
    # -----------------------------------------------------------------------
    def _view_to_segments(self):
        """Read the whole document and return a list of {text, color} segments.

        We 'dump' the Text widget, which gives us the characters in order plus
        markers for where the red 'date' style turns on and off.
        """
        segments = []
        color = "black"
        in_pad = False
        for key, value, _index in self.text.dump("1.0", "end-1c",
                                                  tag=True, text=True):
            if key == "tagon" and value == "date":
                color = "red"
            elif key == "tagoff" and value == "date":
                color = "black"
            elif key == "tagon" and value == "pad":
                in_pad = True
            elif key == "tagoff" and value == "pad":
                in_pad = False
            elif key == "text" and not in_pad:
                segments.append({"text": value, "color": color})
        return segments

    def _segments_to_view(self, segments):
        """Fill the typing area from a list of saved segments."""
        self.text.delete("1.0", "end")
        for seg in segments:
            if seg.get("color") == "red":
                self.text.insert("end", seg["text"], "date")
            else:
                self.text.insert("end", seg["text"])
        self._refresh_pad()                  # invisible filler below the text
        self.text.mark_set("insert", "1.0")  # start at the top of the sheet
        self.text.edit_reset()               # loading can't be "undone"
        self.text.edit_modified(False)

    # -----------------------------------------------------------------------
    # 3d-pad. Invisible filler so any page can scroll to the top
    # -----------------------------------------------------------------------
    def _refresh_pad(self):
        """Keep exactly `rows` blank filler lines (tagged 'pad') below the text,
        giving enough room to scroll the last, half-empty page to the top.

        We trim trailing blank lines by *content* (not by tag) and re-append the
        filler, so a stray tag can never delete or hide real text."""
        self.text.tag_remove("pad", "1.0", "end")
        content = self.text.get("1.0", "end-1c")
        keep = len(content.rstrip())                     # drop trailing blanks
        self.text.delete(f"1.0 + {keep} chars", "end-1c")
        self.text.insert("end-1c", "\n" * self.rows, "pad")

    def _content_end(self):
        """Index where the real text ends and the filler begins."""
        spans = self.text.tag_ranges("pad")
        return spans[0] if spans else "end-1c"

    def _content_display_lines(self):
        """On-screen (wrapped) line count of the real text, excluding filler."""
        n = self.text.count("1.0", self._content_end(), "displaylines")
        return (n[0] if n else 0) + 1

    # -----------------------------------------------------------------------
    # 3d-bis. Page layout: draw the textured desk and the cream sheet
    # -----------------------------------------------------------------------
    def _fit_font(self, avail_w, avail_h):
        """Pick the biggest font size at which a whole page (cols x rows) still
        fits in the space available, so you can see the full page at once."""
        for size in range(MAX_FONT, MIN_FONT - 1, -1):
            self.type_font.configure(size=size)
            cw = self.type_font.measure("0")
            lh = self.type_font.metrics("linespace")
            if (self.cols * cw + 2 * SHEET_PADX <= avail_w and
                    self.rows * lh + 2 * SHEET_PADY <= avail_h):
                return size
        self.type_font.configure(size=MIN_FONT)
        return MIN_FONT

    def _draw_desk(self, w, h):
        """Paint the leather-brown desk with a subtle grain texture."""
        c = self.desk
        c.delete("desk")
        c.create_rectangle(0, 0, w, h, fill=DESK_COLOR, outline="", tags="desk")
        rnd = random.Random(7)               # fixed seed -> stable texture
        for _ in range(min(1500, (w * h) // 1500)):
            x, y = rnd.randint(0, w), rnd.randint(0, h)
            c.create_line(x, y, x + rnd.randint(2, 6), y,
                          fill=rnd.choice(DESK_GRAIN), tags="desk")
        c.tag_lower("desk")

    def _layout(self, _event=None):
        """Size the page to the chosen paper, centre it on the desk, and draw
        its shadow and chrome trim. Runs on launch and on every window resize."""
        if self._laying_out:
            return
        self._laying_out = True
        try:
            c = self.desk
            c.update_idletasks()
            w, h = c.winfo_width(), c.winfo_height()
            if w < 50 or h < 50:
                return
            self._draw_desk(w, h)
            self._fit_font(w - 2 * OUTER_MARGIN, h - 2 * OUTER_MARGIN)
            self.text.configure(width=self.cols, height=self.rows,
                                padx=SHEET_PADX, pady=SHEET_PADY)
            self.text.update_idletasks()
            tw, th = self.text.winfo_reqwidth(), self.text.winfo_reqheight()
            cx, cy = w // 2, h // 2
            x0, y0 = cx - tw // 2, cy - th // 2
            x1, y1 = x0 + tw, y0 + th
            c.delete("frame")
            c.create_rectangle(x0 + 10, y0 + 12, x1 + 10, y1 + 12,
                               fill=SHEET_SHADOW, outline="", tags="frame")
            c.tag_raise("frame", "desk")
            if self._text_window is None:
                self._text_window = c.create_window(cx, cy, window=self.text,
                                                    anchor="center")
            else:
                c.coords(self._text_window, cx, cy)
            c.tag_raise(self._text_window)
            if getattr(self, "_help_btn", None) is not None:
                # NB: Canvas.lift() is aliased to canvas item raise, so to raise
                # the button *widget* in the stacking order we call Tk directly.
                self._help_btn.tk.call("raise", self._help_btn._w)
            self._snap_to_page(self.current_page)
        finally:
            self._laying_out = False

    # -----------------------------------------------------------------------
    # 3d-ter. Pagination: one continuous document shown one page at a time
    # -----------------------------------------------------------------------
    def _cursor_display_line(self):
        """Which on-screen line (0-based) the cursor is on."""
        n = self.text.count("1.0", "insert", "displaylines")
        return n[0] if n else 0

    def _total_pages(self):
        return max(1, (self._content_display_lines() + self.rows - 1) // self.rows)

    def _snap_to_page(self, page):
        """Scroll so that `page` is shown from its first line at the very top."""
        page = max(0, min(page, self._total_pages() - 1))
        self.text.update_idletasks()
        fv = self.text.count("1.0", "@0,0", "displaylines")
        first = fv[0] if fv else 0
        delta = page * self.rows - first
        if delta:
            self.text.yview_scroll(delta, "units")
        self.current_page = page

    def _update_pagination(self, _event=None):
        """After typing or moving the cursor, show the page the cursor is on.
        This is what makes text flow onto a new page automatically."""
        if self._laying_out:
            return
        # Safety: if the user typed real text onto a filler line, drop the
        # 'pad' tag from that line so the text is saved normally (never lost).
        ls, le = self.text.index("insert linestart"), self.text.index("insert lineend")
        if "pad" in self.text.tag_names("insert") and self.text.get(ls, le).strip():
            self.text.tag_remove("pad", ls, le + "+1c")
        self._snap_to_page(self._cursor_display_line() // self.rows)
        self._refresh_status()

    def _go_to_page(self, page):
        """Move the cursor to the top of `page` and show that page."""
        page = max(0, min(page, self._total_pages() - 1))
        self.text.mark_set("insert",
                           self.text.index(f"1.0 + {page * self.rows} display lines"))
        self._snap_to_page(page)
        self._refresh_status()

    def toggle_fullscreen(self, _event=None):
        """Switch between full screen and a normal window."""
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def _exit_fullscreen(self, _event=None):
        """Leave full screen (used by the Esc key in the typing area)."""
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes("-fullscreen", False)

    # -----------------------------------------------------------------------
    # 3e-bis. Key-click sound (a typewriter "clack" as you type)
    # -----------------------------------------------------------------------
    def _find_sound_player(self):
        """Decide how to play sound on this operating system.
        Windows uses the built-in `winsound`; macOS uses `afplay`; Linux/Pi use
        whichever of `paplay`/`aplay` is installed. Returns a command name, the
        string "winsound", or None if no player is available."""
        if sys.platform.startswith("win"):
            return "winsound"
        if sys.platform == "darwin":
            return "afplay"
        return shutil.which("paplay") or shutil.which("aplay")

    def _ensure_click_sound(self):
        """Create the little click sound file once (a 35 ms burst of noise that
        fades out quickly, which sounds like a key striking). Generated with the
        standard library only — no audio file needs to ship with the app."""
        if os.path.exists(self.sound_path):
            return True
        try:
            rate, duration = 22050, 0.035
            samples = int(rate * duration)
            with wave.open(self.sound_path, "w") as w:
                w.setnchannels(1)
                w.setsampwidth(2)        # 16-bit
                w.setframerate(rate)
                data = bytearray()
                for i in range(samples):
                    fade = math.exp(-i / (samples * 0.18))      # quick decay
                    value = int(random.uniform(-1, 1) * fade * 32767 * 0.55)
                    data += struct.pack("<h", value)
                w.writeframes(bytes(data))
            return True
        except OSError:
            return False

    def _play_click(self, event=None):
        """Play one key click. Best-effort and non-blocking: if anything goes
        wrong we simply stay silent. Skips modifier keys and shortcuts so only
        real typing clicks."""
        if not self.sound_on or self._sound_player is None:
            return
        if event is not None:
            if event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R",
                                 "Alt_L", "Alt_R", "Meta_L", "Meta_R",
                                 "Super_L", "Super_R"):
                return
            if event.state & SHORTCUT_MASK:   # MOD held -> it's a shortcut
                return
        if not self._ensure_click_sound():
            return
        try:
            if self._sound_player == "winsound":
                import winsound
                winsound.PlaySound(self.sound_path,
                                   winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                # Fixed command, fixed file, no shell, no user input -> safe.
                subprocess.Popen([self._sound_player, self.sound_path],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        except (OSError, ImportError):
            pass

    def toggle_sound(self):
        """Turn the key-click sound on or off."""
        self.sound_on = not self.sound_on
        self._refresh_status()

    def _store_current_view(self):
        """Save the whole document back into the notebook (as one flowing page;
        the PDF and the on-screen view both re-paginate it on demand)."""
        self.notebook["pages"] = [{"segments": self._view_to_segments()}]

    def _concat_pages(self, pages):
        """Join every page's segments into one continuous list of segments."""
        segments = []
        for i, page in enumerate(pages):
            page_segs = page.get("segments", [])
            if i > 0 and segments and not segments[-1]["text"].endswith("\n"):
                segments.append({"text": "\n", "color": "black"})
            segments.extend(page_segs)
        return segments

    def _load_notebook(self):
        """Load the whole notebook into the typing area and show page 1."""
        self._segments_to_view(self._concat_pages(self.notebook["pages"]))
        self.current_page = 0
        # Loading text fires <<Modified>>, so reset the flag afterwards.
        self.text.edit_modified(False)
        self.modified = False
        self.root.after_idle(self._layout)

    # -----------------------------------------------------------------------
    # 3e. Actions the user triggers with shortcuts
    # -----------------------------------------------------------------------
    def new_page(self):
        """Start a fresh page: fill the rest of the current page with blank
        lines so that what you type next begins at the top of a new sheet."""
        if not self.text.get("1.0", self._content_end()).strip():
            return                            # document is empty - already a page
        lines = self._content_display_lines()
        remainder = lines % self.rows
        pad = self.rows - remainder if remainder else 0
        if pad:
            self.text.insert(self._content_end(), "\n" * pad)
        self.text.mark_set("insert", self._content_end())
        self.modified = True
        self._update_pagination()

    def new_notebook(self):
        """Start a brand-new notebook (asks to save the old one first)."""
        if not self._confirm_discard():
            return
        name = simpledialog.askstring(
            "New Notebook", "Name your notebook:", parent=self.root)
        if not name:
            return
        size = self._ask_paper_size()
        if size is None:
            return
        self.notebook = self._blank_notebook(name, size)
        self.file_path = None
        self._apply_paper_size(size)
        self._load_notebook()
        self._refresh_status()

    def insert_date(self):
        """Type today's date, in red, at the cursor: e.g. 31 MAY 2026."""
        today = datetime.date.today().strftime(DATE_FORMAT).upper()
        self.text.insert("insert", today, "date")
        self._update_pagination()

    def delete_page(self):
        """Delete the lines that make up the page you are on. The document
        always keeps at least one (possibly empty) page."""
        if self._total_pages() == 1:
            if not messagebox.askyesno(APP_NAME, "Clear this page?"):
                return
            self.text.delete("1.0", "end")
        else:
            if not messagebox.askyesno(
                    APP_NAME, f"Delete page {self.current_page + 1}?"):
                return
            page = self.current_page
            start = self.text.index(f"1.0 + {page * self.rows} display lines")
            end = self.text.index(f"1.0 + {(page + 1) * self.rows} display lines")
            self.text.delete(start, end)
        self.modified = True
        self._refresh_pad()                  # restore filler we may have deleted
        self._go_to_page(min(self.current_page, self._total_pages() - 1))

    def next_page(self):
        self._go_to_page(self.current_page + 1)

    def prev_page(self):
        self._go_to_page(self.current_page - 1)

    # -----------------------------------------------------------------------
    # 3f. Saving and opening files
    # -----------------------------------------------------------------------
    def save(self):
        """Save to the known file, or ask where to save the first time."""
        if self.file_path is None:
            return self.save_as()
        self._write_to_disk(self.file_path)

    def save_as(self):
        """Always ask the user for a name and folder, then save there."""
        path = filedialog.asksaveasfilename(
            title="Save notebook",
            defaultextension=FILE_EXT,
            initialfile=self.notebook["name"],
            filetypes=[("Typro notebook", "*" + FILE_EXT)],
        )
        if not path:
            return
        self.file_path = path
        # Use the file name (without folder/extension) as the notebook name.
        self.notebook["name"] = os.path.splitext(os.path.basename(path))[0]
        self._write_to_disk(path)

    def _write_to_disk(self, path):
        self._store_current_view()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.notebook, f, indent=2, ensure_ascii=False)
            self.modified = False
            self.text.edit_modified(False)
            self._refresh_status()
        except OSError as err:
            messagebox.showerror(APP_NAME, f"Could not save:\n{err}")

    def open_notebook(self):
        """Open an existing .typro notebook from disk."""
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            title="Open notebook",
            filetypes=[("Typro notebook", "*" + FILE_EXT), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError, UnicodeDecodeError) as err:
            # ValueError covers json.JSONDecodeError; UnicodeDecodeError covers
            # binary/non-UTF-8 files chosen by mistake.
            messagebox.showerror(APP_NAME, f"Could not open file:\n{err}")
            return
        # A .typro file may come from anyone (it is shareable), so never trust
        # its structure. Rebuild a known-good notebook from it, dropping or
        # repairing anything that does not match the expected shape.
        notebook = self._sanitize_notebook(data)
        if notebook is None:
            messagebox.showerror(APP_NAME, "That file is not a Typro notebook.")
            return
        self.notebook = notebook
        self.file_path = path
        self._apply_paper_size(self.notebook["paper_size"])
        self._load_notebook()
        self._refresh_status()

    def _sanitize_notebook(self, data):
        """Turn untrusted loaded data into a safe, well-formed notebook.

        Returns a clean notebook dictionary, or None if the data cannot be
        recognised as a Typro notebook at all. This is a security boundary:
        only known fields, known types, and known colours are allowed through.
        """
        if not isinstance(data, dict):
            return None
        pages_in = data.get("pages")
        if not isinstance(pages_in, list) or not pages_in:
            return None

        clean_pages = []
        for page in pages_in:
            segs_in = page.get("segments", []) if isinstance(page, dict) else []
            clean_segs = []
            if isinstance(segs_in, list):
                for seg in segs_in:
                    if not isinstance(seg, dict):
                        continue
                    text = seg.get("text", "")
                    if not isinstance(text, str):
                        continue
                    # Only our two known colours are accepted; anything else
                    # (including unexpected tag names) becomes plain black.
                    color = "red" if seg.get("color") == "red" else "black"
                    clean_segs.append({"text": text, "color": color})
            clean_pages.append({"segments": clean_segs})

        size = data.get("paper_size")
        if size not in PAPER_SIZES:
            size = "A4"
        name = data.get("name")
        if not isinstance(name, str) or not name:
            name = "Untitled Notebook"

        return {
            "app": APP_NAME,
            "name": name,
            "paper_size": size,
            "pages": clean_pages,
        }

    # -----------------------------------------------------------------------
    # 3f-bis. Exporting to formats you can open anywhere (PDF / plain text)
    #
    # The .typro file is the EDITABLE format - reopen it in Typro to keep the
    # full layout, red dates, pages and paper size. To read your notes in any
    # other program, export a copy: PDF keeps the exact page look (and the
    # chosen paper size), while plain text is editable everywhere.
    # -----------------------------------------------------------------------
    def export(self):
        """Ask for a name/location and export to PDF or plain text by extension."""
        self._store_current_view()
        path = filedialog.asksaveasfilename(
            title="Export notebook",
            defaultextension=".pdf",
            initialfile=self.notebook["name"],
            filetypes=[("PDF document", "*.pdf"),
                       ("Plain text", "*.txt")],
        )
        if not path:
            return
        try:
            if path.lower().endswith(".txt"):
                self._export_txt(path)
            else:
                # For PDF, ask whether the page should be the vintage cream
                # colour (as shown in the app) or plain white.
                paper_bg = self._ask_pdf_background()
                if paper_bg is None:        # the user cancelled
                    return
                self._export_pdf(path, paper_bg)
        except OSError as err:
            messagebox.showerror(APP_NAME, f"Could not export:\n{err}")
            return
        messagebox.showinfo(APP_NAME, f"Exported to:\n{path}")

    def _ask_pdf_background(self):
        """Keyboard-friendly chooser for the PDF page colour.
        Returns 'cream', 'white', or None if cancelled."""
        win = tk.Toplevel(self.root)
        win.title("PDF page colour")
        win.configure(bg=DESK_COLOR)
        win.transient(self.root)
        win.grab_set()
        choice = {"value": None}

        tk.Label(win, text="PDF page background:", bg=DESK_COLOR, fg=STATUS_FG,
                 font=("Helvetica", 12), pady=8).pack(padx=20)

        def pick(value):
            choice["value"] = value
            win.destroy()

        tk.Button(win, text="1.  Vintage cream (as shown in Typro)",
                  command=lambda: pick("cream"), width=34).pack(padx=20, pady=4)
        tk.Button(win, text="2.  White",
                  command=lambda: pick("white"), width=34).pack(padx=20, pady=4)
        tk.Label(win, text="Press 1 or 2, or Esc to cancel.",
                 bg=DESK_COLOR, fg=STATUS_FG, font=("Helvetica", 9),
                 pady=8).pack()

        win.bind("1", lambda e: pick("cream"))
        win.bind("2", lambda e: pick("white"))
        win.bind("<Escape>", lambda e: win.destroy())
        win.update_idletasks()
        self._center(win)
        self.root.wait_window(win)
        return choice["value"]

    def _export_txt(self, path):
        """Write all pages as plain UTF-8 text (pages separated by a divider)."""
        chunks = []
        for page in self.notebook["pages"]:
            chunks.append("".join(seg["text"] for seg in page["segments"]))
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n\n----------\n\n".join(chunks))

    def _wrap_segments(self, segments, max_chars):
        """Break a page's coloured segments into display lines that fit the
        page width. Returns a list of lines; each line is a list of
        (text, color) runs. Existing newlines force a line break; long lines
        wrap on spaces (and very long words are hard-split)."""
        lines, run_line, length = [], [], 0

        def newline():
            nonlocal run_line, length
            lines.append(run_line)
            run_line, length = [], 0

        def add_word(word, color):
            nonlocal length
            while len(word) > max_chars:                 # word longer than a line
                if length:
                    newline()
                run_line.append((word[:max_chars], color))
                newline()
                word = word[max_chars:]
            if length + len(word) > max_chars and length:
                newline()
            if word:
                run_line.append((word, color))
                length += len(word)

        def add_space(color):
            nonlocal length
            if length and length + 1 <= max_chars:
                run_line.append((" ", color))
                length += 1

        for seg in segments:
            color, word = seg.get("color", "black"), ""
            for ch in seg["text"]:
                if ch == "\n":
                    if word:
                        add_word(word, color); word = ""
                    newline()
                elif ch == " ":
                    if word:
                        add_word(word, color); word = ""
                    add_space(color)
                else:
                    word += ch
            if word:
                add_word(word, color)
        newline()
        return lines

    @staticmethod
    def _pdf_escape(text):
        """Make text safe to place inside a PDF ( ) string."""
        out = text.encode("latin-1", "replace").decode("latin-1")
        return out.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    def _build_pdf(self, paper_bg="white"):
        """Build the whole PDF document as bytes, in the chosen paper size,
        flowing long pages onto extra sheets (a basic 'print flow').

        paper_bg is 'cream' to fill each page with the vintage paper colour, or
        'white' to leave the page white."""
        size = PAPER_SIZES[self.notebook["paper_size"]]
        page_w, page_h = size["pts"]
        margin, fsize = size["margin"], size["pdf_font"]
        leading = fsize * 1.35                       # vertical space per line
        char_w = fsize * 0.6                          # Courier characters are 0.6 em wide
        max_chars = max(1, int((page_w - 2 * margin) / char_w))
        lines_per_sheet = max(1, int((page_h - 2 * margin) / leading))

        # Turn every notebook page into one or more sheets of wrapped lines.
        sheets = []
        for page in self.notebook["pages"]:
            wrapped = self._wrap_segments(page["segments"], max_chars)
            for i in range(0, len(wrapped), lines_per_sheet):
                sheets.append(wrapped[i:i + lines_per_sheet])
        if not sheets:
            sheets = [[]]

        # If the cream background was chosen, the drawing commands that fill the
        # whole page first. (For white we draw nothing - PDF pages are white.)
        bg_cmds = []
        if paper_bg == "cream":
            r, g, b = PDF_CREAM
            bg_cmds = [f"{r:.3f} {g:.3f} {b:.3f} rg",
                       f"0 0 {page_w:.2f} {page_h:.2f} re", "f"]

        # Build a content stream (the drawing commands) for each sheet.
        content_streams = []
        for sheet in sheets:
            cmds = list(bg_cmds)
            cmds += ["BT", f"/F1 {fsize} Tf", f"{leading:.2f} TL",
                     f"1 0 0 1 {margin:.2f} {page_h - margin - fsize:.2f} Tm"]
            for n, line in enumerate(sheet):
                if n > 0:
                    cmds.append("T*")               # move down one line
                for text, color in line:
                    r, g, b = PDF_RGB.get(color, PDF_RGB["black"])
                    cmds.append(f"{r:.3f} {g:.3f} {b:.3f} rg")
                    cmds.append(f"({self._pdf_escape(text)}) Tj")
            cmds.append("ET")
            content_streams.append("\n".join(cmds).encode("latin-1"))

        # Assemble the PDF objects. Object 1 = catalog, 2 = page tree,
        # 3 = font; then a (page, content) pair per sheet.
        objects = []
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(sheets)))
        objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(sheets)} >>"
                       .encode("latin-1"))
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
        for i, stream in enumerate(content_streams):
            content_obj = 4 + 2 * i + 1
            objects.append(
                (f"<< /Type /Page /Parent 2 0 R "
                 f"/MediaBox [0 0 {page_w:.2f} {page_h:.2f}] "
                 f"/Resources << /Font << /F1 3 0 R >> >> "
                 f"/Contents {content_obj} 0 R >>").encode("latin-1"))
            objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\n"
                           b"stream\n" + stream + b"\nendstream")

        # Serialise objects with a cross-reference table (required by PDF).
        out = bytearray(b"%PDF-1.4\n")
        offsets = []
        for n, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
        xref_pos = len(out)
        out += f"xref\n0 {len(objects) + 1}\n".encode()
        out += b"0000000000 65535 f \n"
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_pos}\n%%EOF\n").encode()
        return bytes(out)

    def _export_pdf(self, path, paper_bg="white"):
        with open(path, "wb") as f:
            f.write(self._build_pdf(paper_bg))

    # -----------------------------------------------------------------------
    # 3g. Paper size
    # -----------------------------------------------------------------------
    def choose_paper_size(self):
        size = self._ask_paper_size()
        if size:
            self.notebook["paper_size"] = size
            self._apply_paper_size(size)
            self.modified = True
            self._refresh_status()

    def _ask_paper_size(self):
        """Tiny keyboard-friendly chooser. Returns 'A4', '3x4in', or None."""
        win = tk.Toplevel(self.root)
        win.title("Paper size")
        win.configure(bg=DESK_COLOR)
        win.transient(self.root)
        win.grab_set()
        choice = {"value": None}

        tk.Label(win, text="Choose paper size:", bg=DESK_COLOR, fg=STATUS_FG,
                 font=("Helvetica", 12), pady=8).pack(padx=20)

        def pick(value):
            choice["value"] = value
            win.destroy()

        tk.Button(win, text="1.  A4  (210 x 297 mm)",
                  command=lambda: pick("A4"), width=28).pack(padx=20, pady=4)
        tk.Button(win, text="2.  3 x 4 inch card",
                  command=lambda: pick("3x4in"), width=28).pack(padx=20, pady=4)
        tk.Label(win, text="Press 1 or 2, or Esc to cancel.",
                 bg=DESK_COLOR, fg=STATUS_FG, font=("Helvetica", 9),
                 pady=8).pack()

        win.bind("1", lambda e: pick("A4"))
        win.bind("2", lambda e: pick("3x4in"))
        win.bind("<Escape>", lambda e: win.destroy())
        win.update_idletasks()
        self._center(win)
        self.root.wait_window(win)
        return choice["value"]

    def _apply_paper_size(self, size):
        """Switch the page grid to the chosen paper and re-lay-out. Because the
        document flows continuously, the pages simply re-break to the new size."""
        self.cols = PAPER_SIZES[size]["cols"]
        self.rows = PAPER_SIZES[size]["rows"]
        self.text.configure(width=self.cols, height=self.rows)
        was_modified = self.modified
        self._refresh_pad()                  # filler depends on the new row count
        self.text.edit_modified(False)
        self.modified = was_modified
        self._layout()

    # -----------------------------------------------------------------------
    # 3h. Help window
    # -----------------------------------------------------------------------
    def show_help(self):
        m = MOD_LABEL                         # "Cmd" on macOS, "Ctrl" elsewhere
        text = (
            "TYPRO - KEYBOARD SHORTCUTS\n"
            "============================\n\n"
            f"  {m} + N            New page (page break)\n"
            f"  {m} + Shift + N    New notebook\n"
            f"  {m} + O            Open a .typro notebook\n"
            f"  {m} + S            Save (.typro - editable in Typro)\n"
            f"  {m} + Shift + S    Save as (choose name / folder)\n"
            f"  {m} + P  or  E     Save as PDF / export (PDF or text)\n"
            f"  {m} + D            Insert today's date (red)\n"
            f"  {m} + Delete       Delete the current page\n"
            f"  {m} + Right        Next page\n"
            f"  {m} + Left         Previous page\n"
            f"  {m} + Shift + P    Change paper size (A4 / 3x4 in)\n"
            f"  {m} + B            Key-click sound on/off\n"
            "  F11                Full screen on/off (Esc also exits)\n"
            f"  {m} + Z / {m} + Y    Undo / Redo\n"
            f"  {m} + /  or  F1    This help screen\n"
            f"  {m} + Q            Quit Typro\n\n"
            "Tip: click the round '?' button (bottom-right) any time.\n"
            f"(On macOS the modifier is Command; elsewhere it is Ctrl.)\n"
            "Press Esc to close this window."
        )
        win = tk.Toplevel(self.root)
        win.title("Help")
        win.configure(bg=PAPER_COLOR)
        win.transient(self.root)
        win.grab_set()
        tk.Label(win, text=text, justify="left", bg=PAPER_COLOR, fg=TEXT_COLOR,
                 font=self.type_font, padx=24, pady=20).pack()
        win.bind("<Escape>", lambda e: win.destroy())
        win.update_idletasks()
        self._center(win)
        win.focus_set()

    # -----------------------------------------------------------------------
    # 3i. Quitting safely
    # -----------------------------------------------------------------------
    def quit_app(self):
        if self._confirm_discard():
            self.root.destroy()

    def _confirm_discard(self):
        """If there are unsaved changes, ask what to do. Return True to proceed."""
        if not self.modified:
            return True
        answer = messagebox.askyesnocancel(
            APP_NAME, "You have unsaved changes. Save before continuing?")
        if answer is None:        # Cancel -> do not proceed
            return False
        if answer:                # Yes -> save first
            self.save()
            return not self.modified   # only proceed if the save succeeded
        return True               # No -> discard and proceed

    # -----------------------------------------------------------------------
    # 3j. Status bar and misc
    # -----------------------------------------------------------------------
    def _on_text_modified(self, _event):
        if self.text.edit_modified():
            self.modified = True
            self.text.edit_modified(False)
            self._refresh_status()

    def _refresh_status(self):
        dot = "*" if self.modified else ""
        size_label = PAPER_SIZES[self.notebook["paper_size"]]["label"]
        page_info = f"Page {self.current_page + 1} of {self._total_pages()}"
        snd = "Sound: on" if self.sound_on else "Sound: off"
        self.status.config(
            text=f"  {dot}{self.notebook['name']}    |    "
                 f"{page_info}    |    {size_label}    |    "
                 f"{snd}    |    {MOD_LABEL}+/ = Help"
        )

    def _center(self, win):
        """Place a pop-up window in the middle of the screen."""
        w, h = win.winfo_width(), win.winfo_height()
        x = (win.winfo_screenwidth() - w) // 2
        y = (win.winfo_screenheight() - h) // 2
        win.geometry(f"+{x}+{y}")


# ---------------------------------------------------------------------------
# 4. START THE PROGRAM
#    This block only runs when you launch the file directly (python3 typro.py)
# ---------------------------------------------------------------------------
# Typro needs the GUI runtime "Tk" version 8.6 or newer. macOS used to bundle a
# very old Tk 8.5 with its built-in Python; that old version crashes on modern
# macOS. We check the version up front and exit with a clear, friendly message
# instead of letting the old library crash with a confusing error.
MIN_TK = (8, 6)


def _tk_too_old_message(found):
    return (
        f"{APP_NAME} needs Tk 8.6 or newer, but this Python is using Tk "
        f"{found}.\n\n"
        "The Tk that ships with Apple's built-in Python is outdated and "
        "crashes on modern macOS. Install a newer Python and run Typro with "
        "it. The simplest fix on a Mac with Homebrew:\n\n"
        "    brew install python-tk\n"
        "    /opt/homebrew/bin/python3 typro.py\n\n"
        "Or install Python from https://www.python.org/downloads/ (it bundles "
        "a modern Tk) and run it with that python3.\n\n"
        "Note: the Raspberry Pi is not affected - it already uses Tk 8.6."
    )


def main():
    root = tk.Tk()

    # Read the Tk version safely (this does not start the event loop, so the
    # old-Tk crash cannot happen here).
    patchlevel = root.tk.call("info", "patchlevel")        # e.g. "8.5.9"
    version = tuple(int(part) for part in patchlevel.split(".")[:2])
    if version < MIN_TK:
        message = _tk_too_old_message(patchlevel)
        print(message)                  # visible in the Terminal / launcher
        root.destroy()
        sys.exit(1)

    Typro(root)
    root.mainloop()


if __name__ == "__main__":
    main()
