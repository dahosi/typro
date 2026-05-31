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

- **Two-colour ribbon** — black text, and **red dates** in `DD MON YYYY`
  format (e.g. `31 MAY 2026`), inserted with one shortcut.
- **Real-size pages on a textured desk** — your text sits on a cream sheet,
  drawn at the true proportions of the paper you chose (A4 or the 3 × 4 card),
  resting on a textured brown desk in the project's brand colours — so what you
  see is what the PDF/print will look like.
- **Automatic page flow** — when a page fills to the bottom, typing continues on
  a new page automatically; the on-screen page breaks match the PDF exactly.
  Move between pages with `Ctrl + Left` / `Ctrl + Right`, or start a fresh page
  with `Ctrl + N`.
- **Pages & notebooks** — create single pages, or a **notebook** whose pages
  are all saved together in one file.
- **Full document control** — new, save, save-as, open, edit, and delete pages.
- **Paper sizes** — choose **A4** or a **3 × 4 inch** card.
- **Export to open formats** — export to **PDF** (keeps the exact page layout,
  black/red colours, and chosen paper size, flowing long notes across pages) or
  **plain text** (`.txt`), so you can open your notes in any program. On PDF
  export you choose the page background: **vintage cream** (as shown in the app)
  or **white**.
- **You choose where & under what name** to save (standard save dialog).
- **Opens full screen** — launches like a dedicated writing appliance; press
  `F11` (or `Esc`) to drop to a window.
- **Typewriter key-click sound** — a soft "clack" as you type, with an on/off
  toggle (`Ctrl+B`).
- **Keyboard only** — every action has a shortcut; no mouse required.
- **Built-in help** — press `Ctrl+/` (or `F1`), or click the floating round
  **?** button in the bottom-right corner, for the full shortcut list.
- **App icon** — a bundled typewriter icon (in `img/`) is used for the window,
  the taskbar/Dock, and the desktop launchers, so Typro is easy to spot and to
  switch between with your other open apps.
- **Fully offline** — no network, no accounts, no telemetry.
- **Open file format** — notebooks are plain-text JSON (`.typro`), so your
  writing is never locked in; PDF/TXT export gives universally-openable copies.

## Keyboard shortcuts

> **The modifier key is `Ctrl` on Windows / Raspberry Pi / Linux and `⌘ Command`
> on macOS.** The table uses `Ctrl`; on a Mac, read every `Ctrl` as `Cmd`
> (e.g. `Cmd + S` to save). Typro picks the right one automatically.

| Shortcut            | Action                                  |
| ------------------- | --------------------------------------- |
| `Ctrl + N`          | New page (page break)                   |
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
| `Ctrl + B`          | Key-click sound on/off                  |
| `F11`               | Full screen on/off (`Esc` also exits)   |
| `Ctrl + Z` / `Ctrl + Y` | Undo / Redo                         |
| `Ctrl + /` or `F1`  | Help (this list) — also the **?** button |
| `Ctrl + Q`          | Quit                                    |

> **macOS note:** Typro uses **`⌘ Command`** as the modifier on macOS (so it
> feels native), and **`Ctrl`** on Windows / Raspberry Pi / Linux. Also, the
> function keys are taken by macOS, so **`F1` may not open Help unless you hold
> `Fn`** — use **`Cmd + /`** or the **?** button. On the Raspberry Pi, `F1`
> works normally.

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
cd path/to/typro
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

## App icon

The icons live in the `img/` folder. Typro loads one automatically at startup
for the **window and taskbar**:

- **Raspberry Pi / Linux & Windows:** the app uses
  `img/typewriter_icon_128x128.png` (Windows also uses `img/typewriter_icon.ico`
  if present). It appears in the title bar and the taskbar, so you can switch
  to Typro like any other app.
- **macOS:** Tkinter can show the PNG as the window icon, but the **Dock** icon
  of a script run with `python3` is controlled by the system. To get the
  typewriter icon in the Dock, bundle the app with the provided
  `img/typewriter_icon.icns` (e.g. via `py2app`) — optional and outside the
  single-file scope.

For the **desktop launchers**:

- **Raspberry Pi:** `typro.desktop` already points its `Icon=` line at
  `img/typewriter_icon_128x128.png` (adjust the path to where you put the
  project).
- **Windows:** when you make a shortcut to `Typro.bat`, set its icon via
  *Properties → Change Icon…* and choose `img/typewriter_icon.ico`.
- **macOS:** to give `Typro.command` a custom icon in Finder, copy
  `img/typewriter_icon.icns`, then *Get Info* on the launcher and paste it onto
  the icon in the top-left.

> The app still runs fine if an icon file is missing — it just falls back to the
> default icon.

---

## Theme & brand colours

Typro is themed in the project's brand palette:

`#b81106` `#830a06` `#1f140f` `#d4b9a5` `#ad5e33` `#a88b75` `#cf845b` `#4c3126` `#783c1d`

- **Desk background:** `#4a2f24` with a subtle leather grain.
- **Ink:** near-black `#1f140f`; **dates:** brand red `#b81106`.
- **Status bar:** `#1f140f` with `#d4b9a5` text; **the "?" button:** `#cf845b`.
- **Paper:** vintage cream (`#F5ECD7`) for the classic typewriter look.

All colours live as constants at the top of `typro.py`, so the theme is easy to
adjust in one place.

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
| `.pdf`    | `Ctrl + E`    | **Open/print/share anywhere** — keeps the exact page layout, black/red colours, and the chosen paper size; long notes flow across pages. You pick a **cream** or **white** page background on export. |
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

- A **notebook** is one `.typro` file — your whole document.
- Inside it, text flows across **pages** automatically, sized to the paper you
  chose. You don't manage page edges by hand: fill a page and the next one
  appears; delete text and the following pages flow back up.

`Ctrl + Left` / `Ctrl + Right` move between pages, `Ctrl + N` starts a fresh
page (a page break), and `Ctrl + Delete` removes the current page. `Ctrl + S`
saves the whole notebook at once. The status bar shows *Page X of Y*.

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
├── Typro.command       # macOS double-click launcher
├── Typro.bat           # Windows double-click launcher
├── typro.desktop       # Raspberry Pi / Linux launcher
└── img/                # app icons (see "App icon" below)
    ├── typewriter_icon.icns           # macOS app-bundle icon
    ├── typewriter_icon.ico            # Windows shortcut icon
    ├── typewriter_icon_128x128.png    # window / taskbar icon (used by the app)
    ├── typewriter_icon_48x48.png      # small icon
    └── typewriter_icon_color.svg      # scalable source
```

## Roadmap / ideas

- Optional "carriage return" bell sound on Enter.
- A simple settings file to remember your last folder and font size.
- Word/character count in the status bar.
- Choice of date format and ribbon colour.

## License

Open-source project by **dahosi**, released under the MIT License. Free to use,
read, learn from, modify, and share.
# typro
