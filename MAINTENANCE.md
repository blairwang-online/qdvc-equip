# MAINTENANCE.md

Architecture and maintainer notes for **QDVC Equip**. Read this before changing
the code. It is written for a human or AI worker picking the project up cold.

## Design principle: two layers

The codebase is deliberately split into a **GTK-free core** and a **GTK3 view**.

- **GTK-free core** — pure Python, imports nothing from `gi`/`Gtk`. Holds the
  data model and all rules that can be reasoned about and unit-tested without a
  display server.
- **GTK3 view/controller** — every file is prefaced `gtk3_` and is the only
  place allowed to `import gi`. Builds widgets and wires user actions to core
  calls.

If you add a module, keep this boundary. Anything testable without a screen
belongs in the core; anything that touches widgets goes in a `gtk3_` file.

## File map

```
qdvc_equip.py              Thin entry point. Sets prgname/icon, parses argv,
                           constructs EquipWindow, runs the GTK main loop.
qdvcequip_lib/
  __init__.py              Version + app-name/app-id constants.
  naming.py        (core)  snake_case slugify / humanize / validate /
                           unique_name. The single source of truth for the
                           naming convention.
  asset.py         (core)  Asset model + YAML (de)serialisation. Includes a
                           tiny no-PyYAML fallback dumper/loader so the app
                           runs on a bare install. asset_tag() / notes_snippet()
                           supply the card-view sub-lines.
  workspace.py     (core)  Workspace + FolderNode tree. Scans the filesystem,
                           enforces workspace-wide name uniqueness, computes
                           new asset/folder paths.
  settings.py      (core)  Persisted settings + recent/open workspace list,
                           stored as YAML under $XDG_CONFIG_HOME/qdvc-equip/.
                           Also defines the Preferences-backed keys (code_font,
                           editor_line_spacing, toolbar_style) with bounds.
  gtk3_menubar.py  (view)  MenuBarMixin: builds the File/Edit/View/Help menus
                           (icons on items via Gtk.ImageMenuItem). Mixed into
                           EquipWindow.
  gtk3_toolbar.py  (view)  ToolbarMixin: builds the toolbar and maps the
                           toolbar_style setting to a Gtk.ToolbarStyle. Mixed
                           into EquipWindow. Card view = mail-attachment icon,
                           Preview = document-page-setup icon (same as the
                           notebook).
  gtk3_preferences.py (view) PreferencesDialog: the Edit -> Preferences dialog
                           (Fonts + Interface tabs) with live preview and
                           Save/Cancel-revert.
  gtk3_preview.py  (view)  Builds the read-only "card" shown when Preview is on,
                           including the per-row [copy] buttons.
  gtk3_window.py   (view)  EquipWindow itself: layout, the three panes, the
                           details notebook, the status bar, and all action
                           handlers. Composes the menubar/toolbar mixins.
```

## Mixin composition

`EquipWindow(MenuBarMixin, ToolbarMixin, Gtk.Window)`. The mixins hold only
`_build_menubar` / `_build_toolbar` (plus toolbar-style helpers) and rely on
handlers and attributes defined on the window. This keeps `gtk3_window.py`
focused and mirrors qdvc-markdown-notebook's structure. If you add another
large UI region, give it its own `*Mixin` rather than growing the window file.

## Key concepts

- **Workspace** = a top-level folder. Multiple may be open at once; each gets
  its own root in the navigation tree (`TreeStore`, `KIND_WORKSPACE`). This is
  the main divergence from qdvc-markdown-notebook, which had a single
  "Subfolders" entry.
- **Folder** = a `KIND_FOLDER` node nested arbitrarily deep. The full hierarchy
  is rendered (the notebook only rendered one level). There is **no** mapping
  between folder depth and real-world ontology — `work_desk` may sit at the top
  of one workspace while `study_desk` is nested in another.
- **Asset** = one `.yml` file. Its **location is derived from its folder path**,
  not stored in the file. `Asset.location_parts()` turns the path relative to
  the workspace root into humanized breadcrumb segments; the workspace name is
  prepended by the preview builder.

## The three panes (gtk3_window.py)

Built from two nested `Gtk.Paned`. Column index constants live at module top:
`NAV_*` for the navigation `TreeStore`, `ITEM_*` for the item `ListStore`.

