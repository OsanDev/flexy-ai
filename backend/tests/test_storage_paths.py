from pathlib import Path

import pytest

from app.storage import safe_storage_path


def test_safe_storage_path_accepts_generated_filename(tmp_path):
    root = tmp_path / "media"
    root.mkdir()
    assert safe_storage_path(root, "a1b2c3.mp4") == root / "a1b2c3.mp4"


@pytest.mark.parametrize("name", ["../secret", "..\\secret", "/etc/passwd", "", ".", "..", "folder/file.mp4"])
def test_safe_storage_path_rejects_traversal_and_non_basenames(tmp_path, name):
    root = tmp_path / "media"
    root.mkdir()
    with pytest.raises(ValueError):
        safe_storage_path(root, name)


def test_safe_storage_path_rejects_symlink_escape(tmp_path):
    root = tmp_path / "media"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "link.mp4").symlink_to(outside / "target.mp4")
    with pytest.raises(ValueError):
        safe_storage_path(root, "link.mp4")
