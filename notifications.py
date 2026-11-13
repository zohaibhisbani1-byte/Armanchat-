"""Push and local notifications manager for ArmanChat on Android 12 and desktop."""

import time
from typing import Any, Callable, Dict, Optional

from kivy.clock import Clock
from kivy.utils import platform

from database import FirebaseDatabase


class NotificationManager:
    """Polls unread messages & incoming calls and triggers Android/local notifications."""

    def __init__(self, db: FirebaseDatabase) -> None:
        self.db = db
        self.enabled: bool = True
        self._poll_event = None
        self._seen_call_ids: set = set()
        self._last_chat_timestamps: Dict[str, int] = {}
        self._incoming_call_handler: Optional[Callable[[Dict[str, Any]], None]] = None
        self._ensure_android_channel()

    def _ensure_android_channel(self) -> None:
        if platform != "android":
            return
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")
            NotificationManagerCls = autoclass("android.app.NotificationManager")
            NotificationChannel = autoclass("android.app.NotificationChannel")
            BuildVersion = autoclass("android.os.Build$VERSION")

            if BuildVersion.SDK_INT >= 26:
                activity = PythonActivity.mActivity
                nm = activity.getSystemService(Context.NOTIFICATION_SERVICE)
                channel = NotificationChannel(
                    "armanchat_messages",
                    "ArmanChat Messages & Calls",
                    NotificationManagerCls.IMPORTANCE_HIGH,
                )
                channel.setDescription("Real-time chat alerts and incoming call notifications")
                nm.createNotificationChannel(channel)
        except Exception:
            pass

    def register_device_token(self, uid: str, token: Optional[str] = None) -> None:
        """Save FCM or Android device token to user profile in Firebase RTDB."""
        if not uid:
            return
        device_token = token or self._fetch_android_fcm_token() or f"device_{int(time.time())}"
        self.db.save_user_profile(
            uid,
            {
                "fcm_token": device_token,
                "notifications_enabled": self.enabled,
            },
        )

    def _fetch_android_fcm_token(self) -> Optional[str]:
        if platform != "android":
            return None
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            SettingsSecure = autoclass("android.provider.Settings$Secure")
            resolver = PythonActivity.mActivity.getContentResolver()
            android_id = SettingsSecure.getString(resolver, SettingsSecure.ANDROID_ID)
            return f"android_{android_id}" if android_id else None
        except Exception:
            return None

    def show_local_notification(self, title: str, message: str) -> None:
        if not self.enabled:
            return
        try:
            from plyer import notification

            notification.notify(
                title=title[:48],
                message=message[:120],
                app_name="ArmanChat",
                timeout=5,
            )
        except Exception:
            pass

    def start_listening(
        self,
        uid: str,
        on_incoming_call: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self._incoming_call_handler = on_incoming_call
        self.stop_listening()
        if not uid:
            return
        self._poll_event = Clock.schedule_interval(lambda _dt: self._poll(uid), 4.0)

    def stop_listening(self) -> None:
        if self._poll_event is not None:
            self._poll_event.cancel()
            self._poll_event = None

    def _poll(self, uid: str) -> None:
        # 1. Check incoming WebRTC calls
        def on_calls(ok: bool, calls: Any) -> None:
            if not ok or not isinstance(calls, list):
                return
            for call in calls:
                cid = call.get("call_id")
                if cid and cid not in self._seen_call_ids:
                    self._seen_call_ids.add(cid)
                    caller = call.get("caller_name", "Someone")
                    ctype = call.get("call_type", "audio")
                    self.show_local_notification(
                        "Incoming ArmanChat Call",
                        f"{caller} is calling ({ctype})...",
                    )
                    if self._incoming_call_handler:
                        self._incoming_call_handler(call)

        self.db.get_incoming_calls(uid, on_calls)

        # 2. Check new unread messages across user_chats
        def on_chats(ok: bool, chats: Any) -> None:
            if not ok or not isinstance(chats, list):
                return
            for chat in chats:
                cid = chat.get("chat_id")
                updated = int(chat.get("updated_at", 0))
                unread = int(chat.get("unread", 0))
                last_sender = chat.get("last_sender", "")
                prev_ts = self._last_chat_timestamps.get(cid, 0)
                if prev_ts and updated > prev_ts and unread > 0 and last_sender != uid:
                    self.show_local_notification(
                        chat.get("title", "ArmanChat"),
                        chat.get("last_message", "New message"),
                    )
                if cid:
                    self._last_chat_timestamps[cid] = max(prev_ts, updated)

        self.db.get_user_chats(uid, on_chats)
