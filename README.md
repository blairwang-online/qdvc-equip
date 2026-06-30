# QDVC Equip

A lightweight three-pane desktop tracker for your **tools, equipment, and
materials** — for home, work, travel, and anywhere else — built with
**GTK 3 / PyGObject** for a native MATE / GNOME2-era look and feel (think Pluma
and Atril). It is the equipment-tracking sibling of
[qdvc-markdown-notebook](https://github.com/blairwang-online/qdvc-markdown-notebook).

You point it at one or more **workspace** folders. Inside each workspace, nested
subfolders describe *where* something is stored, and each tool, appliance, or
set of materials — an **asset** — is a single `.yml` file.

```
~/qdvc-equip/home          (workspace)
└── kitchen
    └── pantry
        ├── coffee_machine.yml
        ├── blender.yml
        └── sony_headphones_2.yml
~/qdvc-equip/office        (workspace)
└── work_desk
    └── sony_headphones_3.yml
```

## What you get

- **Pane 1 — Navigation tree.** An **All Assets** row at the top (every asset
  in every open workspace), then one expandable root per open workspace, each
  showing its full nested folder hierarchy so you can see exactly where an asset
  lives. Several workspaces can be open at once.
- **Pane 2 — Items.** The assets stored directly in the selected folder (or all
  of them, under All Assets), with a filter box. Right-click a row for a context
  menu.
- **Pane 3 — Item details.** A tabbed editor. By default it shows the asset's
  raw YAML; flip the **Preview** toggle and it becomes a rendered equipment card
  with a location breadcrumb and copyable asset-information rows. **Read-only**
  and **Preview** are tracked per tab.

Plus a menu bar (**File / Edit / View / Help**, with `Alt+F` … `Alt+H`, icons
on items), a toolbar (**New tab · New asset · Save asset · Card view ·
Read-only · Preview**), and a status bar with a bold mode indicator
(READ-ONLY / EDIT / PREVIEW) followed by a message area.

**Card view** (toolbar/`Ctrl+D`) turns each row in the items pane into a small
card: the asset name in bold, then its asset tag, then a snippet of its
location notes. **Preview** (`Ctrl+\``) renders the asset as a card in pane 3;
turning it on disables the Read-only toggle, since preview is always read-only.

**Edit → Preferences** lets you set the editor's *Code font* and *Editor line
spacing*, and the toolbar's *icon text placement* (beside vs below the icons).
Changes preview live; Save persists them, Cancel reverts.

## Preview cards

The Preview button is the headline feature. For `coffee_machine.yml` it renders:

```
☕ Coffee Machine
Location
    Home → Kitchen → Pantry
Asset Information
    Asset Tag:      SDR892314T              [copy]
    Manufacturer:   Coffee Machines Inc.    [copy]
    Model:          Cino Grande XL Gen. 2   [copy]
    Serial Number:  689D857D6               [copy]
```

Asset-information labels are humanized from their snake_case keys, their values
are aligned in a column, and each **[copy]** button puts that value on the
clipboard. Read-only and Preview are tracked **per tab**: a tab shows a padlock
icon while read-only and a preview icon while previewing.

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

## Naming convention

Folder names and asset filenames are kept in lowercase `snake_case` (no spaces
or special characters). The app slugifies anything you type, and enforces that
**no two folders or assets share a name within a workspace** — hence
`sony_headphones_1`, `sony_headphones_2`, and so on.

## Right-click menu

Right-click an asset in the items pane, or a tab, for a context menu:

- **Locate in subfolders** (tabs only) — selects the asset's containing folder
  in the navigation tree.
- **Open in new tab** — opens the asset in a fresh tab.
- **Move to subfolder** — a submenu of every folder in the asset's workspace
  (plus the workspace root); the folder it already lives in is greyed out, and
  the move is confirmed before the `.yml` file is relocated on disk.
- **Copy full path** — copies the asset's absolute path to the clipboard.
- **Show in file browser** — opens the containing folder in your file manager.

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

## Keyboard shortcuts

| Action          | Shortcut |
| --------------- | -------- |
| New tab         | `Ctrl+T` |
| New asset       | `Ctrl+N` |
| Save asset      | `Ctrl+S` |
| Open workspace  | `Ctrl+O` |
| Close tab       | `Ctrl+W` |
| Card view       | `Ctrl+D` |
| Read-only       | `Ctrl+E` |
| Preview         | `` Ctrl+` `` |
| Refresh         | `F5`     |
| Quit            | `Ctrl+Q` |

See [MAINTENANCE.md](MAINTENANCE.md) for architecture and maintainer notes.
