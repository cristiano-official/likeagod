"""Tests for private duel mode: 50/50 split, lobby exclusion, invite token,
payout without ELO/stat changes, private commission, and join flow."""

import importlib
import sys
import types
from datetime import datetime

import pytest
from fastapi.testclient import TestClient


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
    for name in ["main", "database", "models", "schemas", "test_front"]:
        sys.modules.pop(name, None)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "development")
    for key in [
        "SECRET_KEY", "STEAM_API_KEY", "SERVER_API_KEY", "CRYPTO_PAY_TOKEN",
        "AAIO_MERCHANT_ID", "AAIO_SECRET_1", "AAIO_SECRET_2", "ADMIN_FRONTEND_PATH",
    ]:
        monkeypatch.delenv(key, raising=False)
    if extra_env:
        for key, value in extra_env.items():
            monkeypatch.setenv(key, value)
    return importlib.import_module("main")


def create_user(module, *, username, role="user", balance=1000.0, elo=1000):
    db = module.session_local()
    try:
        user = module.User(steam_id=f"steam_{username}", username=username, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(module.UserStats(user_id=user.id, balance=balance, elo=elo))
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def authenticate(client, module, user_id):
    client.cookies.set("access_token", module.issue_access_token(user_id))
    client.cookies.set("csrf_token", "csrf-test-token")


# ==================== Private duel creation ====================

def test_private_duel_uses_50_50_split(monkeypatch, tmp_path):
    """Private duel creation uses equal creator/guest shares regardless of ELO."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    # Creator with ELO 1500 — would skew shares heavily in public duel
    creator = create_user(module, username="priv_creator", balance=100.0, elo=1500)
    authenticate(client, module, creator.id)

    resp = client.post(
        "/api/v1/duels",
        json={"total_bank": 20.0, "map_name": "aim_redline", "min_rank": 1, "max_rank": 10, "is_private": True},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    duel_id = data["duel_id"]
    assert "invite_token" in data and data["invite_token"]  # invite token returned to creator

    db = module.session_local()
    try:
        duel = db.query(module.Duel).filter(module.Duel.id == duel_id).first()
        assert duel.creator_share == 10.0
        assert duel.guest_share == 10.0
        assert duel.invite_token is not None
    finally:
        db.close()


def test_private_duel_skips_wager_limit(monkeypatch, tmp_path):
    """New user (wagered=0) can create a private duel exceeding the $2 escalation cap."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    # Fresh user: wagered_amount=0, would normally be capped at $2 for public duels
    user = create_user(module, username="priv_wager_skip", balance=500.0, elo=1000)
    authenticate(client, module, user.id)

    resp = client.post(
        "/api/v1/duels",
        json={"total_bank": 20.0, "map_name": "aim_redline", "min_rank": 1, "max_rank": 10, "is_private": True},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"


def test_public_duel_still_enforces_wager_limit(monkeypatch, tmp_path):
    """Public duel for a new user with low wagered_amount still enforces the cap."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    user = create_user(module, username="pub_wager_check", balance=500.0, elo=1000)
    authenticate(client, module, user.id)

    resp = client.post(
        "/api/v1/duels",
        json={"total_bank": 20.0, "map_name": "aim_redline", "min_rank": 1, "max_rank": 10, "is_private": False},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 400
    assert "Bet limit" in resp.json()["detail"]


# ==================== Lobby exclusion ====================

def test_private_duel_not_in_public_lobby(monkeypatch, tmp_path):
    """Private duels must NOT appear in GET /api/v1/duels."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    user = create_user(module, username="priv_lobby", balance=200.0, elo=1000)
    authenticate(client, module, user.id)

    resp = client.post(
        "/api/v1/duels",
        json={"total_bank": 4.0, "map_name": "aim_redline", "min_rank": 1, "max_rank": 10, "is_private": True},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200
    created_id = resp.json()["duel_id"]

    lobby = client.get("/api/v1/duels").json()
    assert all(d["id"] != created_id for d in lobby), "Private duel leaked into public lobby"


# ==================== Invite token visibility ====================

def test_invite_token_visible_to_creator_only(monkeypatch, tmp_path):
    """invite_token is present in GET /api/v1/duels/{id} for creator, absent for others."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    creator = create_user(module, username="tok_creator", balance=200.0, elo=1000)
    other = create_user(module, username="tok_other", balance=200.0, elo=1000)

    authenticate(client, module, creator.id)
    resp = client.post(
        "/api/v1/duels",
        json={"total_bank": 4.0, "map_name": "aim_redline", "min_rank": 1, "max_rank": 10, "is_private": True},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200
    duel_id = resp.json()["duel_id"]

    # Creator can see invite_token
    detail_creator = client.get(f"/api/v1/duels/{duel_id}").json()
    assert detail_creator["invite_token"] is not None

    # Other user cannot see invite_token
    authenticate(client, module, other.id)
    detail_other = client.get(f"/api/v1/duels/{duel_id}").json()
    assert detail_other["invite_token"] is None

    # Anonymous user cannot see invite_token
    client.cookies.clear()
    detail_anon = client.get(f"/api/v1/duels/{duel_id}").json()
    assert detail_anon["invite_token"] is None


def test_by_invite_endpoint_resolves_duel(monkeypatch, tmp_path):
    """GET /api/v1/duels/by-invite/{token} resolves token to duel details."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    creator = create_user(module, username="invite_res_creator", balance=200.0, elo=1000)
    authenticate(client, module, creator.id)

    resp = client.post(
        "/api/v1/duels",
        json={"total_bank": 4.0, "map_name": "aim_redline", "min_rank": 1, "max_rank": 10, "is_private": True},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200
    creation = resp.json()
    duel_id = creation["duel_id"]
    token = creation["invite_token"]

    # Resolve via by-invite endpoint (as anonymous)
    client.cookies.clear()
    invite_resp = client.get(f"/api/v1/duels/by-invite/{token}")
    assert invite_resp.status_code == 200
    data = invite_resp.json()
    assert data["id"] == duel_id
    assert data["is_private"] is True
    # Anonymous user should NOT see the token
    assert data["invite_token"] is None


def test_by_invite_endpoint_invalid_token_returns_404(monkeypatch, tmp_path):
    """GET /api/v1/duels/by-invite/{bogus} returns 404."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    resp = client.get("/api/v1/duels/by-invite/this-token-does-not-exist")
    assert resp.status_code == 404


# ==================== Payout: private commission, no ELO/stat changes ====================

def test_private_duel_payout_no_elo_no_stats(monkeypatch, tmp_path):
    """Completing a private duel does NOT change ELO or duels/wins counters."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    creator = create_user(module, username="payout_creator", balance=500.0, elo=1200)
    guest = create_user(module, username="payout_guest", balance=500.0, elo=1100)

    # Get initial stats
    db = module.session_local()
    try:
        c_stats_before = db.query(module.UserStats).filter(module.UserStats.user_id == creator.id).first()
        g_stats_before = db.query(module.UserStats).filter(module.UserStats.user_id == guest.id).first()
        c_elo_before = c_stats_before.elo
        g_elo_before = g_stats_before.elo
        c_duels_before = c_stats_before.duels
        g_duels_before = g_stats_before.duels
        c_wins_before = c_stats_before.wins
    finally:
        db.close()

    # Create private duel
    authenticate(client, module, creator.id)
    resp = client.post(
        "/api/v1/duels",
        json={"total_bank": 20.0, "map_name": "aim_redline", "min_rank": 1, "max_rank": 10, "is_private": True},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200
    duel_id = resp.json()["duel_id"]

    # Set up duel with guest and trigger payout directly
    db = module.session_local()
    try:
        duel = db.query(module.Duel).filter(module.Duel.id == duel_id).first()
        duel.guest_id = guest.id
        duel.status = "playing"
        g_stats = db.query(module.UserStats).filter(module.UserStats.user_id == guest.id).first()
        g_stats.frozen_balance = round(g_stats.frozen_balance + duel.guest_share, 2)
        g_stats.balance = round(g_stats.balance - duel.guest_share, 2)
        db.commit()

        # Execute payout with creator as winner
        module._execute_duel_payout(duel, creator.id, db)
        db.commit()
    finally:
        db.close()

    db = module.session_local()
    try:
        c_stats_after = db.query(module.UserStats).filter(module.UserStats.user_id == creator.id).first()
        g_stats_after = db.query(module.UserStats).filter(module.UserStats.user_id == guest.id).first()

        # ELO must be unchanged
        assert c_stats_after.elo == c_elo_before, "Creator ELO changed in private duel"
        assert g_stats_after.elo == g_elo_before, "Guest ELO changed in private duel"
        # duels counter must be unchanged
        assert c_stats_after.duels == c_duels_before, "Creator duels counter changed in private duel"
        assert g_stats_after.duels == g_duels_before, "Guest duels counter changed in private duel"
        # wins counter must be unchanged
        assert c_stats_after.wins == c_wins_before, "Creator wins counter changed in private duel"
        # Balance must have been transferred (payout happened)
        assert c_stats_after.balance > 0
    finally:
        db.close()


def test_private_duel_payout_uses_private_commission(monkeypatch, tmp_path):
    """Payout for a private duel uses private_commission_percent, not public commission_percent."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    admin = create_user(module, username="priv_comm_admin", role="admin", balance=100.0)
    creator = create_user(module, username="priv_comm_creator", balance=500.0, elo=1000)
    guest = create_user(module, username="priv_comm_guest", balance=500.0, elo=1000)

    # Set public commission to 10%, private to 5%
    authenticate(client, module, admin.id)
    resp = client.post(
        "/api/v1/admin/commission",
        json={"commission_percent": 10.0, "private_commission_percent": 5.0},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["private_commission_percent"] == 5.0

    # Create private duel with bank=20
    authenticate(client, module, creator.id)
    resp = client.post(
        "/api/v1/duels",
        json={"total_bank": 20.0, "map_name": "aim_redline", "min_rank": 1, "max_rank": 10, "is_private": True},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200
    duel_id = resp.json()["duel_id"]

    db = module.session_local()
    try:
        duel = db.query(module.Duel).filter(module.Duel.id == duel_id).first()
        duel.guest_id = guest.id
        duel.status = "playing"
        g_stats = db.query(module.UserStats).filter(module.UserStats.user_id == guest.id).first()
        g_stats.frozen_balance = round(g_stats.frozen_balance + duel.guest_share, 2)
        g_stats.balance = round(g_stats.balance - duel.guest_share, 2)
        creator_bal_before = db.query(module.UserStats).filter(module.UserStats.user_id == creator.id).first().balance
        db.commit()

        module._execute_duel_payout(duel, creator.id, db)
        db.commit()

        c_stats = db.query(module.UserStats).filter(module.UserStats.user_id == creator.id).first()
        # With 5% commission on $20: payout = 20 * 0.95 = 19.0
        expected_payout = round(20.0 * (1 - 5.0 / 100), 2)
        actual_gain = round(c_stats.balance - creator_bal_before, 2)
        assert actual_gain == expected_payout, f"Expected gain {expected_payout}, got {actual_gain}"
    finally:
        db.close()


# ==================== Admin commission endpoint ====================

def test_admin_can_set_private_commission(monkeypatch, tmp_path):
    """Admin can update private_commission_percent via POST /api/v1/admin/commission."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    admin = create_user(module, username="comm_admin", role="admin", balance=0.0)
    authenticate(client, module, admin.id)

    resp = client.post(
        "/api/v1/admin/commission",
        json={"commission_percent": 8.0, "private_commission_percent": 3.0},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["commission_percent"] == 8.0
    assert data["private_commission_percent"] == 3.0

    # Reflected in /api/main
    main_resp = client.get("/api/main")
    assert main_resp.status_code == 200
    assert main_resp.json()["private_commission_percent"] == 3.0
    assert main_resp.json()["commission_percent"] == 8.0


def test_admin_commission_update_without_private_field_is_backward_compatible(monkeypatch, tmp_path):
    """Sending commission_percent without private_commission_percent still works."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    admin = create_user(module, username="compat_admin", role="admin", balance=0.0)
    authenticate(client, module, admin.id)

    resp = client.post(
        "/api/v1/admin/commission",
        json={"commission_percent": 12.0},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["commission_percent"] == 12.0
    assert "private_commission_percent" in data


# ==================== Join flow works for private duel ====================

def test_request_join_and_accept_works_for_private_duel(monkeypatch, tmp_path):
    """The existing request/accept flow works unmodified for private duels."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    creator = create_user(module, username="prv_join_creator", balance=500.0, elo=1000)
    guest = create_user(module, username="prv_join_guest", balance=500.0, elo=1000)

    # Create a game server so accept can reserve it
    db = module.session_local()
    try:
        server = module.GameServer(
            label="Test-1", connect_url="steam://connect/127.0.0.1:27015",
            ip="127.0.0.1", port=27015, status="open",
        )
        db.add(server)
        db.commit()
    finally:
        db.close()

    authenticate(client, module, creator.id)
    resp = client.post(
        "/api/v1/duels",
        json={"total_bank": 4.0, "map_name": "aim_redline", "min_rank": 1, "max_rank": 10, "is_private": True},
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert resp.status_code == 200
    duel_id = resp.json()["duel_id"]
    token = resp.json()["invite_token"]

    # Guest resolves invite token (simulating navigating via invite link)
    invite_data = client.get(f"/api/v1/duels/by-invite/{token}").json()
    assert invite_data["id"] == duel_id

    # Guest sends join request
    authenticate(client, module, guest.id)
    req_resp = client.post(
        f"/api/v1/duels/{duel_id}/request",
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert req_resp.status_code == 200

    # Creator views requests
    authenticate(client, module, creator.id)
    reqs_resp = client.get(
        f"/api/v1/duels/{duel_id}/requests",
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert reqs_resp.status_code == 200
    reqs = reqs_resp.json()
    assert len(reqs) == 1
    request_id = reqs[0]["request_id"]

    # Creator accepts
    accept_resp = client.post(
        f"/api/v1/requests/{request_id}/accept",
        headers={"X-CSRF-Token": "csrf-test-token"},
    )
    assert accept_resp.status_code == 200

    # Duel now has a guest
    duel_data = client.get(f"/api/v1/duels/{duel_id}").json()
    assert duel_data["guest_id"] == guest.id
