"""Supabase Auth bearer validation and resolved agency context."""

import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from gotrue.errors import AuthError, AuthRetryableError
from supabase import Client

from app.db import RETRY_ATTEMPTS, RETRY_DELAY_SECONDS, with_retry
from app.dependencies import require_supabase_client


@dataclass(frozen=True)
class AuthContext:
    client: Client
    user_id: str
    agency_id: str


bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "authentication required") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(  # noqa: B008
        bearer_scheme
    ),
    client: Client = Depends(require_supabase_client),  # noqa: B008 - FastAPI dependency
) -> AuthContext:
    if credentials is None:
        raise _unauthorized()
    if credentials.scheme.lower() != "bearer" or not credentials.credentials.strip():
        raise _unauthorized()

    token = credentials.credentials.strip()
    # gotrue wraps a transient disconnect as AuthRetryableError (not the raw
    # httpx.TransportError app/db.py's with_retry catches), so it gets its own loop.
    last_retryable_error: AuthRetryableError | None = None
    response = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = client.auth.get_user(token)
            last_retryable_error = None
            break
        except AuthRetryableError as exc:
            last_retryable_error = exc
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_SECONDS)
        except AuthError as exc:
            raise _unauthorized("invalid bearer token") from exc
    if last_retryable_error is not None:
        raise HTTPException(
            status_code=503, detail="authentication service unavailable"
        ) from last_retryable_error
    assert response is not None  # loop only exits via break or the raise above
    user = response.user
    if user is None:
        raise _unauthorized("invalid bearer token")

    membership = with_retry(
        lambda: client.table("agency_member").select("agency_id").eq("user_id", str(user.id)).execute()
    )
    if not membership.data:
        raise HTTPException(status_code=403, detail="user is not assigned to an agency")
    if len(membership.data) != 1:
        raise HTTPException(
            status_code=409, detail="user has ambiguous agency membership"
        )
    return AuthContext(
        client=client,
        user_id=str(user.id),
        agency_id=membership.data[0]["agency_id"],
    )
