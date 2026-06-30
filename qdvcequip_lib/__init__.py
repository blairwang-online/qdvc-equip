"""qdvcequip_lib — application library for QDVC Equip.

This package is split into two layers:

* GTK-free core modules — pure Python with no PyGObject imports. These handle
  the data model (workspaces, folders, assets), YAML (de)serialisation,
  naming-convention helpers, and persisted settings. They can be unit-tested
  without a display server.

* GTK3 view/controller modules — every file here is prefaced ``gtk3_`` and may
  import ``gi`` / ``Gtk``. They build the menubar, toolbar, three panes and
  status bar, and wire user actions back to the core.

See MAINTENANCE.md for the full architecture map.
"""

__version__ = "0.1.0"
__app_name__ = "QDVC Equip"
__app_id__ = "qdvc-equip"
