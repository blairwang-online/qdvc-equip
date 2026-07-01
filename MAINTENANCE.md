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
  asset.py         (core)  Asset model + YAML (de)serialisation. The
                           asset-information mapping is the `asset_information`
                           YAML key with snake_case sub-keys; info_display_items()
                           humanizes them for the Preview pane. asset_tag() /
                           notes_snippet() supply the card-view sub-lines.
                           Includes a no-PyYAML fallback dumper/loader.
  workspace.py     (core)  Workspace + FolderNode tree. Scans the filesystem,
                           enforces workspace-wide name uniqueness, computes
                           new asset/folder paths.
  settings.py      (core)  Persisted settings + recent/open workspace list.
                           Also defines the Preferences-backed keys (code_font,
                           editor_line_spacing, toolbar_style) with bounds.
  gtk3_menubar.py  (view)  MenuBarMixin: File/Edit/View/Help menus (icons on
                           items). New tab sits just before Close tab. Exposes
                           _icon_menu_item, reused by the context menus.
  gtk3_toolbar.py  (view)  ToolbarMixin: the toolbar + toolbar_style mapping.
                           Card view = mail-attachment, Preview =
                           document-page-setup (same icons as the notebook).
  gtk3_contextmenu.py (view) ContextMenuMixin: the pane-2 and tab right-click
                           menus (Locate / Open in new tab / Move to subfolder /
                           Copy full path / Show in file browser) and their
                           helpers, plus _confirm / _error_dialog.
  gtk3_editortab.py (view) AssetTab: one tab's editor view, styled tab label
                           (padding, padlock + preview status icons, title
                           EventBox for right-click, close button), and its
                           per-tab read_only / preview / dirty state.
  gtk3_preferences.py (view) PreferencesDialog: Edit -> Preferences (Fonts +
                           Interface) with live preview and Save/Cancel-revert.
  gtk3_preview.py  (view)  Builds the read-only Preview card: humanized,
                           value-aligned asset-information rows (Gtk.Grid +
                           SizeGroup) with per-row [copy] buttons.
  gtk3_window.py   (view)  EquipWindow: layout, the three panes, the details
                           notebook, the status bar, and action handlers.
                           Composes the four mixins above.
```

## Mixin composition

`EquipWindow(MenuBarMixin, ToolbarMixin, ContextMenuMixin, Gtk.Window)`. The
mixins hold construction/handler groups and rely on attributes defined on the
window; each AssetTab is its own object (not a mixin) created via `new_tab`.
This keeps `gtk3_window.py` focused and mirrors qdvc-markdown-notebook's split.

## Launch behavior & tab shortcuts

Adapted from qdvc-markdown-notebook. In `EquipWindow.__init__`:

- `set_position(Gtk.WindowPosition.CENTER)` centers the window on screen at
  startup instead of using the WM's default placement.
- After construction, `set_focus(self.nav_view)` moves initial keyboard focus
  off the toolbar (the first toolbar button would otherwise show a focus ring
  on launch) and onto the navigation tree.
- `key-press-event` is wired to `_on_key_press`, which maps `Alt+1` .. `Alt+9`
  to `_goto_tab(0..8)` (jump to that notebook page if it exists).

## Per-tab read-only & preview

Read-only and Preview are stored on each `AssetTab` (`tab.read_only`,
`tab.preview`), not globally. The toolbar/menu toggles act on the **active**
tab: `_set_read_only` / `_set_preview` read `_current_tab()`, update that tab,
and re-render it. `self.read_only` / `self.preview_mode` on the window are just
mirrors of the active tab, read by the status bar and gating. On tab switch,
`_sync_toggles_to_tab` pushes the landed-on tab's state back onto the toggles
(guarded by `_syncing_view_toggles`) and re-locks Read-only while previewing.
Each tab's label shows a padlock icon while read-only and a preview icon while
previewing, driven by `AssetTab.refresh_status_icons()` (the icons use
`set_no_show_all` so a blanket `show_all()` can't reveal them).

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
   entry. `_item_visible_func` matches the query against the row's visible
   columns AND the asset's full file contents (read via
   `_asset_contents_lower`, cached per path+mtime), mirroring
   qdvc-markdown-notebook's name-and-contents search. Single-click opens the
   asset in the current tab; double-click / `Enter` opens it in a new tab.
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

## Navigation tree (pane 1)

Built as a `Gtk.TreeStore` with columns `[label, kind, path, ws_root]`. Row
kinds: `KIND_ALL` (the "All Assets" virtual row, always first, re-added by
`refresh_workspaces`), `KIND_WORKSPACE` (one per open workspace), and
`KIND_FOLDER` (nested arbitrarily deep). Selecting All Assets calls
`_fill_item_list_all` (every asset in every workspace); selecting a workspace
or folder calls `_fill_item_list`. There is no mapping between folder depth and
real-world ontology — the tree just mirrors the filesystem.

## Context menus

`gtk3_contextmenu.ContextMenuMixin` builds the shared menu. The pane-2
right-click (`on_items_button_press`, wired to the item view's
`button-press-event`) omits "Locate in subfolders"; the tab right-click
(`on_tab_context_menu`, passed to each `AssetTab` as its `on_context_menu`
callback and fired from the title EventBox) includes it. "Move to subfolder"
lists `(workspace root)` plus a humanized breadcrumb for every folder via
`_all_folder_destinations`, greys out the current folder, confirms, then
`os.rename`s the file and updates any open tab pointing at it.

## Preview alignment

`gtk3_preview.build_preview` lays asset-information rows in a 3-column
`Gtk.Grid` (label, value, copy button). A horizontal `Gtk.SizeGroup` over the
label cells forces them all to the width of the widest label, so the value
column aligns — the GNOME/MATE convention. Labels come humanized from
`Asset.info_display_items()`; the snake_case keys never appear in the UI.

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
