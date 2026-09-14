from __future__ import annotations

import logging
import os

import jwt
from jwt import PyJWKClient

logger = logging.getLogger("trading_bot.clerk_auth")

# Clerk exposes a standard JWKS endpoint per instance, at
# "{frontend_api}/.well-known/jwks.json" (frontend_api is the domain shown
# in Clerk Dashboard -> Configure -> API Keys, e.g.
# "your-app-name-12ab.clerk.accounts.dev" in development). Verifying the
# session JWT against it is Clerk's documented framework-agnostic pattern
# for any backend that isn't Next.js/Express (which get a dedicated SDK
# helper instead) -- this project uses it directly rather than depend on
# the exact current shape of Clerk's Python SDK, which could not be
# verified against live docs from this environment (see README: clerk.com
# is not reachable from here). Double-check this still matches Clerk's
# current documented approach when you wire in your real instance.
_jwk_client: PyJWKClient | None = None


def _get_jwk_client() -> PyJWKClient | None:
    global _jwk_client
    jwks_url = os.getenv("CLERK_JWKS_URL")
    if not jwks_url:
        return None
    if _jwk_client is None:
        _jwk_client = PyJWKClient(jwks_url)
    return _jwk_client


def clerk_configured() -> bool:
    return bool(os.getenv("CLERK_JWKS_URL"))


def verify_session_token(token: str) -> dict:
    """Verifies a Clerk session JWT and returns its claims.

    Raises jwt.PyJWTError (or a subclass) on any failure: expired,
    malformed, wrong signature, wrong issuer. Callers should treat any
    exception from this function as "unauthenticated".
    """
    client = _get_jwk_client()
    if client is None:
        raise RuntimeError("CLERK_JWKS_URL is not configured")

    signing_key = client.get_signing_key_from_jwt(token)
    issuer = os.getenv("CLERK_ISSUER")  # e.g. "https://your-app-name-12ab.clerk.accounts.dev"

    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=issuer if issuer else None,
        options={"verify_aud": False, "verify_iss": bool(issuer)},
    )
    return claims
