__version__ = "0.3.0"


def display_version() -> str:
    """Derive the visible release from the package SemVer mirror."""
    major, minor, patch = __version__.split(".")
    return f"{major}.{minor}.{int(patch):04d}"
