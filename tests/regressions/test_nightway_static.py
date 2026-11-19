from fastapi.testclient import TestClient
from agent.api import app


def test_frontend_fixed_assets_no_store_and_arbitrary_files_not_served():
    with TestClient(app) as client:
        for path in ('/app','/app/index.html','/app/style.css','/app/tokens.css','/app/app.mjs'):
            response=client.get(path)
            assert response.status_code==200 and response.headers['cache-control']=='no-store'
            assert "connect-src 'self'" in response.headers['content-security-policy']
        assert client.get('/app/README.md').status_code==404

