import hashlib
import hmac
import json
import logging
import math
import os
import random
import re
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlsplit

import httpx
import jwt
import requests

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pysteamsignin.steamsignin import SteamSignIn
from dotenv import load_dotenv

from models import User, UserStats, Duel, DuelRoundEvent, Base, GameServer, News, DuelRequest, PremiumTariff, TransactionHistory, PlatformSettings, \
    PaymentMethod
from database import engine, session_local
from schemas import (
    DuelDetailsResponse,
    DuelHistoryEntry,
    DuelLobbyResponse,
    DuelRequestResponse,
    DuelRoundEventResponse,
    GameServerCreate,
    GameServerResponse,
    GameServerUpdate,
    MainPayloadResponse,
    NewsResponse,
    PaymentHistoryEntry,
    PaymentMethodResponse,
    ProfileResponse,
    TariffResponse,
    UserResponse,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
LOGGER = logging.getLogger("likeagod.security")

APP_ENV = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).strip().lower() or "development"
IS_PRODUCTION = APP_ENV in {"prod", "production"}
SESSION_TTL = timedelta(days=7)
SESSION_MAX_AGE = int(SESSION_TTL.total_seconds())
COOKIE_DOMAIN = (os.getenv("COOKIE_DOMAIN") or ("likeagod.net" if IS_PRODUCTION else "")).strip() or None
COOKIE_SAMESITE = (os.getenv("COOKIE_SAMESITE", "lax").strip().lower() or "lax")
if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    COOKIE_SAMESITE = "lax"
COOKIE_SECURE = (os.getenv("COOKIE_SECURE", "1" if IS_PRODUCTION else "0").strip().lower() not in {"0", "false", "no"})
STEAM_RETURN_TO = os.getenv(
    "STEAM_RETURN_TO",
    "https://likeagod.net/auth/steam/callback" if IS_PRODUCTION else "http://localhost/auth/steam/callback"
).strip()
DEFAULT_CORS_ORIGINS = "https://likeagod.net,https://www.likeagod.net,http://localhost,http://127.0.0.1:8000"
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if origin.strip()]
ADMIN_FRONTEND_PATH = "/" + (os.getenv("ADMIN_FRONTEND_PATH", "").strip().strip("/")) if os.getenv("ADMIN_FRONTEND_PATH") else None
if ADMIN_FRONTEND_PATH == "/admin":
    ADMIN_FRONTEND_PATH = None

LANGUAGE_ALLOWLIST = {"en", "ru", "es", "zh", "de"}
MAP_ALLOWLIST = {"aim_redline", "aim_ag_texture", "awp_india"}
PAYMENT_METHOD_TYPES = {"deposit", "withdraw"}
INSECURE_SECRET_MARKERS = {
    "123456:aa....",
    "super_secret_token_for_cs2_server",
    "your_merchant_id",
    "your_secret_1",
    "your_secret_2",
    "changeme",
    "secret",
    "test",
}
USERNAME_RE = re.compile(r"^[A-Za-z0-9]{3,32}$")
COUNTRY_RE = re.compile(r"^[A-Z]{2,5}$")
TELEGRAM_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")
ADMIN_FRONTEND_PATH_RE = re.compile(r"^/[a-f0-9]{16,128}$")
DEFAULT_COUNTRY = (os.getenv("DEFAULT_COUNTRY", "US").strip().upper() or "US")
if not COUNTRY_RE.fullmatch(DEFAULT_COUNTRY):
    DEFAULT_COUNTRY = "US"
MAX_DUEL_BANK = 100000.0
MAX_PAYMENT_AMOUNT = 100000.0
MAX_ADMIN_BALANCE_ADJUSTMENT = 1000000.0
MAX_BIO_LENGTH = 150
MAX_URL_LENGTH = 2048
RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


app = FastAPI(
    title="LikeGod Esports Tournament Platform Core API",
    description="Backend engine for competitive esports matchmaking, player statistics tracking and platform events allocation.",
    version="1.9.7",
    docs_url="/docs"
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "X-CSRF-Token", "X-Requested-With", "X-Server-Api-Key"],
)

steam_login = SteamSignIn()
ALGORITHM = "HS256"
CRYPTO_PAY_API_URL = "https://pay.crypt.bot/api"


