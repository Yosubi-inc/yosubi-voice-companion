from fastapi.testclient import TestClient

from app.main import app


def test_frontend_and_api_routes(tmp_path, monkeypatch):
    (tmp_path / 'index.html').write_text('<html>exported page</html>', encoding='utf-8')
    (tmp_path / 'asset.js').write_text('asset', encoding='utf-8')
    mount = next(route for route in app.routes if getattr(route, 'name', None) == 'frontend')
    monkeypatch.setattr(mount.app, 'directory', str(tmp_path))
    monkeypatch.setattr(mount.app, 'all_directories', [str(tmp_path)])
    with TestClient(app) as client:
        assert 'exported page' in client.get('/').text
        assert 'exported page' in client.get('/unknown/page').text
        assert client.get('/asset.js').text == 'asset'
        assert client.get('/health').json() == {'status': 'ok'}
        assert client.get('/guidance/healthcare').status_code == 200
        assert client.get('/api/missing').status_code == 404
        assert client.get('/guidance/missing').status_code == 404


def test_missing_export_directory_is_tolerated(tmp_path, monkeypatch):
    mount = next(route for route in app.routes if getattr(route, 'name', None) == 'frontend')
    monkeypatch.setattr(mount.app, 'directory', str(tmp_path / 'missing'))
    with TestClient(app) as client:
        assert client.get('/').status_code == 404
        assert client.get('/health').status_code == 200

