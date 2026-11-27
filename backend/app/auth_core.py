from __future__ import annotations
import hashlib, secrets, sqlite3, time, uuid
from dataclasses import dataclass
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()
TTL_SECONDS = 7 * 24 * 60 * 60

@dataclass(frozen=True)
class User:
    id: str
    email: str

class AuthError(Exception): pass
class InvalidCredentials(AuthError): pass
class EmailAlreadyRegistered(AuthError): pass

def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_user(db: sqlite3.Connection, email: str, password: str) -> User:
    email = email.strip().casefold()
    if not email or "@" not in email or len(email) > 254:
        raise ValueError("Enter a valid email address.")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")
    if len(password) > 1024:
        raise ValueError("Password is too long.")
    try:
        user_id = str(uuid.uuid4())
        db.execute("INSERT INTO users(id,email,password_hash) VALUES(?,?,?)",
                   (user_id, email, _hasher.hash(password)))
        db.commit()
        return User(user_id, email)
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyRegistered() from exc

def authenticate(db: sqlite3.Connection, email: str, password: str) -> User:
    email = email.strip().casefold()
    row = db.execute("SELECT id,email,password_hash,is_active FROM users WHERE email=?", (email,)).fetchone()
    if row is None:
        raise InvalidCredentials()
    try:
        valid = _hasher.verify(row["password_hash"], password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, TypeError):
        valid = False
    if not valid or not row["is_active"]:
        raise InvalidCredentials()
    if _hasher.check_needs_rehash(row["password_hash"]):
        db.execute("UPDATE users SET password_hash=? WHERE id=?", (_hasher.hash(password), row["id"]))
        db.commit()
    return User(row["id"], row["email"])

def create_session(db: sqlite3.Connection, user_id: str) -> tuple[str, int]:
    token = secrets.token_urlsafe(32)
    expires = int(time.time()) + TTL_SECONDS
    db.execute("INSERT INTO sessions(id,user_id,token_hash,expires_at) VALUES(?,?,?,?)",
               (str(uuid.uuid4()), user_id, _digest(token), expires))
    db.commit()
    return token, expires

def resolve_session(db: sqlite3.Connection, token: str | None) -> User | None:
    if not token or len(token) > 512:
        return None
    now = int(time.time())
    row = db.execute("""SELECT u.id,u.email FROM sessions s JOIN users u ON u.id=s.user_id
        WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>? AND u.is_active=1""",
        (_digest(token), now)).fetchone()
    if row is None:
        return None
    db.execute("UPDATE sessions SET last_seen_at=? WHERE token_hash=?", (now, _digest(token)))
    db.commit()
    return User(row["id"], row["email"])

def revoke_session(db: sqlite3.Connection, token: str) -> None:
    db.execute("UPDATE sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
               (int(time.time()), _digest(token)))
    db.commit()
