#!/usr/bin/env python3
"""
Typro - An offline, keyboard-only typewriter for the Raspberry Pi.

Visual inspiration: Olympia SM3 (Italic typeface, 1956).
- Vintage cream "paper" background, black text, red dates.
- No mouse required: every action has a keyboard shortcut.
- Works fully offline. Saves notebooks as plain .typro files (JSON inside).

This is a single-file program written with Python's built-in Tkinter toolkit,
so it runs the same on macOS (for testing) and on Raspberry Pi OS.

Author: mholanda
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

PAPER_COLOR   = "#F5ECD7"                 # cream / yellowish vintage paper
DESK_COLOR    = "#3B342B"                 # dark "desk" behind the paper
TEXT_COLOR    = "#1A1A1A"                 # near-black, softer than pure black
DATE_COLOR    = "#B22222"                 # firebrick red, like a 2-colour ribbon
STATUS_BG     = "#2A2520"                 # dark strip at the bottom
STATUS_FG     = "#E8DFC8"                 # light text on the dark strip

# Preferred fonts, best first. We pick the first one your computer actually has.
# Courier Prime and TT2020 are free classic typewriter fonts (see README).
FONT_WISHLIST = ["Courier Prime", "TT2020", "Courier New", "Courier"]
FONT_SIZE     = 14

# Paper sizes.
#   cols      = how many characters fit across one line on screen.
#   pts       = the real page size in PDF points (1 point = 1/72 inch),
#               used when exporting to PDF so the file matches the paper.
#   margin    = blank border in points around the PDF text.
#   pdf_font  = font size in points used in the exported PDF.
PAPER_SIZES = {
    "A4":    {"cols": 78, "rows": 34, "label": "A4 (210 x 297 mm)",
              "pts": (595.28, 841.89), "margin": 56.7, "pdf_font": 11},
    "3x4in": {"cols": 30, "rows": 22, "label": "3 x 4 inch card",
              "pts": (216.0, 288.0),   "margin": 18.0, "pdf_font": 9},
}

# Text colours expressed for PDF (red/green/blue, each 0.0 to 1.0).
PDF_RGB = {"black": (0.0, 0.0, 0.0), "red": (0.698, 0.133, 0.133)}

# The date format the user asked for: DD MON YYYY  ->  e.g. 31 MAY 2026
DATE_FORMAT = "%d %b %Y"


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
        self.current_page = 0          # which page we are looking at (0 = first)
        self.file_path = None          # where this notebook lives on disk
        self.modified = False          # True if there are unsaved changes

        # ---- Typewriter view ------------------------------------------------
        # When on, the line you are typing stays at the TOP and earlier lines
        # scroll up out of sight (you can scroll back up to read them), like
        # paper feeding up through a real typewriter. We do this by keeping a
        # block of blank "filler" lines below your text (tagged so they are
        # never saved) so that even the last line can be scrolled to the top.
        self.typewriter_mode = True

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
        self._load_page_into_view(self.current_page)
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

    # -----------------------------------------------------------------------
    # 3b. Building the visible window
    # -----------------------------------------------------------------------
    def _build_window(self):
        self.root.title(APP_NAME)
        self.root.configure(bg=DESK_COLOR)
        self.root.geometry("900x680")          # the size if you leave fullscreen
        self.root.minsize(640, 480)
        self.root.attributes("-fullscreen", self.fullscreen)   # open fullscreen

        # The "desk" area that surrounds the paper.
        self.desk = tk.Frame(self.root, bg=DESK_COLOR)
        self.desk.pack(fill="both", expand=True)
        desk = self.desk

        # The "paper": a Text widget the user types into.
        # We wrap on whole words so text never gets cut mid-word.
        cols = PAPER_SIZES[self.notebook["paper_size"]]["cols"]
        self.text = tk.Text(
            desk,
            width=cols,
            wrap="word",
            font=self.type_font,
            bg=PAPER_COLOR,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,   # the blinking cursor colour
            padx=28, pady=28,              # margins inside the paper
            spacing1=2, spacing3=2,        # a little breathing room per line
            relief="flat",
            borderwidth=0,
            undo=True,                     # enables Ctrl+Z / Ctrl+Y
            highlightthickness=0,
        )
        # Centre the paper on the desk with some margin around it.
        self.text.pack(expand=True, padx=40, pady=30)

        # Define the "date" style: any text tagged "date" turns red.
        self.text.tag_configure("date", foreground=DATE_COLOR)
        # The "pad" style marks the blank filler lines so we never save them.
        self.text.tag_configure("pad")

        # Whenever the user types, remember that there are unsaved changes.
        self.text.bind("<<Modified>>", self._on_text_modified)

        # Typewriter view: after each key, keep the current line at the top.
        self.text.bind("<KeyRelease>", self._typewriter_scroll)
        # Play the key-click sound as keys go down.
        self.text.bind("<KeyPress>", self._play_click)

        # The status strip along the bottom.
        self.status = tk.Label(
            self.root, anchor="w", bg=STATUS_BG, fg=STATUS_FG,
            font=("Helvetica", 11), padx=12, pady=4,
        )
        self.status.pack(side="bottom", fill="x")

        # A floating round "?" button in the bottom-right corner that opens the
        # shortcuts help. It is a visible hint; the keyboard (F1) still works.
        self._build_help_button(self.desk)

        self.text.focus_set()   # so the user can type immediately

    def _build_help_button(self, parent):
        """A small round brass '?' button, bottom-right, that opens Help."""
        size = 44
        btn = tk.Canvas(parent, width=size, height=size, bg=DESK_COLOR,
                        highlightthickness=0, bd=0, cursor="hand2")
        btn.create_oval(3, 3, size - 3, size - 3, fill="#C9A24B", outline="")
        btn.create_text(size // 2, size // 2 - 1, text="?",
                        fill="#2A2520", font=("Helvetica", 20, "bold"))
        btn.bind("<Button-1>", lambda e: self.show_help())
        btn.bind("<Enter>", lambda e: self._show_tip(btn, "Keyboard shortcuts (F1)"))
        btn.bind("<Leave>", lambda e: self._hide_tip())
        btn.place(relx=1.0, rely=1.0, anchor="se", x=-18, y=-18)
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
        b = self.root.bind_all
        b("<Control-n>",        lambda e: self.new_page())
        b("<Control-N>",        lambda e: self.new_page())
        b("<Control-Shift-N>",  lambda e: self.new_notebook())
        b("<Control-s>",        lambda e: self.save())
        b("<Control-Shift-S>",  lambda e: self.save_as())
        b("<Control-o>",        lambda e: self.open_notebook())
        b("<Control-d>",        lambda e: self.insert_date())
        b("<Control-Delete>",   lambda e: self.delete_page())
        b("<Control-Right>",    lambda e: self.next_page())
        b("<Control-Left>",     lambda e: self.prev_page())
        b("<Control-p>",        lambda e: self.export())          # "Print" -> PDF
        b("<Control-e>",        lambda e: self.export())
        b("<Control-Shift-P>",  lambda e: self.choose_paper_size())
        b("<Control-m>",        lambda e: self.toggle_typewriter())
        b("<Control-b>",        lambda e: self.toggle_sound())
        b("<F11>",              lambda e: self.toggle_fullscreen())
        # Help: F1 works on the Raspberry Pi; on macOS the F-keys are taken by
        # the system, so Ctrl+/ is the reliable shortcut (the "?" button always
        # works too).
        b("<F1>",               lambda e: self.show_help())
        b("<Control-slash>",    lambda e: self.show_help())
        # Esc leaves full screen (only from the typing area, so it does not
        # clash with Esc closing a pop-up window).
        self.text.bind("<Escape>", self._exit_fullscreen)
        b("<Control-q>",        lambda e: self.quit_app())
        # When the window's close button is used, run our safe-quit routine.
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)

    # -----------------------------------------------------------------------
    # 3d. Converting between the typing area and our saved data
    # -----------------------------------------------------------------------
    def _view_to_segments(self):
        """Read the typing area and return a list of {text, color} segments.

        We 'dump' the Text widget, which gives us the characters in order plus
        markers for where the red 'date' style turns on and off.
        """
        segments = []
        color = "black"
        in_padding = False
        for key, value, _index in self.text.dump("1.0", "end-1c",
                                                  tag=True, text=True):
            if key == "tagon" and value == "date":
                color = "red"
            elif key == "tagoff" and value == "date":
                color = "black"
            elif key == "tagon" and value == "pad":
                in_padding = True
            elif key == "tagoff" and value == "pad":
                in_padding = False
            elif key == "text" and not in_padding:
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
        self._add_padding()                  # blank filler lines for typewriter view
        self.text.mark_set("insert", "1.0")  # start at the top of the sheet
        self.text.edit_reset()               # so filler/loading can't be "undone"

    # -----------------------------------------------------------------------
    # 3d-bis. Typewriter view: keep the current line at the top
    # -----------------------------------------------------------------------
    def _pad_count(self):
        """How many blank filler lines to keep below the text: about a full
        screen's worth, so even the last line can be scrolled to the top."""
        line = max(1, self.type_font.metrics("linespace"))
        return self.text.winfo_screenheight() // line

    def _add_padding(self):
        """Append blank filler lines (tagged 'pad' so they are never saved)."""
        if not self.typewriter_mode:
            return
        self.text.insert("end", "\n" * self._pad_count(), "pad")

    def _remove_padding(self):
        """Delete the blank filler lines, if any."""
        spans = self.text.tag_ranges("pad")
        # tag_ranges returns pairs (start, end); delete each pair.
        for i in range(0, len(spans), 2):
            self.text.delete(spans[i], spans[i + 1])

    def _typewriter_scroll(self, _event=None):
        """After typing, scroll so the line with the cursor sits at the top.
        The blank filler below gives the room to do this on the last line too."""
        if not self.typewriter_mode:
            return
        self.text.update_idletasks()
        self.text.see("insert")
        first = int(self.text.index("@0,0").split(".")[0])
        current = int(self.text.index("insert").split(".")[0])
        if current > first:
            self.text.yview_scroll(current - first, "units")

    def toggle_typewriter(self):
        """Turn the top-line typewriter view on or off."""
        was_modified = self.modified          # adding/removing filler must not
        self.typewriter_mode = not self.typewriter_mode   # count as an edit
        if self.typewriter_mode:
            self._add_padding()
            self._typewriter_scroll()
        else:
            self._remove_padding()
            self.text.see("insert")
        self.text.edit_modified(False)
        self.modified = was_modified
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
            if event.state & 0x0004:          # Control held -> it's a shortcut
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
        """Save whatever is on screen back into the current page in memory."""
        self.notebook["pages"][self.current_page]["segments"] = \
            self._view_to_segments()

    def _load_page_into_view(self, index):
        """Show page number `index` in the typing area."""
        self.current_page = index
        self._segments_to_view(self.notebook["pages"][index]["segments"])
        self._typewriter_scroll()
        # Loading text fires <<Modified>>, so reset the flag afterwards.
        self.text.edit_modified(False)
        self.modified = False

    # -----------------------------------------------------------------------
    # 3e. Actions the user triggers with shortcuts
    # -----------------------------------------------------------------------
    def new_page(self):
        """Add a blank page to the current notebook and jump to it."""
        self._store_current_view()
        self.notebook["pages"].append(self._blank_page())
        self._load_page_into_view(len(self.notebook["pages"]) - 1)
        self.modified = True
        self._refresh_status()

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
        self._load_page_into_view(0)
        self._refresh_status()

    def insert_date(self):
        """Type today's date, in red, at the cursor: e.g. 31 MAY 2026."""
        today = datetime.date.today().strftime(DATE_FORMAT).upper()
        self.text.insert("insert", today, "date")
        self._typewriter_scroll()

    def delete_page(self):
        """Delete the page you are on (a notebook always keeps >= 1 page)."""
        if len(self.notebook["pages"]) == 1:
            messagebox.showinfo(
                APP_NAME, "This is the only page - it cannot be deleted.")
            return
        if not messagebox.askyesno(
                APP_NAME, f"Delete page {self.current_page + 1}?"):
            return
        del self.notebook["pages"][self.current_page]
        new_index = max(0, self.current_page - 1)
        self._load_page_into_view(new_index)
        self.modified = True
        self._refresh_status()

    def next_page(self):
        self._store_current_view()
        if self.current_page < len(self.notebook["pages"]) - 1:
            self._load_page_into_view(self.current_page + 1)
        self._refresh_status()

    def prev_page(self):
        self._store_current_view()
        if self.current_page > 0:
            self._load_page_into_view(self.current_page - 1)
        self._refresh_status()

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
        self._load_page_into_view(0)
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
                self._export_pdf(path)
        except OSError as err:
            messagebox.showerror(APP_NAME, f"Could not export:\n{err}")
            return
        messagebox.showinfo(APP_NAME, f"Exported to:\n{path}")

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

    def _build_pdf(self):
        """Build the whole PDF document as bytes, in the chosen paper size,
        flowing long pages onto extra sheets (a basic 'print flow')."""
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

        # Build a content stream (the drawing commands) for each sheet.
        content_streams = []
        for sheet in sheets:
            cmds = ["BT", f"/F1 {fsize} Tf", f"{leading:.2f} TL",
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

    def _export_pdf(self, path):
        with open(path, "wb") as f:
            f.write(self._build_pdf())

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
        """Resize the typing area to match the chosen paper."""
        self.text.configure(width=PAPER_SIZES[size]["cols"])

    # -----------------------------------------------------------------------
    # 3h. Help window
    # -----------------------------------------------------------------------
    def show_help(self):
        text = (
            "TYPRO - KEYBOARD SHORTCUTS\n"
            "============================\n\n"
            "  Ctrl + N           New page (in this notebook)\n"
            "  Ctrl + Shift + N   New notebook\n"
            "  Ctrl + O           Open a .typro notebook\n"
            "  Ctrl + S           Save (.typro - editable in Typro)\n"
            "  Ctrl + Shift + S   Save as (choose name / folder)\n"
            "  Ctrl + P  or  E    Save as PDF / export (PDF or text)\n"
            "  Ctrl + D           Insert today's date (red)\n"
            "  Ctrl + Delete      Delete the current page\n"
            "  Ctrl + Right       Next page\n"
            "  Ctrl + Left        Previous page\n"
            "  Ctrl + Shift + P   Change paper size (A4 / 3x4 in)\n"
            "  Ctrl + M           Typewriter view on/off (line at top)\n"
            "  Ctrl + B           Key-click sound on/off\n"
            "  F11                Full screen on/off (Esc also exits)\n"
            "  Ctrl + Z / Ctrl+Y  Undo / Redo\n"
            "  Ctrl + /  or  F1   This help screen\n"
            "  Ctrl + Q           Quit Typro\n\n"
            "Tip: click the round '?' button (bottom-right) any time.\n"
            "(On macOS, F1 may need the Fn key; Ctrl + / always works.)\n"
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
        page_info = f"Page {self.current_page + 1} of {len(self.notebook['pages'])}"
        tw = "Typewriter: on" if self.typewriter_mode else "Typewriter: off"
        snd = "Sound: on" if self.sound_on else "Sound: off"
        self.status.config(
            text=f"  {dot}{self.notebook['name']}    |    "
                 f"{page_info}    |    {size_label}    |    {tw}    |    "
                 f"{snd}    |    Ctrl+/ = Help"
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
