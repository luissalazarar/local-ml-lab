from local_ml_lab.storage import SAVED_DATA_DIRECTORIES, clear_saved_files


def test_clear_saved_files_preserves_layout_and_database(tmp_path):
    database = tmp_path / "db" / "app.sqlite3"
    database.parent.mkdir()
    database.write_text("keep", encoding="utf-8")
    for name in SAVED_DATA_DIRECTORIES:
        directory = tmp_path / name
        directory.mkdir()
        (directory / "nested").mkdir()
        (directory / "nested" / "artifact.txt").write_text("saved", encoding="utf-8")
        (directory / "loose.txt").write_text("saved", encoding="utf-8")

    removed = clear_saved_files(tmp_path)

    assert removed == len(SAVED_DATA_DIRECTORIES) * 2
    assert database.read_text(encoding="utf-8") == "keep"
    assert all(directory.exists() and not any(directory.iterdir()) for directory in (
        tmp_path / name for name in SAVED_DATA_DIRECTORIES
    ))
