"""
Shared dependencies to avoid circular imports
"""
import os
from fastapi import HTTPException, Request


def require_profile_secret(request: Request):
    """
    Require a static secret for accessing protected endpoints.
    - Set DOCTOR_PROFILE_SECRET in environment.
    - Client must send Doctor-Secret header with the exact same value.
    If header is missing or does not match, return 403.
    """
    secret = os.getenv("DOCTOR_PROFILE_SECRET") or ""
    provided = request.headers.get("Doctor-Secret")
    if not provided or provided != secret:
        raise HTTPException(status_code=403, detail="forbidden")
