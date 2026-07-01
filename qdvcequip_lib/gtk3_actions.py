"""gtk3_actions.py — workspace/item handlers, menu-toolbar actions (GTK3 view).

A **mixin** combined into EquipWindow (see gtk3_window.py). It wires user
intent to the GTK-free core: opening/closing/refreshing workspaces and building
their nav rows, filling the item list (pane 2) for the selected nav node or
tag/genre filter, the pane-2 selection / activation / search / Alt+N tab
navigation, every File/Edit/View menu and toolbar action handler, the
app-wide/per-tab view toggles (card view, read-only, preview) with their
toolbar↔menu sync, and small shared helpers (text prompt, recent menu, status
bar).

Relies on attributes/handlers defined across the window and its other mixins
(nav_store/nav_view, item_store/item_filter/item_view, notebook/tabs,
_workspaces_iter, _current_tab/new_tab/_render_tab, _apply_toolbar_style,
_apply_editor_style_all, _invalidate_icon_caches, recent_menu, toolbar/menu
toggle widgets).
"""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk  # noqa: E402

from . import __version__, __app_name__
from .workspace import Workspace
from .asset import Asset
from . import naming
from .gtk3_preferences import PreferencesDialog
from .gtk3_addproperty import AddPropertyDialog
from . import property_catalog as catalog
from .gtk3_common import (
    NAV_LABEL, NAV_KIND, NAV_PATH, NAV_WS_ROOT, NAV_COUNT,
    KIND_ALL, KIND_WORKSPACE, KIND_FOLDER,
    KIND_TAGS_ROOT, KIND_TAGGED, KIND_UNTAGGED,
    KIND_GENRE_ROOT, KIND_GENRE, KIND_WORKSPACES_ROOT,
    NO_GENRE_SENTINEL,
    ITEM_PATH, ITEM_WS_ROOT,
)


def _count_label(n):
    """Format a nav-row count: '(N)' when positive, '' when zero.

    The empty string keeps the count column blank for rows that would show no
    assets in pane 2, per the spec.
    """
    return "(%d)" % n if n > 0 else ""


