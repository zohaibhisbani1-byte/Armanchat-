"""Audio and Video Calling screens, WebRTC signaling manager, and Call History."""

from typing import Any, Dict, List, Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from database import format_timestamp
from webrtc_bridge import AndroidWebRTCBridge


PRIMARY_DARK = (0.027, 0.369, 0.329, 1)    # #075E54
PRIMARY_TEAL = (0.071, 0.549, 0.494, 1)    # #128C7E
ACCENT_GREEN = (0.145, 0.827, 0.400, 1)    # #25D366
DANGER_RED = (0.863, 0.149, 0.149, 1)      # #DC2626
WHITE = (1, 1, 1, 1)
MUTED = (0.82, 0.90, 0.88, 1)


class CallScreen(Screen):
    """Handles Outgoing, Incoming, and Active WebRTC Audio/Video Calls."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.call_id: str = ""
        self.peer_uid: str = ""
        self.peer_name: str = ""
        self.call_type: str = "audio"
        self.direction: str = "outgoing"
        self.state_mode: str = "outgoing"  # outgoing | incoming | active
        self.mic_muted: bool = False
        self.speaker_on: bool = False
        self.camera_on: bool = True
        self.elapsed_seconds: int = 0
        self._timer_ev = None
        self._poll_ev = None
        self.bridge: Optional[AndroidWebRTCBridge] = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(18))
        with root.canvas.before:
            Color(*PRIMARY_DARK)
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=self._sync_bg, size=self._sync_bg)

        self.mode_label = Label(
            text="ArmanChat Audio Call",
            font_size="15sp",
            color=MUTED,
            size_hint_y=None,
            height=dp(32),
        )
        root.add_widget(self.mode_label)

        avatar_wrap = BoxLayout(size_hint_y=None, height=dp(140), padding=[dp(90), dp(10)])
        self.avatar_badge = Label(
            text="AC",
            font_size="34sp",
            bold=True,
            color=PRIMARY_DARK,
        )
        with self.avatar_badge.canvas.before:
            Color(*WHITE)
            self._avatar_circle = Ellipse(pos=self.avatar_badge.pos, size=(dp(110), dp(110)))
        self.avatar_badge.bind(pos=self._sync_avatar, size=self._sync_avatar)
        avatar_wrap.add_widget(self.avatar_badge)
        root.add_widget(avatar_wrap)

        self.peer_label = Label(
            text="Contact Name",
            font_size="24sp",
            bold=True,
            color=WHITE,
            size_hint_y=None,
            height=dp(40),
        )
        root.add_widget(self.peer_label)

        self.status_label = Label(
            text="Calling...",
            font_size="16sp",
            color=MUTED,
            size_hint_y=None,
            height=dp(32),
        )
        root.add_widget(self.status_label)

        self.bridge_info = Label(
            text="End-to-end WebRTC signaling via Firebase",
            font_size="12sp",
            color=MUTED,
            size_hint_y=None,
            height=dp(26),
        )
        root.add_widget(self.bridge_info)

        root.add_widget(BoxLayout())  # Spacer

        # Active media controls row
        self.media_controls = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(10))
        self.mute_btn = Button(
            text="Mute",
            background_normal="",
            background_color=PRIMARY_TEAL,
            color=WHITE,
            on_release=lambda _x: self.toggle_mute(),
        )
        self.speaker_btn = Button(
            text="Speaker",
            background_normal="",
            background_color=PRIMARY_TEAL,
            color=WHITE,
            on_release=lambda _x: self.toggle_speaker(),
        )
        self.cam_btn = Button(
            text="Cam On",
            background_normal="",
            background_color=PRIMARY_TEAL,
            color=WHITE,
            on_release=lambda _x: self.toggle_camera(),
        )
        self.media_controls.add_widget(self.mute_btn)
        self.media_controls.add_widget(self.speaker_btn)
        self.media_controls.add_widget(self.cam_btn)
        root.add_widget(self.media_controls)

        # Call action buttons (Accept / Reject / End)
        self.action_row = BoxLayout(size_hint_y=None, height=dp(60), spacing=dp(16))
        self.accept_btn = Button(
            text="Accept Call",
            background_normal="",
            background_color=ACCENT_GREEN,
            color=(0.05, 0.15, 0.10, 1),
            bold=True,
            on_release=lambda _x: self.accept_call(),
        )
        self.reject_btn = Button(
            text="End / Reject",
            background_normal="",
            background_color=DANGER_RED,
            color=WHITE,
            bold=True,
            on_release=lambda _x: self.end_or_reject_call(),
        )
        self.action_row.add_widget(self.accept_btn)
        self.action_row.add_widget(self.reject_btn)
        root.add_widget(self.action_row)

        self.add_widget(root)

    def _sync_bg(self, instance: Any, _val: Any) -> None:
        self._bg.pos = instance.pos
        self._bg.size = instance.size

    def _sync_avatar(self, instance: Any, _val: Any) -> None:
        diameter = min(instance.width, instance.height, dp(110))
        self._avatar_circle.size = (diameter, diameter)
        self._avatar_circle.pos = (
            instance.center_x - diameter / 2,
            instance.center_y - diameter / 2,
        )

    def start_outgoing_call(self, peer_uid: str, peer_name: str, call_type: str = "audio") -> None:
        app = App.get_running_app()
        self.peer_uid = peer_uid
        self.peer_name = peer_name
        self.call_type = call_type
        self.direction = "outgoing"
        self.state_mode = "outgoing"
        self.elapsed_seconds = 0
        self.mic_muted = False
        self.speaker_on = call_type == "video"
        self.camera_on = call_type == "video"
        self._refresh_controls_ui()

        self.peer_label.text = peer_name or "ArmanChat User"
        self.avatar_badge.text = (peer_name[:2] or "AC").upper()
        self.mode_label.text = "ArmanChat Video Call" if call_type == "video" else "ArmanChat Voice Call"
        self.status_label.text = "Ringing..."

        def on_created(ok: bool, data: Any) -> None:
            if not ok or not isinstance(data, dict):
                self.status_label.text = f"Call failed: {data}"
                return
            self.call_id = data["call_id"]
            self._start_polling_call()

        my_name = app.current_profile.get("name", "ArmanChat User")
        app.db.create_call_session(
            app.auth.uid,
            my_name,
            peer_uid,
            peer_name,
            call_type=call_type,
            callback=on_created,
        )

    def open_incoming_call(self, call_payload: Dict[str, Any]) -> None:
        self.call_id = call_payload.get("call_id", "")
        self.peer_uid = call_payload.get("caller_id", "")
        self.peer_name = call_payload.get("caller_name", "Unknown")
        self.call_type = call_payload.get("call_type", "audio")
        self.direction = "incoming"
        self.state_mode = "incoming"
        self.elapsed_seconds = 0
        self.mic_muted = False
        self.speaker_on = self.call_type == "video"
        self.camera_on = self.call_type == "video"

        self.peer_label.text = self.peer_name
        self.avatar_badge.text = (self.peer_name[:2] or "AC").upper()
        self.mode_label.text = (
            "Incoming Video Call" if self.call_type == "video" else "Incoming Voice Call"
        )
        self.status_label.text = "Incoming call..."
        self._refresh_controls_ui()
        self._start_polling_call()

    def _refresh_controls_ui(self) -> None:
        if self.state_mode == "incoming":
            self.accept_btn.disabled = False
            self.accept_btn.opacity = 1
            self.reject_btn.text = "Reject"
        else:
            self.accept_btn.disabled = True
            self.accept_btn.opacity = 0
            self.reject_btn.text = "End Call"

        self.mute_btn.text = "Unmute" if self.mic_muted else "Mute"
        self.speaker_btn.text = "Speaker On" if self.speaker_on else "Earpiece"
        self.cam_btn.text = "Cam On" if self.camera_on else "Cam Off"
        self.cam_btn.disabled = self.call_type != "video"

    def accept_call(self) -> None:
        app = App.get_running_app()
        if not self.call_id:
            return
        self.state_mode = "active"
        self.status_label.text = "Connecting media..."
        self._refresh_controls_ui()
        app.db.update_call_status(self.call_id, "accepted", callee_uid=app.auth.uid)
        self._activate_webrtc_media(role="callee")

    def end_or_reject_call(self) -> None:
        app = App.get_running_app()
        self._stop_timers()
        if self.bridge:
            self.bridge.stop_media_session()
            self.bridge = None

        final_status = "rejected" if self.state_mode == "incoming" else "ended"
        callee_target = app.auth.uid if self.direction == "incoming" else self.peer_uid
        if self.call_id:
            app.db.update_call_status(self.call_id, final_status, callee_uid=callee_target)

        if self.peer_uid:
            app.db.log_call_history(
                app.auth.uid,
                self.peer_uid,
                self.peer_name,
                self.call_type,
                self.direction,
                "completed" if self.elapsed_seconds > 0 else final_status,
                self.elapsed_seconds,
            )

        app.sm.current = "home"

    def toggle_mute(self) -> None:
        self.mic_muted = not self.mic_muted
        if self.bridge:
            self.bridge.set_mic_muted(self.mic_muted)
        self._refresh_controls_ui()

    def toggle_speaker(self) -> None:
        self.speaker_on = not self.speaker_on
        if self.bridge:
            self.bridge.set_speaker(self.speaker_on)
        self._refresh_controls_ui()

    def toggle_camera(self) -> None:
        self.camera_on = not self.camera_on
        if self.bridge:
            self.bridge.set_camera_enabled(self.camera_on)
        self._refresh_controls_ui()

    def _activate_webrtc_media(self, role: str) -> None:
        app = App.get_running_app()
        self.bridge = AndroidWebRTCBridge(app.config_obj)
        note = self.bridge.start_media_session(
            call_id=self.call_id,
            role=role,
            call_type=self.call_type,
            id_token=app.auth.id_token,
        )
        self.bridge_info.text = note
        self._start_duration_timer()

    def _start_duration_timer(self) -> None:
        if self._timer_ev is not None:
            self._timer_ev.cancel()
        self.elapsed_seconds = 0

        def tick(_dt: float) -> None:
            self.elapsed_seconds += 1
            mins, secs = divmod(self.elapsed_seconds, 60)
            self.status_label.text = f"In call  {mins:02d}:{secs:02d}"

        self._timer_ev = Clock.schedule_interval(tick, 1.0)

    def _start_polling_call(self) -> None:
        if self._poll_ev is not None:
            self._poll_ev.cancel()

        def poll(_dt: float) -> None:
            app = App.get_running_app()
            if not self.call_id:
                return

            def on_session(ok: bool, data: Any) -> None:
                if not ok or not isinstance(data, dict):
                    return
                remote_status = data.get("status", "")
                if remote_status == "accepted" and self.state_mode == "outgoing":
                    self.state_mode = "active"
                    self._refresh_controls_ui()
                    self._activate_webrtc_media(role="caller")
                elif remote_status in ("rejected", "ended"):
                    self.status_label.text = f"Call {remote_status}"
                    Clock.schedule_once(lambda _t: self.end_or_reject_call(), 0.6)

            app.db.get_call_session(self.call_id, on_session)

        self._poll_ev = Clock.schedule_interval(poll, 2.0)

    def _stop_timers(self) -> None:
        if self._timer_ev is not None:
            self._timer_ev.cancel()
            self._timer_ev = None
        if self._poll_ev is not None:
            self._poll_ev.cancel()
            self._poll_ev = None


class CallHistoryView(BoxLayout):
    """Embedded tab showing user's recent audio/video calls with redial buttons."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(12), **kwargs)
        header = BoxLayout(size_hint_y=None, height=dp(40))
        header.add_widget(
            Label(
                text="Recent Calls",
                color=(0.05, 0.15, 0.12, 1),
                font_size="17sp",
                bold=True,
                halign="left",
            )
        )
        refresh_btn = Button(
            text="Refresh",
            size_hint_x=None,
            width=dp(90),
            background_normal="",
            background_color=PRIMARY_TEAL,
            color=WHITE,
            on_release=lambda _x: self.load_history(),
        )
        header.add_widget(refresh_btn)
        self.add_widget(header)

        self.scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        self.add_widget(self.scroll)

    def load_history(self) -> None:
        app = App.get_running_app()
        if not app.auth.uid:
            return
        app.db.get_call_history(app.auth.uid, self._render_history)

    def _render_history(self, ok: bool, data: Any) -> None:
        self.list_box.clear_widgets()
        if not ok:
            self.list_box.add_widget(
                Label(
                    text=str(data),
                    color=(0.6, 0.1, 0.1, 1),
                    size_hint_y=None,
                    height=dp(44),
                )
            )
            return
        items: List[Dict[str, Any]] = data or []
        if not items:
            self.list_box.add_widget(
                Label(
                    text="No call history yet. Open Contacts to start a voice or video call.",
                    color=(0.4, 0.45, 0.43, 1),
                    size_hint_y=None,
                    height=dp(60),
                )
            )
            return

        app = App.get_running_app()
        for entry in items:
            row = BoxLayout(size_hint_y=None, height=dp(62), padding=dp(8), spacing=dp(8))
            with row.canvas.before:
                Color(0.96, 0.98, 0.97, 1)
                bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(10)])
            row.bind(pos=lambda inst, _v, r=bg: setattr(r, "pos", inst.pos))
            row.bind(size=lambda inst, _v, r=bg: setattr(r, "size", inst.size))

            info_col = BoxLayout(orientation="vertical")
            peer_name = entry.get("peer_name", "Contact")
            direction = entry.get("direction", "outgoing").capitalize()
            ctype = entry.get("call_type", "audio").capitalize()
            dur = int(entry.get("duration_sec", 0))
            ts_str = format_timestamp(entry.get("timestamp"))
            info_col.add_widget(
                Label(
                    text=peer_name,
                    color=(0.06, 0.12, 0.10, 1),
                    bold=True,
                    font_size="15sp",
                    halign="left",
                    text_size=(dp(200), None),
                )
            )
            info_col.add_widget(
                Label(
                    text=f"{direction} {ctype} · {entry.get('status', '')} · {dur}s · {ts_str}",
                    color=(0.35, 0.42, 0.40, 1),
                    font_size="12sp",
                    halign="left",
                    text_size=(dp(210), None),
                )
            )
            row.add_widget(info_col)

            redial_btn = Button(
                text="Call",
                size_hint_x=None,
                width=dp(72),
                background_normal="",
                background_color=ACCENT_GREEN,
                color=(0.05, 0.15, 0.10, 1),
                bold=True,
                on_release=lambda _x, e=entry: app.start_call(
                    e.get("peer_uid", ""),
                    e.get("peer_name", "Contact"),
                    e.get("call_type", "audio"),
                ),
            )
            row.add_widget(redial_btn)
            self.list_box.add_widget(row)
