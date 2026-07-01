# QDVC Equip

A lightweight three-pane desktop tracker for your **tools, equipment, and
materials** — for home, work, travel, and anywhere else — built with
**GTK 3 / PyGObject** for a native MATE / GNOME2-era look and feel (think Pluma
and Atril).

- Vibe-coding details in [vibe-coding/](vibe-coding/)
- See [MAINTENANCE.md](MAINTENANCE.md) for architecture and maintainer notes.

## Asset file format

```yaml
name: Coffee Machine
genre: appliances
emoji: ☕
location_notes: "You might need to move aside the cartons of UHT milk which may be
  blocking your view of the coffee machine."
asset_information:
  asset_tag: SDR892314T
  retailer: Beverages 4 YOU
  manufacturer: Coffee Machines Inc.
  model: Cino Grande XL Gen. 2
  serial_number: 689D857D6
  receipt_ref: AUx8RVRQAU
  purchased: 2026-07-01
  price: 251.50 EUR
```

Everything except `name` is optional. The asset's **location is not stored** in
the file — it is derived from the folders the file is nested in. Keys under
`asset_information` are written in `snake_case` (matching the project naming
convention) and **humanized for display** in the Preview pane, where their
values are column-aligned and each gets a `[copy]` button. In the item list
(pane 2) each asset is labelled by its `name`.

The optional top-level `genre` groups an asset under one of the built-in
genres (see below). Unlike everything else, a genre is shown **verbatim** —
never humanized (`laptop-docks`, not "Laptop Docks"). A `purchased` date
(`YYYY-MM-DD`) is rendered in Preview as a friendly date plus the asset's age,
e.g. `Wed 01 Jul 2026 (52d)` under a year old, or `Fri 14 Oct 2022 (3.7y)`
beyond it.

## Genres

An asset may set `genre:` to one of the built-in genres, each mapped to a
system icon shown for that asset in the item list (pane 2): `appliances`,
`audio`, `baby`, `cables`, `chargers`, `components`, `displays`,
`electronics`, `hdd`, `infrastructure`, `lights`, `keyboards`, `laptop-docks`,
`laptops`, `printers`, `psu`, `smartphones`, `ssd`, `wearables`. The icons come
from the host Linux icon theme; you can override any genre's icon with your own
image under **Edit → Preferences → Genres**, which also lists which genres
currently have custom icons and offers a one-click reset.

The navigation tree (pane 1) has, in order: **All Assets**; **Asset Tags**
(expanding to *Tagged* / *Not Tagged*, filtering pane 2 by whether an
`asset_tag` is present); **Genres** (each built-in genre plus *(no genre)*,
filtering pane 2 to that genre); and **Workspaces**, under which every open
workspace and its folder tree is nested. Each row shows a right-aligned count
of the assets selecting it would list, and rows that would list nothing show no
count.

## Card view and Add property

Pane 2 opens in **Card view** (bold name over the asset tag and a
location-notes snippet, with a larger genre icon); toggle it from the toolbar
or **View → Card view**. **Add property** (toolbar, or **Edit → Add property**)
opens a picker of the documented properties the current asset doesn't yet have;
choose one, fill in the field it offers (a dropdown for `genre`, a date picker
for `purchased`, a text box otherwise), and Save to insert it into the asset's
YAML for review.

## Usage

```bash
python3 qdvc_equip.py ~/qdvc-equip/home ~/qdvc-equip/office   # open workspaces
python3 qdvc_equip.py                                          # reopen last session
```

With no arguments it reopens whatever workspaces were open last time; use
**File → Open workspace** (`Ctrl+O`) to add more.

The window opens centered on screen. Use `Alt+1` .. `Alt+9` to jump to that
open tab. The pane-2 filter box matches an asset's **name and full file
contents** (including notes and asset-information values that aren't shown in
the list), not just the visible list text.

## Desktop integration (application menu entry)

To make "QDVC Equip" appear in your MATE/GNOME application menu, install a
`.desktop` file.

First decide where the script lives. Assuming you keep the project at
`~/Applications/qdvc-equip/` (adjust the `Exec` path below to match), create
`~/.local/share/applications/qdvc-equip.desktop` with:

```ini
[Desktop Entry]
Type=Application
Name=QDVC Equip
Comment=Track your tools, equipment, and materials across workspaces
Exec=python3 /home/YOUR_USERNAME/Applications/qdvc-equip/qdvc_equip.py %F
Icon=package-x-generic
Terminal=false
Categories=Office;Utility;
MimeType=inode/directory;
StartupNotify=true
StartupWMClass=qdvc-equip
```

Notes:

- Replace the `Exec` path with the absolute path to `qdvc_equip.py`. The script
  must be able to find its `qdvcequip_lib/` package alongside it, which it will
  as long as you point `Exec` at the script in its own directory.
- `%F` lets the launcher pass workspace folders you drop onto the icon as
  arguments; launching with no argument reopens your last session.
- `Icon=package-x-generic` is a standard freedesktop icon present on a typical
  GNOME/MATE install. To use your own, point `Icon=` at an absolute path to a
  `.png` or `.svg`.
- `StartupWMClass=qdvc-equip` lets the panel/taskbar match the running window to
  this entry, so it shows the app icon instead of a generic window icon. The app
  sets its program name to `qdvc-equip` to match, and sets its window icon to
  `package-x-generic` directly so the icon appears even before any `.desktop`
  matching.

Then refresh the menu database (often automatic):

```bash
update-desktop-database ~/.local/share/applications
```

For a system-wide entry available to all users, place the file in
`/usr/share/applications/` instead (requires root).

## Requirements

- Python 3
- GTK 3 with PyGObject (`python3-gi`, `gir1.2-gtk-3.0`)
- PyYAML (optional) — used for richer YAML and for saving settings; the app runs
  without it.

On Debian/Ubuntu/MATE:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-yaml
```
