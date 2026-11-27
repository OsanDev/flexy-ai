from __future__ import annotations
import hmac, os, secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from . import storage
from .auth_core import (AuthError, InvalidCredentials, authenticate, create_session,
                        create_user, resolve_session, revoke_session)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
COOKIE = "flexy_session"
CSRF = "flexy_csrf"

class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=1024)

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
    try:
        user = authenticate(db, payload.email, payload.password)
        token, _ = create_session(db, user.id)
    except InvalidCredentials as exc:
        raise HTTPException(401, "Invalid email or password.") from exc
    finally:
        db.close()
    _issue(response, token)
    return {"id": user.id, "email": user.email}

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
