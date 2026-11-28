from __future__ import annotations
import hashlib, hmac, os, secrets, smtplib, time, logging
from email.message import EmailMessage
from argon2 import PasswordHasher
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from . import storage
from .auth_core import (AuthError, InvalidCredentials, authenticate, create_session,
                        create_user, resolve_session, revoke_session)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
COOKIE = "flexy_session"
CSRF = "flexy_csrf"
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_FAILURES = 5
RESET_TOKEN_TTL_SECONDS = 30 * 60
_password_hasher = PasswordHasher()
_logger = logging.getLogger(__name__)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=1024)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=12, max_length=1024)


def _origins():
    raw = os.getenv("FLEXY_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return {v.strip().rstrip("/") for v in raw.split(",") if v.strip()}


def _origin_check(request: Request):
    origin = request.headers.get("origin", "").rstrip("/")
    if not origin or origin not in _origins():
        raise HTTPException(403, "Untrusted request origin.")


def _csrf_check(request: Request):
    _origin_check(request)
    a = request.cookies.get(CSRF, "")
    b = request.headers.get("x-csrf-token", "")
    if not a or not b or not hmac.compare_digest(a, b):
        raise HTTPException(403, "CSRF validation failed.")


def _login_key(request: Request, email: str) -> str:
    # Store only a digest, never raw email addresses or client IPs, in limiter state.
    client_ip = request.client.host if request.client else "unknown"
    value = f"{email.strip().casefold()}\\0{client_ip}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reserve_login_attempt(db, key_hash: str, now: int) -> bool:
    """Atomically reserve an attempt so parallel requests cannot bypass the limit."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS auth_login_limits (
            key_hash TEXT PRIMARY KEY,
            failures INTEGER NOT NULL,
            window_started INTEGER NOT NULL
        )
    """)
    db.execute("BEGIN IMMEDIATE")
    db.execute(
        "DELETE FROM auth_login_limits WHERE window_started < ?",
        (now - 2 * LOGIN_WINDOW_SECONDS,),
    )
    row = db.execute("""
        INSERT INTO auth_login_limits(key_hash, failures, window_started)
        VALUES(?, 1, ?)
        ON CONFLICT(key_hash) DO UPDATE SET
            failures = CASE
                WHEN excluded.window_started - auth_login_limits.window_started >= ?
                THEN 1 ELSE auth_login_limits.failures + 1
            END,
            window_started = CASE
                WHEN excluded.window_started - auth_login_limits.window_started >= ?
                THEN excluded.window_started ELSE auth_login_limits.window_started
            END
        RETURNING failures
    """, (key_hash, now, LOGIN_WINDOW_SECONDS, LOGIN_WINDOW_SECONDS)).fetchone()
    db.commit()
    return int(row["failures"]) <= LOGIN_MAX_FAILURES


def _send_password_reset_email(email: str, token: str) -> None:
    """Send reset link using explicitly configured SMTP; never log the secret token."""
    host = os.getenv("FLEXY_SMTP_HOST")
    sender = os.getenv("FLEXY_SMTP_FROM")
    if not host or not sender:
        raise RuntimeError("Password reset email delivery is not configured.")
    port = int(os.getenv("FLEXY_SMTP_PORT", "587"))
    username = os.getenv("FLEXY_SMTP_USER", "")
    password = os.getenv("FLEXY_SMTP_PASSWORD", "")
    app_url = os.getenv("FLEXY_PUBLIC_APP_URL", "").rstrip("/")
    if not app_url.startswith("https://"):
        raise RuntimeError("FLEXY_PUBLIC_APP_URL must be an HTTPS URL.")
    message = EmailMessage()
    message["Subject"] = "Reset your FLEXY AI password"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        "We received a request to reset your FLEXY AI password.\n\n"
        f"Use this one-time link within 30 minutes: {app_url}/reset-password?token={token}\n\n"
        "If you did not request this, you can ignore this email."
    )
    with smtplib.SMTP(host, port, timeout=10) as server:
        server.starttls()
        if username:
            server.login(username, password)
        server.send_message(message)


def current_user(request: Request):
    db = storage.connect()
    try:
        user = resolve_session(db, request.cookies.get(COOKIE))
    finally:
        db.close()
    if user is None:
        raise HTTPException(401, "Authentication required.")
    return user


