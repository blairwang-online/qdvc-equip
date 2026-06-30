"""gtk3_editortab.py — one tab in the details notebook (pane 3) (GTK3 view).

Each AssetTab owns its own editor view *and* its own read-only / preview state,
mirroring qdvc-markdown-notebook's per-tab model: toggling Read-only or Preview
affects only the active tab, and switching tabs updates the toolbar/menu to
reflect the tab you land on.

The tab *label* is a small horizontal box (with a little padding) holding, from
left to right: a padlock icon shown only while this tab is read-only, a preview
icon shown only while previewing, the (truncated) asset title in an EventBox
that catches right-clicks for the context menu, and a close button. The two
mode icons use set_no_show_all so a blanket show_all() can't reveal them; their
visibility is driven by refresh_status_icons().
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from . import naming

READONLY_ICON_NAME = "changes-prevent-symbolic"
PREVIEW_ICON_NAME = "document-page-setup"


class AssetTab(object):
    """State + widgets for one tab in the details notebook.

    Args:
        on_close:        callback(tab) invoked when the close button is clicked.
        on_context_menu: callback(tab, event) for a right-click on the tab
                         label (only fires when the tab has an asset open).
        on_buffer_changed: callback(buffer, tab) wired to the editor buffer.
        read_only:       initial per-tab read-only state.
    """

    def __init__(self, on_close, on_context_menu, on_buffer_changed,
                 read_only=True):
        self.asset = None
        self.workspace_disp = ""
        self.read_only = bool(read_only)   # per-tab
        self.preview = False               # per-tab
        self.dirty = False
        self._title_length = 14
        self._on_close = on_close
        self._on_context_menu = on_context_menu
        self._css_provider = None

        # ---- body: a scroller holding the plaintext editor ----
        self.container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.AUTOMATIC,
                                 Gtk.PolicyType.AUTOMATIC)
        self.textview = Gtk.TextView()
        self.textview.set_monospace(True)
        self.textview.set_left_margin(8)
        self.textview.set_right_margin(8)
        self.textview.get_buffer().connect("changed", on_buffer_changed, self)
        self.scroller.add(self.textview)
        self.container.pack_start(self.scroller, True, True, 0)

        # ---- tab label: status icons + title + close button ----
        self.tab_label = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                 spacing=4)
        # A little padding on every side of the tab contents.
        self.tab_label.set_margin_top(2)
        self.tab_label.set_margin_bottom(2)
        self.tab_label.set_margin_start(4)
        self.tab_label.set_margin_end(4)

        self._readonly_icon = Gtk.Image.new_from_icon_name(
            READONLY_ICON_NAME, Gtk.IconSize.MENU)
        self._preview_icon = Gtk.Image.new_from_icon_name(
            PREVIEW_ICON_NAME, Gtk.IconSize.MENU)
        for ic in (self._readonly_icon, self._preview_icon):
            ic.set_no_show_all(True)
        self.tab_label.pack_start(self._readonly_icon, False, False, 0)
        self.tab_label.pack_start(self._preview_icon, False, False, 0)

        self._title_label = Gtk.Label(label="(empty)")
        self._title_event_box = Gtk.EventBox()
        self._title_event_box.set_visible_window(False)
        self._title_event_box.add(self._title_label)
        self._title_event_box.connect("button-press-event",
                                      self._on_tab_label_button_press)
        self.tab_label.pack_start(self._title_event_box, True, True, 0)

        close_btn = Gtk.Button()
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.set_focus_on_click(False)
        close_btn.add(Gtk.Image.new_from_icon_name(
            "window-close", Gtk.IconSize.MENU))
        close_btn.set_tooltip_text("Close tab")
        close_btn.connect("clicked", lambda _b: self._on_close(self))
        self.tab_label.pack_start(close_btn, False, False, 0)

        self.tab_label.show_all()
        self.refresh_status_icons()
        self.refresh_title()

    # ----- tab-label interaction ------------------------------------------
    def _on_tab_label_button_press(self, _widget, event):
        if event.button != 3:
            return False
        if self._on_context_menu is None or self.asset is None:
            return False
        self._on_context_menu(self, event)
        return True

    # ----- state -----------------------------------------------------------
    def refresh_status_icons(self):
        """Show/hide the tab-label mode icons to match this tab's state."""
        self._readonly_icon.set_visible(self.read_only)
        self._preview_icon.set_visible(self.preview)

    def set_title_length(self, length):
        self._title_length = max(4, int(length))
        self.refresh_title()

    def refresh_title(self):
        if self.asset and self.asset.name:
            t = self.asset.name
        elif self.asset and self.asset.stem:
            t = naming.humanize(self.asset.stem)
        else:
            t = "(empty)"
        n = self._title_length
        if len(t) > n:
            t = t[: n - 2] + "\u2026"
        self._title_label.set_text(("*" + t) if self.dirty else t)

    # ----- editor content --------------------------------------------------
    def get_content(self):
        buf = self.textview.get_buffer()
        start, end = buf.get_bounds()
        return buf.get_text(start, end, True)
