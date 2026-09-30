"""Lazy Firestore client."""
import json
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
            # Option 1: Firebase credentials supplied as JSON
            # This is the preferred method for Render.
            service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

            if service_account_json:
                info = json.loads(service_account_json)
                cred = credentials.Certificate(info)
                firebase_admin.initialize_app(cred)

            else:
                # Option 2: Local service-account file
                cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

                if cred_path:
                    p = Path(cred_path)

                    if not p.is_absolute():
                        p = (config.BACKEND_DIR / p).resolve()

                    if not p.exists():
                        raise FileNotFoundError(
                            f"Service account key not found at {p}"
                        )

                    firebase_admin.initialize_app(
                        credentials.Certificate(str(p))
                    )

                else:
                    # Option 3: Application Default Credentials
                    # Useful on Google Cloud environments.
                    firebase_admin.initialize_app()

        _client = firestore.client()
        return _client

    except Exception as exc:
        raise RuntimeError(
            f"Could not initialise Firestore: {exc}. "
            "Check Firebase credentials and that the Firestore database exists."
        ) from exc