def _issue(response: Response, token: str):
    secure = os.getenv("FLEXY_COOKIE_SECURE", "true").lower() == "true"
    csrf = secrets.token_urlsafe(32)
    response.set_cookie(COOKIE, token, max_age=7*86400, httponly=True,
                        secure=secure, samesite="lax", path="/")
    response.set_cookie(CSRF, csrf, max_age=7*86400, httponly=False,
                        secure=secure, samesite="lax", path="/")


@router.post("/register", status_code=201)
def register(payload: Credentials, request: Request, response: Response):
    _origin_check(request)
    db = storage.connect()
    try:
        user = create_user(db, payload.email, payload.password)
        token, _ = create_session(db, user.id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(409, "An account with that email already exists.") from exc
    finally:
        db.close()
    _issue(response, token)
    return {"id": user.id, "email": user.email}


@router.post("/login")
def login(payload: Credentials, request: Request, response: Response):
    _origin_check(request)
    db = storage.connect()
    key_hash = _login_key(request, payload.email)
    try:
        if not _reserve_login_attempt(db, key_hash, int(time.time())):
            raise HTTPException(429, "Too many login attempts. Please try again in 15 minutes.")
        try:
            user = authenticate(db, payload.email, payload.password)
        except InvalidCredentials as exc:
            raise HTTPException(401, "Invalid email or password.") from exc
        db.execute("DELETE FROM auth_login_limits WHERE key_hash=?", (key_hash,))
        db.commit()
        token, _ = create_session(db, user.id)
    finally:
        db.close()
    _issue(response, token)
    return {"id": user.id, "email": user.email}


@router.post("/password-reset/request")
def request_password_reset(payload: PasswordResetRequest, request: Request):
    _origin_check(request)
    email = payload.email.strip().casefold()
    db = storage.connect()
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    try:
        user = db.execute(
            "SELECT id,email FROM users WHERE email=? AND is_active=1", (email,)
        ).fetchone()
        if user:
            now = int(time.time())
            db.execute(
                "UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",
                (now, user["id"]),
            )
            db.execute(
                "INSERT INTO password_reset_tokens(token_hash,user_id,expires_at) VALUES(?,?,?)",
                (token_hash, user["id"], now + RESET_TOKEN_TTL_SECONDS),
            )
            db.commit()
            recipient = user["email"]
        else:
            recipient = None
    finally:
        db.close()
    if recipient:
        try:
            _send_password_reset_email(recipient, token)
        except Exception:
            _logger.exception("Password reset email could not be delivered")
    # Same response for known and unknown addresses prevents account enumeration.
    return {"message": "If an account exists for that email, password reset instructions will be sent."}


@router.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirm, request: Request):
    _origin_check(request)
    if len(payload.new_password) > 1024:
        raise HTTPException(422, "Password is too long.")
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    now = int(time.time())
    db = storage.connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""
            SELECT user_id FROM password_reset_tokens
            WHERE token_hash=? AND used_at IS NULL AND expires_at>?
        """, (token_hash, now)).fetchone()
        if row is None:
            db.rollback()
            raise HTTPException(400, "This password reset link is invalid or has expired.")
        db.execute(
            "UPDATE users SET password_hash=? WHERE id=? AND is_active=1",
            (_password_hasher.hash(payload.new_password), row["user_id"]),
        )
        db.execute(
            "UPDATE password_reset_tokens SET used_at=? WHERE token_hash=? AND used_at IS NULL",
            (now, token_hash),
        )
        db.execute(
            "UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",
            (now, row["user_id"]),
        )
        # A password change invalidates every existing session on every device.
        db.execute(
            "UPDATE sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
            (now, row["user_id"]),
        )
        db.commit()
    finally:
        db.close()
    return {"password_reset": True, "message": "Password updated. Please sign in again."}


@router.get("/me")
def me(user=Depends(current_user)):
    return {"id": user.id, "email": user.email}


@router.post("/logout")
def logout(request: Request, response: Response):
    _csrf_check(request)
    token = request.cookies.get(COOKIE, "")
    db = storage.connect()
    try:
        if token:
            revoke_session(db, token)
    finally:
        db.close()
    response.delete_cookie(COOKIE, path="/")
    response.delete_cookie(CSRF, path="/")
    return {"logged_out": True}
