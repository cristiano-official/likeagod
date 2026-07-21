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
    for key in ['SECRET_KEY', 'STEAM_API_KEY', 'SERVER_API_KEY', 'CRYPTO_PAY_TOKEN', 'AAIO_MERCHANT_ID', 'AAIO_SECRET_1',
                'AAIO_SECRET_2', 'ADMIN_FRONTEND_PATH']:
        monkeypatch.delenv(key, raising=False)
    if extra_env:
        for key, value in extra_env.items():
            monkeypatch.setenv(key, value)
    return importlib.import_module('main')


def create_user(module, *, username, role='user'):
    db = module.session_local()
    try:
        user = module.User(steam_id=f'steam_{username}', username=username, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(module.UserStats(user_id=user.id, balance=500.0, elo=1200))
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def authenticate(client, module, user_id):
    client.cookies.set('access_token', module.issue_access_token(user_id))
    client.cookies.set('csrf_token', 'csrf-test-token')


def test_non_admin_gets_404_on_admin_page(monkeypatch, tmp_path):
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)
    user = create_user(module, username='alice01')
    authenticate(client, module, user.id)

    response = client.get('/admin')

    assert response.status_code == 404


def test_admin_alias_requires_admin_and_renders_for_admin(monkeypatch, tmp_path):
    module = load_module(monkeypatch, tmp_path, {'ADMIN_FRONTEND_PATH': '/0123abcdef456789'})
    client = TestClient(module.app)
    admin = create_user(module, username='admin01', role='admin')
    authenticate(client, module, admin.id)

    response = client.get('/0123abcdef456789')

    assert response.status_code == 200
    assert '/static/js/app.js' in response.text


def test_csrf_is_required_for_cookie_authenticated_post(monkeypatch, tmp_path):
    module = load_module(monkeypatch, tmp_path)
    client = TestClient(module.app)
    user = create_user(module, username='player01')
    client.cookies.set('access_token', module.issue_access_token(user.id))

    rejected = client.post('/user/update', json={'bio': 'updated'})
    assert rejected.status_code == 403
    assert rejected.json()['detail'] == 'CSRF verification failed'

    client.cookies.set('csrf_token', 'csrf-test-token')
    accepted = client.post('/user/update', json={'bio': 'updated'}, headers={'X-CSRF-Token': 'csrf-test-token'})
    assert accepted.status_code == 200
    assert accepted.json()['status'] == 'success'


def test_production_secret_validation_fails_fast(monkeypatch, tmp_path):
    strong_env = {
        'APP_ENV': 'production',
        'STEAM_API_KEY': 'steam-key-value-1234567890',
        'SERVER_API_KEY': 'Server-Api-Key-1234567890!Strong',
        'CRYPTO_PAY_TOKEN': 'CryptoPayToken-1234567890!Strong',
        'AAIO_MERCHANT_ID': 'merchant-123456',
        'AAIO_SECRET_1': 'AAIO-Secret-One-1234567890!',
        'AAIO_SECRET_2': 'AAIO-Secret-Two-1234567890!',
    }

    with pytest.raises(RuntimeError, match='SECRET_KEY must be configured'):
        load_module(monkeypatch, tmp_path, strong_env)

    with pytest.raises(RuntimeError, match='SECRET_KEY is too weak'):
        load_module(monkeypatch, tmp_path, {**strong_env, 'SECRET_KEY': 'short'})


def test_admin_api_and_webhook_stay_protected(monkeypatch, tmp_path):
    module = load_module(monkeypatch, tmp_path, {'CRYPTO_PAY_TOKEN': 'CryptoPayToken-1234567890!Strong'})
    client = TestClient(module.app)
    assert client.get('/api/v1/payments/history').status_code == 401

    user = create_user(module, username='guard01')
    authenticate(client, module, user.id)

    admin_response = client.post(
        '/api/v1/admin/commission',
        json={'commission_percent': 9},
        headers={'X-CSRF-Token': 'csrf-test-token'},
    )
    assert admin_response.status_code == 403

    payment_response = client.get('/api/v1/payments/history')
    assert payment_response.status_code == 200

    webhook_response = client.post('/api/v1/payments/webhook', json={'update_type': 'invoice_paid', 'payload': {'invoice_id': '1'}})
    assert webhook_response.status_code == 401
