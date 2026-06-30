"""naming.py — snake_case naming-convention helpers (GTK-free core).

The on-disk layout follows a strict convention so that workspaces stay tidy and
portable: folder names and asset file stems are lowercase ``snake_case`` with no
spaces or special characters. These helpers slugify arbitrary human input into
that form and validate names the user types directly.

This module imports nothing from GTK and can be unit-tested in isolation.
"""

import re

# A valid name is one or more lowercase alphanumeric tokens joined by single
# underscores. No leading/trailing underscore, no doubled underscores.
_VALID_NAME_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def slugify(text):
    """Convert arbitrary text into a snake_case slug.

    "Coffee Machine!"      -> "coffee_machine"
    "Sony Headphones #2"   -> "sony_headphones_2"
    "  Cino  Grande  XL "  -> "cino_grande_xl"

    Returns an empty string if nothing usable remains.
    """
    if text is None:
        return ""
    text = str(text).strip().lower()
    # Replace any run of non-alphanumeric characters with a single underscore.
    text = re.sub(r"[^a-z0-9]+", "_", text)
    # Collapse repeats and trim stray underscores.
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def is_valid_name(name):
    """Return True if *name* already obeys the snake_case convention."""
    if not name:
        return False
    return bool(_VALID_NAME_RE.match(name))


def humanize(name):
    """Turn a snake_case slug into a human-friendly Title Case label.

    "coffee_machine"     -> "Coffee Machine"
    "sony_headphones_2"  -> "Sony Headphones 2"

    Used purely for display; never written back to disk.
    """
    if not name:
        return ""
    parts = str(name).replace("_", " ").split()
    return " ".join(p.capitalize() for p in parts)


def unique_name(base, existing):
    """Return a snake_case name based on *base* not present in *existing*.

    *existing* is any container of names. If ``base`` (after slugify) is free it
    is returned as-is; otherwise a numeric suffix is appended: ``base_2``,
    ``base_3`` ... matching the sony_headphones_1 / _2 pattern in the docs.
    """
    base = slugify(base) or "asset"
    existing = set(existing)
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"
