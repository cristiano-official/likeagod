"""Regression tests for the 6-bug fix sprint.

Covers:
1. CryptoBot: pay.crypt.bot and testnet-pay.crypt.bot both pass validate_url_host
   when CRYPTO_PAY_API_URL is configured accordingly.
2. Duel history: GET /api/v1/duels/my-history returns each duel exactly once.
3. Duel creation: rejected 503 when all configured servers are busy (and passes
   when at least one server is open).
4. Waiting duel auto-cancel: a waiting duel with no guest older than 5 min is
   cancelled and the creator's frozen balance is returned.
"""

import importlib
import sys
import types
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def stub_steam_signin():
    steam = types.ModuleType("pysteamsignin")
    submodule = types.ModuleType("pysteamsignin.steamsignin")

    class SteamSignIn:
        def ConstructURL(self, return_to):
            return ""
        def ValidateResults(self, params):
            return None

    submodule.SteamSignIn = SteamSignIn
    sys.modules["pysteamsignin"] = steam
    sys.modules["pysteamsignin.steamsignin"] = submodule


def load_module(monkeypatch, tmp_path, extra_env=None):
    stub_steam_signin()
    for name in ["main", "database", "models", "schemas"]:
        sys.modules.pop(name, None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "development")
    for key in ["SECRET_KEY", "STEAM_API_KEY", "SERVER_API_KEY", "CRYPTO_PAY_TOKEN",
                "AAIO_MERCHANT_ID", "AAIO_SECRET_1", "AAIO_SECRET_2", "ADMIN_FRONTEND_PATH"]:
        monkeypatch.delenv(key, raising=False)
    if extra_env:
        for k, v in extra_env.items():
            monkeypatch.setenv(k, v)
    return importlib.import_module("main")


