import os
import uuid

import httpx
import pytest

BASE = os.environ.get("BASE_URL", "http://localhost:18000")
import ssl
VERIFY = (ssl.create_default_context(cafile=os.environ["CA_FILE"]) if os.environ.get("CA_FILE") else True) if BASE.startswith("https") else False
PWD = os.environ["SEED_PASSWORD"]
USERS = {"admin": "admin@redalimenta.test", "coordinador": "coordinador@redalimenta.test",
         "social": "social@redalimenta.test", "voluntario": "voluntario.norte@redalimenta.test"}


class Cliente:
    def __init__(self, email=None):
        self.c = httpx.Client(base_url=BASE, verify=VERIFY, timeout=20)
        self.csrf = None
        if email:
            r = self.c.post("/api/auth/login", json={"email": email, "password": PWD})
            assert r.status_code == 200, r.text
            self.csrf = r.json()["csrf"]

    def _h(self):
        return {"x-csrf-token": self.csrf} if self.csrf else {}

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, json=None, csrf=True):
        return self.c.post(url, json=json or {}, headers=self._h() if csrf else {})

    def put(self, url, json=None):
        return self.c.put(url, json=json, headers=self._h())

    def delete(self, url):
        return self.c.delete(url, headers=self._h())


@pytest.fixture(scope="session")
def admin():
    return Cliente(USERS["admin"])


@pytest.fixture(scope="session")
def coord():
    return Cliente(USERS["coordinador"])


@pytest.fixture(scope="session")
def social():
    return Cliente(USERS["social"])


@pytest.fixture(scope="session")
def vol():
    return Cliente(USERS["voluntario"])


@pytest.fixture
def uid():
    return uuid.uuid4().hex[:6].upper()
