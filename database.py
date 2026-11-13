"""Firebase Realtime Database and Storage client for ArmanChat.

All network requests execute on background worker threads and marshal UI
callbacks safely back onto the Kivy main thread using Clock.schedule_once.
"""

import mimetypes
import os
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
from kivy.clock import Clock

from firebase_config import FirebaseConfig, load_firebase_config


Callback = Callable[[bool, Any], None]


def make_direct_chat_id(uid_a: str, uid_b: str) -> str:
    """Return deterministic 1-to-1 chat room ID for two user IDs."""
    pair = sorted([uid_a, uid_b])
    return f"dm_{pair[0]}_{pair[1]}"


def format_timestamp(ts: Optional[float]) -> str:
    """Convert Unix epoch seconds to readable local HH:MM or date string."""
    if not ts:
        return ""
    try:
        local = time.localtime(float(ts))
        now = time.localtime()
        if (local.tm_year, local.tm_yday) == (now.tm_year, now.tm_yday):
            return time.strftime("%I:%M %p", local).lstrip("0")
        return time.strftime("%b %d, %I:%M %p", local).lstrip("0")
    except Exception:
        return ""


class FirebaseDatabase:
    """Thread-safe Firebase RTDB & Storage REST API client."""

    def __init__(self, config: Optional[FirebaseConfig] = None) -> None:
        self.config: FirebaseConfig = config or load_firebase_config()
        self.id_token: Optional[str] = None
        self.current_uid: Optional[str] = None
        self.session = requests.Session()
        self.timeout = 15

    def set_credentials(self, uid: Optional[str], id_token: Optional[str]) -> None:
        self.current_uid = uid
        self.id_token = id_token

    def _dispatch(self, callback: Optional[Callback], success: bool, data: Any) -> None:
        if callback is None:
            return
        Clock.schedule_once(lambda _dt: callback(success, data), 0)

    def _run_async(self, fn: Callable[[], Tuple[bool, Any]], callback: Optional[Callback]) -> None:
        def worker() -> None:
            try:
                ok, result = fn()
                self._dispatch(callback, ok, result)
            except requests.RequestException as exc:
                self._dispatch(callback, False, f"Network error: {exc}")
            except Exception as exc:
                self._dispatch(callback, False, f"Unexpected error: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Any] = None,
        query: str = "",
    ) -> Tuple[bool, Any]:
        if not self.config.is_configured:
            return False, "Firebase is not configured. Add firebase_client_config.json."
        url = self.config.rtdb_url(path, self.id_token, query=query)
        resp = self.session.request(method, url, json=payload, timeout=self.timeout)
        if resp.status_code >= 400:
            try:
                err_json = resp.json()
                msg = err_json.get("error", resp.text)
            except Exception:
                msg = resp.text
            return False, f"Database error ({resp.status_code}): {msg}"
        if not resp.text or resp.text == "null":
            return True, None
        return True, resp.json()

    # ------------------------------------------------------------------
    # User Profiles & Presence
    # ------------------------------------------------------------------

    def save_user_profile(
        self,
        uid: str,
        profile_data: Dict[str, Any],
        callback: Optional[Callback] = None,
    ) -> None:
        payload = {
            **profile_data,
            "uid": uid,
            "updated_at": int(time.time()),
        }

        def task() -> Tuple[bool, Any]:
            return self._request("PATCH", f"users/{uid}", payload)

        self._run_async(task, callback)

    def get_user_profile(self, uid: str, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            return self._request("GET", f"users/{uid}")

        self._run_async(task, callback)

    def update_presence(self, uid: str, online: bool) -> None:
        """Fire-and-forget online status and last_seen update."""
        if not uid or not self.id_token or not self.config.is_configured:
            return
        payload = {
            "online": online,
            "last_seen": int(time.time()),
        }
        self._run_async(lambda: self._request("PATCH", f"users/{uid}", payload), None)

    def get_all_users(self, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            ok, data = self._request("GET", "users")
            if not ok:
                return False, data
            users = []
            if isinstance(data, dict):
                for uid, info in data.items():
                    if isinstance(info, dict):
                        item = dict(info)
                        item["uid"] = uid
                        users.append(item)
            users.sort(key=lambda u: (u.get("name") or u.get("phone") or "").lower())
            return True, users

        self._run_async(task, callback)

    # ------------------------------------------------------------------
    # Blocking & Reporting
    # ------------------------------------------------------------------

    def get_blocked_users(self, uid: str, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            ok, data = self._request("GET", f"user_blocks/{uid}")
            if not ok:
                return False, data
            return True, data if isinstance(data, dict) else {}

        self._run_async(task, callback)

    def block_user(self, my_uid: str, target_uid: str, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            return self._request(
                "PUT",
                f"user_blocks/{my_uid}/{target_uid}",
                {"blocked_at": int(time.time())},
            )

        self._run_async(task, callback)

    def unblock_user(self, my_uid: str, target_uid: str, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            return self._request("DELETE", f"user_blocks/{my_uid}/{target_uid}")

        self._run_async(task, callback)

    def report_user(
        self,
        reporter_uid: str,
        reported_uid: str,
        reason: str,
        callback: Optional[Callback] = None,
    ) -> None:
        report_id = f"rep_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        payload = {
            "report_id": report_id,
            "reporter_id": reporter_uid,
            "reported_uid": reported_uid,
            "reason": reason.strip() or "Inappropriate behavior",
            "status": "open",
            "created_at": int(time.time()),
        }

        def task() -> Tuple[bool, Any]:
            return self._request("PUT", f"reports/{report_id}", payload)

        self._run_async(task, callback)

    # ------------------------------------------------------------------
    # Direct & Group Conversations
    # ------------------------------------------------------------------

    def ensure_direct_chat(
        self,
        my_uid: str,
        peer_uid: str,
        my_name: str,
        peer_name: str,
        peer_avatar: str = "",
        callback: Optional[Callback] = None,
    ) -> None:
        chat_id = make_direct_chat_id(my_uid, peer_uid)
        now = int(time.time())

        def task() -> Tuple[bool, Any]:
            ok, existing = self._request("GET", f"chats/{chat_id}/participants")
            if ok and not existing:
                meta = {
                    "chat_id": chat_id,
                    "type": "direct",
                    "participants": {my_uid: True, peer_uid: True},
                    "created_at": now,
                }
                ok_put, err = self._request("PATCH", f"chats/{chat_id}", meta)
                if not ok_put:
                    return False, err

            # Ensure user_chats index exists for both users
            self._request(
                "PATCH",
                f"user_chats/{my_uid}/{chat_id}",
                {
                    "chat_id": chat_id,
                    "peer_uid": peer_uid,
                    "title": peer_name or "ArmanChat User",
                    "avatar_url": peer_avatar,
                    "updated_at": now,
                },
            )
            self._request(
                "PATCH",
                f"user_chats/{peer_uid}/{chat_id}",
                {
                    "chat_id": chat_id,
                    "peer_uid": my_uid,
                    "title": my_name or "ArmanChat User",
                    "updated_at": now,
                },
            )
            return True, chat_id

        self._run_async(task, callback)

    def get_user_chats(self, uid: str, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            ok, data = self._request("GET", f"user_chats/{uid}")
            if not ok:
                return False, data
            chats: List[Dict[str, Any]] = []
            if isinstance(data, dict):
                for cid, entry in data.items():
                    if isinstance(entry, dict):
                        item = dict(entry)
                        item["chat_id"] = cid
                        chats.append(item)
            chats.sort(key=lambda c: c.get("updated_at", 0), reverse=True)
            return True, chats

        self._run_async(task, callback)

    def get_messages(
        self,
        room_id: str,
        is_group: bool = False,
        callback: Optional[Callback] = None,
    ) -> None:
        base_path = f"groups/{room_id}/messages" if is_group else f"chats/{room_id}/messages"

        def task() -> Tuple[bool, Any]:
            ok, data = self._request("GET", base_path)
            if not ok:
                return False, data
            msgs: List[Dict[str, Any]] = []
            if isinstance(data, dict):
                for mid, msg in data.items():
                    if isinstance(msg, dict):
                        item = dict(msg)
                        item["message_id"] = mid
                        msgs.append(item)
            msgs.sort(key=lambda m: float(m.get("timestamp", 0)))
            return True, msgs

        self._run_async(task, callback)

    def send_message(
        self,
        room_id: str,
        sender_uid: str,
        sender_name: str,
        text: str = "",
        msg_type: str = "text",
        media_url: str = "",
        file_name: str = "",
        is_group: bool = False,
        peer_uid: Optional[str] = None,
        member_uids: Optional[List[str]] = None,
        callback: Optional[Callback] = None,
    ) -> None:
        msg_id = f"msg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:5]}"
        now = time.time()
        msg_payload = {
            "message_id": msg_id,
            "sender_id": sender_uid,
            "sender_name": sender_name,
            "text": text,
            "type": msg_type,
            "media_url": media_url,
            "file_name": file_name,
            "timestamp": now,
            "status": "sent",
            "read_by": {sender_uid: True},
            "deleted": False,
        }
        base_path = f"groups/{room_id}/messages/{msg_id}" if is_group else f"chats/{room_id}/messages/{msg_id}"
        preview = text if msg_type == "text" else (f"Photo" if msg_type == "image" else f"File: {file_name or 'attachment'}")

        def task() -> Tuple[bool, Any]:
            ok, err = self._request("PUT", base_path, msg_payload)
            if not ok:
                return False, err

            summary = {
                "last_message": preview[:80],
                "last_sender": sender_uid,
                "updated_at": int(now),
            }
            if is_group:
                self._request("PATCH", f"groups/{room_id}", summary)
                if member_uids:
                    for m_uid in member_uids:
                        self._request(
                            "PATCH",
                            f"user_groups/{m_uid}/{room_id}",
                            {**summary, "unread": 0 if m_uid == sender_uid else 1},
                        )
            else:
                self._request("PATCH", f"user_chats/{sender_uid}/{room_id}", {**summary, "unread": 0})
                if peer_uid:
                    self._request("PATCH", f"user_chats/{peer_uid}/{room_id}", {**summary, "unread": 1})
                    # Queue push notification event for optional FCM dispatcher
                    notif_id = f"n_{int(now * 1000)}_{uuid.uuid4().hex[:4]}"
                    self._request(
                        "PUT",
                        f"notifications_queue/{notif_id}",
                        {
                            "sender_id": sender_uid,
                            "sender_name": sender_name,
                            "recipient_id": peer_uid,
                            "room_id": room_id,
                            "preview": preview[:100],
                            "created_at": int(now),
                        },
                    )
            return True, msg_payload

        self._run_async(task, callback)

    def mark_messages_read(
        self,
        room_id: str,
        my_uid: str,
        messages: List[Dict[str, Any]],
        is_group: bool = False,
    ) -> None:
        if not my_uid or not self.id_token:
            return
        unread_msgs = [
            m
            for m in messages
            if m.get("sender_id") != my_uid
            and not (m.get("read_by") or {}).get(my_uid)
            and m.get("message_id")
        ]
        if not unread_msgs and is_group:
            return

        def task() -> Tuple[bool, Any]:
            prefix = f"groups/{room_id}/messages" if is_group else f"chats/{room_id}/messages"
            for msg in unread_msgs:
                mid = msg["message_id"]
                self._request("PUT", f"{prefix}/{mid}/read_by/{my_uid}", True)
                self._request("PUT", f"{prefix}/{mid}/status", "read")
            if is_group:
                self._request("PUT", f"user_groups/{my_uid}/{room_id}/unread", 0)
            else:
                self._request("PUT", f"user_chats/{my_uid}/{room_id}/unread", 0)
            return True, len(unread_msgs)

        self._run_async(task, None)

    def delete_message(
        self,
        room_id: str,
        message_id: str,
        is_group: bool = False,
        callback: Optional[Callback] = None,
    ) -> None:
        prefix = f"groups/{room_id}/messages/{message_id}" if is_group else f"chats/{room_id}/messages/{message_id}"

        def task() -> Tuple[bool, Any]:
            return self._request(
                "PATCH",
                prefix,
                {
                    "deleted": True,
                    "text": "This message was deleted",
                    "type": "deleted",
                    "media_url": "",
                    "file_name": "",
                },
            )

        self._run_async(task, callback)

    def set_typing(self, room_id: str, uid: str, is_typing: bool) -> None:
        if not uid or not self.id_token or not self.config.is_configured:
            return
        payload = {"typing": is_typing, "ts": int(time.time())}
        self._run_async(lambda: self._request("PUT", f"typing/{room_id}/{uid}", payload), None)

    def get_typing_users(self, room_id: str, my_uid: str, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            ok, data = self._request("GET", f"typing/{room_id}")
            if not ok:
                return False, data
            active = []
            now = int(time.time())
            if isinstance(data, dict):
                for uid, info in data.items():
                    if uid != my_uid and isinstance(info, dict):
                        if info.get("typing") and now - int(info.get("ts", 0)) <= 8:
                            active.append(uid)
            return True, active

        self._run_async(task, callback)

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def create_group(
        self,
        creator_uid: str,
        group_name: str,
        member_uids: List[str],
        description: str = "",
        callback: Optional[Callback] = None,
    ) -> None:
        group_id = f"grp_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        unique_members = list(dict.fromkeys([creator_uid] + member_uids))
        now = int(time.time())
        members_map = {uid: True for uid in unique_members}

        payload = {
            "group_id": group_id,
            "name": group_name.strip(),
            "description": description.strip(),
            "created_by": creator_uid,
            "admins": {creator_uid: True},
            "members": members_map,
            "created_at": now,
            "updated_at": now,
            "last_message": "Group created",
        }

        def task() -> Tuple[bool, Any]:
            ok, err = self._request("PUT", f"groups/{group_id}", payload)
            if not ok:
                return False, err
            for uid in unique_members:
                self._request(
                    "PUT",
                    f"user_groups/{uid}/{group_id}",
                    {
                        "group_id": group_id,
                        "name": group_name.strip(),
                        "last_message": "Group created",
                        "updated_at": now,
                        "unread": 0,
                    },
                )
            return True, payload

        self._run_async(task, callback)

    def get_user_groups(self, uid: str, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            ok, data = self._request("GET", f"user_groups/{uid}")
            if not ok:
                return False, data
            groups: List[Dict[str, Any]] = []
            if isinstance(data, dict):
                for gid, info in data.items():
                    if isinstance(info, dict):
                        item = dict(info)
                        item["group_id"] = gid
                        groups.append(item)
            groups.sort(key=lambda g: g.get("updated_at", 0), reverse=True)
            return True, groups

        self._run_async(task, callback)

    def get_group_details(self, group_id: str, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            return self._request("GET", f"groups/{group_id}")

        self._run_async(task, callback)

    # ------------------------------------------------------------------
    # Firebase Storage Upload (Images, Avatars, Files)
    # ------------------------------------------------------------------

    def upload_file(
        self,
        local_path: str,
        remote_folder: str,
        callback: Optional[Callback] = None,
    ) -> None:
        def task() -> Tuple[bool, Any]:
            if not self.config.is_configured:
                return False, "Firebase is not configured."
            if not os.path.exists(local_path):
                return False, f"File not found: {local_path}"

            file_name = os.path.basename(local_path)
            safe_name = f"{int(time.time())}_{uuid.uuid4().hex[:6]}_{file_name}"
            object_path = f"{remote_folder.strip('/')}/{safe_name}"
            mime_type, _ = mimetypes.guess_type(local_path)
            mime_type = mime_type or "application/octet-stream"

            url = self.config.storage_upload_url(object_path)
            headers = {
                "Content-Type": mime_type,
            }
            if self.id_token:
                headers["Authorization"] = f"Firebase {self.id_token}"

            with open(local_path, "rb") as fh:
                data_bytes = fh.read()

            resp = self.session.post(url, headers=headers, data=data_bytes, timeout=45)
            if resp.status_code >= 400:
                return False, f"Storage upload failed ({resp.status_code}): {resp.text}"

            meta = resp.json()
            tokens = meta.get("downloadTokens", "")
            token = tokens.split(",")[0] if tokens else None
            download_url = self.config.storage_download_url(object_path, token=token)
            return True, {"url": download_url, "file_name": file_name, "mime_type": mime_type}

        self._run_async(task, callback)

    # ------------------------------------------------------------------
    # WebRTC Call Signaling & Call History
    # ------------------------------------------------------------------

    def create_call_session(
        self,
        caller_uid: str,
        caller_name: str,
        callee_uid: str,
        callee_name: str,
        call_type: str = "audio",
        callback: Optional[Callback] = None,
    ) -> None:
        call_id = f"call_{int(time.time() * 1000)}_{uuid.uuid4().hex[:5]}"
        now = int(time.time())
        payload = {
            "call_id": call_id,
            "caller_id": caller_uid,
            "caller_name": caller_name,
            "callee_id": callee_uid,
            "callee_name": callee_name,
            "call_type": call_type,
            "status": "ringing",
            "created_at": now,
        }

        def task() -> Tuple[bool, Any]:
            ok, err = self._request("PUT", f"calls/{call_id}", payload)
            if not ok:
                return False, err
            self._request("PUT", f"incoming_calls/{callee_uid}/{call_id}", payload)
            return True, payload

        self._run_async(task, callback)

    def update_call_status(
        self,
        call_id: str,
        status: str,
        callee_uid: Optional[str] = None,
        callback: Optional[Callback] = None,
    ) -> None:
        def task() -> Tuple[bool, Any]:
            ok, err = self._request("PATCH", f"calls/{call_id}", {"status": status, "updated_at": int(time.time())})
            if callee_uid and status in ("accepted", "rejected", "ended", "missed"):
                self._request("DELETE", f"incoming_calls/{callee_uid}/{call_id}")
            return ok, err

        self._run_async(task, callback)

    def get_call_session(self, call_id: str, callback: Optional[Callback] = None) -> None:
        self._run_async(lambda: self._request("GET", f"calls/{call_id}"), callback)

    def get_incoming_calls(self, uid: str, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            ok, data = self._request("GET", f"incoming_calls/{uid}")
            if not ok:
                return False, data
            items = []
            if isinstance(data, dict):
                for cid, entry in data.items():
                    if isinstance(entry, dict) and entry.get("status") == "ringing":
                        entry_copy = dict(entry)
                        entry_copy["call_id"] = cid
                        items.append(entry_copy)
            items.sort(key=lambda c: c.get("created_at", 0), reverse=True)
            return True, items

        self._run_async(task, callback)

    def log_call_history(
        self,
        uid: str,
        peer_uid: str,
        peer_name: str,
        call_type: str,
        direction: str,
        status: str,
        duration_sec: int = 0,
    ) -> None:
        entry_id = f"ch_{int(time.time() * 1000)}_{uuid.uuid4().hex[:4]}"
        payload = {
            "entry_id": entry_id,
            "peer_uid": peer_uid,
            "peer_name": peer_name,
            "call_type": call_type,
            "direction": direction,
            "status": status,
            "duration_sec": duration_sec,
            "timestamp": int(time.time()),
        }
        self._run_async(lambda: self._request("PUT", f"call_history/{uid}/{entry_id}", payload), None)

    def get_call_history(self, uid: str, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            ok, data = self._request("GET", f"call_history/{uid}")
            if not ok:
                return False, data
            history = []
            if isinstance(data, dict):
                for _, item in data.items():
                    if isinstance(item, dict):
                        history.append(item)
            history.sort(key=lambda h: h.get("timestamp", 0), reverse=True)
            return True, history

        self._run_async(task, callback)

    # ------------------------------------------------------------------
    # Admin Operations (Protected by Firebase Security Rules)
    # ------------------------------------------------------------------

    def check_is_admin(self, uid: str, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            ok, data = self._request("GET", f"admins/{uid}")
            return True, bool(ok and data is True)

        self._run_async(task, callback)

    def admin_fetch_dashboard(self, callback: Optional[Callback] = None) -> None:
        def task() -> Tuple[bool, Any]:
            ok_u, users_raw = self._request("GET", "users")
            ok_g, groups_raw = self._request("GET", "groups")
            ok_r, reports_raw = self._request("GET", "reports")
            if not ok_u:
                return False, users_raw

            users: List[Dict[str, Any]] = []
            if isinstance(users_raw, dict):
                for uid, info in users_raw.items():
                    if isinstance(info, dict):
                        row = dict(info)
                        row["uid"] = uid
                        users.append(row)

            groups: List[Dict[str, Any]] = []
            if ok_g and isinstance(groups_raw, dict):
                for gid, info in groups_raw.items():
                    if isinstance(info, dict):
                        row = dict(info)
                        row["group_id"] = gid
                        groups.append(row)

            reports: List[Dict[str, Any]] = []
            if ok_r and isinstance(reports_raw, dict):
                for rid, info in reports_raw.items():
                    if isinstance(info, dict):
                        row = dict(info)
                        row["report_id"] = rid
                        reports.append(row)
            reports.sort(key=lambda r: r.get("created_at", 0), reverse=True)

            stats = {
                "total_users": len(users),
                "online_users": sum(1 for u in users if u.get("online")),
                "blocked_users": sum(1 for u in users if u.get("blocked")),
                "total_groups": len(groups),
                "open_reports": sum(1 for r in reports if r.get("status", "open") == "open"),
            }
            return True, {
                "stats": stats,
                "users": users,
                "groups": groups,
                "reports": reports,
            }

        self._run_async(task, callback)

    def admin_set_user_blocked(
        self,
        target_uid: str,
        blocked: bool,
        callback: Optional[Callback] = None,
    ) -> None:
        self._run_async(
            lambda: self._request("PUT", f"users/{target_uid}/blocked", blocked),
            callback,
        )

    def admin_resolve_report(
        self,
        report_id: str,
        status: str = "resolved",
        callback: Optional[Callback] = None,
    ) -> None:
        self._run_async(
            lambda: self._request("PUT", f"reports/{report_id}/status", status),
            callback,
        )

    def admin_delete_group(self, group_id: str, callback: Optional[Callback] = None) -> None:
        self._run_async(lambda: self._request("DELETE", f"groups/{group_id}"), callback)
