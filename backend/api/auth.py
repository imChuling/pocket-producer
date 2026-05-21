import os

import firebase_admin
from fastapi import Header, HTTPException
from firebase_admin import auth, credentials

_app = None


def _init_firebase():
    global _app
    if _app is None:
        cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
        if cred_path:
            cred = credentials.Certificate(cred_path)
            _app = firebase_admin.initialize_app(cred)
        else:
            _app = firebase_admin.initialize_app()


async def verify_firebase_token(authorization: str = Header(...)) -> str:
    """Extract and verify Firebase ID token from Authorization header."""
    _init_firebase()
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization[7:]
    try:
        decoded = auth.verify_id_token(token)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
