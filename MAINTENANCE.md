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
                           notes_snippet() supply the card-view sub-lines;
                           has_tag() backs the Asset Tags nav filters. The
                           optional top-level `genre` key is stored/shown
                           verbatim. Includes a no-PyYAML fallback dumper/loader.
  genre.py         (core)  The built-in genres and their default freedesktop
                           icons (GENRE_ICONS). icon_name() strips the category
                           for GTK lookup; genres are never humanized.
  dates.py         (core)  Purchase-date parsing + friendly formatting and age
                           ("Wed 01 Jul 2026 (52d)" / "(3.7y)"). Pure/testable.
  property_catalog.py (core) The catalog of documented asset properties for the
                           Add-property dialog: each PropertySpec records its
                           key, storage location (top-level attr vs info key),
                           help text, and field kind (text / genre / date).
                           missing_specs(asset) returns what an asset lacks.
  workspace.py     (core)  Workspace + FolderNode tree. Scans the filesystem,
                           enforces workspace-wide name uniqueness, computes
                           new asset/folder paths.
  settings.py      (core)  Persisted settings + recent/open workspace list.
                           Also defines the Preferences-backed keys (code_font,
                           editor_line_spacing, toolbar_style) with bounds, and
                           the genre_icons map (genre -> custom icon path).
  gtk3_common.py   (view*) Shared TreeStore/ListStore column indices, nav
                           node-kind tags, the NO_GENRE_SENTINEL, and stateless
                           helpers (xml_escape, parse_font). Imported by the
                           window mixins; avoids a circular import. (*No GTK,
                           but grouped with the view since it serves it.)
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
                           Interface + Genres) with live preview and
                           Save/Cancel-revert.
  gtk3_addproperty.py (view) AddPropertyDialog: pick a not-yet-present property
                           (left list from property_catalog.missing_specs) and
                           enter its value (right: description + genre dropdown /
                           date picker / text). run_modal() returns (spec,value).
  gtk3_preview.py  (view)  Builds the read-only Preview card: optional Genre
                           section (verbatim), humanized value-aligned
                           asset-information rows (Gtk.Grid + SizeGroup) with
                           per-row [copy] buttons, and the `purchased` date+age
                           special-case.
  gtk3_panes.py    (view)  PanesMixin: _build_ui + the three panes + status bar,
                           and the pane-1/pane-2 cell rendering (nav icons + the
                           right-aligned count column, the shared genre-icon
                           logic sized 16/24 px + pixbuf caches, item icons,
                           card-view markup, full-contents search filter).
  gtk3_tabs.py     (view)  TabsMixin: the pane-3 notebook — tab lifecycle,
                           editor/preview rendering, per-tab editor styling, and
                           tab-switch → toggle sync.
  gtk3_actions.py  (view)  ActionsMixin: workspace open/close/refresh + nav-row
                           building (with per-row counts), item-list filling
                           (folder / All Assets / tag+genre filters) labelled by
                           asset name, selection/search/Alt+N nav, every
                           menu+toolbar action handler (incl. Add property), the
                           card-view/read-only/preview toggles, and helpers
                           (prompt, recent menu, nav counts, status, on_destroy).
  gtk3_window.py   (view)  EquipWindow: a thin composition of the mixins above
                           plus __init__ (window setup + session bootstrap). Re-
                           exports the gtk3_common constants for compatibility.
```

## Mixin composition

```
EquipWindow(MenuBarMixin, ToolbarMixin, ContextMenuMixin,
            PanesMixin, TabsMixin, ActionsMixin, Gtk.Window)