def is_secret_strong(value: str, min_length: int) -> bool:
    if len(value) < min_length or any(value.casefold() == marker.casefold() for marker in INSECURE_SECRET_MARKERS):
        return False
    classes = (
        any(ch.islower() for ch in value),
        any(ch.isupper() for ch in value),
        any(ch.isdigit() for ch in value),
        any(not ch.isalnum() for ch in value),
    )
    return sum(classes) >= 3 and len(set(value)) >= min(12, max(6, min_length // 2))


def read_secret(name: str, *, min_length: int, required_in_production: bool, allow_dev_fallback: bool = False) -> Optional[str]:
    value = os.getenv(name, "").strip()
    if not value:
        if allow_dev_fallback and not IS_PRODUCTION:
            return secrets.token_urlsafe(max(min_length, 32))
        if required_in_production:
            raise RuntimeError(f"{name} must be configured via environment in production")
        return None
    if not is_secret_strong(value, min_length):
        if required_in_production:
            raise RuntimeError(f"{name} is too weak for production; provide a longer high-entropy value")
        if allow_dev_fallback:
            return secrets.token_urlsafe(max(min_length, 32))
    return value


def read_required_setting(name: str, *, required_in_production: bool, placeholder_values: tuple[str, ...] = ()) -> Optional[str]:
    value = os.getenv(name, "").strip()
    if not value:
        if required_in_production:
            raise RuntimeError(f"{name} must be configured via environment in production")
        return None
    if value.lower() in {placeholder.lower() for placeholder in placeholder_values} and required_in_production:
        raise RuntimeError(f"{name} must not use a placeholder value in production")
    return value


def validate_runtime_configuration():
    if ADMIN_FRONTEND_PATH and not ADMIN_FRONTEND_PATH_RE.fullmatch(ADMIN_FRONTEND_PATH):
        raise RuntimeError("ADMIN_FRONTEND_PATH must be a hex-like path such as /0123abcdef456789")


SECRET_KEY = read_secret("SECRET_KEY", min_length=32, required_in_production=True, allow_dev_fallback=True)
STEAM_API_KEY = read_required_setting("STEAM_API_KEY", required_in_production=IS_PRODUCTION)
SERVER_API_KEY = read_secret("SERVER_API_KEY", min_length=24, required_in_production=IS_PRODUCTION)
CRYPTO_PAY_TOKEN = read_secret("CRYPTO_PAY_TOKEN", min_length=24, required_in_production=IS_PRODUCTION)
AAIO_MERCHANT_ID = read_required_setting(
    "AAIO_MERCHANT_ID", required_in_production=IS_PRODUCTION, placeholder_values=("your_merchant_id",)
)
AAIO_SECRET_1 = read_secret("AAIO_SECRET_1", min_length=24, required_in_production=IS_PRODUCTION)
AAIO_SECRET_2 = read_secret("AAIO_SECRET_2", min_length=24, required_in_production=IS_PRODUCTION)
validate_runtime_configuration()

Base.metadata.create_all(bind=engine)

# ---- Schema migrations (idempotent column additions) ----
_mig_db = session_local()
try:
    from sqlalchemy import text as _sql_text
    try:
        _mig_db.execute(_sql_text("ALTER TABLE platform_settings ADD COLUMN maintenance_mode BOOLEAN DEFAULT 0"))
        _mig_db.commit()
    except Exception as _mig_exc:
        _mig_db.rollback()
        if "duplicate column" not in str(_mig_exc).lower() and "already exists" not in str(_mig_exc).lower():
            LOGGER.warning("Migration warning for maintenance_mode column: %s", _mig_exc)
finally:
    _mig_db.close()

db = session_local()
try:
    if not db.query(PlatformSettings).first():
        db.add(PlatformSettings(commission_percent=10.0))
        db.commit()

    if not db.query(PaymentMethod).first():
        db.add_all([
            PaymentMethod(name="Telegram CryptoBot", gateway_alias="cryptobot", type="deposit",
                          commission_label="Fee: 3%", commission_percent=3.0, min_amount=1.0, currency_code="USD",
                          is_active=True),
            PaymentMethod(name="Crypto Wallet Payout", gateway_alias="cryptobot", type="withdraw",
                          commission_label="Fee: 1.5%", commission_percent=0.0, min_amount=1.0, currency_code="USD",
                          is_active=True),
            PaymentMethod(name="Visa / Mastercard / СБП", gateway_alias="aaio_rub", type="deposit",
                          commission_label="Fee: 0%", commission_percent=0.0, min_amount=1.0, currency_code="RUB",
                          is_active=True)
        ])
        db.commit()
finally:
    db.close()


# ==================== UTILS & CORE MIDDLEWARES ====================


def normalize_string(value, *, field: str, max_length: int, allow_empty: bool = True) -> str:
    text = str(value or "").strip()
    if not allow_empty and not text:
        raise HTTPException(status_code=400, detail=f"{field} is required")
    if len(text) > max_length:
        raise HTTPException(status_code=400, detail=f"{field} is too long")
    return text


def parse_float_field(value, *, field: str, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{field} must be a number")
    if not math.isfinite(parsed):
        raise HTTPException(status_code=400, detail=f"{field} must be finite")
    if minimum is not None and parsed < minimum:
        raise HTTPException(status_code=400, detail=f"{field} is below the allowed minimum")
    if maximum is not None and parsed > maximum:
        raise HTTPException(status_code=400, detail=f"{field} exceeds the allowed maximum")
    return parsed


def parse_int_field(value, *, field: str, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{field} must be an integer")
    if minimum is not None and parsed < minimum:
        raise HTTPException(status_code=400, detail=f"{field} is below the allowed minimum")
    if maximum is not None and parsed > maximum:
        raise HTTPException(status_code=400, detail=f"{field} exceeds the allowed maximum")
    return parsed


def parse_bool_field(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise HTTPException(status_code=400, detail="Boolean field contains an invalid value")


def validate_url_field(value, *, field: str, allow_empty: bool = True) -> Optional[str]:
    text = normalize_string(value, field=field, max_length=MAX_URL_LENGTH, allow_empty=allow_empty)
    if not text:
        return None
    parts = urlsplit(text)
    if parts.scheme and parts.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail=f"{field} must use http, https, or a relative path")
    if parts.scheme and not parts.netloc:
        raise HTTPException(status_code=400, detail=f"{field} is invalid")
    if text.lower().startswith("javascript:"):
        raise HTTPException(status_code=400, detail=f"{field} is invalid")
    return text


def validate_url_host(url: str, *, field: str, allowed_hosts: tuple[str, ...]) -> str:
    parts = urlsplit(url)
    if parts.netloc and parts.netloc not in allowed_hosts:
        raise HTTPException(status_code=502, detail=f"{field} host is invalid")
    return url


def ensure_payment_gateway_configured(*required_values: Optional[str]):
    if not all(required_values):
        raise HTTPException(status_code=503, detail="Payment gateway is temporarily unavailable")


def issue_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"user_id": user_id, "iat": now, "exp": now + SESSION_TTL, "jti": secrets.token_hex(16)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_session_cookies(response: RedirectResponse, user_id: int):
    response.set_cookie(
        "access_token",
        issue_access_token(user_id),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
        max_age=SESSION_MAX_AGE,
    )
    response.set_cookie(
        "csrf_token",
        generate_csrf_token(),
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
        max_age=SESSION_MAX_AGE,
    )


def clear_session_cookies(response: RedirectResponse):
    response.delete_cookie("access_token", domain=COOKIE_DOMAIN, path="/")
    response.delete_cookie("csrf_token", domain=COOKIE_DOMAIN, path="/")


def resolve_current_user(request: Request, db: Session) -> Optional[User]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    user_id = decode_jwt_token(token)
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def client_rate_limit_key(request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    token_user = decode_jwt_token(request.cookies.get("access_token", "")) or "anon"
    return f"{token_user}:{ip}"


def get_rate_limit_rule(request: Request) -> Optional[tuple[str, int, int]]:
    path = request.url.path
    if path in {"/auth/steam", "/auth/steam/callback"}:
        return "auth", 60, 20
    if path in {"/api/v1/payments/deposit", "/api/v1/payments/withdraw", "/api/v1/payments/cancel"}:
        return "payments", 60, 10
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and (
        path.startswith("/api/v1/admin/") or path == "/news/create" or path.startswith("/news/")
    ):
        return "admin", 60, 20
    if path.startswith("/api/v1/server/"):
        return "server", 60, 120
    return None


def is_csrf_exempt_path(path: str) -> bool:
    return path == "/api/v1/payments/webhook" or path.startswith("/api/v1/server/")


def verify_csrf(request: Request):
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    if is_csrf_exempt_path(request.url.path) or not request.cookies.get("access_token"):
        return
    csrf_cookie = request.cookies.get("csrf_token")
    csrf_header = request.headers.get("x-csrf-token", "")
    if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="CSRF verification failed")


def verify_crypto_pay_signature(request: Request, raw_body: bytes):
    ensure_payment_gateway_configured(CRYPTO_PAY_TOKEN)
    signature = request.headers.get("crypto-pay-api-signature", "").strip()
    if not signature:
        raise HTTPException(status_code=401, detail="Webhook signature missing")
    expected_signature = hmac.new(CRYPTO_PAY_TOKEN.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Webhook signature invalid")


@app.middleware("http")
async def security_controls(request: Request, call_next):
    admin_paths = {"/admin"}
    if ADMIN_FRONTEND_PATH:
        admin_paths.add(ADMIN_FRONTEND_PATH)

    if request.url.path in admin_paths:
        db = session_local()
        try:
            current_user = resolve_current_user(request, db)
        finally:
            db.close()
        if not current_user or current_user.role != "admin":
            return PlainTextResponse("Not Found", status_code=404)
        if request.url.path != "/admin":
            request.scope["path"] = "/admin"
            request.scope["raw_path"] = b"/admin"

    rule = get_rate_limit_rule(request)
    if rule:
        bucket, window_seconds, max_requests = rule
        key = f"{bucket}:{client_rate_limit_key(request)}"
        now = time.monotonic()
        window = RATE_LIMIT_BUCKETS[key]
        while window and now - window[0] >= window_seconds:
            window.popleft()
        if len(window) >= max_requests:
            return JSONResponse(status_code=429, content={"detail": "Too many requests. Please retry later."})
        window.append(now)

    try:
        verify_csrf(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "accelerometer=(), camera=(), geolocation=(), microphone=(), payment=(), usb=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self' https://steamcommunity.com; "
        "img-src 'self' data: https:; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self' https://pay.crypt.bot https://aaio.so https://api.steampowered.com https://steamcommunity.com;"
    )

    if request.cookies.get("access_token") and not request.cookies.get("csrf_token"):
        response.set_cookie(
            "csrf_token",
            generate_csrf_token(),
            httponly=False,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            domain=COOKIE_DOMAIN,
            path="/",
            max_age=SESSION_MAX_AGE,
        )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    LOGGER.exception("Unhandled server error on %s %s", request.method, request.url.path)
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        try:
            return templates.TemplateResponse(request, "500.html", status_code=500)
        except Exception:
            pass
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and exc.status_code == 404:
        try:
            return templates.TemplateResponse(request, "404.html", status_code=404)
        except Exception:
            pass
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def get_db():
    db = session_local()
    try:
        yield db
    finally:
        db.close()


def decode_jwt_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get('user_id')
    except jwt.InvalidTokenError:
        return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    return resolve_current_user(request, db)


def require_auth(current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication missing or expired")
    return current_user


def require_admin(current_user: User = Depends(require_auth)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return current_user


def require_server_key(request: Request):
    """Authenticate CS2 server-to-server calls via X-Server-Api-Key header.

    NOTE: This currently uses a single shared secret for all CS2 servers
    (single dathost operator). TODO: add per-server API keys if multiple
    independent CS2 hosting operators are supported in the future.
    """
    if not SERVER_API_KEY:
        raise HTTPException(status_code=503, detail="Server API key not configured")
    provided = request.headers.get("X-Server-Api-Key", "")
    if not provided or not secrets.compare_digest(provided, SERVER_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing server API key")


def calculate_shares(creator_elo: int, opponent_elo: int, total_bank: float):
    weight_creator = 10 ** (creator_elo / 400)
    weight_opponent = 10 ** (opponent_elo / 400)
    chance_creator = weight_creator / (weight_creator + weight_opponent)
    return round(total_bank * chance_creator, 2), round(total_bank * (1 - chance_creator), 2)


def check_wager_limit(wagered: float, required_share: float):
    if wagered < 6.0 and required_share > 2.0:
        raise HTTPException(status_code=400, detail="Bet limit capped at $2.00 until overall wager reaches $6.00")
    elif wagered < 20.0 and required_share > 4.0:
        raise HTTPException(status_code=400, detail="Bet limit capped at $4.00 until overall wager reaches $20.00")


def check_active_match_existence(user_id: int, db: Session):
    match = db.query(Duel).filter(
        ((Duel.creator_id == user_id) | (Duel.guest_id == user_id)),
        Duel.status.in_(_ACTIVE_STATUSES)
    ).first()
    if match:
        raise HTTPException(status_code=400, detail=f"Action blocked: You are already in an active match #{match.id}")


def get_current_commission(db: Session) -> float:
    settings = db.query(PlatformSettings).first()
    return settings.commission_percent if settings else 10.0


def get_maintenance_mode(db: Session) -> bool:
    settings = db.query(PlatformSettings).first()
    return bool(settings.maintenance_mode) if settings and settings.maintenance_mode is not None else False


def get_rank_from_elo(elo: int) -> int:
    return max(1, min(10, (elo - 700) // 100))


def get_user_stats_or_404(user_id: int, db: Session) -> UserStats:
    stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
    if not stats:
        raise HTTPException(status_code=404, detail="Player statistics not found")
    return stats


def get_duel_or_404(duel_id: int, db: Session) -> Duel:
    duel = db.query(Duel).filter(Duel.id == duel_id).first()
    if not duel:
        raise HTTPException(status_code=404, detail="Duel not found")
    return duel


# ==================== MATCH-ORCHESTRATION HELPERS ====================

_RESERVATION_TIMEOUT = timedelta(minutes=5)
_ACTIVE_STATUSES = {'waiting', 'ready', 'playing', 'processing', 'disputed', 'warmup', 'paused', 'reserving'}


def _release_server(server: GameServer, db: Session) -> None:
    """Mark a game server as open and clear its current duel binding."""
    server.status = "open"
    server.current_duel_id = None


def _release_frozen_balances(duel: Duel, db: Session) -> None:
    """Unfreeze both players' frozen balance contributions for a duel."""
    creator_stats = db.query(UserStats).filter(UserStats.user_id == duel.creator_id).first()
    if creator_stats:
        creator_stats.balance = round(creator_stats.balance + duel.creator_share, 2)
        creator_stats.frozen_balance = round(max(0.0, creator_stats.frozen_balance - duel.creator_share), 2)
    if duel.guest_id:
        guest_stats = db.query(UserStats).filter(UserStats.user_id == duel.guest_id).first()
        if guest_stats:
            guest_stats.balance = round(guest_stats.balance + duel.guest_share, 2)
            guest_stats.frozen_balance = round(max(0.0, guest_stats.frozen_balance - duel.guest_share), 2)


def _cancel_duel_and_release(duel: Duel, db: Session) -> None:
    """Transition a duel to 'cancelled', release server, and unfreeze balances.

    Keeps the duel row as an audit record instead of deleting it.
    """
    if duel.game_server_id:
        server = db.query(GameServer).filter(GameServer.id == duel.game_server_id).first()
        if server:
            _release_server(server, db)
    _release_frozen_balances(duel, db)
    duel.status = "cancelled"
    duel.ended_at = datetime.utcnow()
    db.query(DuelRequest).filter(
        DuelRequest.duel_id == duel.id, DuelRequest.status == "pending"
    ).update({"status": "declined"}, synchronize_session=False)


def _execute_duel_payout(duel: Duel, winner_id: int, db: Session) -> None:
    """Apply commission-adjusted payout, ELO update, and balance settlement.

    Reused by both the user-facing confirm endpoint and the CS2 server
    complete endpoint. Caller is responsible for committing.
    """
    creator_stats = db.query(UserStats).filter(UserStats.user_id == duel.creator_id).first()
    guest_stats = db.query(UserStats).filter(UserStats.user_id == duel.guest_id).first() if duel.guest_id else None
    winner_stats = creator_stats if winner_id == duel.creator_id else guest_stats
    loser_stats = guest_stats if winner_id == duel.creator_id else creator_stats
    commission_percent = get_current_commission(db)
    payout_amount = round(duel.total_bank * (1 - commission_percent / 100), 2)

    if creator_stats:
        creator_stats.frozen_balance = round(max(0.0, creator_stats.frozen_balance - duel.creator_share), 2)
    if guest_stats:
        guest_stats.frozen_balance = round(max(0.0, guest_stats.frozen_balance - duel.guest_share), 2)
    if winner_stats:
        winner_stats.balance = round(winner_stats.balance + payout_amount, 2)
        winner_stats.wins += 1
        winner_stats.elo += 20
    if loser_stats:
        loser_stats.elo = max(700, loser_stats.elo - 20)
    if creator_stats:
        creator_stats.duels += 1
    if guest_stats:
        guest_stats.duels += 1
    duel.winner_id = winner_id
    duel.status = "completed"
    duel.ended_at = datetime.utcnow()

    if duel.game_server_id:
        server = db.query(GameServer).filter(GameServer.id == duel.game_server_id).first()
        if server:
            _release_server(server, db)


def _validate_final_score(creator_score: int, guest_score: int) -> bool:
    """Return True only if the reported score is a valid CS2 match-ending state.

    Valid endings: one side reaches 13 with the other at ≤11 (standard win),
    OR both sides are ≥12 and the leader is exactly 2 ahead (overtime win).
    """
    a, b = creator_score, guest_score
    if a == 13 and b <= 11:
        return True
    if b == 13 and a <= 11:
        return True
    if a >= 12 and b >= 12 and abs(a - b) == 2:
        return True
    return False


def _check_and_expire_reservations(db: Session) -> None:
    """Lazy 5-minute no-show timeout: cancel warmup/reserving duels whose
    server was reserved more than 5 minutes ago and live play hasn't started.
    Called at the top of read endpoints and CS2-facing endpoints.
    """
    cutoff = datetime.utcnow() - _RESERVATION_TIMEOUT
    expired = db.query(Duel).filter(
        Duel.status.in_(["warmup", "reserving"]),
        Duel.reserved_at < cutoff,
        Duel.live_started_at.is_(None),
    ).all()
    if expired:
        for duel in expired:
            _cancel_duel_and_release(duel, db)
        db.commit()


def serialize_duel(duel: Duel, db: Session) -> dict:
    creator = db.query(User).filter(User.id == duel.creator_id).first()
    creator_stats = get_user_stats_or_404(duel.creator_id, db)
    guest = db.query(User).filter(User.id == duel.guest_id).first() if duel.guest_id else None
    guest_stats = get_user_stats_or_404(duel.guest_id, db) if duel.guest_id else None
    connect_url = None
    if duel.game_server_id and duel.status in {"warmup", "playing", "paused"}:
        server = db.query(GameServer).filter(GameServer.id == duel.game_server_id).first()
        if server:
            connect_url = server.connect_url
    return {
        "id": duel.id,
        "creator_id": duel.creator_id,
        "guest_id": duel.guest_id,
        "creator_username": creator.username if creator else "Unknown",
        "creator_elo": creator_stats.elo,
        "creator_rank": get_rank_from_elo(creator_stats.elo),
        "guest_username": guest.username if guest else None,
        "guest_elo": guest_stats.elo if guest_stats else None,
        "guest_rank": get_rank_from_elo(guest_stats.elo) if guest_stats else None,
        "map_name": duel.map_name,
        "total_bank": duel.total_bank,
        "creator_score": duel.creator_score,
        "guest_score": duel.guest_score,
        "status": duel.status,
        "creator_share": duel.creator_share,
        "guest_share": duel.guest_share,
        "game_server_id": duel.game_server_id,
        "connect_url": connect_url,
        "warmup_started_at": duel.warmup_started_at,
        "live_started_at": duel.live_started_at,
        "reserved_at": duel.reserved_at,
        "creator_connected": duel.creator_connected,
        "guest_connected": duel.guest_connected,
        "last_round_number": duel.last_round_number,
        "paused_by_user_id": duel.paused_by_user_id,
    }


def find_user_by_target(target: str, db: Session) -> User:
    cleaned_target = normalize_string(target, field="target", max_length=64, allow_empty=False)
    user = db.query(User).filter((User.username == cleaned_target) | (User.steam_id == cleaned_target)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ==================== REST API ENDPOINTS ====================

@app.get("/auth/steam", tags=["Auth"])
async def auth_steam():
    return RedirectResponse(f"https://steamcommunity.com/openid/login?{steam_login.ConstructURL(STEAM_RETURN_TO)}")


@app.get("/auth/steam/callback", tags=["Auth"])
async def auth_steam_callback(request: Request, db: Session = Depends(get_db)):
    steam_id = steam_login.ValidateResults(dict(request.query_params))
    if not steam_id: raise HTTPException(status_code=403, detail="Invalid Steam OpenID response")

    db_user = db.query(User).filter(User.steam_id == str(steam_id)).first()
    if not db_user:
        avatar_url = ""
        if STEAM_API_KEY:
            try:
                r = requests.get(
                    "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/",
                    params={"key": STEAM_API_KEY, "steamids": steam_id},
                    timeout=5,
                )
                player_payload = r.json()
                avatar_url = player_payload["response"]["players"][0]["avatarfull"]
            except (KeyError, IndexError, ValueError, requests.RequestException):
                avatar_url = ""

        db_user = User(steam_id=str(steam_id), username=f"User_{random.randint(1000, 999999)}", avatar=avatar_url)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        db.add(UserStats(user_id=db_user.id))
        db.commit()

    response = RedirectResponse(url="/main")
    set_session_cookies(response, db_user.id)
    return response


@app.get("/auth/logout", tags=["Auth"])
async def logout():
    response = RedirectResponse(url="/main")
    clear_session_cookies(response)
    return response


@app.get("/user/me", response_model=UserResponse, tags=["User Profile"])
async def get_my_info(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    st = get_user_stats_or_404(current_user.id, db)

    active_tx = db.query(TransactionHistory).filter(
        TransactionHistory.user_id == current_user.id,
        TransactionHistory.type == "deposit",
        TransactionHistory.status == "pending"
    ).first()

    active_invoice_payload = None
    if active_tx:
        active_invoice_payload = {
            "amount": active_tx.amount,
            "currency": active_tx.currency,
            "pay_url": active_tx.address
        }

    return {
        "id": current_user.id, "username": current_user.username, "steam_id": current_user.steam_id,
        "avatar": current_user.avatar, "bio": current_user.bio, "country": current_user.country,
        "language": current_user.language, "theme": current_user.theme, "effects": current_user.effects,
        "is_premium": current_user.is_premium, "premium_until": current_user.premium_until, "role": current_user.role,
        "balance": st.balance, "frozen_balance": st.frozen_balance, "elo": st.elo,
        "rank": get_rank_from_elo(st.elo),
        "active_invoice": active_invoice_payload
    }


@app.post("/user/update", tags=["User Profile"])
async def update_profile(data: dict, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    if data.get('username'):
        name = normalize_string(data.get("username"), field="username", max_length=32, allow_empty=False)
        if not USERNAME_RE.fullmatch(name):
            raise HTTPException(status_code=400, detail="Invalid alphanumeric username")
        if db.query(User).filter(User.username == name, User.id != current_user.id).first(): raise HTTPException(
            status_code=409, detail="Username occupied")
        current_user.username = name
    current_user.bio = normalize_string(data.get("bio", current_user.bio), field="bio", max_length=MAX_BIO_LENGTH)
    country = normalize_string(data.get("country", current_user.country or DEFAULT_COUNTRY), field="country", max_length=5, allow_empty=False).upper()
    if not COUNTRY_RE.fullmatch(country):
        raise HTTPException(status_code=400, detail="Invalid country code")
    current_user.country = country
    if data.get("language") is not None:
        language = normalize_string(data.get("language"), field="language", max_length=5, allow_empty=False).lower()
        if language not in LANGUAGE_ALLOWLIST:
            raise HTTPException(status_code=400, detail="Unsupported language")
        current_user.language = language
    if data.get("theme") is not None:
        current_user.theme = parse_int_field(data.get("theme"), field="theme", minimum=0, maximum=1)
    if data.get("effects") is not None:
        current_user.effects = parse_bool_field(data.get("effects"))
    db.commit()
    return {"status": "success"}


@app.get("/user/by-name/{username}", response_model=ProfileResponse, tags=["User Profile"])
async def get_public_profile(username: str, request: Request, db: Session = Depends(get_db)):
    username = normalize_string(username, field="username", max_length=64, allow_empty=False)
    u = db.query(User).filter(User.username == username).first()
    if not u: raise HTTPException(status_code=404, detail="Profile not found")
    st = get_user_stats_or_404(u.id, db)
    curr = get_current_user(request, db)

    # Build recent completed duels (last 20, non-cancelled)
    completed_duels = db.query(Duel).filter(
        ((Duel.creator_id == u.id) | (Duel.guest_id == u.id)),
        Duel.status == "completed"
    ).order_by(Duel.ended_at.desc()).limit(20).all()

    recent_duels = []
    for d in completed_duels:
        i_am_creator = d.creator_id == u.id
        opponent_id = d.guest_id if i_am_creator else d.creator_id
        opponent = db.query(User).filter(User.id == opponent_id).first() if opponent_id else None
        won = d.winner_id == u.id
        recent_duels.append({
            "id": d.id,
            "map_name": d.map_name,
            "total_bank": d.total_bank,
            "opponent_username": opponent.username if opponent else "Unknown",
            "creator_score": d.creator_score,
            "guest_score": d.guest_score,
            "i_am_creator": i_am_creator,
            "won": won,
            "ended_at": d.ended_at,
        })

    return {
        "id": u.id, "username": u.username, "avatar": u.avatar, "bio": u.bio, "country": u.country,
        "language": u.language, "theme": u.theme, "effects": u.effects,
        "is_premium": u.is_premium,
        "stats": {"duels": st.duels, "wins": st.wins, "kills": st.kills, "deaths": st.deaths, "elo": st.elo,
                  "rank": get_rank_from_elo(st.elo), "wagered_amount": st.wagered_amount,
                  "winrate": round((st.wins / st.duels * 100) if st.duels > 0 else 0, 1)},
        "is_own_profile": bool(curr and curr.id == u.id),
        "recent_duels": recent_duels,
    }


@app.post("/api/v1/duels", tags=["Matchmaking"])
async def create_duel(data: dict, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    if get_maintenance_mode(db):
        raise HTTPException(status_code=503, detail="Site is under maintenance. Please try again later.")
    check_active_match_existence(current_user.id, db)
    st = db.query(UserStats).filter(UserStats.user_id == current_user.id).first()
    bank = parse_float_field(data.get("total_bank", 0), field="total_bank", minimum=0.01, maximum=MAX_DUEL_BANK)
    min_rank = parse_int_field(data.get("min_rank", 1), field="min_rank", minimum=1, maximum=10)
    max_rank = parse_int_field(data.get("max_rank", 10), field="max_rank", minimum=1, maximum=10)
    if min_rank > max_rank:
        raise HTTPException(status_code=400, detail="Rank range is invalid")
    map_name = normalize_string(data.get("map_name", "aim_redline"), field="map_name", max_length=32, allow_empty=False)
    if map_name not in MAP_ALLOWLIST:
        raise HTTPException(status_code=400, detail="Map is not supported")
    is_private = parse_bool_field(data.get("is_private", False))

    max_c_share, _ = calculate_shares(st.elo, 700 + (min_rank * 100), bank)
    if not is_private:
        check_wager_limit(st.wagered_amount, max_c_share)
    if st.balance < max_c_share: raise HTTPException(status_code=400, detail="Insufficient margin balance")

    st.balance, st.frozen_balance = round(st.balance - max_c_share, 2), round(st.frozen_balance + max_c_share, 2)
    duel = Duel(creator_id=current_user.id, map_name=map_name, total_bank=bank,
                creator_share=max_c_share, guest_share=round(bank - max_c_share, 2),
                min_rank=min_rank, max_rank=max_rank, is_private=is_private)
    db.add(duel)
    db.commit()
    return {"status": "success", "duel_id": duel.id}


@app.get("/api/v1/duels", response_model=list[DuelLobbyResponse], tags=["Matchmaking"])
async def list_lobbies(db: Session = Depends(get_db)):
    _check_and_expire_reservations(db)
    result = []
    for d in db.query(Duel).filter(Duel.status == 'waiting', Duel.is_private == False).all():
        creator = db.query(User).filter(User.id == d.creator_id).first()
        elo = db.query(UserStats.elo).filter(UserStats.user_id == d.creator_id).scalar() or 1000
        result.append({
            "id": d.id, "map_name": d.map_name, "total_bank": d.total_bank,
            "min_rank": d.min_rank, "max_rank": d.max_rank,
            "creator_username": creator.username if creator else "Unknown",
            "creator_avatar": creator.avatar if creator else "",
            "creator_elo": elo,
            "creator_rank": get_rank_from_elo(elo),
        })
    return result


@app.get("/api/v1/duels/my-history", response_model=list[DuelHistoryEntry], tags=["Matchmaking"])
async def get_my_duel_history(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Return current user's completed and cancelled duels, most recent first."""
    duels = db.query(Duel).filter(
        ((Duel.creator_id == current_user.id) | (Duel.guest_id == current_user.id)),
        Duel.status.in_(["completed", "cancelled"])
    ).order_by(Duel.ended_at.desc(), Duel.created_at.desc()).all()

    result = []
    for d in duels:
        i_am_creator = d.creator_id == current_user.id
        opponent_id = d.guest_id if i_am_creator else d.creator_id
        opponent = db.query(User).filter(User.id == opponent_id).first() if opponent_id else None
        won = d.winner_id == current_user.id
        result.append({
            "id": d.id,
            "map_name": d.map_name,
            "total_bank": d.total_bank,
            "opponent_username": opponent.username if opponent else "Unknown",
            "opponent_avatar": opponent.avatar if opponent else "",
            "creator_score": d.creator_score,
            "guest_score": d.guest_score,
            "status": d.status,
            "won": won,
            "ended_at": d.ended_at,
            "created_at": d.created_at,
        })
    return result


@app.get("/api/v1/duels/{duel_id}", response_model=DuelDetailsResponse, tags=["Matchmaking"])
async def get_duel_details(duel_id: int, db: Session = Depends(get_db)):
    _check_and_expire_reservations(db)
    duel = get_duel_or_404(duel_id, db)
    return serialize_duel(duel, db)


@app.post("/api/v1/duels/{duel_id}/request", tags=["Matchmaking"])
async def create_duel_request(duel_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    duel = get_duel_or_404(duel_id, db)
    if duel.creator_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot join your own duel")
    if duel.status != "waiting":
        raise HTTPException(status_code=400, detail="This duel is no longer accepting requests")
    if duel.guest_id:
        raise HTTPException(status_code=400, detail="This duel already has an opponent")

    current_stats = get_user_stats_or_404(current_user.id, db)
    check_active_match_existence(current_user.id, db)
    if current_stats.balance < duel.guest_share:
        raise HTTPException(status_code=400, detail="Insufficient margin balance")
    if not db.query(DuelRequest).filter(
        DuelRequest.duel_id == duel.id, DuelRequest.guest_id == current_user.id, DuelRequest.status == "pending"
    ).first():
        db.add(DuelRequest(duel_id=duel.id, guest_id=current_user.id))
        db.commit()
    return {"status": "success"}


@app.get("/api/v1/duels/{duel_id}/requests", response_model=list[DuelRequestResponse], tags=["Matchmaking"])
async def list_duel_requests(duel_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    duel = get_duel_or_404(duel_id, db)
    if duel.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the duel creator can review requests")
    requests_list = db.query(DuelRequest).filter(DuelRequest.duel_id == duel.id, DuelRequest.status == "pending").all()
    payload = []
    for item in requests_list:
        guest = db.query(User).filter(User.id == item.guest_id).first()
        guest_stats = get_user_stats_or_404(item.guest_id, db)
        payload.append({
            "request_id": item.id,
            "guest_id": item.guest_id,
            "username": guest.username if guest else "Unknown",
            "avatar": guest.avatar if guest else "",
            "elo": guest_stats.elo,
            "rank": get_rank_from_elo(guest_stats.elo),
        })
    return payload


@app.post("/api/v1/requests/{req_id}/accept", tags=["Matchmaking"])
async def accept_duel_request(req_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    if get_maintenance_mode(db):
        raise HTTPException(status_code=503, detail="Site is under maintenance. Please try again later.")
    req = db.query(DuelRequest).filter(DuelRequest.id == req_id, DuelRequest.status == "pending").first()
    if not req:
        raise HTTPException(status_code=404, detail="Duel request not found")
    duel = get_duel_or_404(req.duel_id, db)
    if duel.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the duel creator can accept requests")
    if duel.status != "waiting" or duel.guest_id:
        raise HTTPException(status_code=400, detail="This duel can no longer accept requests")

    guest_stats = get_user_stats_or_404(req.guest_id, db)
    if guest_stats.balance < duel.guest_share:
        raise HTTPException(status_code=400, detail="Opponent balance is no longer sufficient")

    # Attempt synchronous server reservation — fail fast with 503 if none available.
    server = db.query(GameServer).filter(GameServer.status == "open").first()
    if not server:
        raise HTTPException(status_code=503, detail="All servers are busy. Please try again shortly.")

    now = datetime.utcnow()

    # Freeze guest balance
    guest_stats.balance = round(guest_stats.balance - duel.guest_share, 2)
    guest_stats.frozen_balance = round(guest_stats.frozen_balance + duel.guest_share, 2)

    # Accept request
    duel.guest_id = req.guest_id
    req.status = "accepted"

    # Reserve server and transition to warmup
    server.status = "busy"
    server.current_duel_id = duel.id
    duel.game_server_id = server.id
    duel.reserved_at = now
    duel.warmup_started_at = now
    duel.status = "warmup"

    # Snapshot premium status at reservation time for skin-changer access
    creator_user = db.query(User).filter(User.id == duel.creator_id).first()
    guest_user = db.query(User).filter(User.id == req.guest_id).first()
    duel.creator_is_premium = bool(creator_user and creator_user.is_premium)
    duel.guest_is_premium = bool(guest_user and guest_user.is_premium)

    db.query(DuelRequest).filter(DuelRequest.duel_id == duel.id, DuelRequest.id != req.id).update(
        {"status": "declined"}, synchronize_session=False
    )
    db.commit()
    return {"status": "success"}


@app.delete("/api/v1/duels/{duel_id}/cancel", tags=["Matchmaking"])
async def cancel_duel(duel_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    duel = get_duel_or_404(duel_id, db)
    if duel.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the duel creator can cancel this duel")
    if duel.status != "waiting":
        raise HTTPException(status_code=400, detail="Only waiting duels can be cancelled")

    creator_stats = get_user_stats_or_404(duel.creator_id, db)
    creator_stats.balance = round(creator_stats.balance + duel.creator_share, 2)
    creator_stats.frozen_balance = round(max(0.0, creator_stats.frozen_balance - duel.creator_share), 2)
    db.query(DuelRequest).filter(DuelRequest.duel_id == duel.id, DuelRequest.status == "pending").update(
        {"status": "declined"}, synchronize_session=False
    )
    db.delete(duel)
    db.commit()
    return {"status": "success"}


@app.post("/api/v1/duels/{duel_id}/confirm", tags=["Matchmaking"])
async def confirm_duel_payout(duel_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    duel = get_duel_or_404(duel_id, db)
    if current_user.id not in {duel.creator_id, duel.guest_id}:
        raise HTTPException(status_code=403, detail="Only match participants can confirm a payout")
    if duel.status not in {"processing", "ready", "playing"}:
        raise HTTPException(status_code=400, detail="This duel cannot be confirmed right now")

    winner_id = duel.winner_id or duel.creator_id
    _execute_duel_payout(duel, winner_id, db)
    db.commit()
    return {"status": "success"}


@app.post("/api/v1/duels/{duel_id}/dispute", tags=["Matchmaking"])
async def dispute_duel(duel_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    duel = get_duel_or_404(duel_id, db)
    if current_user.id not in {duel.creator_id, duel.guest_id}:
        raise HTTPException(status_code=403, detail="Only match participants can dispute this duel")
    if duel.status not in {"ready", "playing", "processing"}:
        raise HTTPException(status_code=400, detail="This duel cannot be disputed right now")
    duel.status = "disputed"
    db.commit()
    return {"status": "success"}


# ==================== GATES AND PAYMENTS SYSTEM ====================

@app.get("/api/v1/payments/methods", response_model=list[PaymentMethodResponse], tags=["Payments"])
async def get_payment_methods(type: str, db: Session = Depends(get_db)):
    if type not in PAYMENT_METHOD_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported payment method type")
    return db.query(PaymentMethod).filter(PaymentMethod.type == type, PaymentMethod.is_active == True).all()


@app.post("/api/v1/payments/deposit", tags=["Payments"])
async def create_deposit(data: dict, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    amount = parse_float_field(data.get("amount", 0), field="amount", minimum=0.01, maximum=MAX_PAYMENT_AMOUNT)
    method_id = parse_int_field(data.get("method_id", 0), field="method_id", minimum=1, maximum=1000000)

    existing_tx = db.query(TransactionHistory).filter(
        TransactionHistory.user_id == current_user.id,
        TransactionHistory.type == "deposit",
        TransactionHistory.status == "pending"
    ).first()
    if existing_tx:
        raise HTTPException(status_code=400, detail="You already have an active pending invoice. Cancel it first.")

    method = db.query(PaymentMethod).filter(PaymentMethod.id == method_id, PaymentMethod.type == 'deposit',
                                            PaymentMethod.is_active == True).first()
    if not method: raise HTTPException(status_code=404, detail="Payment method not available")
    if amount < method.min_amount: raise HTTPException(status_code=400,
                                                       detail=f"Minimum deposit is ${method.min_amount}")

    charge_amount = round(amount * (1 + method.commission_percent / 100), 2)

    if method.gateway_alias == "cryptobot":
        ensure_payment_gateway_configured(CRYPTO_PAY_TOKEN)
        headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
        payload = {
            "currency_type": "crypto",
            "asset": "USDT",
            "amount": str(charge_amount),
            "description": f"Platform Services Allocation for User #{current_user.id}",
            "paid_btn_name": "callback",
            "paid_btn_url": "https://likeagod.net/main"
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(f"{CRYPTO_PAY_API_URL}/createInvoice", json=payload, headers=headers)
                if response.status_code != 200:
                    raise HTTPException(status_code=502, detail="Payment gateway unavailable")
                res_data = response.json()
                if not res_data.get("ok") or "result" not in res_data:
                    raise HTTPException(status_code=502, detail="Payment gateway unavailable")
                invoice = res_data["result"]

                invoice_url = validate_url_field(invoice.get("bot_invoice_url"), field="bot_invoice_url", allow_empty=False)
                invoice_url = validate_url_host(invoice_url, field="bot_invoice_url", allowed_hosts=("pay.crypt.bot",))
                tx = TransactionHistory(user_id=current_user.id, amount=amount, currency="USDT", type="deposit",
                                        status="pending", payment_id=str(invoice["invoice_id"]),
                                        address=invoice_url)
                db.add(tx)
                db.commit()
                return {"pay_url": invoice_url}
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="Payment gateway unavailable")

    elif method.gateway_alias == "aaio_rub":
        ensure_payment_gateway_configured(AAIO_MERCHANT_ID, AAIO_SECRET_1)
        rub_amount = round(charge_amount * 90.0, 2)
        tx = TransactionHistory(user_id=current_user.id, amount=amount, currency="RUB", type="deposit",
                                status="pending")
        db.add(tx)
        db.commit()
        db.refresh(tx)

        signature_str = f"{AAIO_MERCHANT_ID}:{rub_amount}:RUB:{AAIO_SECRET_1}:{tx.id}"
        signature = hashlib.sha256(signature_str.encode('utf-8')).hexdigest()
        pay_url = f"https://aaio.so/merchant/pay?merchant_id={AAIO_MERCHANT_ID}&amount={rub_amount}&currency=RUB&order_id={tx.id}&sign={signature}&desc=Deposit+User+{current_user.id}&lang=ru"

        tx.address = pay_url
        db.commit()
        return {"pay_url": pay_url}

    raise HTTPException(status_code=400, detail="Unsupported gateway configuration")


@app.post("/api/v1/payments/cancel", tags=["Payments"])
async def cancel_pending_deposit(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    tx = db.query(TransactionHistory).filter(
        TransactionHistory.user_id == current_user.id,
        TransactionHistory.type == "deposit",
        TransactionHistory.status == "pending"
    ).first()

    if not tx: raise HTTPException(status_code=404, detail="No active pending deposits found.")

    if tx.payment_id and tx.currency == "USDT":
        ensure_payment_gateway_configured(CRYPTO_PAY_TOKEN)
        headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
        payload = {"invoice_id": int(tx.payment_id)}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                await client.post(f"{CRYPTO_PAY_API_URL}/deleteInvoice", json=payload, headers=headers)
        except httpx.HTTPError:
            pass

    tx.status = "failed"
    db.commit()
    return {"status": "success", "message": "Invoice cancelled successfully."}


@app.get("/api/v1/payments/history", response_model=list[PaymentHistoryEntry], tags=["Payments"])
async def get_payment_history(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    history = db.query(TransactionHistory).filter(TransactionHistory.user_id == current_user.id).order_by(
        TransactionHistory.created_at.desc()).all()
    return [{
        "id": tx.id, "amount": tx.amount, "currency": tx.currency, "type": tx.type, "status": tx.status,
        "date": tx.created_at.strftime("%Y-%m-%d %H:%M"), "address": tx.address
    } for tx in history]


@app.post("/api/v1/payments/webhook", tags=["Payments"])
async def crypto_pay_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    verify_crypto_pay_signature(request, raw_body)
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    if body.get("update_type") == "invoice_paid":
        invoice = body.get("payload") or {}
        invoice_id = normalize_string(invoice.get("invoice_id"), field="invoice_id", max_length=64, allow_empty=False)
        tx = db.query(TransactionHistory).filter(TransactionHistory.payment_id == invoice_id,
                                                 TransactionHistory.status == 'pending').first()
        if tx:
            tx.status = 'completed'
            user_stats = db.query(UserStats).filter(UserStats.user_id == tx.user_id).first()
            if user_stats: user_stats.balance = round(user_stats.balance + tx.amount, 2)
            db.commit()
    return {"status": "ok"}


# ==================== CONTENT, PREMIUM AND ADMIN TOOLS ====================

@app.get("/news", response_model=list[NewsResponse], tags=["Public Content Engine"])
async def list_news(db: Session = Depends(get_db)):
    return db.query(News).order_by(News.created_at.desc()).all()


@app.post("/news/create", tags=["Admin"])
async def create_news(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    title = normalize_string(data.get("title", ""), field="title", max_length=120, allow_empty=False)
    image_path = validate_url_field(data.get("image_path", ""), field="image_path", allow_empty=False)
    if not title or not image_path:
        raise HTTPException(status_code=400, detail="Title and image are required")

    news = News(
        title=title,
        image_path=image_path,
        btn_text=normalize_string(data.get("btn_text"), field="btn_text", max_length=80) or None,
        btn_url=validate_url_field(data.get("btn_url"), field="btn_url") or None,
    )
    db.add(news)
    db.commit()
    db.refresh(news)
    return {"status": "success", "id": news.id}


@app.delete("/news/{news_id}", tags=["Admin"])
async def delete_news(news_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    news = db.query(News).filter(News.id == news_id).first()
    if not news:
        raise HTTPException(status_code=404, detail="News item not found")
    db.delete(news)
    db.commit()
    return {"status": "success"}


@app.get("/api/v1/premium/tariffs", response_model=list[TariffResponse], tags=["Premium"])
async def get_premium_tariffs(db: Session = Depends(get_db)):
    return db.query(PremiumTariff).order_by(PremiumTariff.duration_months.asc()).all()


@app.post("/api/v1/premium/buy", tags=["Premium"])
async def buy_premium(data: dict, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    tariff_id = parse_int_field(data.get("tariff_id", 0), field="tariff_id", minimum=1, maximum=1000000)
    tariff = db.query(PremiumTariff).filter(PremiumTariff.id == tariff_id).first()
    if not tariff:
        raise HTTPException(status_code=404, detail="Premium tariff not found")
    stats = get_user_stats_or_404(current_user.id, db)
    if stats.balance < tariff.price:
        raise HTTPException(status_code=400, detail="Insufficient balance for premium purchase")

    stats.balance = round(stats.balance - tariff.price, 2)
    current_user.is_premium = True
    base_date = current_user.premium_until if current_user.premium_until and current_user.premium_until > datetime.utcnow() else datetime.utcnow()
    current_user.premium_until = base_date + timedelta(days=30 * tariff.duration_months)
    db.commit()
    return {"status": "success", "premium_until": current_user.premium_until}


@app.post("/api/v1/admin/adjust-balance", tags=["Admin"])
async def admin_adjust_balance(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = find_user_by_target(str(data.get("target", "")).strip(), db)
    stats = get_user_stats_or_404(user.id, db)
    amount = parse_float_field(
        data.get("amount", 0), field="amount", minimum=-MAX_ADMIN_BALANCE_ADJUSTMENT, maximum=MAX_ADMIN_BALANCE_ADJUSTMENT
    )
    stats.balance = round(stats.balance + amount, 2)
    db.commit()
    return {"status": "success", "message": f"Balance updated for {user.username}"}


@app.post("/api/v1/admin/adjust-elo", tags=["Admin"])
async def admin_adjust_elo(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = find_user_by_target(str(data.get("target", "")).strip(), db)
    stats = get_user_stats_or_404(user.id, db)
    stats.elo = max(700, parse_int_field(data.get("amount", stats.elo), field="amount", minimum=700, maximum=5000))
    db.commit()
    return {"status": "success", "message": f"ELO updated for {user.username}"}


@app.post("/api/v1/admin/tariffs", tags=["Admin"])
async def admin_upsert_tariff(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    duration_months = parse_int_field(data.get("duration_months", 0), field="duration_months", minimum=1, maximum=24)
    price = parse_float_field(data.get("price", 0), field="price", minimum=0.01, maximum=MAX_PAYMENT_AMOUNT)
    tariff = db.query(PremiumTariff).filter(PremiumTariff.duration_months == duration_months).first()
    if not tariff:
        tariff = PremiumTariff(duration_months=duration_months, price=price)
        db.add(tariff)
    tariff.price = price
    tariff.discount_text = normalize_string(data.get("discount_text"), field="discount_text", max_length=64) or None
    db.commit()
    return {"status": "success"}


@app.post("/api/v1/admin/commission", tags=["Admin"])
async def admin_update_commission(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    commission_percent = parse_float_field(data.get("commission_percent", 10.0), field="commission_percent", minimum=0, maximum=100)
    settings = db.query(PlatformSettings).first()
    if not settings:
        settings = PlatformSettings(commission_percent=commission_percent)
        db.add(settings)
    settings.commission_percent = commission_percent
    db.commit()
    return {"status": "success", "commission_percent": settings.commission_percent}


@app.post("/api/v1/admin/maintenance", tags=["Admin"])
async def admin_toggle_maintenance(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    enabled = parse_bool_field(data.get("enabled", False))
    settings = db.query(PlatformSettings).first()
    if not settings:
        settings = PlatformSettings(maintenance_mode=enabled)
        db.add(settings)
    settings.maintenance_mode = enabled
    db.commit()
    return {"status": "success", "maintenance_mode": settings.maintenance_mode}


# ==================== ADMIN: GAME SERVER CRUD ====================

@app.get("/api/v1/admin/servers", response_model=list[GameServerResponse], tags=["Admin"])
async def admin_list_servers(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(GameServer).order_by(GameServer.id.asc()).all()


@app.post("/api/v1/admin/servers", response_model=GameServerResponse, tags=["Admin"])
async def admin_create_server(data: GameServerCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if data.port < 1 or data.port > 65535:
        raise HTTPException(status_code=400, detail="port must be between 1 and 65535")
    server = GameServer(
        label=normalize_string(data.label, field="label", max_length=64, allow_empty=False),
        connect_url=normalize_string(data.connect_url, field="connect_url", max_length=MAX_URL_LENGTH, allow_empty=False),
        ip=normalize_string(data.ip, field="ip", max_length=64, allow_empty=False),
        port=data.port,
    )
    db.add(server)
    db.commit()
    db.refresh(server)
    return server


@app.patch("/api/v1/admin/servers/{server_id}", response_model=GameServerResponse, tags=["Admin"])
async def admin_update_server(server_id: int, data: GameServerUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    server = db.query(GameServer).filter(GameServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Game server not found")
    if data.label is not None:
        server.label = normalize_string(data.label, field="label", max_length=64, allow_empty=False)
    if data.connect_url is not None:
        server.connect_url = normalize_string(data.connect_url, field="connect_url", max_length=MAX_URL_LENGTH, allow_empty=False)
    if data.ip is not None:
        server.ip = normalize_string(data.ip, field="ip", max_length=64, allow_empty=False)
    if data.port is not None:
        if data.port < 1 or data.port > 65535:
            raise HTTPException(status_code=400, detail="port must be between 1 and 65535")
        server.port = data.port
    if data.status is not None:
        if data.status not in {"open", "busy", "offline"}:
            raise HTTPException(status_code=400, detail="status must be open, busy, or offline")
        server.status = data.status
    db.commit()
    db.refresh(server)
    return server


@app.delete("/api/v1/admin/servers/{server_id}", tags=["Admin"])
async def admin_delete_server(server_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    server = db.query(GameServer).filter(GameServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Game server not found")
    if server.current_duel_id:
        raise HTTPException(status_code=400, detail="Cannot delete a server that has an active duel bound to it")
    db.delete(server)
    db.commit()
    return {"status": "success"}


# ==================== CS2 SERVER-TO-BACKEND API ====================

@app.get("/api/v1/server/servers/available", tags=["CS2 Server"])
async def server_list_available(
    _: None = Depends(require_server_key),
    db: Session = Depends(get_db),
):
    """Return game servers currently in 'open' state for plugin/ops introspection."""
    servers = db.query(GameServer).filter(GameServer.status == "open").all()
    return [{"id": s.id, "label": s.label, "connect_url": s.connect_url, "ip": s.ip, "port": s.port} for s in servers]


@app.post("/api/v1/server/servers/{server_id}/heartbeat", tags=["CS2 Server"])
async def server_heartbeat(
    server_id: int,
    data: dict,
    _: None = Depends(require_server_key),
    db: Session = Depends(get_db),
):
    """CS2 server reports liveness and optionally self-reports offline for maintenance.

    Does not allow overriding busy status when an active duel is bound.
    """
    server = db.query(GameServer).filter(GameServer.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Game server not found")

    new_status = normalize_string(data.get("status", ""), field="status", max_length=16, allow_empty=False)
    if new_status not in {"open", "busy", "offline"}:
        raise HTTPException(status_code=400, detail="status must be open, busy, or offline")

    server.last_heartbeat_at = datetime.utcnow()

    # Only allow status changes when no duel is actively bound to this server.
    if server.current_duel_id is None:
        server.status = new_status
    elif new_status == "offline":
        # Defensive: ignore offline self-report while a duel is in progress.
        pass

    db.commit()
    return {"status": "ok", "server_status": server.status}


@app.get("/api/v1/server/duels/pending", tags=["CS2 Server"])
async def server_get_pending_duels(
    server_id: int,
    _: None = Depends(require_server_key),
    db: Session = Depends(get_db),
):
    """Return warmup/reserving duels for a given server_id so the plugin knows what to spin up."""
    _check_and_expire_reservations(db)
    duels = db.query(Duel).filter(
        Duel.game_server_id == server_id,
        Duel.status.in_(["warmup", "reserving"]),
    ).all()
    result = []
    for d in duels:
        creator = db.query(User).filter(User.id == d.creator_id).first()
        guest = db.query(User).filter(User.id == d.guest_id).first() if d.guest_id else None
        skin_changer_enabled = bool(d.creator_is_premium or d.guest_is_premium)
        result.append({
            "duel_id": d.id,
            "map_name": d.map_name,
            "total_bank": d.total_bank,
            "creator_steam_id": creator.steam_id if creator else None,
            "guest_steam_id": guest.steam_id if guest else None,
            "creator_is_premium": d.creator_is_premium,
            "guest_is_premium": d.guest_is_premium,
            "skin_changer_enabled": skin_changer_enabled,
        })
    return result


@app.post("/api/v1/server/duels/{duel_id}/players-connected", tags=["CS2 Server"])
async def server_players_connected(
    duel_id: int,
    data: dict,
    _: None = Depends(require_server_key),
    db: Session = Depends(get_db),
):
    """Plugin reports which players have connected during warmup (for frontend display)."""
    _check_and_expire_reservations(db)
    duel = get_duel_or_404(duel_id, db)
    if duel.status not in {"warmup", "reserving"}:
        raise HTTPException(status_code=409, detail="Duel is not in warmup state")
    duel.creator_connected = bool(data.get("creator_connected", duel.creator_connected))
    duel.guest_connected = bool(data.get("guest_connected", duel.guest_connected))
    db.commit()
    return {"status": "ok"}


@app.post("/api/v1/server/duels/{duel_id}/live-start", tags=["CS2 Server"])
async def server_live_start(
    duel_id: int,
    _: None = Depends(require_server_key),
    db: Session = Depends(get_db),
):
    """Plugin signals that warmup is over and live rounds have begun."""
    duel = get_duel_or_404(duel_id, db)
    if duel.status != "warmup":
        raise HTTPException(status_code=409, detail=f"Cannot start live play from status '{duel.status}'")
    duel.status = "playing"
    duel.live_started_at = datetime.utcnow()
    db.commit()
    return {"status": "ok"}


@app.post("/api/v1/server/duels/{duel_id}/round", tags=["CS2 Server"])
async def server_round_result(
    duel_id: int,
    data: dict,
    _: None = Depends(require_server_key),
    db: Session = Depends(get_db),
):
    """Plugin reports a completed round's score and optional per-round kill/death stats."""
    duel = get_duel_or_404(duel_id, db)
    if duel.status != "playing":
        raise HTTPException(status_code=409, detail="Round updates are only accepted while the duel is playing")

    round_number = parse_int_field(data.get("round_number"), field="round_number", minimum=1, maximum=999)
    creator_score = parse_int_field(data.get("creator_score"), field="creator_score", minimum=0, maximum=999)
    guest_score = parse_int_field(data.get("guest_score"), field="guest_score", minimum=0, maximum=999)

    if round_number != duel.last_round_number + 1:
        raise HTTPException(status_code=400, detail=f"Expected round {duel.last_round_number + 1}, got {round_number}")
    if creator_score < duel.creator_score or guest_score < duel.guest_score:
        raise HTTPException(status_code=400, detail="Score must not regress")

    stats_payload = data.get("stats")
    payload_text = None
    if stats_payload is not None:
        try:
            payload_text = json.dumps(stats_payload)
        except (TypeError, ValueError):
            payload_text = str(stats_payload)

    event = DuelRoundEvent(
        duel_id=duel.id,
        round_number=round_number,
        creator_score=creator_score,
        guest_score=guest_score,
        payload=payload_text,
    )
    db.add(event)
    duel.creator_score = creator_score
    duel.guest_score = guest_score
    duel.last_round_number = round_number
    db.commit()
    return {"status": "ok", "round_number": round_number}


@app.get("/api/v1/server/duels/{duel_id}/rounds", response_model=list[DuelRoundEventResponse], tags=["CS2 Server"])
async def server_get_rounds(
    duel_id: int,
    _: None = Depends(require_server_key),
    db: Session = Depends(get_db),
):
    """Return the per-round event log for a duel (useful for replay / audit)."""
    get_duel_or_404(duel_id, db)
    return db.query(DuelRoundEvent).filter(
        DuelRoundEvent.duel_id == duel_id
    ).order_by(DuelRoundEvent.round_number.asc()).all()


@app.post("/api/v1/server/duels/{duel_id}/pause", tags=["CS2 Server"])
async def server_pause_duel(
    duel_id: int,
    data: dict,
    _: None = Depends(require_server_key),
    db: Session = Depends(get_db),
):
    """Plugin signals that a player disconnected; transitions duel to paused state."""
    duel = get_duel_or_404(duel_id, db)
    if duel.status != "playing":
        raise HTTPException(status_code=409, detail="Duel is not currently playing")

    disconnected_user_id = parse_int_field(data.get("disconnected_user_id"), field="disconnected_user_id", minimum=1)
    if disconnected_user_id not in {duel.creator_id, duel.guest_id}:
        raise HTTPException(status_code=400, detail="disconnected_user_id does not match a duel participant")

    is_creator = disconnected_user_id == duel.creator_id
    if is_creator and duel.creator_pause_used:
        raise HTTPException(status_code=400, detail="Creator has already used their pause for this duel")
    if not is_creator and duel.guest_pause_used:
        raise HTTPException(status_code=400, detail="Guest has already used their pause for this duel")

    duel.status = "paused"
    duel.paused_by_user_id = disconnected_user_id
    duel.pause_started_at = datetime.utcnow()
    if is_creator:
        duel.creator_pause_used = True
    else:
        duel.guest_pause_used = True
    db.commit()
    return {"status": "ok"}


@app.post("/api/v1/server/duels/{duel_id}/resume", tags=["CS2 Server"])
async def server_resume_duel(
    duel_id: int,
    _: None = Depends(require_server_key),
    db: Session = Depends(get_db),
):
    """Plugin signals that the disconnected player has reconnected; resumes live play."""
    duel = get_duel_or_404(duel_id, db)
    if duel.status != "paused":
        raise HTTPException(status_code=409, detail="Duel is not currently paused")
    duel.status = "playing"
    duel.paused_by_user_id = None
    duel.pause_started_at = None
    db.commit()
    return {"status": "ok"}


@app.post("/api/v1/server/duels/{duel_id}/cancel", tags=["CS2 Server"])
async def server_cancel_duel(
    duel_id: int,
    data: dict,
    _: None = Depends(require_server_key),
    db: Session = Depends(get_db),
):
    """Plugin cancels a duel (no-show, both-disconnect, warmup-timeout).

    Releases the server and unfreezes both players' frozen balances.
    """
    duel = get_duel_or_404(duel_id, db)
    if duel.status in {"completed", "cancelled"}:
        raise HTTPException(status_code=409, detail=f"Duel already in terminal status '{duel.status}'")
    _cancel_duel_and_release(duel, db)
    db.commit()
    reason = normalize_string(data.get("reason", ""), field="reason", max_length=256)
    return {"status": "ok", "reason": reason or "cancelled by server"}


@app.post("/api/v1/server/duels/{duel_id}/complete", tags=["CS2 Server"])
async def server_complete_duel(
    duel_id: int,
    data: dict,
    _: None = Depends(require_server_key),
    db: Session = Depends(get_db),
):
    """Plugin reports match end. Backend derives winner from scores (not from winner_steam_id),
    validates score plausibility, runs payout, and releases the server.
    """
    duel = get_duel_or_404(duel_id, db)
    if duel.status not in {"playing", "paused"}:
        raise HTTPException(status_code=409, detail=f"Cannot complete duel from status '{duel.status}'")
    if not duel.guest_id:
        raise HTTPException(status_code=400, detail="Duel has no guest; cannot complete")

    creator_score = parse_int_field(data.get("creator_score"), field="creator_score", minimum=0, maximum=999)
    guest_score = parse_int_field(data.get("guest_score"), field="guest_score", minimum=0, maximum=999)

    if not _validate_final_score(creator_score, guest_score):
        raise HTTPException(
            status_code=400,
            detail=f"Score {creator_score}:{guest_score} is not a valid CS2 match-ending state"
        )

    # Backend determines winner by round count; winner_steam_id from plugin is advisory only.
    if creator_score > guest_score:
        winner_id = duel.creator_id
    else:
        winner_id = duel.guest_id

    demo_url_raw = data.get("demo_url")
    if demo_url_raw:
        duel.demo_url = validate_url_field(demo_url_raw, field="demo_url") or None

    duel.creator_score = creator_score
    duel.guest_score = guest_score
    _execute_duel_payout(duel, winner_id, db)
    db.commit()
    return {"status": "ok", "winner_id": winner_id}


# ==================== ROUNDS FEED (PUBLIC, FOR FRONTEND POLLING) ====================

@app.get("/api/v1/duels/{duel_id}/rounds", response_model=list[DuelRoundEventResponse], tags=["Matchmaking"])
async def get_duel_rounds(duel_id: int, db: Session = Depends(get_db)):
    """Return per-round events for live score feed (polled by frontend during playing/paused states)."""
    get_duel_or_404(duel_id, db)
    return db.query(DuelRoundEvent).filter(
        DuelRoundEvent.duel_id == duel_id
    ).order_by(DuelRoundEvent.round_number.asc()).all()


@app.get("/api/main", response_model=MainPayloadResponse, tags=["Public Content Engine"])
async def get_landing_page_payload(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    news = db.query(News).order_by(News.created_at.desc()).limit(10).all()
    news_payload = [
        {"id": n.id, "title": n.title, "image_path": n.image_path, "btn_text": n.btn_text, "btn_url": n.btn_url,
         "created_at": n.created_at} for n in news]
    commission = get_current_commission(db)

    my_duels_payload = []
    if current_user:
        my_duels = db.query(Duel).filter(((Duel.creator_id == current_user.id) | (Duel.guest_id == current_user.id)),
                                         Duel.status.in_(
                                             ['waiting', 'ready', 'playing', 'processing', 'disputed',
                                              'warmup', 'paused', 'reserving'])).all()
        for d in my_duels:
            creator = db.query(User).filter(User.id == d.creator_id).first()
            guest = db.query(User).filter(User.id == d.guest_id).first() if d.guest_id else None
            my_duels_payload.append({"id": d.id, "status": d.status, "total_bank": d.total_bank,
                                     "creator_name": creator.username if creator else "Unknown",
                                     "guest_name": guest.username if guest else "Waiting..."})

    response = {"news": news_payload, "commission_percent": commission, "authenticated": False, "user": None,
                "stats": None, "my_duels": my_duels_payload, "maintenance_mode": get_maintenance_mode(db)}
    if current_user:
        st = db.query(UserStats).filter(UserStats.user_id == current_user.id).first()
        elo_val = st.elo if st else 1000

        response.update({"authenticated": True, "user": {
            "id": current_user.id, "username": current_user.username, "avatar": current_user.avatar,
            "balance": st.balance if st else 0.0, "is_premium": current_user.is_premium,
            "premium_until": current_user.premium_until, "theme": current_user.theme, "effects": current_user.effects,
            "country": current_user.country, "language": current_user.language
        }})
        if st: response["stats"] = {"duels": st.duels, "wins": st.wins, "kills": st.kills, "deaths": st.deaths,
                                    "elo_val": elo_val, "rank": get_rank_from_elo(elo_val),
                                    "winrate": round((st.wins / st.duels * 100) if st.duels > 0 else 0, 1)}
    return response


@app.post("/api/v1/payments/withdraw", tags=["Payments"])
async def create_withdrawal(data: dict, current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    amount = parse_float_field(data.get("amount", 0), field="amount", minimum=0.01, maximum=MAX_PAYMENT_AMOUNT)
    method_id = parse_int_field(data.get("method_id", 0), field="method_id", minimum=1, maximum=1000000)
    raw_tg = normalize_string(data.get("address", ""), field="address", max_length=64, allow_empty=False)

    # Очищаем от собачки, если ввели @username
    tg_identifier = raw_tg.replace("@", "")

    if not tg_identifier or not (tg_identifier.isdigit() or TELEGRAM_USERNAME_RE.fullmatch(tg_identifier)):
        raise HTTPException(status_code=400, detail="Telegram ID or Username is invalid.")

    method = db.query(PaymentMethod).filter(PaymentMethod.id == method_id, PaymentMethod.type == 'withdraw',
                                            PaymentMethod.is_active == True).first()
    if not method:
        raise HTTPException(status_code=404, detail="Withdrawal method not found.")

    if amount < method.min_amount:
        raise HTTPException(status_code=400, detail=f"Minimum withdrawal is ${method.min_amount}")

    # Проверка на наличие уже ожидающей заявки
    existing_payout = db.query(TransactionHistory).filter(
        TransactionHistory.user_id == current_user.id,
        TransactionHistory.type == "withdraw",
        TransactionHistory.status == "pending"
    ).first()
    if existing_payout:
        raise HTTPException(status_code=400, detail="You already have an active pending withdrawal request.")

    user_stats = db.query(UserStats).filter(UserStats.user_id == current_user.id).first()
    if not user_stats or user_stats.balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient liquid balance to process payout.")

    # Списание с баланса (холдирование)
    user_stats.balance = round(user_stats.balance - amount, 2)
    db.commit()

    ensure_payment_gateway_configured(CRYPTO_PAY_TOKEN)

    # Формируем боевой payload для реального CryptoBot
    is_numeric_id = tg_identifier.isdigit()
    transfer_payload = {
        "asset": "USDT",
        "amount": str(amount),
        "spend_id": f"payout_tx_{random.randint(100000, 99999999)}_{current_user.id}"
    }

    # Если ввели чистые цифры — шлем как user_id, если буквы — как username
    if is_numeric_id:
        transfer_payload["user_id"] = int(tg_identifier)
    else:
        transfer_payload["username"] = str(tg_identifier)

    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}

    tx = TransactionHistory(
        user_id=current_user.id,
        amount=amount,
        currency="USDT",
        type="withdraw",
        status="pending",
        address=f"TG: @{tg_identifier}" if not is_numeric_id else f"TG ID: {tg_identifier}"
    )
    db.add(tx)
    db.commit()

    try:
        response = requests.post(f"{CRYPTO_PAY_API_URL}/transfer", json=transfer_payload, headers=headers, timeout=8)
        res_data = response.json()

        if response.status_code == 200 and res_data.get("ok"):
            # ВСЁ ПРОШЛО УСПЕШНО
            tx.status = "completed"
            tx.payment_id = str(res_data["result"]["transfer_id"])
            db.commit()
            return {"status": "success",
                    "message": f"Success! Instant payout of ${amount} sent to your @CryptoBot wallet."}
        else:
            error_msg = res_data.get("error", {}).get("name", "TRANSFER_FAILED")
            # МГНОВЕННЫЙ РОЛЛБЭК БАЛАНСА ИГРОКУ
            user_stats.balance = round(user_stats.balance + amount, 2)
            tx.status = "failed"

            if error_msg == "USER_NOT_FOUND" or error_msg == "USER_ID_REQUIRED":
                tx.address += f" (Rejected: User not found or privacy blocked)"
                db.commit()
                return {
                    "status": "failed",
                    "message": "Transfer rejected! CryptoBot cannot find this username (due to your privacy settings or registration status). Please try using your numeric Telegram ID instead. Money refunded."
                }
            else:
                db.commit()
                return {"status": "failed", "message": "Transfer rejected by gateway. Your funds have been instantly refunded."}

    except (ValueError, requests.RequestException):
        # Сетевой таймаут — оставляем в pending для безопасности
        return {"status": "success", "message": "Payout is processing. Waiting for network confirmation."}

import test_front

app.router.routes.extend(test_front.router.routes)