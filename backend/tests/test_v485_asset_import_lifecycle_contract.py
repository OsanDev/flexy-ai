from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_asset_library_uses_shared_validation_and_keeps_valid_files_when_some_are_rejected():
    source = (ROOT / "frontend-reference/apps/web/src/components/AssetLibrary.tsx").read_text()
    helper = (ROOT / "frontend-reference/apps/web/src/lib/mediaValidation.ts").read_text()
    assert 'import { validateMediaFiles } from "../lib/mediaValidation"' in source
    assert "const validation = validateMediaFiles(files)" in source
    assert "const acceptedFiles = validation.accepted as File[]" in source
    assert "validation.rejected.map" in source
    assert "await mediaApi.upload(projectId, file, controller.signal)" in source
    assert "const cancelUpload = () => uploadController.current?.abort()" in source
    assert "Retry {retryFiles.length} failed file" in source
    assert "failed.push(...acceptedFiles.slice(index))" in source
    assert "export const MAX_UPLOAD_BYTES = 1024 * 1024 * 1024" in helper
    assert '"video/", "audio/", "image/"' in helper
    assert "MEDIA_EXTENSIONS.has(extension)" in helper
    assert 'reason: "too_large"' in helper
    assert 'reason: "unsupported"' in helper


def test_asset_preview_urls_are_revoked_and_stale_loads_are_ignored():
    source = (ROOT / "frontend-reference/apps/web/src/components/AssetLibrary.tsx").read_text()
    assert "requestSequence.current" in source
    assert "previewUrls.current.forEach(URL.revokeObjectURL)" in source
    assert "nextUrls.forEach(URL.revokeObjectURL)" in source
    assert "if (sequence !== requestSequence.current) return" in source


def test_frontend_ci_does_not_require_a_missing_lockfile_for_cache_setup():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    package_dir = ROOT / "frontend-reference/apps/web"
    assert not (package_dir / "package-lock.json").exists()
    assert "cache: npm" not in workflow
    assert "npm install --no-audit --no-fund" in workflow
    assert "npm run build" in workflow


def test_upload_validation_supports_known_extensions_when_browser_mime_is_blank():
    helper = (ROOT / "frontend-reference/apps/web/src/lib/mediaValidation.ts").read_text()
    assert 'file.name.split(".").pop()?.toLowerCase()' in helper
    assert "MEDIA_EXTENSIONS.has(extension)" in helper
