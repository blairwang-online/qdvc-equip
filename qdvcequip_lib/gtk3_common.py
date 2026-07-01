"""gtk3_common.py — shared constants + free helpers for the window mixins.

`EquipWindow` is assembled from several `gtk3_` mixins (panes, tabs, actions,
menubar, toolbar, context menu). Those mixins — and `gtk3_window` itself — all
need the same handful of TreeStore/ListStore column indices, node-kind tags,
and a couple of stateless string helpers. Putting them here avoids a circular
import between the mixins and keeps a single source of truth.

Nothing here touches GTK; it is plain module-level data and functions.
"""

# Navigation tree (Gtk.TreeStore) column indices: [label, kind, path, ws_root].
NAV_LABEL, NAV_KIND, NAV_PATH, NAV_WS_ROOT = range(4)

# Navigation row kinds.
KIND_ALL = "all_assets"
KIND_WORKSPACE = "workspace"
KIND_FOLDER = "folder"
# Grouping rows and their filter children (added after All Assets).
KIND_TAGS_ROOT = "tags_root"          # "Asset Tags" parent
KIND_TAGGED = "tagged"                # assets that HAVE an asset_tag
KIND_UNTAGGED = "untagged"            # assets WITHOUT an asset_tag
KIND_GENRE_ROOT = "genre_root"        # "Genres" parent
KIND_GENRE = "genre"                  # one built-in genre (NAV_PATH = name)
KIND_WORKSPACES_ROOT = "workspaces"   # "Workspaces" parent holding all open ws

# Sentinel stored in NAV_PATH for the "(no genre)" filter row. It must not be
# storable-clobbered (no NUL bytes — GTK string columns are NUL-terminated) and
# must never collide with a real genre (which are lowercase [a-z0-9-]).
NO_GENRE_SENTINEL = "__no_genre__"

# Item list (Gtk.ListStore) column indices: label, path, ws_root, tag (card
# line 2), notes snippet (card line 3), genre (drives the row icon).
ITEM_LABEL, ITEM_PATH, ITEM_WS_ROOT, ITEM_TAG, ITEM_SNIPPET, ITEM_GENRE = range(6)


def xml_escape(text):
    """Escape the three characters Pango markup treats specially."""
    return (str(text).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def parse_font(font_desc):
    """Split a Pango font string like 'monospace 11' into (family, size_pt)."""
    parts = str(font_desc).split()
    size = 11
    if parts and parts[-1].isdigit():
        size = int(parts[-1])
        parts = parts[:-1]
    family = " ".join(parts) or "monospace"
    return family, size
