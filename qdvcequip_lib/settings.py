"""settings.py — persisted user settings and recent workspaces (GTK-free core).

Settings live in a plain, git-trackable YAML file under the XDG config dir
(``~/.config/qdvc-equip/config.yml`` by default). The app runs fine without
PyYAML — in that case settings simply aren't persisted between runs.

Stored keys:
    open_workspaces: list of absolute workspace paths to reopen on launch.
    recent_workspaces: most-recently-opened workspace paths (capped).
    show_toolbar / show_statusbar: View-menu toggles.
    read_only: whether the app starts in read-only mode.
"""

import io
import os

try:
    import yaml
    _HAVE_YAML = True
except Exception:  # pragma: no cover
    yaml = None
    _HAVE_YAML = False

from . import __app_id__

_MAX_RECENT = 10

_DEFAULTS = {
    "open_workspaces": [],
    "recent_workspaces": [],
    "show_toolbar": True,
    "show_statusbar": True,
    "read_only": True,
}


def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, __app_id__)


def config_path():
    return os.path.join(config_dir(), "config.yml")


class Settings(object):
    """Load/save a small dict of user settings."""

    def __init__(self, data=None):
        self._data = dict(_DEFAULTS)
        if data:
            self._data.update(data)

    # dict-ish access
    def __getitem__(self, key):
        return self._data.get(key, _DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    # ----- recent / open workspace bookkeeping ----------------------------
    def note_opened(self, path):
        """Record *path* as opened: add to open + bump in recent list."""
        path = os.path.abspath(os.path.expanduser(path))
        opens = [p for p in self._data["open_workspaces"] if p != path]
        opens.append(path)
        self._data["open_workspaces"] = opens
        recent = [p for p in self._data["recent_workspaces"] if p != path]
        recent.insert(0, path)
        self._data["recent_workspaces"] = recent[:_MAX_RECENT]

    def note_closed(self, path):
        path = os.path.abspath(os.path.expanduser(path))
        self._data["open_workspaces"] = [
            p for p in self._data["open_workspaces"] if p != path
        ]

    # ----- persistence -----------------------------------------------------
    @classmethod
    def load(cls):
        path = config_path()
        if _HAVE_YAML and os.path.exists(path):
            try:
                with io.open(path, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) or {}
                if isinstance(data, dict):
                    return cls(data)
            except Exception:
                pass
        return cls()

    def save(self):
        if not _HAVE_YAML:
            return False
        try:
            os.makedirs(config_dir(), exist_ok=True)
            with io.open(config_path(), "w", encoding="utf-8") as fh:
                yaml.safe_dump(
                    self._data, fh, default_flow_style=False, sort_keys=True,
                    allow_unicode=True,
                )
            return True
        except Exception:
            return False
