import importlib
import sys
import types

from fastapi.testclient import TestClient


def load_app():
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
    sys.modules.pop('main', None)
    return importlib.import_module('main').app


app = load_app()
client = TestClient(app)


def test_shared_frontend_pages_use_static_assets():
    for path in ['/main', '/duels', '/duel', '/premium', '/admin', '/terms', '/privacy', '/refund']:
        response = client.get(path)
        assert response.status_code == 200
        assert '/static/css/style.css' in response.text
        assert '/static/js/app.js' in response.text
        assert '/static/js/theme.js' in response.text
        assert '/static/js/effects.js' in response.text


def test_legal_pages_are_template_backed():
    response = client.get('/terms')
    assert response.status_code == 200
    assert 'data-i18n-html="legal.terms.body"' in response.text
    assert 'toggleLanguage()' not in response.text
    assert 'Public Offer & Terms of Service' not in response.text


def test_static_i18n_assets_are_served():
    response = client.get('/static/i18n/en.json')
    assert response.status_code == 200
    payload = response.json()
    assert payload['common']['nav']['home'] == 'Home'
    assert payload['common']['nav']['theme'] == 'Theme'
    assert payload['home']['hero']['guestValue']
    assert 'legal' in payload


def test_expected_routes_are_registered():
    paths = {getattr(route, 'path', None) for route in app.routes}
    assert '/api/v1/duels/{duel_id}' in paths
    assert '/main' in paths
    assert '/terms' in paths
