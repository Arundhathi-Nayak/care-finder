"""Lazy Firestore client. The only place (besides repository.py) that touches firebase_admin."""
import os
from pathlib import Path

from . import config

_client = None


def get_client():
    global _client
    if _client is not None:
        return _client
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if cred_path:
                p = Path(cred_path)
                if not p.is_absolute():
                    p = (config.BACKEND_DIR / p).resolve()
                if not p.exists():
                    raise FileNotFoundError(f"Service account key not found at {p}")
                firebase_admin.initialize_app(credentials.Certificate(str(p)))
            else:
                firebase_admin.initialize_app()  # Application Default Credentials (Cloud Run)
        _client = firestore.client()
        return _client
    except Exception as exc:
        raise RuntimeError(
            f"Could not initialise Firestore: {exc}. Check GOOGLE_APPLICATION_CREDENTIALS in backend/.env "
            "and that the Firestore database exists."
        ) from exc
