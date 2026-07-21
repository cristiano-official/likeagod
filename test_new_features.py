"""Tests for new features: maintenance mode, duel history endpoint, public profile
recent_duels, and custom error pages (404/500)."""

import importlib
import sys
import types

import pytest
from fastapi.testclient import TestClient


def stub_steam_signin():
    steam = types.ModuleType('pysteamsignin')
    submodule = types.ModuleType('pysteamsignin.steamsignin')

    class SteamSignIn:
        def ConstructURL(self, return_to):
            return ''

        def ValidateResults(self, params):
            return None

    submodule.SteamSignIn = SteamSignIn
    sys.modules['pysteamsignin'] = steam
    sys.modules['pysteamsignin.steamsignin'] = submodule


def load_module(monkeypatch, tmp_path, extra_env=None):
    stub_steam_signin()
    for name in ['main', 'database', 'models', 'schemas', 'test_front']:
        sys.modules.pop(name, None)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('APP_ENV', 'development')
    for key in ['SECRET_KEY', 'STEAM_API_KEY', 'SERVER_API_KEY', 'CRYPTO_PAY_TOKEN',
                'AAIO_MERCHANT_ID', 'AAIO_SECRET_1', 'AAIO_SECRET_2', 'ADMIN_FRONTEND_PATH']:
        monkeypatch.delenv(key, raising=False)
    if extra_env:
        for key, value in extra_env.items():
            monkeypatch.setenv(key, value)
    return importlib.import_module('main')


