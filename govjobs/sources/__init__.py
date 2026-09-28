"""Every .py file in this folder (except _helpers) is a source; see _helpers.py for the interface."""
import pkgutil
from importlib import import_module


def all_sources():
    return [import_module(f"{__name__}.{m.name}") for m in pkgutil.iter_modules(__path__) if not m.name.startswith("_")]
