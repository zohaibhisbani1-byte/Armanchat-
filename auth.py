"""Authentication, OTP verification, session persistence, and Android 12 permissions."""

import json
import os
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

import requests
from kivy.clock import Clock
from kivy.utils import platform

from firebase_config import APP_DIR, FirebaseConfig, load_firebase_config


SESSION_FILE = os.path.join(APP_DIR, "user_session.json")
AuthCallback = Callable[[bool, Any], None]


def request_android_permissions() -> None:
    """Request runtime permissions required on Android 12+ devices."""
    if platform != "android":
        return
    try:
        from android.permissions import Permission, request_permissions

        perms = [
            Permission.INTERNET,
            Permission.CAMERA,
            Permission.RECORD_AUDIO,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
        ]
        for optional_perm in ("READ_MEDIA_IMAGES", "POST_NOTIFICATIONS", "BLUETOOTH_CONNECT"):
            val = getattr(Permission, optional_perm, None)
            if val:
                perms.append(val)
        request_permissions(perms)
    except Exception:
        pass


class FirebaseAuthManager:
    """Handles Firebase Phone OTP, Email/Password sign-in, and token refresh."""

    def __init__(self, config: Optional[FirebaseConfig] = None) -> None:
        self.config: FirebaseConfig = config or load_firebase_config()
        self.session_data: Dict[str, Any] = {}
        self.pending_phone: str = ""
        self.pending_session_info: str = ""
        self._http = requests.Session()
        self._load_local_session()

    @property
    def is_authenticated(self) -> bool:
        return bool(self.session_data.get("localId") and self.session_data.get("idToken"))

    @property
    def uid(self) -> str:
        return self.session_data.get("localId", "")

    @property
    def id_token(self) -> str:
        return self.session_data.get("idToken", "")

    @property
    def phone_number(self) -> str:
        return self.session_data.get("phoneNumber", "")

    @property
    def email(self) -> str:
        return self.session_data.get("email", "")

    def _dispatch(self, callback: Optional[AuthCallback], ok: bool, payload: Any) -> None:
        if callback is None:
            return
        Clock.schedule_once(lambda _dt: callback(ok, payload), 0)

    def _run_async(self, fn: Callable[[], Tuple[bool, Any]], callback: Optional[AuthCallback]) -> None:
        def worker() -> None:
            try:
                ok, result = fn()
                self._dispatch(callback, ok, result)
            except requests.RequestException as exc:
                self._dispatch(callback, False, f"Network error: {exc}")
            except Exception as exc:
                self._dispatch(callback, False, f"Auth error: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _load_local_session(self) -> None:
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r", encoding="utf-8") as fh:
                    self.session_data = json.load(fh)
            except Exception:
                self.session_data = {}

    def _save_local_session(self, data: Dict[str, Any]) -> None:
        self.session_data = {
            "localId": data.get("localId") or data.get("user_id", ""),
            "idToken": data.get("idToken") or data.get("id_token", ""),
            "refreshToken": data.get("refreshToken") or data.get("refresh_token", ""),
            "phoneNumber": data.get("phoneNumber", self.pending_phone),
            "email": data.get("email", ""),
            "expiresAt": int(time.time()) + int(data.get("expiresIn", 3600)),
        }
        with open(SESSION_FILE, "w", encoding="utf-8") as fh:
            json.dump(self.session_data, fh, indent=2)

    def logout(self) -> None:
        self.session_data = {}
        self.pending_phone = ""
        self.pending_session_info = ""
        if os.path.exists(SESSION_FILE):
            try:
                os.remove(SESSION_FILE)
            except OSError:
                pass

    def refresh_session(self, callback: Optional[AuthCallback] = None) -> None:
        """Refresh expired Firebase ID token using stored refreshToken."""
        refresh_token = self.session_data.get("refreshToken")
        if not refresh_token or not self.config.is_configured:
            self._dispatch(callback, False, "No active session.")
            return

        def task() -> Tuple[bool, Any]:
            resp = self._http.post(
                self.config.token_refresh_endpoint,
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                timeout=15,
            )
            data = resp.json()
            if resp.status_code >= 400:
                return False, data.get("error", {}).get("message", "Session expired.")
            merged = {
                "localId": data.get("user_id", self.uid),
                "idToken": data.get("id_token", ""),
                "refreshToken": data.get("refresh_token", refresh_token),
                "phoneNumber": self.phone_number,
                "email": self.email,
                "expiresIn": data.get("expires_in", 3600),
            }
            self._save_local_session(merged)
            return True, self.session_data

        self._run_async(task, callback)

    # ------------------------------------------------------------------
    # Phone Number + OTP Verification (Firebase Identity Toolkit)
    # ------------------------------------------------------------------

    def send_phone_otp(
        self,
        phone_number: str,
        recaptcha_token: str,
        callback: Optional[AuthCallback] = None,
    ) -> None:
        """Send SMS OTP via Firebase Auth REST API.

        Firebase requires a valid reCAPTCHA v2/Enterprise token from the
        client app or Firebase Console test phone numbers for OTP dispatch.
        """
        cleaned = phone_number.strip().replace(" ", "")
        if not cleaned.startswith("+") or len(cleaned) < 8:
            self._dispatch(callback, False, "Enter phone number with country code (e.g. +923001234567).")
            return
        if not self.config.is_configured:
            self._dispatch(callback, False, "Firebase config missing. Configure firebase_client_config.json first.")
            return
        if not recaptcha_token.strip():
            self._dispatch(
                callback,
                False,
                "reCAPTCHA verification token is required by Firebase Phone Auth. "
                "Complete reCAPTCHA or sign in with Email/Password below.",
            )
            return

        self.pending_phone = cleaned

        def task() -> Tuple[bool, Any]:
            url = self.config.auth_endpoint("accounts:sendVerificationCode")
            payload = {
                "phoneNumber": cleaned,
                "recaptchaToken": recaptcha_token.strip(),
            }
            resp = self._http.post(url, json=payload, timeout=15)
            data = resp.json()
            if resp.status_code >= 400:
                msg = data.get("error", {}).get("message", "Failed to send OTP.")
                return False, f"Firebase Phone Auth error: {msg}"
            self.pending_session_info = data.get("sessionInfo", "")
            return True, {"sessionInfo": self.pending_session_info, "phone": cleaned}

        self._run_async(task, callback)

    def verify_phone_otp(self, otp_code: str, callback: Optional[AuthCallback] = None) -> None:
        code = otp_code.strip()
        if len(code) != 6 or not code.isdigit():
            self._dispatch(callback, False, "Enter the 6-digit verification code.")
            return
        if not self.pending_session_info:
            self._dispatch(callback, False, "OTP session expired. Request a new code.")
            return

        def task() -> Tuple[bool, Any]:
            url = self.config.auth_endpoint("accounts:signInWithPhoneNumber")
            payload = {
                "sessionInfo": self.pending_session_info,
                "code": code,
            }
            resp = self._http.post(url, json=payload, timeout=15)
            data = resp.json()
            if resp.status_code >= 400:
                msg = data.get("error", {}).get("message", "Invalid OTP code.")
                return False, f"OTP verification failed: {msg}"
            self._save_local_session(data)
            return True, self.session_data

        self._run_async(task, callback)

    # ------------------------------------------------------------------
    # Email + Password Authentication (Standard Firebase Auth)
    # ------------------------------------------------------------------

    def sign_in_with_email(
        self,
        email: str,
        password: str,
        create_account: bool = False,
        callback: Optional[AuthCallback] = None,
    ) -> None:
        clean_email = email.strip()
        if "@" not in clean_email or len(password) < 6:
            self._dispatch(callback, False, "Provide a valid email and a password of at least 6 characters.")
            return
        if not self.config.is_configured:
            self._dispatch(callback, False, "Firebase is not configured yet.")
            return

        action = "accounts:signUp" if create_account else "accounts:signInWithPassword"

        def task() -> Tuple[bool, Any]:
            url = self.config.auth_endpoint(action)
            payload = {
                "email": clean_email,
                "password": password,
                "returnSecureToken": True,
            }
            resp = self._http.post(url, json=payload, timeout=15)
            data = resp.json()
            if resp.status_code >= 400:
                msg = data.get("error", {}).get("message", "Authentication failed.")
                return False, f"Auth failed: {msg}"
            self._save_local_session(data)
            return True, self.session_data

        self._run_async(task, callback)