def create_user(module, *, username, role='user', balance=500.0):
    db = module.session_local()
    try:
        user = module.User(steam_id=f'steam_{username}', username=username, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(module.UserStats(user_id=user.id, balance=balance, elo=1200))
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def authenticate(client, module, user_id):
    client.cookies.set('access_token', module.issue_access_token(user_id))
    client.cookies.set('csrf_token', 'csrf-test-token')


# ==================== Maintenance Mode Tests ====================

def test_maintenance_mode_blocks_new_duel_creation(monkeypatch, tmp_path):
    """When maintenance mode is ON, POST /api/v1/duels returns 503."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    user = create_user(module, username='player_m1', balance=1000.0)
    authenticate(client, module, user.id)

    # Enable maintenance mode directly via DB
    db = module.session_local()
    try:
        settings = db.query(module.PlatformSettings).first()
        settings.maintenance_mode = True
        db.commit()
    finally:
        db.close()

    response = client.post(
        '/api/v1/duels',
        json={'total_bank': 10.0, 'map_name': 'aim_redline', 'min_rank': 1, 'max_rank': 10},
        headers={'X-CSRF-Token': 'csrf-test-token'},
    )
    assert response.status_code == 503
    assert 'maintenance' in response.json()['detail'].lower()


def test_maintenance_mode_does_not_block_cs2_server_endpoints(monkeypatch, tmp_path):
    """CS2 server-to-server endpoints remain accessible during maintenance."""
    module = load_module(monkeypatch, tmp_path, {'SERVER_API_KEY': 'Server-Api-Key-Test1234567890!'})
    client = TestClient(module.app)

    # Enable maintenance mode
    db = module.session_local()
    try:
        settings = db.query(module.PlatformSettings).first()
        settings.maintenance_mode = True
        db.commit()
    finally:
        db.close()

    # Server heartbeat endpoint should NOT be blocked
    db2 = module.session_local()
    try:
        server = module.GameServer(label='EU-1', connect_url='steam://connect/127.0.0.1:27015',
                                   ip='127.0.0.1', port=27015)
        db2.add(server)
        db2.commit()
        server_id = server.id
    finally:
        db2.close()

    response = client.post(
        f'/api/v1/server/servers/{server_id}/heartbeat',
        json={'status': 'open'},
        headers={'X-Server-Api-Key': 'Server-Api-Key-Test1234567890!'},
    )
    # Should be accessible (200 OK), not 503
    assert response.status_code == 200


def test_maintenance_mode_toggle_via_admin_endpoint(monkeypatch, tmp_path):
    """Admin can toggle maintenance mode via POST /api/v1/admin/maintenance."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    admin = create_user(module, username='admin_m1', role='admin')
    authenticate(client, module, admin.id)

    # Enable maintenance
    response = client.post(
        '/api/v1/admin/maintenance',
        json={'enabled': True},
        headers={'X-CSRF-Token': 'csrf-test-token'},
    )
    assert response.status_code == 200
    assert response.json()['maintenance_mode'] is True

    # Verify it's reflected in /api/main
    main_resp = client.get('/api/main')
    assert main_resp.status_code == 200
    assert main_resp.json()['maintenance_mode'] is True

    # Disable maintenance
    response = client.post(
        '/api/v1/admin/maintenance',
        json={'enabled': False},
        headers={'X-CSRF-Token': 'csrf-test-token'},
    )
    assert response.status_code == 200
    assert response.json()['maintenance_mode'] is False


def test_non_admin_cannot_toggle_maintenance(monkeypatch, tmp_path):
    """Regular users cannot access the maintenance toggle endpoint."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    user = create_user(module, username='regular_m1')
    authenticate(client, module, user.id)

    response = client.post(
        '/api/v1/admin/maintenance',
        json={'enabled': True},
        headers={'X-CSRF-Token': 'csrf-test-token'},
    )
    assert response.status_code == 403


# ==================== Duel History Endpoint Tests ====================

def test_duel_history_endpoint_returns_completed_and_cancelled(monkeypatch, tmp_path):
    """GET /api/v1/duels/my-history returns completed and cancelled duels for current user."""
    from datetime import datetime

    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    user1 = create_user(module, username='hist_user1', balance=1000.0)
    user2 = create_user(module, username='hist_user2', balance=1000.0)
    authenticate(client, module, user1.id)

    db = module.session_local()
    try:
        # Create a completed duel
        d_completed = module.Duel(
            creator_id=user1.id, guest_id=user2.id,
            map_name='aim_redline', total_bank=20.0,
            creator_share=10.0, guest_share=10.0,
            status='completed', winner_id=user1.id,
            ended_at=datetime.utcnow()
        )
        db.add(d_completed)
        # Create a cancelled duel
        d_cancelled = module.Duel(
            creator_id=user1.id, map_name='awp_india', total_bank=5.0,
            creator_share=5.0, guest_share=0.0,
            status='cancelled', ended_at=datetime.utcnow()
        )
        db.add(d_cancelled)
        # Create a waiting duel (should NOT appear in history)
        d_waiting = module.Duel(
            creator_id=user1.id, map_name='aim_redline', total_bank=10.0,
            creator_share=5.0, guest_share=5.0,
            status='waiting'
        )
        db.add(d_waiting)
        db.commit()
    finally:
        db.close()

    response = client.get('/api/v1/duels/my-history')
    assert response.status_code == 200
    data = response.json()

    statuses = [item['status'] for item in data]
    assert 'completed' in statuses
    assert 'cancelled' in statuses
    assert 'waiting' not in statuses


def test_duel_history_requires_auth(monkeypatch, tmp_path):
    """Unauthenticated access to duel history returns 401."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    response = client.get('/api/v1/duels/my-history')
    assert response.status_code == 401


def test_duel_history_won_field(monkeypatch, tmp_path):
    """The 'won' field is True for duels where current user is the winner."""
    from datetime import datetime

    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    user1 = create_user(module, username='winner_user', balance=1000.0)
    user2 = create_user(module, username='loser_user', balance=1000.0)
    authenticate(client, module, user1.id)

    db = module.session_local()
    try:
        duel = module.Duel(
            creator_id=user1.id, guest_id=user2.id,
            map_name='aim_redline', total_bank=20.0,
            creator_share=10.0, guest_share=10.0,
            status='completed', winner_id=user1.id,
            creator_score=13, guest_score=5,
            ended_at=datetime.utcnow()
        )
        db.add(duel)
        db.commit()
    finally:
        db.close()

    response = client.get('/api/v1/duels/my-history')
    assert response.status_code == 200
    data = response.json()
    completed = [d for d in data if d['status'] == 'completed']
    assert len(completed) == 1
    assert completed[0]['won'] is True


# ==================== Public Profile Recent Duels Tests ====================

def test_public_profile_includes_recent_duels(monkeypatch, tmp_path):
    """GET /user/by-name/{username} includes recent_duels field with completed duels."""
    from datetime import datetime

    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    user1 = create_user(module, username='pub_user1', balance=1000.0)
    user2 = create_user(module, username='pub_user2', balance=1000.0)

    db = module.session_local()
    try:
        # Completed duel - should appear
        d_completed = module.Duel(
            creator_id=user1.id, guest_id=user2.id,
            map_name='aim_redline', total_bank=20.0,
            creator_share=10.0, guest_share=10.0,
            status='completed', winner_id=user1.id,
            creator_score=13, guest_score=5,
            ended_at=datetime.utcnow()
        )
        db.add(d_completed)
        # Cancelled duel - should NOT appear in recent_duels (public profile only shows completed)
        d_cancelled = module.Duel(
            creator_id=user1.id, map_name='awp_india', total_bank=5.0,
            creator_share=5.0, guest_share=0.0,
            status='cancelled', ended_at=datetime.utcnow()
        )
        db.add(d_cancelled)
        db.commit()
    finally:
        db.close()

    response = client.get('/user/by-name/pub_user1')
    assert response.status_code == 200
    data = response.json()
    assert 'recent_duels' in data
    recent = data['recent_duels']
    assert isinstance(recent, list)
    # Only completed duels should be in recent_duels
    assert all(d['won'] is not None for d in recent)  # won field exists
    assert len(recent) >= 1


def test_public_profile_recent_duels_not_cancelled(monkeypatch, tmp_path):
    """recent_duels on public profile only includes completed duels, not cancelled."""
    from datetime import datetime

    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    user = create_user(module, username='only_cancelled', balance=1000.0)

    db = module.session_local()
    try:
        # Only a cancelled duel — no completed ones
        d_cancelled = module.Duel(
            creator_id=user.id, map_name='aim_redline', total_bank=5.0,
            creator_share=5.0, guest_share=0.0,
            status='cancelled', ended_at=datetime.utcnow()
        )
        db.add(d_cancelled)
        db.commit()
    finally:
        db.close()

    response = client.get('/user/by-name/only_cancelled')
    assert response.status_code == 200
    data = response.json()
    assert data['recent_duels'] == []


# ==================== Custom Error Pages Tests ====================

def test_404_html_for_browser_navigation(monkeypatch, tmp_path):
    """Browser navigations (Accept: text/html) to missing routes get a 404 HTML page."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app, raise_server_exceptions=False)

    response = client.get(
        '/this-route-absolutely-does-not-exist-xyz',
        headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'},
    )
    assert response.status_code == 404
    assert 'text/html' in response.headers.get('content-type', '')
    assert '404' in response.text


def test_404_json_for_api_requests(monkeypatch, tmp_path):
    """API requests (Accept: application/json) to missing routes get JSON 404."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app, raise_server_exceptions=False)

    response = client.get(
        '/api/v1/nonexistent',
        headers={'Accept': 'application/json'},
    )
    assert response.status_code == 404
    data = response.json()
    assert 'detail' in data


def test_duel_lobby_includes_creator_avatar(monkeypatch, tmp_path):
    """GET /api/v1/duels returns creator_avatar field in each lobby entry."""
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)

    user = create_user(module, username='avatar_creator', balance=1000.0)
    # Set an avatar URL
    db = module.session_local()
    try:
        u = db.query(module.User).filter(module.User.id == user.id).first()
        u.avatar = 'https://example.com/avatar.jpg'
        db.commit()
    finally:
        db.close()

    authenticate(client, module, user.id)
    # Create a duel within the new-user bet limit
    client.post(
        '/api/v1/duels',
        json={'total_bank': 2.0, 'map_name': 'aim_redline', 'min_rank': 1, 'max_rank': 10},
        headers={'X-CSRF-Token': 'csrf-test-token'},
    )

    response = client.get('/api/v1/duels')
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    for lobby in data:
        assert 'creator_avatar' in lobby