```

The mixins hold construction/handler groups and rely on attributes defined
across each other and on the window; each AssetTab is its own object (not a
mixin) created via `new_tab`. `gtk3_window.py` itself is intentionally tiny —
just the class declaration and `__init__` (window setup + session bootstrap).
This keeps each file focused and mirrors qdvc-markdown-notebook's split
(`gtk3_panes` / `gtk3_actions` / …).

Because the mixins share TreeStore/ListStore column indices and node-kind
constants, those live in `gtk3_common` (not in `gtk3_window`) so any mixin can
import them without a cycle; `gtk3_window` re-exports them so older imports like
`from qdvcequip_lib.gtk3_window import KIND_TAGGED` still resolve. When you add
a method, drop it in the mixin that owns that concern (panes = construction +
cell rendering; tabs = the notebook; actions = handlers + item filling), not in
`gtk3_window`.

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

## The three panes (gtk3_panes.py)

Built from two nested `Gtk.Paned`. Column-index constants (`NAV_*` for the
navigation `TreeStore`, `ITEM_*` for the item `ListStore`) live in
`gtk3_common`.

1. **Navigation tree** — `self.nav_view` / `self.nav_store`. Fixed grouping
   rows (All Assets, Asset Tags, Genres, Workspaces) plus workspaces nested
   under the last; selecting a node fills the item list. See the fuller
   "Navigation tree (pane 1)" section below.
2. **Items** — `self.item_view` over a `TreeModelFilter` driven by the search
   entry. Rows are labelled by the asset's `name` (falling back to the humanized
   filename only when a file has no name). Each row's icon (`_item_icon_data`)
   reflects its genre, sized 24 px in card view and 16 px in the plain list. The
   `_item_visible_func` matches the query against the row's visible columns AND
   the asset's full file contents (read via `_asset_contents_lower`, cached per
   path+mtime), mirroring qdvc-markdown-notebook's name-and-contents search.
   Single-click opens the asset in the current tab; double-click / `Enter`
   opens it in a new tab.
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
Card view is the launch default: `__init__` calls `_set_card_view(True)` after
`_build_ui`, which drives the toolbar button and menu item through the same
entry point so they start in sync.

**Preview disables Read-only.** `_set_preview` calls
`btn_readonly.set_sensitive(not preview)` and the same on the menu item, because
preview is read-only by construction — matching qdvc-markdown-notebook.

## Navigation tree (pane 1)

Built as a `Gtk.TreeStore` with columns `[label, kind, path, ws_root, count]`.
The `count` column is a pre-formatted right-aligned string (`"(500)"`, or `""`
when the row would list nothing) shown in a second, right-aligned
`TreeViewColumn`. The fixed top-level rows are laid down by
`_build_static_nav_rows` (also re-run by `refresh_workspaces`), in order:

- `KIND_ALL` — the "All Assets" virtual row. Selecting it calls
  `_fill_item_list_all` (every asset in every workspace).
- `KIND_TAGS_ROOT` — the "Asset Tags" group parent, holding `KIND_TAGGED` and
  `KIND_UNTAGGED`. These call `_fill_item_list_filtered` with `Asset.has_tag()`
  (or its negation) across all workspaces.
- `KIND_GENRE_ROOT` — the "Genres" group parent, holding one `KIND_GENRE` row
  per built-in genre (from `genre.all_genres()`, label == name, shown verbatim)
  plus a trailing "(no genre)" row whose `NAV_PATH` is `NO_GENRE_SENTINEL`.
  Selecting a genre filters to `asset.genre == <name>`; "(no genre)" filters to
  assets with no genre. `NO_GENRE_SENTINEL` must be free of NUL bytes (GTK
  string columns are NUL-terminated) and can't collide with a real genre.
- `KIND_WORKSPACES_ROOT` — the "Workspaces" group parent. Every open workspace
  (`KIND_WORKSPACE`) is nested **under** this row (via `self._workspaces_iter`),
  each expanding its full `KIND_FOLDER` hierarchy. Selecting a workspace/folder
  calls `_fill_item_list`.

Selecting a group *parent* (`KIND_TAGS_ROOT` / `KIND_GENRE_ROOT` /
`KIND_WORKSPACES_ROOT`) lists nothing — it just expands and prompts. Row icons
come from `_nav_icon_func`: workspace = `applications-other`, Workspaces parent
= `emblem-generic`, Tagged = `emblem-default`, Not Tagged = `important`, and a
`KIND_GENRE` row shows its genre icon (custom or built-in) via
`_apply_genre_icon`. There is no mapping between folder depth and real-world
ontology — the tree just mirrors the filesystem.

Note the two "new" actions (`on_new_asset`, `on_new_folder`) require a real
folder path, so they proceed only for `KIND_WORKSPACE`/`KIND_FOLDER` rows.

**Counts.** Workspace/folder rows get their count (direct `asset_files`, what a
click lists) when the row is built. The aggregate filter rows (All Assets,
Tagged / Not Tagged, each genre, "(no genre)") are filled by
`_update_nav_counts`, which scans every open asset once and writes each row's
`NAV_COUNT` via `_set_count` (`_count_label` renders `"(N)"` or `""`). It runs
after any change to the set of assets: `open_workspace`, `refresh_workspaces`
(new asset/folder/close call this), and `on_save_asset` (a save can change an
asset's genre/tag).

## Add property (gtk3_addproperty.py)

`on_add_property` (Edit menu + toolbar) first `_sync_asset_from_buffer`s the
active tab (so unsaved edits aren't lost), then runs `AddPropertyDialog`, a view
over `property_catalog`. The dialog lists `missing_specs(asset)` on the left and
shows the selected spec's description plus a field on the right — a genre
`ComboBoxText` (verbatim), a `Gtk.Calendar` for `purchased` (read back as
`YYYY-MM-DD`), or a text `Entry`. On Save it returns `(spec, value)`; the
handler calls `Asset.add_property(key, value, in_info)` (top-level attribute vs
`asset_information` key, per `spec.location`), which sets the value and
regenerates the cached YAML. The tab is reloaded and marked dirty so the user
reviews and saves. Adding a property to the catalog is a one-line `PropertySpec`
in `property_catalog._SPECS`; no view changes are needed unless it wants a new
field kind.

## Genre icons

`genre.py` is the single source of truth: `GENRE_ICONS` maps each built-in
genre to a `category/icon-name` default; `icon_name()` returns the bare name
GTK's icon theme wants. A user override lives in `settings.genre_icons`
(`genre -> absolute image path`). `EquipWindow._apply_genre_icon(cell, genre,
size)` renders the icon to a pixbuf at *size* px — the override via
`_custom_icon_pixbuf` (cached by path+size, revalidated on mtime) or the stock
named icon via `_themed_icon_pixbuf` (cached by name+size). This lets the nav
tree ask for 16 px while card view asks for 24 px. It drives both the pane-1
genre rows and the pane-2 item icons (`_item_icon_data`). After Preferences
changes an icon, `_apply_preferences` calls `_invalidate_icon_caches` to drop
the custom-icon pixbuf cache and redraw both views (the themed-icon cache is not
cleared — theme icons don't change).

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
column aligns — the GNOME/MATE convention. Labels are humanized from the
snake_case keys here in the builder (iterating `asset.info` directly so the raw
key is retained); the snake_case keys never appear in the UI. Two special
cases: an optional **Genre** section is rendered above Location (verbatim,
never humanized), and the `purchased` row shows `dates.format_purchased(value)`
(friendly date + age) while its [copy] button still copies the raw ISO value.

## Card view (items pane)

Two cell renderers share the pane-2 column: a `Gtk.CellRendererPixbuf` driven
by `_item_icon_data` (the genre icon, or `package-x-generic` when genreless,
rendered to a pixbuf at 24 px in card view and 16 px otherwise), and a
`Gtk.CellRendererText` with `_item_cell_data` that paints each row either as a
plain title (list view) or, in card view, as three lines: bold name, asset tag,
and a location-notes snippet. The row's `ITEM_LABEL` is the asset's `name`; the
extra card data lives in `ITEM_TAG`, `ITEM_SNIPPET`, and `ITEM_GENRE`, filled
from `Asset.asset_tag()` / `Asset.notes_snippet()` / `Asset.genre`. Toggling
card view just queues a redraw (`_set_card_view` also re-resizes column 0 so the
new icon size takes effect); no store rebuild needed. Named theme icons are
rendered through `_themed_icon_pixbuf` (cached by name+size) so a size can be
requested regardless of the renderer's stock-size.

## Preferences

`gtk3_preferences.PreferencesDialog` is the view over the Preferences-backed
settings keys, with Fonts, Interface, and Genres tabs. It snapshots the
originals on open (including `genre_icons`), live-applies on every change via
the `on_apply` callback (`EquipWindow._apply_preferences`, which re-applies the
toolbar style, re-styles every editor tab, and invalidates the icon caches),
and on Cancel restores the snapshot and re-applies. The Genres tab lets the
user pick a genre, set/clear a custom icon image (a `Gtk.FileChooserDialog`),
see the overview line ("The current genre have custom icons set: …" or "No
custom icons set."), and reset all custom icons (confirmed first). Adding a new
preference means: add the key+bounds in `settings.py`, a control in the
relevant tab here, an entry in the dialog's `_original` snapshot, and an apply
step in `_apply_preferences`.

## Editing / saving flow

- The plaintext editor is the source of truth while editing. On save (or before
  rendering preview), `_sync_asset_from_buffer` re-parses the buffer text into
  the `Asset` via `Asset.update_from_raw`.
- `read_only` disables editing across all tabs; saving is blocked while it is on.
- Dirty state is tracked per tab and shown with a `*` prefix in the tab title.

## YAML and the no-PyYAML fallback

`asset.py` prefers PyYAML but falls back to `_fallback_dump`/`_fallback_load`,
which handle exactly the subset this app writes: scalar top-level keys (which
now include `genre`), a multiline `location_notes` block (`|`), and a one-level
`info` mapping. If you extend the schema (e.g. nested structures under `info`),
**either** require PyYAML **or** extend both fallback functions and add a
round-trip test.

## Settings

`settings.py` persists to `$XDG_CONFIG_HOME/qdvc-equip/config.yml`. Keys:
`open_workspaces`, `recent_workspaces`, `show_toolbar`, `show_statusbar`,
`read_only`, `code_font`, `editor_line_spacing`, `toolbar_style`, and
`genre_icons` (a `genre -> custom icon path` map; see the Genre icons section).
Saving silently no-ops without PyYAML. On launch with no argv the window
reopens `open_workspaces`.

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