def create_user(module, *, username, balance=500.0, elo=1000, wagered=100.0):
    db = module.session_local()
    try:
        user = module.User(steam_id=f"steam_{username}", username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(module.UserStats(user_id=user.id, balance=balance, elo=elo, wagered_amount=wagered))
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def authenticate(client, module, user_id):
    client.cookies.set("access_token", module.issue_access_token(user_id))
    client.cookies.set("csrf_token", "csrf-test-token")


def create_open_server(module):
    db = module.session_local()
    try:
        server = module.GameServer(label="EU-1", connect_url="steam://connect/1.2.3.4:27015",
                                   ip="1.2.3.4", port=27015, status="open")
        db.add(server)
        db.commit()
        db.refresh(server)
        return server
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fix 1: CryptoBot host validation
# ---------------------------------------------------------------------------

def test_cryptobot_mainnet_host_passes_validation(monkeypatch, tmp_path):
    """validate_url_host accepts pay.crypt.bot when CRYPTO_PAY_API_URL is mainnet."""
    monkeypatch.delenv("CRYPTO_PAY_API_URL", raising=False)
    module = load_module(monkeypatch, tmp_path)
    # Default config → mainnet host
    assert module._CRYPTO_PAY_EXPECTED_HOST == "pay.crypt.bot"
    # Should not raise
    result = module.validate_url_host(
        "https://pay.crypt.bot/pay?invoice_id=123",
        field="bot_invoice_url",
        allowed_hosts=(module._CRYPTO_PAY_EXPECTED_HOST,),
    )
    assert "pay.crypt.bot" in result


def test_cryptobot_testnet_host_passes_when_configured(monkeypatch, tmp_path):
    """validate_url_host accepts testnet-pay.crypt.bot when CRYPTO_PAY_API_URL is testnet."""
    module = load_module(monkeypatch, tmp_path,
                         extra_env={"CRYPTO_PAY_API_URL": "https://testnet-pay.crypt.bot/api"})
    assert module._CRYPTO_PAY_EXPECTED_HOST == "testnet-pay.crypt.bot"
    result = module.validate_url_host(
        "https://testnet-pay.crypt.bot/pay?invoice_id=456",
        field="bot_invoice_url",
        allowed_hosts=(module._CRYPTO_PAY_EXPECTED_HOST,),
    )
    assert "testnet-pay.crypt.bot" in result


def test_cryptobot_wrong_host_is_rejected(monkeypatch, tmp_path):
    """validate_url_host rejects an arbitrary host not matching the configured one."""
    from fastapi import HTTPException
    module = load_module(monkeypatch, tmp_path)
    with pytest.raises(HTTPException) as exc_info:
        module.validate_url_host(
            "https://evil.example.com/pay?invoice_id=789",
            field="bot_invoice_url",
            allowed_hosts=(module._CRYPTO_PAY_EXPECTED_HOST,),
        )
    assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# Fix 4: Duel history — each duel appears exactly once
# ---------------------------------------------------------------------------

def test_duel_history_no_duplicates(monkeypatch, tmp_path):
    """GET /api/v1/duels/my-history returns each duel exactly once."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)
    user = create_user(module, username="history_user", balance=500.0)
    authenticate(client, module, user.id)

    # Insert two completed duels directly (one as creator, one as guest)
    db = module.session_local()
    try:
        other = module.User(steam_id="steam_opp", username="opp")
        db.add(other)
        db.commit()
        db.refresh(other)
        db.add(module.UserStats(user_id=other.id, balance=500.0, elo=1000))

        d1 = module.Duel(creator_id=user.id, guest_id=other.id, map_name="aim_redline",
                         total_bank=10.0, creator_share=5.0, guest_share=5.0,
                         status="completed", ended_at=datetime.utcnow())
        d2 = module.Duel(creator_id=other.id, guest_id=user.id, map_name="aim_redline",
                         total_bank=20.0, creator_share=10.0, guest_share=10.0,
                         status="cancelled", ended_at=datetime.utcnow())
        db.add_all([d1, d2])
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/duels/my-history")
    assert resp.status_code == 200
    rows = resp.json()
    ids = [r["id"] for r in rows]
    # Each duel ID must appear exactly once
    assert len(ids) == len(set(ids)), f"Duplicate duel IDs found: {ids}"
    assert len(ids) == 2


# ---------------------------------------------------------------------------
# Fix 6: Server availability check at duel creation
# ---------------------------------------------------------------------------

def test_duel_creation_blocked_when_all_servers_busy(monkeypatch, tmp_path):
    """POST /api/v1/duels returns 503 when all configured servers are busy."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)
    user = create_user(module, username="creator_busy", balance=500.0)
    authenticate(client, module, user.id)

    # Create a server in busy status
    db = module.session_local()
    try:
        db.add(module.GameServer(label="EU-1", connect_url="steam://connect/1.2.3.4:27015",
                                 ip="1.2.3.4", port=27015, status="busy"))
        db.commit()
    finally:
        db.close()

    resp = client.post(
        "/api/v1/duels",
        json={"total_bank": 10.0, "map_name": "aim_redline", "min_rank": 1, "max_rank": 10},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 503
    assert "busy" in resp.json()["detail"].lower()


def test_duel_creation_succeeds_when_open_server_exists(monkeypatch, tmp_path):
    """POST /api/v1/duels succeeds when at least one server is open."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)
    user = create_user(module, username="creator_ok", balance=500.0)
    create_open_server(module)
    authenticate(client, module, user.id)

    resp = client.post(
        "/api/v1/duels",
        json={"total_bank": 10.0, "map_name": "aim_redline", "min_rank": 1, "max_rank": 10},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200
    assert "duel_id" in resp.json()


def test_duel_creation_allowed_when_no_servers_configured(monkeypatch, tmp_path):
    """POST /api/v1/duels succeeds when the game_servers table is empty (dev/unconfigured)."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)
    user = create_user(module, username="creator_noserv", balance=500.0)
    authenticate(client, module, user.id)

    # No GameServer rows at all → check is skipped
    resp = client.post(
        "/api/v1/duels",
        json={"total_bank": 10.0, "map_name": "aim_redline", "min_rank": 1, "max_rank": 10},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Fix 6: Auto-cancel waiting duel with no guest after 5 minutes
# ---------------------------------------------------------------------------

def test_waiting_duel_auto_cancelled_after_5_min(monkeypatch, tmp_path):
    """A waiting duel with no guest older than 5 min is auto-cancelled by the lazy check."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    creator = create_user(module, username="stale_creator", balance=500.0)
    authenticate(client, module, creator.id)

    # Insert a stale waiting duel directly (created > 5 min ago)
    db = module.session_local()
    try:
        stale_time = datetime.utcnow() - timedelta(minutes=6)
        stats = db.query(module.UserStats).filter(module.UserStats.user_id == creator.id).first()
        stats.frozen_balance = 50.0
        stale_duel = module.Duel(
            creator_id=creator.id,
            map_name="aim_redline",
            total_bank=100.0,
            creator_share=50.0,
            guest_share=50.0,
            status="waiting",
            created_at=stale_time,
        )
        db.add(stale_duel)
        db.commit()
        db.refresh(stale_duel)
        duel_id = stale_duel.id
    finally:
        db.close()

    # Trigger the lazy check by calling a read endpoint
    client.get("/api/v1/duels")

    # Duel should now be cancelled
    db = module.session_local()
    try:
        duel = db.query(module.Duel).filter(module.Duel.id == duel_id).first()
        assert duel.status == "cancelled", f"Expected cancelled, got {duel.status}"
        # Creator's frozen balance should be released back to balance
        stats = db.query(module.UserStats).filter(module.UserStats.user_id == creator.id).first()
        assert stats.frozen_balance == 0.0, f"Frozen balance not released: {stats.frozen_balance}"
    finally:
        db.close()


def test_waiting_duel_not_cancelled_before_5_min(monkeypatch, tmp_path):
    """A waiting duel created less than 5 min ago is NOT auto-cancelled."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    creator = create_user(module, username="fresh_creator", balance=500.0)
    authenticate(client, module, creator.id)

    db = module.session_local()
    try:
        fresh_duel = module.Duel(
            creator_id=creator.id,
            map_name="aim_redline",
            total_bank=100.0,
            creator_share=50.0,
            guest_share=50.0,
            status="waiting",
            created_at=datetime.utcnow() - timedelta(minutes=2),
        )
        db.add(fresh_duel)
        db.commit()
        db.refresh(fresh_duel)
        duel_id = fresh_duel.id
    finally:
        db.close()

    client.get("/api/v1/duels")

    db = module.session_local()
    try:
        duel = db.query(module.Duel).filter(module.Duel.id == duel_id).first()
        assert duel.status == "waiting", f"Duel should still be waiting, got {duel.status}"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fix 2: News localization
# ---------------------------------------------------------------------------

def test_news_returns_localized_title(monkeypatch, tmp_path):
    """GET /news?lang=ru returns the Russian title when available."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)
    import json as _json

    db = module.session_local()
    try:
        title_data = _json.dumps({"en": "Hello", "ru": "Привет", "es": "Hola", "zh": "你好"})
        db.add(module.News(title=title_data, image_path="https://example.com/img.jpg"))
        db.commit()
    finally:
        db.close()

    resp_en = client.get("/news?lang=en")
    assert resp_en.status_code == 200
    assert resp_en.json()[0]["title"] == "Hello"

    resp_ru = client.get("/news?lang=ru")
    assert resp_ru.json()[0]["title"] == "Привет"


def test_news_legacy_title_returned_as_is(monkeypatch, tmp_path):
    """Legacy plain-string news title is returned unchanged as English fallback."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    db = module.session_local()
    try:
        db.add(module.News(title="Legacy plain title", image_path="https://example.com/img.jpg"))
        db.commit()
    finally:
        db.close()

    resp = client.get("/news?lang=ru")
    assert resp.status_code == 200
    assert resp.json()[0]["title"] == "Legacy plain title"


def test_create_news_stores_multilang_titles(monkeypatch, tmp_path):
    """POST /news/create stores titles as JSON and GET /news returns the correct language."""
    import json as _json
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    db = module.session_local()
    try:
        admin = module.User(steam_id="steam_admin_news", username="admin_news_t", role="admin")
        db.add(admin)
        db.commit()
        db.refresh(admin)
        admin_id = admin.id
        db.add(module.UserStats(user_id=admin_id, balance=0.0, elo=1000))
        db.commit()
    finally:
        db.close()

    authenticate(client, module, admin_id)

    resp = client.post(
        "/news/create",
        json={
            "title_en": "Breaking News",
            "title_ru": "Срочные новости",
            "title_es": "Noticias de última hora",
            "title_zh": "突发新闻",
            "image_path": "https://example.com/img.jpg",
        },
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200

    resp_zh = client.get("/news?lang=zh")
    assert resp_zh.json()[0]["title"] == "突发新闻"

    resp_unsupported = client.get("/news?lang=xx")  # unsupported lang → fallback to en
    assert resp_unsupported.json()[0]["title"] == "Breaking News"
