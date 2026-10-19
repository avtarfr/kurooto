"""Kurooto: a personal assistant that runs on your own computer."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("kurooto")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+source"