1. **Navigation tree** — `self.nav_view` / `self.nav_store`. Selecting a node
   fills the item list via `_fill_item_list`.
2. **Items** — `self.item_view` over a `TreeModelFilter` driven by the search
   entry. Single-click opens the asset in the current tab; double-click /
   `Enter` opens it in a new tab.
3. **Item details** — `self.notebook`, a `Gtk.Notebook` of tabs. Each tab is an
   `AssetTab` holding both the plaintext `TextView` and (when Preview is on) a
   freshly built preview widget. `_render_tab` swaps between them.

## Toolbar ↔ menu toggle sync

**Read-only**, **Preview**, and **Card view** are app-wide and appear both on
the toolbar and in the View menu. To avoid feedback loops, `_sync_toggle`
(borrowed from the notebook) sets both widgets while a guard flag
`_syncing_view_toggles` is raised; every `on_*_toggle_*` handler returns early
when the guard is up. Each toggle has a single `_set_*` entry point. If you add
a third surface for these toggles, funnel it through the same `_set_*` method.

**Preview disables Read-only.** `_set_preview` calls
`btn_readonly.set_sensitive(not preview)` and the same on the menu item, because
preview is read-only by construction — matching qdvc-markdown-notebook.

## Card view (items pane)

A single `Gtk.CellRendererText` with a `cell-data-func` (`_item_cell_data`)
paints each row either as a plain title (list view) or, in card view, as three
lines: bold name, asset tag, and a location-notes snippet. The extra data lives
in the item `ListStore` columns `ITEM_TAG` and `ITEM_SNIPPET`, filled from
`Asset.asset_tag()` / `Asset.notes_snippet()` when the folder is selected.
Toggling the mode just queues a redraw; no store rebuild needed.

## Preferences

`gtk3_preferences.PreferencesDialog` is the view over the Preferences-backed
settings keys. It snapshots the originals on open, live-applies on every change
via the `on_apply` callback (`EquipWindow._apply_preferences`, which re-applies
the toolbar style and re-styles every editor tab), and on Cancel restores the
snapshot and re-applies. Adding a new preference means: add the key+bounds in
`settings.py`, a control in the relevant tab here, and an apply step in
`_apply_preferences`.

## Editing / saving flow

- The plaintext editor is the source of truth while editing. On save (or before
  rendering preview), `_sync_asset_from_buffer` re-parses the buffer text into
  the `Asset` via `Asset.update_from_raw`.
- `read_only` disables editing across all tabs; saving is blocked while it is on.
- Dirty state is tracked per tab and shown with a `*` prefix in the tab title.

## YAML and the no-PyYAML fallback

`asset.py` prefers PyYAML but falls back to `_fallback_dump`/`_fallback_load`,
which handle exactly the subset this app writes: scalar top-level keys, a
multiline `location_notes` block (`|`), and a one-level `info` mapping. If you
extend the schema (e.g. nested structures under `info`), **either** require
PyYAML **or** extend both fallback functions and add a round-trip test.

## Settings

`settings.py` persists to `$XDG_CONFIG_HOME/qdvc-equip/config.yml`. Keys:
`open_workspaces`, `recent_workspaces`, `show_toolbar`, `show_statusbar`,
`read_only`. Saving silently no-ops without PyYAML. On launch with no argv the
window reopens `open_workspaces`.

## Testing

The core is exercised without a display. For the GTK layer, run under a virtual
framebuffer:

```bash
PYTHONPATH=. xvfb-run -a python3 your_smoke_test.py
```

A useful smoke test: open the sample workspaces, open an asset into the current
tab, toggle Preview on/off, assert the expected number of `[copy]` buttons, and
assert toolbar/menu toggles stay in sync.

## Known simplifications / good first issues

- The editor code-font is applied via a per-tab `Gtk.CssProvider`; the parser
  in `_parse_font` handles the common "Family Size" form. Exotic Pango
  descriptions (styles/weights in the string) fall back to family+size only.
- Preview is rebuilt wholesale on every render; fine for typical asset counts.
- Renaming/moving assets between folders is not yet exposed in the UI (the core
  has the pieces: `naming.unique_name`, `Workspace.all_names`).
- No drag-and-drop in the navigation tree yet.
