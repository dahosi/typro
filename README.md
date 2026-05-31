# Typro — An Offline Raspberry Pi Typewriter

> A distraction-free, keyboard-only writing app for the Raspberry Pi, styled
> after the **Olympia SM3 (Italic typeface, 1956)**. Cream vintage paper,
> black ink, red dates. No mouse. No internet. Just you and the page.

![status](https://img.shields.io/badge/status-working-brightgreen)
![python](https://img.shields.io/badge/python-3.7%2B-blue)
![platform](https://img.shields.io/badge/platform-Raspberry%20Pi%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## What it is

Typro turns a Raspberry Pi (or any computer) into a focused digital typewriter.
It is built in a single Python file using **Tkinter**, the graphical toolkit
that ships with Python — so there is nothing to download and it runs completely
offline. Everything you write is saved locally to the Pi's storage (internal or
a microSD card).

The design borrows from the Olympia SM3: warm brown/cream tones, a classic
monospaced typewriter font, and the two-colour ribbon look where **dates print
in red** and everything else prints in **black**.

## Features

- **Vintage paper look** — cream/yellowish page on a dark "desk" background.
- **Two-colour ribbon** — black text, and **red dates** in `DD MON YYYY`
  format (e.g. `31 MAY 2026`), inserted with one shortcut.
- **Typewriter view** — the line you are typing stays at the **top** of the
  page and earlier lines scroll up out of sight, like paper feeding through a
  real typewriter. Scroll up any time to re-read what you wrote. Toggle on/off.
- **Pages & notebooks** — create single pages, or a **notebook** whose pages
  are all saved together in one file.
- **Full document control** — new, save, save-as, open, edit, and delete pages.
- **Paper sizes** — choose **A4** or a **3 × 4 inch** card.
- **Export to open formats** — export to **PDF** (keeps the exact page layout,
  black/red colours, and chosen paper size, flowing long notes across pages) or
  **plain text** (`.txt`), so you can open your notes in any program.
- **You choose where & under what name** to save (standard save dialog).
- **Opens full screen** — launches like a dedicated writing appliance; press
  `F11` (or `Esc`) to drop to a window.
- **Typewriter key-click sound** — a soft "clack" as you type, with an on/off
  toggle (`Ctrl+B`).
- **Keyboard only** — every action has a shortcut; no mouse required.
- **Built-in help** — press `Ctrl+/` (or `F1`), or click the floating round
  **?** button in the bottom-right corner, for the full shortcut list.
- **Fully offline** — no network, no accounts, no telemetry.
- **Open file format** — notebooks are plain-text JSON (`.typro`), so your
  writing is never locked in; PDF/TXT export gives universally-openable copies.

## Keyboard shortcuts

| Shortcut            | Action                                  |
| ------------------- | --------------------------------------- |
| `Ctrl + N`          | New page in the current notebook        |
| `Ctrl + Shift + N`  | New notebook                            |
| `Ctrl + O`          | Open a `.typro` notebook                |
| `Ctrl + S`          | Save (`.typro`, editable in Typro)      |
| `Ctrl + Shift + S`  | Save as (choose name / folder)          |
| `Ctrl + P` or `Ctrl + E` | Save as PDF / export (PDF or text) |
| `Ctrl + D`          | Insert today's date (red)               |
| `Ctrl + Delete`     | Delete the current page                 |
| `Ctrl + Right`      | Next page                               |
| `Ctrl + Left`       | Previous page                           |
| `Ctrl + Shift + P`  | Change paper size (A4 / 3×4 in)         |
| `Ctrl + M`          | Typewriter view on/off (line at top)    |
| `Ctrl + B`          | Key-click sound on/off                  |
| `F11`               | Full screen on/off (`Esc` also exits)   |
| `Ctrl + Z` / `Ctrl + Y` | Undo / Redo                         |
| `Ctrl + /` or `F1`  | Help (this list) — also the **?** button |
| `Ctrl + Q`          | Quit                                    |

> **macOS note:** the function keys are taken by the system, so **`F1` may not
> open Help unless you also hold `Fn`**. Use **`Ctrl + /`** or the **?** button
> instead. On the Raspberry Pi, `F1` works normally.

> On a Mac, `Ctrl` still works for these shortcuts (Typro uses `Ctrl`, not
> `Cmd`, so the behaviour matches the Raspberry Pi exactly).

---

## Running it

### On macOS (for development / testing)

> Apple's built-in Python uses an outdated **Tk 8.5** that crashes on modern
> macOS. Install a modern Python with a current Tk first (one time):
> ```bash
> brew install python-tk      # or install from https://www.python.org/downloads/
> ```

Then run:

```bash
cd /Users/mholanda/Developer/typro
python3 typro.py
```

Typro requires **Tk 8.6+** and checks this at startup, exiting with a clear
message instead of crashing if it finds an older Tk.

### On the Raspberry Pi

Raspberry Pi OS includes Python 3 but sometimes not the Tk package. Install it
once:

```bash
sudo apt update
sudo apt install -y python3-tk
```

Then copy `typro.py` onto the Pi (USB stick, microSD, or `scp`) and run:

```bash
python3 typro.py
```

To launch it like a real appliance — full screen, on boot — see
**"Kiosk mode"** below.

---

## Fonts (free, classic typewriter look)

Typro automatically picks the first font it finds from this list:

1. **Courier Prime** — free, polished typewriter font (SIL Open Font License).
   Download: <https://fonts.google.com/specimen/Courier+Prime>
2. **TT2020** — free vintage typewriter font with subtle irregularities.
   Download: <https://github.com/ctrlcctrlv/TT2020>
3. **Courier New** — present on most systems.
4. **Courier** — universal fallback.

To install a font on the Raspberry Pi, copy its `.ttf` files into
`~/.local/share/fonts/` and run `fc-cache -f`. Restart Typro and it will use it.

---

## Where your writing is saved

When you save, Typro asks for a **name** and a **folder**. You can point it at:

- the Pi's internal storage (e.g. `/home/pi/Documents`), or
- an external microSD / USB drive (e.g. `/media/pi/MY_CARD`).

Each notebook is one `.typro` file. It is human-readable JSON, so even without
Typro you can open it in any text editor and read your words.

### File formats: which one to use

| Format    | Made with     | Use it to…                                              |
| --------- | ------------- | ------------------------------------------------------- |
| `.typro`  | `Ctrl + S`    | **Keep editing in Typro** — preserves pages, red dates, paper size, and the full UI. This is your working copy. |
| `.pdf`    | `Ctrl + E`    | **Open/print/share anywhere** — keeps the exact page layout, black/red colours, and the chosen paper size; long notes flow across pages. |
| `.txt`    | `Ctrl + E`    | Plain editable text in any program (loses colour and layout). |

> Rule of thumb: **save as `.typro`** while you are writing, and **export a PDF**
> when you want to read or share your notes outside Typro. Re-opening a `.typro`
> file restores everything exactly as you left it.

Example of what a saved `.typro` file looks like:

```json
{
  "app": "Typro",
  "name": "My Diary",
  "paper_size": "A4",
  "pages": [
    { "segments": [
        { "text": "31 MAY 2026", "color": "red" },
        { "text": "\nDear diary, today I built a typewriter.", "color": "black" }
    ] }
  ]
}
```

---

## Pages vs. notebooks

- A **page** is a single sheet you type on.
- A **notebook** is a collection of pages stored together in one `.typro` file.

When you start Typro you are already in a notebook (called *Untitled Notebook*)
with one blank page. `Ctrl+N` adds more pages to it; `Ctrl+S` saves them all at
once. If you only ever make one page, that's fine too — it just becomes a
one-page notebook.

---

## Kiosk mode (optional: behave like a real typewriter)

To make the Pi boot straight into Typro, full screen, edit the autostart file:

```bash
mkdir -p ~/.config/autostart
nano ~/.config/autostart/typro.desktop
```

Paste:

```ini
[Desktop Entry]
Type=Application
Name=Typro
Exec=python3 /home/pi/typro/typro.py
X-GNOME-Autostart-enabled=true
```

(Adjust the path to wherever you copied `typro.py`.) Typro already **opens in
full screen** by default, so combined with autostart the Pi behaves like a
dedicated typewriter. Press `F11` or `Esc` to leave full screen if needed.

---

## Project structure

```
typro/
├── typro.py            # the entire application (one file)
├── README.md           # this file — what the project is and how to use it
├── QUICKSTART.md       # minimal "how to open it" steps per OS
├── SHORTCUTS.md        # full keyboard shortcut reference
├── INSTALL.md          # detailed install/run guide + troubleshooting
├── LAUNCHERS.md        # double-click launchers and adding an icon
├── Typro.command       # macOS double-click launcher
├── Typro.bat           # Windows double-click launcher
├── typro.desktop       # Raspberry Pi / Linux launcher
├── REQUIREMENTS.md     # software requirements specification
├── TESTING.md          # the test plan
├── SECURITY.md         # security policy and review
├── CODE_EXPLAINED.md   # the code explained line-by-line for beginners
└── PROMPT.md           # the project brief, written professionally
```

## Roadmap / ideas

- Optional "carriage return" bell sound on Enter.
- A simple settings file to remember your last folder and font size.
- Word/character count in the status bar.
- Choice of date format and ribbon colour.

## License

Personal portfolio project by **mholanda**. Free to read, learn from, and
adapt.
# typro
