from app.main import resolve_upload_media_type


def test_upload_type_prefers_valid_browser_media_type():
    assert resolve_upload_media_type("clip.mp4", "video/mp4") == "video/mp4"


def test_upload_type_falls_back_to_extension_when_browser_type_is_empty():
    assert resolve_upload_media_type("clip.mkv", "") == "video/matroska"
    assert resolve_upload_media_type("voice.wav", "application/octet-stream") == "audio/x-wav"
    assert resolve_upload_media_type("cover.webp", None) == "image/webp"


def test_upload_type_rejects_unknown_or_non_media_extensions():
    assert resolve_upload_media_type("notes.txt", "") is None
    assert resolve_upload_media_type("archive.zip", "application/octet-stream") is None


import pytest


@pytest.mark.parametrize("filename", ["stream.m3u", "stream.m3u8", "audio.pls", "playlist.xspf", "manifest.mpd", "vector.svg", "vector.svgz"])
def test_upload_type_rejects_playlists_and_svg_even_with_spoofed_media_type(filename):
    assert resolve_upload_media_type(filename, "video/mp4") is None