class ActionsMixin:
    """Workspace/item handlers, action handlers, view toggles, and helpers."""

    # ====================================================================
    # Workspace management
    # ====================================================================
    def open_workspace(self, path, persist=True):
        path = os.path.abspath(os.path.expanduser(path))
        for ws in self.workspaces:
            if ws.root == path:
                self.set_status("Workspace already open: %s" % ws.display_name)
                return ws
        ws = Workspace(path)
        self.workspaces.append(ws)
        self._add_workspace_to_nav(ws)
        self._update_nav_counts()
        if persist:
            self.settings.note_opened(path)
            self.settings.save()
            self._rebuild_recent_menu()
        self.set_status("Opened workspace: %s" % ws.display_name)
        return ws

    def _add_workspace_to_nav(self, ws):
        # A workspace row lists its root folder's direct assets when clicked.
        ws_iter = self.nav_store.append(
            self._workspaces_iter,
            [ws.display_name, KIND_WORKSPACE, ws.root, ws.root,
             _count_label(len(ws.root_node.asset_files))])
        self._populate_folder_children(ws_iter, ws.root_node, ws.root)
        self.nav_view.expand_row(
            self.nav_store.get_path(self._workspaces_iter), False)
        self.nav_view.expand_row(self.nav_store.get_path(ws_iter), False)

    def _populate_folder_children(self, parent_iter, node, ws_root):
        for child in node.children:
            child_iter = self.nav_store.append(
                parent_iter,
                [child.display_name, KIND_FOLDER, child.path, ws_root,
                 _count_label(len(child.asset_files))])
            self._populate_folder_children(child_iter, child, ws_root)

    def _workspace_for_root(self, ws_root):
        for ws in self.workspaces:
            if ws.root == ws_root:
                return ws
        return None

    def refresh_workspaces(self):
        self.nav_store.clear()
        self._build_static_nav_rows()
        for ws in self.workspaces:
            ws.refresh()
            self._add_workspace_to_nav(ws)
        self._update_nav_counts()

    def _update_nav_counts(self):
        """Fill the count column for the fixed rows (All Assets, Tagged / Not
        Tagged, each genre and "(no genre)") by scanning every open asset once.

        Workspace/folder row counts are set when those rows are built (they
        never change without a rebuild), so this only refreshes the aggregate
        filter rows. A blank string is stored when a count would be 0, so the
        column stays empty for rows that would show nothing in pane 2.
        """
        total = 0
        tagged = 0
        untagged = 0
        genre_counts = {}
        no_genre = 0
        for ws in self.workspaces:
            for asset_path in ws.all_asset_files():
                try:
                    a = ws.load_asset(asset_path)
                except Exception:
                    continue
                total += 1
                if a.has_tag():
                    tagged += 1
                else:
                    untagged += 1
                if a.genre:
                    genre_counts[a.genre] = genre_counts.get(a.genre, 0) + 1
                else:
                    no_genre += 1

        def walk(it):
            while it is not None:
                kind = self.nav_store[it][NAV_KIND]
                if kind == KIND_ALL:
                    self._set_count(it, total)
                elif kind == KIND_TAGGED:
                    self._set_count(it, tagged)
                elif kind == KIND_UNTAGGED:
                    self._set_count(it, untagged)
                elif kind == KIND_GENRE:
                    val = self.nav_store[it][NAV_PATH]
                    n = no_genre if val == NO_GENRE_SENTINEL \
                        else genre_counts.get(val, 0)
                    self._set_count(it, n)
                walk(self.nav_store.iter_children(it))
                it = self.nav_store.iter_next(it)

        walk(self.nav_store.get_iter_first())

    def _set_count(self, it, n):
        self.nav_store[it][NAV_COUNT] = _count_label(n)

    # ====================================================================
    # Selection handlers + item list filling
    # ====================================================================
    def on_nav_selected(self, selection):
        model, it = selection.get_selected()
        if it is None:
            return
        kind = model[it][NAV_KIND]
        if kind == KIND_ALL:
            self._fill_item_list_all()
            return
        if kind in (KIND_TAGS_ROOT, KIND_GENRE_ROOT, KIND_WORKSPACES_ROOT):
            # Grouping parents don't themselves list assets; just expand.
            self.nav_view.expand_row(model.get_path(it), False)
            self.item_store.clear()
            self.set_status("Select an item under \u201c%s\u201d"
                            % model[it][NAV_LABEL])
            return
        if kind == KIND_TAGGED:
            self._fill_item_list_filtered(
                lambda a: a.has_tag(), "tagged")
            return
        if kind == KIND_UNTAGGED:
            self._fill_item_list_filtered(
                lambda a: not a.has_tag(), "untagged")
            return
        if kind == KIND_GENRE:
            g = model[it][NAV_PATH]
            if g == NO_GENRE_SENTINEL:
                self._fill_item_list_filtered(
                    lambda a: not a.genre, "with no genre")
            else:
                self._fill_item_list_filtered(
                    lambda a, gg=g: a.genre == gg, "in genre %s" % g)
            return
        self._fill_item_list(model[it][NAV_PATH], model[it][NAV_WS_ROOT])

    def _append_item_row(self, ws, asset_path, ws_root):
        stem = os.path.splitext(os.path.basename(asset_path))[0]
        # Label by the asset's `name` field; fall back to the humanized
        # filename only when the file has no name (e.g. malformed/unreadable).
        label = naming.humanize(stem)
        tag, snippet, asset_genre = "", "", ""
        try:
            a = ws.load_asset(asset_path)
            if a.name:
                label = a.name
            tag = a.asset_tag()
            snippet = a.notes_snippet()
            asset_genre = a.genre
        except Exception:
            pass
        self.item_store.append(
            [label, asset_path, ws_root, tag, snippet, asset_genre])

    def _fill_item_list(self, folder_path, ws_root):
        self.item_store.clear()
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        node = ws.find_node(folder_path)
        if node is None:
            return
        for asset_path in node.asset_files:
            self._append_item_row(ws, asset_path, ws_root)
        count = len(node.asset_files)
        self.set_status("%d asset%s in this folder"
                        % (count, "" if count == 1 else "s"))

    def _fill_item_list_all(self):
        self.item_store.clear()
        total = 0
        for ws in self.workspaces:
            for asset_path in ws.all_asset_files():
                self._append_item_row(ws, asset_path, ws.root)
                total += 1
        self.set_status("%d asset%s across all workspaces"
                        % (total, "" if total == 1 else "s"))

    def _fill_item_list_filtered(self, predicate, descriptor):
        """List every asset (all workspaces) for which *predicate(asset)* holds.

        Used by the Asset Tags (Tagged / Not Tagged) and Genres nav filters.
        *descriptor* is a short phrase for the status bar.
        """
        self.item_store.clear()
        total = 0
        for ws in self.workspaces:
            for asset_path in ws.all_asset_files():
                try:
                    a = ws.load_asset(asset_path)
                except Exception:
                    continue
                if not predicate(a):
                    continue
                stem = os.path.splitext(os.path.basename(asset_path))[0]
                label = a.name or naming.humanize(stem)
                self.item_store.append([
                    label, asset_path, ws.root,
                    a.asset_tag(), a.notes_snippet(), a.genre])
                total += 1
        self.set_status("%d asset%s %s"
                        % (total, "" if total == 1 else "s", descriptor))

    def on_filter_changed(self, _entry):
        self.item_filter.refilter()

    def _goto_tab(self, index):
        """Jump to tab `index` (0-based) if it exists."""
        if 0 <= index < len(self.tabs):
            self.notebook.set_current_page(index)

    def _on_key_press(self, _widget, event):
        """Tab navigation: Alt+1 .. Alt+9 jump to that tab (like the notebook).

        Returns True to stop further handling when we act.
        """
        alt = bool(event.state & Gdk.ModifierType.MOD1_MASK)
        keyval = event.keyval
        if alt and Gdk.KEY_1 <= keyval <= Gdk.KEY_9:
            self._goto_tab(keyval - Gdk.KEY_1)
            return True
        return False

    def on_item_selected(self, selection):
        model, it = selection.get_selected()
        if it is None:
            return
        self._open_asset_in_current_tab(
            model[it][ITEM_PATH], model[it][ITEM_WS_ROOT])

    def on_item_activated(self, _view, _path, _col):
        model, it = self.item_view.get_selection().get_selected()
        if it is None:
            return
        self._open_asset_in_new_tab(model[it][ITEM_PATH], model[it][ITEM_WS_ROOT])

    def _open_asset_in_current_tab(self, asset_path, ws_root):
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        tab = self._current_tab() or self.new_tab()
        try:
            tab.asset = ws.load_asset(asset_path)
        except Exception as exc:
            self.set_status("Could not open asset: %s" % exc)
            return
        tab.workspace_disp = ws.display_name
        self._load_tab_content(tab)
        self.set_status("Opened %s" % tab.asset.name)

    def _open_asset_in_new_tab(self, asset_path, ws_root):
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        try:
            asset = ws.load_asset(asset_path)
        except Exception as exc:
            self.set_status("Could not open asset: %s" % exc)
            return
        self.new_tab(asset=asset, workspace_disp=ws.display_name)

    def _navigate_to_asset(self, tab):
        """Reveal the tab's asset: select its folder in pane 1 (which fills
        pane 2) and then select the asset row in pane 2.

        Invoked by the Preview "navigate" button.
        """
        asset = getattr(tab, "asset", None)
        if asset is None or not asset.path:
            return
        ws_root = asset.workspace_root
        folder = os.path.dirname(asset.path)
        nav_it = self._find_nav_folder_iter(folder, ws_root)
        if nav_it is None:
            self.set_status("Could not locate this asset in the tree.")
            return
        # Expand ancestors and select the folder/workspace row; the selection
        # handler fills pane 2 for that node.
        path = self.nav_store.get_path(nav_it)
        self.nav_view.expand_to_path(path)
        self.nav_view.get_selection().select_iter(nav_it)
        self.nav_view.scroll_to_cell(path, None, False, 0, 0)
        # Now select the asset in pane 2.
        item_it = self._find_item_iter(asset.path)
        if item_it is not None:
            self.item_view.get_selection().select_iter(item_it)
            self.item_view.scroll_to_cell(
                self.item_filter.get_path(item_it), None, False, 0, 0)
        self.set_status("Located %s" % (asset.name or asset.stem))

    def _find_nav_folder_iter(self, folder, ws_root):
        """Return the nav iter for the KIND_FOLDER/KIND_WORKSPACE row whose path
        matches *folder* within workspace *ws_root*, or None."""
        target = os.path.abspath(folder)

        def walk(it):
            while it is not None:
                kind = self.nav_store[it][NAV_KIND]
                if kind in (KIND_FOLDER, KIND_WORKSPACE) \
                        and self.nav_store[it][NAV_WS_ROOT] == ws_root \
                        and os.path.abspath(self.nav_store[it][NAV_PATH]) == target:
                    return it
                found = walk(self.nav_store.iter_children(it))
                if found is not None:
                    return found
                it = self.nav_store.iter_next(it)
            return None

        return walk(self.nav_store.get_iter_first())

    def _find_item_iter(self, asset_path):
        """Return the item-filter iter for the row whose ITEM_PATH matches
        *asset_path* (respecting the active search filter), or None."""
        target = os.path.abspath(asset_path)
        it = self.item_filter.get_iter_first()
        while it is not None:
            if os.path.abspath(self.item_filter[it][ITEM_PATH]) == target:
                return it
            it = self.item_filter.iter_next(it)
        return None

    # ====================================================================
    # Action handlers
    # ====================================================================
    def on_new_tab(self, *_):
        self.new_tab()

    def on_close_tab(self, *_):
        tab = self._current_tab()
        if tab:
            self._close_specific_tab(tab)

    def on_quit(self, *_):
        self.close()

    def on_new_asset(self, *_):
        model, it = self.nav_view.get_selection().get_selected()
        if it is None or model[it][NAV_KIND] not in (KIND_WORKSPACE, KIND_FOLDER):
            self.set_status("Select a workspace or folder first.")
            return
        folder_path = model[it][NAV_PATH]
        ws_root = model[it][NAV_WS_ROOT]
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        name = self._prompt_text("New asset", "Asset name:", "new_asset")
        if not name:
            return
        new_path = ws.new_asset_path(folder_path, name)
        asset = Asset(path=None, workspace_root=ws_root)
        asset.name = naming.humanize(
            os.path.splitext(os.path.basename(new_path))[0])
        try:
            asset.save(new_path)
        except Exception as exc:
            self.set_status("Could not create asset: %s" % exc)
            return
        ws.refresh()
        self.refresh_workspaces()
        self.new_tab(asset=ws.load_asset(new_path), workspace_disp=ws.display_name)
        self.set_status("Created %s" % os.path.basename(new_path))

    def on_save_asset(self, *_):
        tab = self._current_tab()
        if tab is None or tab.asset is None:
            self.set_status("Nothing to save in this tab.")
            return
        if tab.read_only:
            self.set_status("Read-only mode is on \u2014 cannot save.")
            return
        if not tab.preview:
            self._sync_asset_from_buffer(tab)
        try:
            tab.asset.save()
        except Exception as exc:
            self.set_status("Save failed: %s" % exc)
            return
        tab.dirty = False
        tab.refresh_title()
        # A save can change the asset's genre/tag/name, so keep the nav counts
        # fresh and re-fill pane 2 for the current nav selection.
        self._update_nav_counts()
        self._refresh_item_list()
        self.set_status("Saved %s" % os.path.basename(tab.asset.path))

    def _refresh_item_list(self):
        """Re-fill pane 2 for whatever is currently selected in the nav tree.

        Re-runs the nav selection handler so label/genre/tag changes from a
        save (or similar) are reflected without the user reselecting.
        """
        sel = self.nav_view.get_selection()
        if sel is not None:
            self.on_nav_selected(sel)

    def on_add_property(self, *_):
        tab = self._current_tab()
        if tab is None or tab.asset is None:
            self.set_status("Open an asset first to add a property.")
            return
        # Capture any unsaved edits in the buffer before mutating the asset, so
        # the added property merges with the current text rather than a stale
        # copy. (In preview mode the asset is already synced.)
        if not tab.preview:
            self._sync_asset_from_buffer(tab)
        result = AddPropertyDialog(self, tab.asset).run_modal()
        if result is None:
            return
        spec, value = result
        in_info = (spec.location == catalog.LOC_INFO)
        tab.asset.add_property(spec.key, value, in_info)
        # Reload the editor buffer from the regenerated YAML and flag dirty so
        # the user can review and save.
        self._load_tab_content(tab)
        tab.dirty = True
        tab.refresh_title()
        self.update_status()
        self.set_status("Added property \u201c%s\u201d \u2014 review and save."
                        % spec.label)

    def on_open_workspace(self, *_):
        dialog = Gtk.FileChooserDialog(
            title="Open workspace folder", parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons("_Cancel", Gtk.ResponseType.CANCEL,
                           "_Open", Gtk.ResponseType.ACCEPT)
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            self.open_workspace(dialog.get_filename())
        dialog.destroy()

    def on_close_workspace(self, *_):
        model, it = self.nav_view.get_selection().get_selected()
        if it is None:
            self.set_status("Select a workspace to close.")
            return
        ws_root = model[it][NAV_WS_ROOT]
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            self.set_status("Select a workspace to close.")
            return
        self.workspaces.remove(ws)
        self.settings.note_closed(ws_root)
        self.settings.save()
        self.refresh_workspaces()
        self.item_store.clear()
        self.set_status("Closed workspace: %s" % ws.display_name)

    def on_new_folder(self, *_):
        model, it = self.nav_view.get_selection().get_selected()
        if it is None or model[it][NAV_KIND] not in (KIND_WORKSPACE, KIND_FOLDER):
            self.set_status("Select a workspace or folder first.")
            return
        parent_path = model[it][NAV_PATH]
        ws_root = model[it][NAV_WS_ROOT]
        ws = self._workspace_for_root(ws_root)
        if ws is None:
            return
        name = self._prompt_text("New folder", "Folder name:", "new_folder")
        if not name:
            return
        try:
            ws.create_folder(parent_path, name)
        except Exception as exc:
            self.set_status("Could not create folder: %s" % exc)
            return
        self.refresh_workspaces()
        self.set_status("Created folder %s" % naming.slugify(name))

    def on_refresh(self, *_):
        self.refresh_workspaces()
        self.set_status("Workspaces refreshed.")

    def on_preferences(self, *_):
        dlg = PreferencesDialog(self, self.settings, self._apply_preferences)
        dlg.run_modal()

    def _apply_preferences(self):
        self._apply_toolbar_style()
        self._apply_editor_style_all()
        # Custom genre icons may have changed; repaint the icon-bearing views.
        self._invalidate_icon_caches()

    def on_toggle_toolbar(self, item):
        self.settings["show_toolbar"] = item.get_active()
        self.toolbar.set_visible(item.get_active())
        self.settings.save()

    def on_toggle_statusbar(self, item):
        self.settings["show_statusbar"] = item.get_active()
        self.statusbar_box.set_visible(item.get_active())
        self.settings.save()

    # ----- toggle sync helper (toolbar <-> menu) ---------------------------
    def _sync_toggle(self, button, menu_item, active):
        self._syncing_view_toggles = True
        try:
            button.set_active(active)
            menu_item.set_active(active)
        finally:
            self._syncing_view_toggles = False

    # ----- card view (app-wide) --------------------------------------------
    def _set_card_view(self, value):
        self.card_view = bool(value)
        self._sync_toggle(self.btn_cardview, self.mi_cardview, self.card_view)
        self.item_view.get_column(0).queue_resize()
        self.item_view.queue_draw()
        self.set_status("Card view %s" % ("on" if self.card_view else "off"))

    def on_toggle_card_view(self, button):
        if self._syncing_view_toggles:
            return
        self._set_card_view(button.get_active())

    def on_menu_toggle_card_view(self, item):
        if self._syncing_view_toggles:
            return
        self._set_card_view(item.get_active())

    # ----- read-only (per active tab) --------------------------------------
    def _set_read_only(self, value):
        tab = self._current_tab()
        self.read_only = bool(value)
        # Remember the latest choice as the default for new tabs.
        self.settings["read_only"] = self.read_only
        self.settings.save()
        self._sync_toggle(self.btn_readonly, self.mi_readonly, self.read_only)
        if tab is not None:
            tab.read_only = self.read_only
            tab.textview.set_editable(
                tab.asset is not None and not tab.read_only and not tab.preview)
            tab.refresh_status_icons()
        self.update_status()

    def on_toggle_read_only(self, button):
        if self._syncing_view_toggles:
            return
        self._set_read_only(button.get_active())

    def on_menu_toggle_read_only(self, item):
        if self._syncing_view_toggles:
            return
        self._set_read_only(item.get_active())

    # ----- preview (per active tab) ----------------------------------------
    def _set_preview(self, value):
        tab = self._current_tab()
        self.preview_mode = bool(value)
        self._sync_toggle(self.btn_preview, self.mi_preview, self.preview_mode)
        # Preview is read-only by construction → lock the Read-only toggle.
        self.btn_readonly.set_sensitive(not self.preview_mode)
        self.mi_readonly.set_sensitive(not self.preview_mode)
        if tab is not None:
            tab.preview = self.preview_mode
            self._render_tab(tab)
        self.update_status()

    def on_toggle_preview(self, button):
        if self._syncing_view_toggles:
            return
        self._set_preview(button.get_active())

    def on_menu_toggle_preview(self, item):
        if self._syncing_view_toggles:
            return
        self._set_preview(item.get_active())

    def on_about(self, *_):
        dlg = Gtk.AboutDialog(transient_for=self, modal=True)
        dlg.set_program_name(__app_name__)
        dlg.set_version(__version__)
        dlg.set_comments(
            "Track your tools, equipment, and materials across workspaces.")
        dlg.set_license_type(Gtk.License.MIT_X11)
        dlg.set_logo_icon_name("package-x-generic")
        dlg.run()
        dlg.destroy()

    # ====================================================================
    # Helpers
    # ====================================================================
    def _prompt_text(self, title, label_text, default=""):
        dialog = Gtk.Dialog(title=title, transient_for=self, modal=True)
        dialog.add_buttons("_Cancel", Gtk.ResponseType.CANCEL,
                           "_OK", Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_spacing(6)
        box.set_border_width(10)
        box.pack_start(Gtk.Label(label=label_text, xalign=0.0), False, False, 0)
        entry = Gtk.Entry()
        entry.set_text(default)
        entry.set_activates_default(True)
        box.pack_start(entry, False, False, 0)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()
        result = dialog.run()
        text = entry.get_text().strip()
        dialog.destroy()
        return text if result == Gtk.ResponseType.OK else None

    def _rebuild_recent_menu(self):
        for child in self.recent_menu.get_children():
            self.recent_menu.remove(child)
        recents = self.settings["recent_workspaces"]
        if not recents:
            empty = Gtk.MenuItem.new_with_label("(none)")
            empty.set_sensitive(False)
            self.recent_menu.append(empty)
        else:
            for path in recents:
                item = Gtk.MenuItem.new_with_label(path)
                item.connect(
                    "activate", lambda _i, p=path: self.open_workspace(p))
                self.recent_menu.append(item)
        self.recent_menu.show_all()

    def _apply_view_settings(self):
        self.toolbar.set_visible(bool(self.settings["show_toolbar"]))
        self.statusbar_box.set_visible(bool(self.settings["show_statusbar"]))

    def set_status(self, text):
        self._last_status = text
        self.update_status()

    def update_status(self):
        # Bold mode label reflects the ACTIVE tab; preview overrides read-only.
        if self.preview_mode:
            self.mode_label.set_markup("<b>PREVIEW</b>")
        elif self.read_only:
            self.mode_label.set_markup("<b>READ-ONLY</b>")
        else:
            self.mode_label.set_markup("<b>EDIT</b>")

        msg = self._last_status
        tab = self._current_tab()
        if tab and tab.dirty:
            msg += "  *"
        if len(self.tabs) > 1:
            idx = self.notebook.get_current_page() + 1
            msg += "    \u2014    Tab %d of %d" % (idx, len(self.tabs))
        self.statusbar.pop(self._status_ctx)
        self.statusbar.push(self._status_ctx, msg)
        self._update_action_sensitivity()

    def _update_action_sensitivity(self):
        """Enable/disable the New asset and Save asset actions to match state.

        New asset is available only when a workspace or folder row is selected
        in the nav tree (the only places an asset can be created). Save asset is
        available only when the active tab holds an asset with unsaved (dirty)
        changes. Both the toolbar buttons and the (accelerator-bearing) menu
        items are updated, so the keyboard shortcuts follow suit.
        """
        # New asset — depends on the current nav selection.
        can_new = False
        sel = self.nav_view.get_selection() if hasattr(self, "nav_view") else None
        if sel is not None:
            model, it = sel.get_selected()
            if it is not None and model[it][NAV_KIND] in (
                    KIND_WORKSPACE, KIND_FOLDER):
                can_new = True
        # Save asset — depends on the active tab having dirty asset content.
        tab = self._current_tab()
        can_save = bool(tab is not None and tab.asset is not None and tab.dirty)

        for w in (getattr(self, "btn_new_asset", None),
                  getattr(self, "mi_new_asset", None)):
            if w is not None:
                w.set_sensitive(can_new)
        for w in (getattr(self, "btn_save", None),
                  getattr(self, "mi_save", None)):
            if w is not None:
                w.set_sensitive(can_save)

    def on_destroy(self, *_):
        self.settings.save()
        Gtk.main_quit()
