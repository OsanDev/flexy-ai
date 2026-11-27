"""Small SQLite persistence layer for FLEXY AI development deployments."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = DATA_DIR / "flexy.sqlite3"
MEDIA_DIR = DATA_DIR / "media"
RENDER_DIR = DATA_DIR / "renders"

def safe_storage_path(directory: Path, filename: str) -> Path:
    """Resolve a database-provided storage name without permitting path escape.

    Stored names are expected to be single generated filenames. Reject separators,
    traversal components, and symlinks that resolve outside the storage directory.
    """
    if not isinstance(filename, str) or not filename or filename in {".", ".."}:
        raise ValueError("Invalid storage filename")
    if Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise ValueError("Invalid storage filename")
    root = directory.resolve()
    candidate = (root / filename).resolve()
    if candidate.parent != root:
        raise ValueError("Storage path escapes its directory")
    return candidate

def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    RENDER_DIR.mkdir(parents=True, exist_ok=True)

def connect() -> sqlite3.Connection:
    ensure_dirs()
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

class ProjectVersionConflict(Exception):
    """Raised when a save is based on an outdated cloud revision."""


def init_db() -> None:
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
            email_verified_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at INTEGER NOT NULL,
            last_seen_at INTEGER,
            revoked_at INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user_active
            ON sessions(user_id, revoked_at, expires_at);
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            owner_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            project_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            revision INTEGER NOT NULL DEFAULT 1,
            folder_name TEXT NOT NULL DEFAULT '',
            is_favorite INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS project_versions (
            project_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            name TEXT NOT NULL,
            project_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(project_id, revision),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS media (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            duration REAL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE TABLE IF NOT EXISTS render_jobs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            status TEXT NOT NULL,
            progress INTEGER NOT NULL DEFAULT 0,
            output_name TEXT,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        """)
        project_columns = {row[1] for row in db.execute("PRAGMA table_info(projects)").fetchall()}
        if "owner_id" not in project_columns:
            # Legacy projects remain unowned. Never silently assign them to a new account.
            db.execute("ALTER TABLE projects ADD COLUMN owner_id TEXT REFERENCES users(id) ON DELETE CASCADE")
        db.execute("CREATE INDEX IF NOT EXISTS idx_projects_owner_updated ON projects(owner_id, updated_at DESC)")
        if "revision" not in project_columns:
            db.execute("ALTER TABLE projects ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
        if "folder_name" not in project_columns:
            db.execute("ALTER TABLE projects ADD COLUMN folder_name TEXT NOT NULL DEFAULT ''")
        if "is_favorite" not in project_columns:
            db.execute("ALTER TABLE projects ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0")
        # Upgrade existing projects with a snapshot of their current state. Older
        # revisions cannot be reconstructed retroactively.
        db.execute("""
            INSERT OR IGNORE INTO project_versions(project_id,revision,name,project_json)
            SELECT id,revision,name,project_json FROM projects
        """)
        columns = {row[1] for row in db.execute("PRAGMA table_info(media)").fetchall()}
        if "metadata_json" not in columns:
            db.execute("ALTER TABLE media ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")

def save_project(project_id: str, name: str, project: dict[str, Any],
                 expected_revision: int = 0) -> dict[str, Any]:
    """Create a project or update it only when the caller has the current revision.

    New projects start at revision 1 and must be created with expected_revision=0.
    Existing projects use optimistic concurrency to prevent stale tabs/drafts
    from silently overwriting newer cloud edits.
    """
    serialized = json.dumps(project)
    with connect() as db:
        row = db.execute("SELECT revision FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            if expected_revision != 0:
                raise ProjectVersionConflict("Project no longer exists at the expected revision.")
            db.execute(
                "INSERT INTO projects(id,name,project_json,revision) VALUES(?,?,?,1)",
                (project_id, name, serialized),
            )
            db.execute(
                "INSERT INTO project_versions(project_id,revision,name,project_json) VALUES(?,?,?,?)",
                (project_id, 1, name, serialized),
            )
        else:
            current_revision = int(row["revision"])
            if current_revision != expected_revision:
                raise ProjectVersionConflict(
                    f"Project has a newer cloud revision ({current_revision}); your draft is based on revision {expected_revision}."
                )
            cursor = db.execute(
                "UPDATE projects SET name=?, project_json=?, revision=revision+1, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=? AND revision=?",
                (name, serialized, project_id, expected_revision),
            )
            if cursor.rowcount != 1:
                latest = db.execute("SELECT revision FROM projects WHERE id=?", (project_id,)).fetchone()
                latest_revision = int(latest["revision"]) if latest else 0
                raise ProjectVersionConflict(
                    f"Project changed during save (current revision {latest_revision}). Reload before saving again."
                )
            db.execute(
                "INSERT INTO project_versions(project_id,revision,name,project_json) VALUES(?,?,?,?)",
                (project_id, expected_revision + 1, name, serialized),
            )
        result = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(result)

def list_project_versions(project_id: str) -> list[dict[str, Any]]:
    """List immutable project snapshots, newest first, without exposing project payloads."""
    with connect() as db:
        rows = db.execute(
            "SELECT project_id, revision, name, created_at FROM project_versions "
            "WHERE project_id=? ORDER BY revision DESC", (project_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_project_version(project_id: str, revision: int) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute(
            "SELECT project_id, revision, name, project_json, created_at FROM project_versions "
            "WHERE project_id=? AND revision=?", (project_id, revision)
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["project"] = json.loads(result.pop("project_json"))
    return result


def get_project(project_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["project"] = json.loads(result.pop("project_json"))
    return result

def add_media(media: dict[str, Any]) -> None:
    with connect() as db:
        db.execute("""
        INSERT INTO media(id,project_id,filename,stored_name,mime_type,size_bytes,duration,metadata_json)
        VALUES(?,?,?,?,?,?,?,?)
        """, (media["id"], media["project_id"], media["filename"], media["stored_name"],
              media["mime_type"], media["size_bytes"], media.get("duration"),
              json.dumps(media.get("metadata", {}))))

def get_media(media_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM media WHERE id=?", (media_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["metadata"] = json.loads(result.pop("metadata_json", "{}"))
    return result

def create_job(job_id: str, project_id: str) -> None:
    with connect() as db:
        db.execute("INSERT INTO render_jobs(id,project_id,status) VALUES(?,?,?)",
                   (job_id, project_id, "queued"))

def update_job(job_id: str, *, status: str, progress: int, output_name: str | None = None,
               error: str | None = None) -> None:
    with connect() as db:
        db.execute("""UPDATE render_jobs SET status=?,progress=?,output_name=?,error=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                   (status, progress, output_name, error, job_id))

def get_job(job_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM render_jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None



def rename_project(project_id: str, new_name: str) -> dict[str, Any] | None:
    """Rename a project and its current snapshot without creating a content revision."""
    clean_name = new_name.strip()
    with connect() as db:
        cursor = db.execute(
            "UPDATE projects SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (clean_name, project_id),
        )
        if cursor.rowcount != 1:
            return None
        db.execute(
            "UPDATE project_versions SET name=? WHERE project_id=? AND revision=(SELECT revision FROM projects WHERE id=?)",
            (clean_name, project_id, project_id),
        )
        row = db.execute(
            "SELECT id,name,created_at,updated_at,revision,folder_name,is_favorite FROM projects WHERE id=?",
            (project_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_project(project_id: str) -> dict[str, Any] | None:
    """Delete a project and return owned filenames; active exports block deletion."""
    with connect() as db:
        row = db.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            return None
        active = db.execute(
            "SELECT COUNT(*) FROM render_jobs WHERE project_id=? AND status IN ('queued','processing','cancelling')",
            (project_id,),
        ).fetchone()[0]
        if active:
            raise RuntimeError("Project has an active export. Wait for it to finish or cancel it before deleting.")
        media = [r[0] for r in db.execute("SELECT stored_name FROM media WHERE project_id=?", (project_id,)).fetchall()]
        renders = [r[0] for r in db.execute("SELECT output_name FROM render_jobs WHERE project_id=? AND output_name IS NOT NULL", (project_id,)).fetchall()]
        db.execute("DELETE FROM project_versions WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM media WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM render_jobs WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))
    return {"media_files": media, "render_files": renders}

def list_projects() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            "SELECT id, name, created_at, updated_at, revision, folder_name, is_favorite "
            "FROM projects ORDER BY is_favorite DESC, updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def list_project_media(project_id: str) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """SELECT id, project_id, filename, mime_type, size_bytes, duration, metadata_json, created_at
               FROM media WHERE project_id=? ORDER BY created_at ASC""",
            (project_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json", "{}"))
        result.append(item)
    return result


def request_job_cancel(job_id: str) -> dict[str, Any] | None:
    """Atomically request cancellation only while a job is queued or processing."""
    with connect() as db:
        db.execute(
            "UPDATE render_jobs SET status='cancelling', updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND status IN ('queued','processing')",
            (job_id,),
        )
        row = db.execute("SELECT * FROM render_jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def start_job(job_id: str) -> bool:
    """Move a queued job to processing without overwriting a concurrent cancel request."""
    with connect() as db:
        cursor = db.execute(
            "UPDATE render_jobs SET status='processing', progress=1, updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND status='queued'",
            (job_id,),
        )
    return cursor.rowcount == 1


def update_job_progress(job_id: str, progress: int) -> None:
    """Update progress only while the job remains actively processing."""
    with connect() as db:
        db.execute(
            "UPDATE render_jobs SET progress=?, updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND status='processing'",
            (max(1, min(99, int(progress))), job_id),
        )


def complete_job_if_processing(job_id: str, output_name: str) -> bool:
    """Publish an output only if cancellation did not win the completion race."""
    with connect() as db:
        cursor = db.execute(
            "UPDATE render_jobs SET status='completed', progress=100, output_name=?, error=NULL, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='processing'",
            (output_name, job_id),
        )
    return cursor.rowcount == 1


def recover_interrupted_jobs() -> list[dict[str, Any]]:
    """Mark jobs left active by a process restart as interrupted, never completed.

    A job that was still queued, processing, or cancelling when the server
    stopped cannot safely resume because its in-memory render graph is gone.
    """
    with connect() as db:
        rows = db.execute(
            "SELECT id, project_id, status, progress, output_name FROM render_jobs "
            "WHERE status IN ('queued','processing','cancelling')"
        ).fetchall()
        db.execute(
            "UPDATE render_jobs SET status='interrupted', error=?, updated_at=CURRENT_TIMESTAMP "
            "WHERE status IN ('queued','processing','cancelling')",
            ("Server restarted before this render finished. Start a new export to retry.",),
        )
    return [dict(row) for row in rows]


def list_project_renders(project_id: str) -> list[dict[str, Any]]:
    """Return render history for one project, newest first."""
    with connect() as db:
        rows = db.execute(
            "SELECT id, project_id, status, progress, output_name, error, created_at, updated_at "
            "FROM render_jobs WHERE project_id=? ORDER BY created_at DESC, rowid DESC",
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_terminal_job(job_id: str) -> dict[str, Any] | None:
    """Delete a render record only after it has reached a terminal state."""
    with connect() as db:
        row = db.execute("SELECT * FROM render_jobs WHERE id=?", (job_id,)).fetchone()
        if not row or row["status"] not in ("completed", "failed", "cancelled", "interrupted"):
            return None
        result = dict(row)
        db.execute("DELETE FROM render_jobs WHERE id=?", (job_id,))
    return result


def duplicate_project(source_project_id: str, new_project_id: str, new_name: str,
                      project: dict[str, Any], media_copies: list[dict[str, Any]]) -> dict[str, Any]:
    """Create an independent project copy with its own media IDs and revision history."""
    serialized = json.dumps(project)
    with connect() as db:
        source = db.execute("SELECT id FROM projects WHERE id=?", (source_project_id,)).fetchone()
        if source is None:
            raise KeyError("Source project not found")
        db.execute(
            "INSERT INTO projects(id,name,project_json,revision) VALUES(?,?,?,1)",
            (new_project_id, new_name, serialized),
        )
        db.execute(
            "INSERT INTO project_versions(project_id,revision,name,project_json) VALUES(?,?,?,?)",
            (new_project_id, 1, new_name, serialized),
        )
        for media in media_copies:
            db.execute(
                """INSERT INTO media(id,project_id,filename,stored_name,mime_type,size_bytes,duration,metadata_json)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (media["id"], new_project_id, media["filename"], media["stored_name"],
                 media["mime_type"], media["size_bytes"], media.get("duration"),
                 json.dumps(media.get("metadata", {}))),
            )
        row = db.execute("SELECT * FROM projects WHERE id=?", (new_project_id,)).fetchone()
    return dict(row)


def duplicate_project_for_owner(owner_id: str, source_project_id: str, new_project_id: str, new_name: str,
                                project: dict[str, Any], media_copies: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a project copy only when its source belongs to the requesting account."""
    serialized = json.dumps(project)
    with connect() as db:
        source = db.execute("SELECT id FROM projects WHERE id=? AND owner_id=?",
                            (source_project_id, owner_id)).fetchone()
        if source is None:
            raise KeyError("Source project not found")
        db.execute(
            "INSERT INTO projects(id,owner_id,name,project_json,revision) VALUES(?,?,?,?,1)",
            (new_project_id, owner_id, new_name, serialized),
        )
        db.execute(
            "INSERT INTO project_versions(project_id,revision,name,project_json) VALUES(?,?,?,?)",
            (new_project_id, 1, new_name, serialized),
        )
        for media in media_copies:
            db.execute(
                """INSERT INTO media(id,project_id,filename,stored_name,mime_type,size_bytes,duration,metadata_json)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (media["id"], new_project_id, media["filename"], media["stored_name"],
                 media["mime_type"], media["size_bytes"], media.get("duration"),
                 json.dumps(media.get("metadata", {}))),
            )
        row = db.execute("SELECT * FROM projects WHERE id=? AND owner_id=?", (new_project_id, owner_id)).fetchone()
    return dict(row)


def get_project_media_records(project_id: str) -> list[dict[str, Any]]:
    """Return internal media records, including storage filenames, for safe project copying."""
    with connect() as db:
        rows = db.execute("SELECT * FROM media WHERE project_id=? ORDER BY created_at ASC", (project_id,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json", "{}"))
        result.append(item)
    return result


def update_project_organization(project_id: str, *, folder_name: str | None = None,
                                is_favorite: bool | None = None) -> dict[str, Any] | None:
    """Update dashboard metadata without creating a content revision."""
    updates: list[str] = []
    values: list[Any] = []
    if folder_name is not None:
        updates.append("folder_name=?")
        values.append(folder_name.strip())
    if is_favorite is not None:
        updates.append("is_favorite=?")
        values.append(1 if is_favorite else 0)
    if not updates:
        with connect() as db:
            row = db.execute("SELECT id,name,created_at,updated_at,revision,folder_name,is_favorite FROM projects WHERE id=?", (project_id,)).fetchone()
        return dict(row) if row else None
    values.append(project_id)
    with connect() as db:
        cursor = db.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id=?", values)
        if cursor.rowcount != 1:
            return None
        row = db.execute("SELECT id,name,created_at,updated_at,revision,folder_name,is_favorite FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(row) if row else None




def update_project_organization_for_owner(owner_id: str, project_id: str, *,
                                          folder_name: str | None = None,
                                          is_favorite: bool | None = None) -> dict[str, Any] | None:
    """Update dashboard metadata only when the project belongs to the signed-in owner."""
    updates: list[str] = []
    values: list[Any] = []
    if folder_name is not None:
        clean_folder = folder_name.strip()
        if len(clean_folder) > 80:
            raise ValueError("Folder name must be 80 characters or fewer.")
        updates.append("folder_name=?")
        values.append(clean_folder)
    if is_favorite is not None:
        updates.append("is_favorite=?")
        values.append(1 if is_favorite else 0)
    if not updates:
        with connect() as db:
            row = db.execute(
                "SELECT id,name,created_at,updated_at,revision,folder_name,is_favorite "
                "FROM projects WHERE id=? AND owner_id=?", (project_id, owner_id)
            ).fetchone()
        return dict(row) if row else None
    values.extend([project_id, owner_id])
    with connect() as db:
        cursor = db.execute(
            f"UPDATE projects SET {', '.join(updates)} WHERE id=? AND owner_id=?", values
        )
        if cursor.rowcount != 1:
            return None
        row = db.execute(
            "SELECT id,name,created_at,updated_at,revision,folder_name,is_favorite "
            "FROM projects WHERE id=? AND owner_id=?", (project_id, owner_id)
        ).fetchone()
    return dict(row) if row else None

# Owner-scoped methods are the required persistence boundary for authenticated routes.
# Legacy rows with owner_id NULL are deliberately invisible to these methods.
def save_project_for_owner(owner_id: str, project_id: str, name: str,
                           project: dict[str, Any], expected_revision: int = 0) -> dict[str, Any]:
    serialized = json.dumps(project)
    with connect() as db:
        owner = db.execute("SELECT id FROM users WHERE id=? AND is_active=1", (owner_id,)).fetchone()
        if owner is None:
            raise KeyError("Account not found")
        row = db.execute("SELECT revision FROM projects WHERE id=? AND owner_id=?",
                         (project_id, owner_id)).fetchone()
        # If the ID exists but belongs to another account (or is a legacy row),
        # treat it as unavailable and never overwrite/reassign it.
        any_row = db.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None and any_row is not None:
            raise KeyError("Project not found")
        if row is None:
            if expected_revision != 0:
                raise ProjectVersionConflict("Project no longer exists at the expected revision.")
            db.execute("INSERT INTO projects(id,owner_id,name,project_json,revision) VALUES(?,?,?,?,1)",
                       (project_id, owner_id, name, serialized))
            db.execute("INSERT INTO project_versions(project_id,revision,name,project_json) VALUES(?,?,?,?)",
                       (project_id, 1, name, serialized))
        else:
            current = int(row["revision"])
            if current != expected_revision:
                raise ProjectVersionConflict(f"Project has a newer cloud revision ({current}).")
            cursor = db.execute("UPDATE projects SET name=?,project_json=?,revision=revision+1,updated_at=CURRENT_TIMESTAMP "
                                "WHERE id=? AND owner_id=? AND revision=?",
                                (name, serialized, project_id, owner_id, expected_revision))
            if cursor.rowcount != 1:
                raise ProjectVersionConflict("Project changed during save.")
            db.execute("INSERT INTO project_versions(project_id,revision,name,project_json) VALUES(?,?,?,?)",
                       (project_id, expected_revision + 1, name, serialized))
        result = db.execute("SELECT * FROM projects WHERE id=? AND owner_id=?", (project_id, owner_id)).fetchone()
    return dict(result)


def list_project_versions_for_owner(owner_id: str, project_id: str) -> list[dict[str, Any]] | None:
    """List revision metadata only after proving the project belongs to the account."""
    with connect() as db:
        owned = db.execute("SELECT 1 FROM projects WHERE id=? AND owner_id=?",
                           (project_id, owner_id)).fetchone()
        if owned is None:
            return None
        rows = db.execute(
            "SELECT project_id,revision,name,created_at FROM project_versions "
            "WHERE project_id=? ORDER BY revision DESC", (project_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_project_version_for_owner(owner_id: str, project_id: str,
                                  revision: int) -> dict[str, Any] | None:
    """Read a snapshot only through an account-owned parent project."""
    with connect() as db:
        row = db.execute(
            "SELECT v.project_id,v.revision,v.name,v.project_json,v.created_at "
            "FROM project_versions v JOIN projects p ON p.id=v.project_id "
            "WHERE p.owner_id=? AND v.project_id=? AND v.revision=?",
            (owner_id, project_id, revision)
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["project"] = json.loads(result.pop("project_json"))
    return result


def get_project_for_owner(owner_id: str, project_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM projects WHERE id=? AND owner_id=?", (project_id, owner_id)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["project"] = json.loads(result.pop("project_json"))
    return result


def list_projects_for_owner(owner_id: str) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT id,name,created_at,updated_at,revision,folder_name,is_favorite "
                           "FROM projects WHERE owner_id=? ORDER BY is_favorite DESC,updated_at DESC",
                           (owner_id,)).fetchall()
    return [dict(row) for row in rows]


def rename_project_for_owner(owner_id: str, project_id: str, new_name: str) -> dict[str, Any] | None:
    clean_name = new_name.strip()
    with connect() as db:
        cursor = db.execute("UPDATE projects SET name=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND owner_id=?",
                            (clean_name, project_id, owner_id))
        if cursor.rowcount != 1:
            return None
        db.execute("UPDATE project_versions SET name=? WHERE project_id=? AND revision=(SELECT revision FROM projects WHERE id=? AND owner_id=?)",
                   (clean_name, project_id, project_id, owner_id))
        row = db.execute("SELECT id,name,created_at,updated_at,revision,folder_name,is_favorite FROM projects WHERE id=? AND owner_id=?",
                         (project_id, owner_id)).fetchone()
    return dict(row) if row else None


def delete_project_for_owner(owner_id: str, project_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT id FROM projects WHERE id=? AND owner_id=?", (project_id, owner_id)).fetchone()
        if row is None:
            return None
        active = db.execute("SELECT COUNT(*) FROM render_jobs WHERE project_id=? AND status IN ('queued','processing','cancelling')",
                            (project_id,)).fetchone()[0]
        if active:
            raise RuntimeError("Project has an active export. Wait for it to finish or cancel it before deleting.")
        media = [r[0] for r in db.execute("SELECT stored_name FROM media WHERE project_id=?", (project_id,)).fetchall()]
        renders = [r[0] for r in db.execute("SELECT output_name FROM render_jobs WHERE project_id=? AND output_name IS NOT NULL", (project_id,)).fetchall()]
        db.execute("DELETE FROM project_versions WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM media WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM render_jobs WHERE project_id=?", (project_id,))
        cursor = db.execute("DELETE FROM projects WHERE id=? AND owner_id=?", (project_id, owner_id))
        if cursor.rowcount != 1:
            raise RuntimeError("Project ownership changed during deletion.")
    return {"media_files": media, "render_files": renders}


# Owner-scoped media access. Authorization is inherited from the parent project.
def add_media_for_owner(owner_id: str, media: dict[str, Any]) -> None:
    with connect() as db:
        project = db.execute(
            "SELECT id FROM projects WHERE id=? AND owner_id=?",
            (media["project_id"], owner_id),
        ).fetchone()
        if project is None:
            raise KeyError("Project not found")
        db.execute("""
            INSERT INTO media(id,project_id,filename,stored_name,mime_type,size_bytes,duration,metadata_json)
            VALUES(?,?,?,?,?,?,?,?)
        """, (media["id"], media["project_id"], media["filename"], media["stored_name"],
              media["mime_type"], media["size_bytes"], media.get("duration"),
              json.dumps(media.get("metadata", {}))))


def list_project_media_for_owner(owner_id: str, project_id: str) -> list[dict[str, Any]] | None:
    with connect() as db:
        project = db.execute(
            "SELECT id FROM projects WHERE id=? AND owner_id=?",
            (project_id, owner_id),
        ).fetchone()
        if project is None:
            return None
        rows = db.execute(
            """SELECT m.id,m.project_id,m.filename,m.mime_type,m.size_bytes,m.duration,
                      m.metadata_json,m.created_at
               FROM media m JOIN projects p ON p.id=m.project_id
               WHERE m.project_id=? AND p.owner_id=? ORDER BY m.created_at ASC""",
            (project_id, owner_id),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json", "{}"))
        result.append(item)
    return result


def get_media_for_owner(owner_id: str, media_id: str, project_id: str | None = None) -> dict[str, Any] | None:
    query = """SELECT m.* FROM media m JOIN projects p ON p.id=m.project_id
               WHERE m.id=? AND p.owner_id=?"""
    params: tuple[Any, ...] = (media_id, owner_id)
    if project_id is not None:
        query += " AND m.project_id=?"
        params += (project_id,)
    with connect() as db:
        row = db.execute(query, params).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["metadata"] = json.loads(result.pop("metadata_json", "{}"))
    return result


def create_job_for_owner(owner_id: str, job_id: str, project_id: str) -> bool:
    """Create a render job only when its project belongs to the authenticated owner."""
    with connect() as db:
        project = db.execute(
            "SELECT id FROM projects WHERE id=? AND owner_id=?", (project_id, owner_id)
        ).fetchone()
        if project is None:
            return False
        db.execute(
            "INSERT INTO render_jobs(id,project_id,status) VALUES(?,?,?)",
            (job_id, project_id, "queued"),
        )
    return True


def get_job_for_owner(owner_id: str, job_id: str) -> dict[str, Any] | None:
    """Read a render job only through a project owned by the authenticated user."""
    with connect() as db:
        row = db.execute(
            "SELECT r.* FROM render_jobs r JOIN projects p ON p.id=r.project_id "
            "WHERE r.id=? AND p.owner_id=?", (job_id, owner_id)
        ).fetchone()
    return dict(row) if row else None


def list_project_renders_for_owner(owner_id: str, project_id: str) -> list[dict[str, Any]] | None:
    """Return None for a missing/foreign project; otherwise return its render history."""
    with connect() as db:
        project = db.execute(
            "SELECT id FROM projects WHERE id=? AND owner_id=?", (project_id, owner_id)
        ).fetchone()
        if project is None:
            return None
        rows = db.execute(
            "SELECT r.id,r.project_id,r.status,r.progress,r.output_name,r.error,r.created_at,r.updated_at "
            "FROM render_jobs r WHERE r.project_id=? ORDER BY r.created_at DESC,r.rowid DESC",
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def request_job_cancel_for_owner(owner_id: str, job_id: str) -> dict[str, Any] | None:
    """Atomically request cancellation only for a job belonging to this owner."""
    with connect() as db:
        db.execute(
            "UPDATE render_jobs SET status='cancelling',updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND status IN ('queued','processing') AND project_id IN "
            "(SELECT id FROM projects WHERE owner_id=?)", (job_id, owner_id)
        )
        row = db.execute(
            "SELECT r.* FROM render_jobs r JOIN projects p ON p.id=r.project_id "
            "WHERE r.id=? AND p.owner_id=?", (job_id, owner_id)
        ).fetchone()
    return dict(row) if row else None


def delete_terminal_job_for_owner(owner_id: str, job_id: str) -> dict[str, Any] | None:
    """Delete a terminal render record only when its parent project is owner-scoped."""
    with connect() as db:
        row = db.execute(
            "SELECT r.* FROM render_jobs r JOIN projects p ON p.id=r.project_id "
            "WHERE r.id=? AND p.owner_id=?", (job_id, owner_id)
        ).fetchone()
        if row is None or row["status"] not in ("completed", "failed", "cancelled", "interrupted"):
            return None
        result = dict(row)
        db.execute("DELETE FROM render_jobs WHERE id=?", (job_id,))
    return result
