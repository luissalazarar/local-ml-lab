import shutil
from pathlib import Path

SAVED_DATA_DIRECTORIES = ("uploads", "datasets", "preflights", "runs", "logs", "tmp")


def clear_saved_files(data_root: Path) -> int:
    """Remove saved user artifacts while preserving the application data layout."""
    removed = 0
    root = Path(data_root)
    for name in SAVED_DATA_DIRECTORIES:
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        for child in directory.iterdir():
            if child.is_symlink() or child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child)
            removed += 1
    return removed
