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
emoji: ☕
location_notes: "You might need to move aside the cartons of UHT milk which may be
  blocking your view of the coffee machine."
asset_information:
  asset_tag: SDR892314T
  manufacturer: Coffee Machines Inc.
  model: Cino Grande XL Gen. 2
  serial_number: 689D857D6
```

Everything except `name` is optional. The asset's **location is not stored** in
the file — it is derived from the folders the file is nested in. Keys under
`asset_information` are written in `snake_case` (matching the project naming
convention) and **humanized for display** in the Preview pane, where their
values are column-aligned and each gets a `[copy]` button.

## Usage

```bash
python3 qdvc_equip.py ~/qdvc-equip/home ~/qdvc-equip/office   # open workspaces
python3 qdvc_equip.py                                          # reopen last session
```

With no arguments it reopens whatever workspaces were open last time; use
**File → Open workspace** (`Ctrl+O`) to add more.

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
