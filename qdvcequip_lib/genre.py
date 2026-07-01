"""genre.py — the built-in asset genres and their icons (GTK-free core).

A *genre* is a coarse classification a user may assign to an asset via the
``genre:`` top-level YAML key (e.g. ``genre: appliances``). It is entirely
optional. Each built-in genre maps to a freedesktop icon supplied by the host
Linux icon theme; that icon is shown for the asset's row in the items pane and
alongside the genre in Preview.

Two deliberate rules:

- **Genre names are never humanized.** Unlike snake_case asset-information keys
  (which become "Asset Tag" for display), a genre is always shown verbatim in
  the on-disk form: lowercase, words separated by single dashes
  (``laptop-docks``, not ``Laptop Docks`` or ``laptop_docks``). Callers must not
  run genre strings through ``naming.humanize``.
- **The mapping is the single source of truth.** ``GENRE_ICONS`` below lists
  every built-in genre in display order together with its default icon, given
  as a ``category/icon-name`` path in the freedesktop convention. GTK looks up
  icons by *name* only, so :func:`icon_name` strips the category; the full path
  is retained here for documentation and future use.

This module imports nothing from PyGObject and is unit-testable in isolation.
"""

from collections import OrderedDict

# Built-in genres in the order they should appear in menus and the nav tree.
# Values are the default icon as "<freedesktop-category>/<icon-name>".
GENRE_ICONS = OrderedDict([
    ("appliances", "devices/drive-multidisk"),
    ("audio", "devices/audio-headset"),
    ("baby", "emblems/emblem-favorite"),
    ("cables", "devices/gnome-dev-ethernet"),
    ("chargers", "devices/ac-adapter"),
    ("components", "devices/audio-card"),
    ("displays", "devices/display"),
    ("electronics", "devices/ac-adapter"),
    ("hdd", "devices/drive-harddisk"),
    ("infrastructure", "devices/network-wireless"),
    ("lights", "status/info"),
    ("keyboards", "devices/input-keyboard"),
    ("laptop-docks", "devices/drive-multidisk"),
    ("laptops", "devices/computer"),
    ("printers", "devices/printer"),
    ("psu", "devices/ac-adapter"),
    ("smartphones", "devices/pda"),
    ("ssd", "devices/drive-removable-media"),
    ("wearables", "apps/access"),
])


def all_genres():
    """Return the built-in genre names in canonical display order."""
    return list(GENRE_ICONS.keys())


def is_genre(name):
    """True if *name* is one of the built-in genres (exact, verbatim match)."""
    return name in GENRE_ICONS


def default_icon_path(genre):
    """Return the ``category/icon-name`` default icon path for *genre*, or ''."""
    return GENRE_ICONS.get(genre, "")


def icon_name(genre):
    """Return the bare freedesktop icon *name* for *genre* (no category), or ''.

    GTK's icon theme is queried by name alone, so ``devices/drive-multidisk``
    resolves to ``drive-multidisk``. Returns '' for an unknown genre.
    """
    path = GENRE_ICONS.get(genre, "")
    if not path:
        return ""
    return path.rsplit("/", 1)[-1]


def normalize(value):
    """Coerce a raw ``genre:`` value to a clean genre string, or ''.

    Trims surrounding whitespace and lowercases; does not alter internal dashes.
    An empty or None value yields ''. The result is *not* validated against the
    built-in list — unknown genres simply have no icon (see
    :func:`is_genre`).
    """
    if not value:
        return ""
    return str(value).strip().lower()
