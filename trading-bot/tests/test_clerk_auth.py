import time
from dataclasses import dataclass

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src import clerk_auth

PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_KEY = PRIVATE_KEY.public_key()

OTHER_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

ISSUER = "https://test-app.clerk.accounts.dev"


@dataclass
class _FakeSigningKey:
    key: object


class _FakeJWKClient:
    def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
        return _FakeSigningKey(key=PUBLIC_KEY)


def _make_token(private_key, issuer=ISSUER, exp_delta=3600, **extra_claims) -> str:
    payload = {"sub": "user_123", "iss": issuer, "exp": int(time.time()) + exp_delta, **extra_claims}
    return jwt.encode(payload, private_key, algorithm="RS256")


@pytest.fixture(autouse=True)
def fake_jwk_client(monkeypatch):
    monkeypatch.setenv("CLERK_ISSUER", ISSUER)
    monkeypatch.setattr(clerk_auth, "_get_jwk_client", lambda: _FakeJWKClient())


def test_valid_token_is_accepted_and_claims_returned():
    token = _make_token(PRIVATE_KEY)
    claims = clerk_auth.verify_session_token(token)
    assert claims["sub"] == "user_123"


def test_token_signed_with_wrong_key_is_rejected():
    token = _make_token(OTHER_PRIVATE_KEY)
    with pytest.raises(jwt.PyJWTError):
        clerk_auth.verify_session_token(token)


def test_expired_token_is_rejected():
    token = _make_token(PRIVATE_KEY, exp_delta=-10)
    with pytest.raises(jwt.PyJWTError):
        clerk_auth.verify_session_token(token)


def test_wrong_issuer_is_rejected():
    token = _make_token(PRIVATE_KEY, issuer="https://someone-elses-app.clerk.accounts.dev")
    with pytest.raises(jwt.PyJWTError):
        clerk_auth.verify_session_token(token)


def test_missing_jwk_client_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(clerk_auth, "_get_jwk_client", lambda: None)
    with pytest.raises(RuntimeError):
        clerk_auth.verify_session_token("irrelevant")
