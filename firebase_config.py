"""Firebase client configuration loader and endpoint builder for ArmanChat.

Important Security Note:
Never store a Firebase Admin SDK service account private key or hardcoded
administrator password inside the Android APK. Only standard client-side
Firebase configuration values (from firebase_client_config.json) belong here.
"""

import json
import os
from dataclasses import dataclass
from typing import Optional


APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(APP_DIR, "firebase_client_config.json")
EXAMPLE_CONFIG_PATH = os.path.join(APP_DIR, "firebase_client_config.example.json")


@dataclass
class FirebaseConfig:
    api_key: str
    auth_domain: str
    database_url: str
    project_id: str
    storage_bucket: str
    messaging_sender_id: str
    app_id: str
    recaptcha_site_key: str = ""
    turn_server_url: str = ""
    turn_username: str = ""
    turn_credential: str = ""

    @property
    def is_configured(self) -> bool:
        return (
            bool(self.api_key)
            and "YOUR_FIREBASE" not in self.api_key
            and bool(self.database_url)
            and "your-project-id" not in self.database_url
            and bool(self.project_id)
        )

    @property
    def clean_database_url(self) -> str:
        return self.database_url.rstrip("/")

    def auth_endpoint(self, action: str) -> str:
        return (
            f"https://identitytoolkit.googleapis.com/v1/{action}"
            f"?key={self.api_key}"
        )

    @property
    def token_refresh_endpoint(self) -> str:
        return f"https://securetoken.googleapis.com/v1/token?key={self.api_key}"

    def rtdb_url(self, path: str, id_token: Optional[str] = None, query: str = "") -> str:
        clean_path = path.strip("/")
        base = f"{self.clean_database_url}/{clean_path}.json" if clean_path else f"{self.clean_database_url}/.json"
        params = []
        if id_token:
            params.append(f"auth={id_token}")
        if query:
            params.append(query)
        return f"{base}?{'&'.join(params)}" if params else base

    def storage_upload_url(self, object_path: str) -> str:
        from urllib.parse import quote

        encoded = quote(object_path.lstrip("/"), safe="")
        return (
            f"https://firebasestorage.googleapis.com/v0/b/"
            f"{self.storage_bucket}/o?uploadType=media&name={encoded}"
        )

    def storage_download_url(self, object_path: str, token: Optional[str] = None) -> str:
        from urllib.parse import quote

        encoded = quote(object_path.lstrip("/"), safe="")
        base = (
            f"https://firebasestorage.googleapis.com/v0/b/"
            f"{self.storage_bucket}/o/{encoded}?alt=media"
        )
        if token:
            return f"{base}&token={token}"
        return base


def load_firebase_config(config_path: Optional[str] = None) -> FirebaseConfig:
    """Load Firebase client configuration from JSON or environment variables."""
    target = config_path or DEFAULT_CONFIG_PATH
    data = {}

    if os.path.exists(target):
        with open(target, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    elif os.path.exists(EXAMPLE_CONFIG_PATH):
        with open(EXAMPLE_CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)

    return FirebaseConfig(
        api_key=os.environ.get("ARMANCHAT_FIREBASE_API_KEY", data.get("apiKey", "")),
        auth_domain=os.environ.get("ARMANCHAT_FIREBASE_AUTH_DOMAIN", data.get("authDomain", "")),
        database_url=os.environ.get("ARMANCHAT_FIREBASE_DB_URL", data.get("databaseURL", "")),
        project_id=os.environ.get("ARMANCHAT_FIREBASE_PROJECT_ID", data.get("projectId", "")),
        storage_bucket=os.environ.get("ARMANCHAT_FIREBASE_STORAGE_BUCKET", data.get("storageBucket", "")),
        messaging_sender_id=os.environ.get("ARMANCHAT_FIREBASE_SENDER_ID", data.get("messagingSenderId", "")),
        app_id=os.environ.get("ARMANCHAT_FIREBASE_APP_ID", data.get("appId", "")),
        recaptcha_site_key=data.get("recaptchaSiteKey", ""),
        turn_server_url=data.get("turnServerUrl", ""),
        turn_username=data.get("turnUsername", ""),
        turn_credential=data.get("turnCredential", ""),
    )


def save_firebase_config(config: FirebaseConfig, config_path: Optional[str] = None) -> None:
    """Persist updated client-side Firebase configuration locally."""
    target = config_path or DEFAULT_CONFIG_PATH
    payload = {
        "apiKey": config.api_key.strip(),
        "authDomain": config.auth_domain.strip(),
        "databaseURL": config.database_url.strip(),
        "projectId": config.project_id.strip(),
        "storageBucket": config.storage_bucket.strip(),
        "messagingSenderId": config.messaging_sender_id.strip(),
        "appId": config.app_id.strip(),
        "recaptchaSiteKey": config.recaptcha_site_key.strip(),
        "turnServerUrl": config.turn_server_url.strip(),
        "turnUsername": config.turn_username.strip(),
        "turnCredential": config.turn_credential.strip(),
    }
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
