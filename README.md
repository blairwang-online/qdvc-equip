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

- **Pane 1 — Navigation tree.** One expandable root per open workspace, each
  showing its full nested folder hierarchy so you can see exactly where an asset
  lives. Several workspaces can be open at once.
- **Pane 2 — Items.** The assets stored directly in the selected folder, with a
  filter box.
- **Pane 3 — Item details.** A tabbed editor. By default it shows the asset's
  raw YAML; flip the **Preview** toggle and it becomes a rendered equipment card
  with a location breadcrumb, location notes, and copyable asset-information
  rows.

Plus a menu bar (**File / Edit / View / Help**, with `Alt+F` … `Alt+H`), a
toolbar (**New tab · New asset · Save asset · Card view · Read-only ·
Preview**), and a status bar that shows the current mode.

## Preview cards

The Preview button is the headline feature. For `coffee_machine.yml` it renders:

```
☕ Coffee Machine
Location
| Home → Kitchen → Pantry
Location Notes
| You might need to move aside the cartons of UHT milk…
Asset Information
| Asset tag: SDR892314T              [copy]
| Manufacturer: Coffee Machines Inc. [copy]
| Model: Cino Grande XL Gen. 2       [copy]
| Serial number: 689D857D6           [copy]
```

Each **[copy]** button puts that value on the clipboard.

## Asset file format

```yaml
name: Coffee Machine
emoji: "☕"
location_notes: |
  You might need to move aside the cartons of UHT milk
  which may be blocking your view of the coffee machine.
info:
  Asset tag: SDR892314T
  Manufacturer: Coffee Machines Inc.
  Model: Cino Grande XL Gen. 2
  Serial number: 689D857D6
```

Everything except `name` is optional. The asset's **location is not stored** in
the file — it is derived from the folders the file is nested in.

## Naming convention

Folder names and asset filenames are kept in lowercase `snake_case` (no spaces
or special characters). The app slugifies anything you type, and enforces that
**no two folders or assets share a name within a workspace** — hence
`sony_headphones_1`, `sony_headphones_2`, and so on.

## Usage

```bash
python3 qdvc_equip.py ~/qdvc-equip/home ~/qdvc-equip/office   # open workspaces
python3 qdvc_equip.py                                          # reopen last session
```

With no arguments it reopens whatever workspaces were open last time; use
**File → Open workspace** (`Ctrl+O`) to add more.

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
| Refresh         | `F5`     |
| Quit            | `Ctrl+Q` |

See [MAINTENANCE.md](MAINTENANCE.md) for architecture and maintainer notes.
