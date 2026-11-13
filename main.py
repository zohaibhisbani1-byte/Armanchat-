"""ArmanChat — Complete Kivy Android Messaging & WebRTC Calling Application."""

import os
from typing import Any, Dict

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager
from kivy.uix.textinput import TextInput
from kivy.utils import platform

from admin_panel import AdminPanelScreen
from auth import FirebaseAuthManager, request_android_permissions
from calls import CallHistoryView, CallScreen
from chat import ChatRoomScreen, ChatsView, ContactsView, GroupsView
from database import FirebaseDatabase
from firebase_config import APP_DIR, load_firebase_config
from notifications import NotificationManager
from profile import ProfileScreen, ProfileSetupScreen, SettingsView


if platform not in ("android", "ios"):
    Window.size = (400, 760)


PRIMARY_DARK = (0.027, 0.369, 0.329, 1)    # #075E54
PRIMARY_TEAL = (0.071, 0.549, 0.494, 1)    # #128C7E
ACCENT_GREEN = (0.145, 0.827, 0.400, 1)    # #25D366
TEXT_DARK = (0.08, 0.12, 0.10, 1)
TEXT_MUTED = (0.38, 0.44, 0.42, 1)
WHITE = (1, 1, 1, 1)
DANGER_RED = (0.86, 0.15, 0.15, 1)


class SplashScreen(Screen):
    """ArmanChat splash screen that verifies saved session on startup."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=dp(32), spacing=dp(16))
        with root.canvas.before:
            Color(*PRIMARY_DARK)
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=lambda i, _v: setattr(self._bg, "pos", i.pos))
        root.bind(size=lambda i, _v: setattr(self._bg, "size", i.size))

        root.add_widget(BoxLayout())
        badge = Label(text="AC", font_size="44sp", bold=True, color=PRIMARY_DARK, size_hint_y=None, height=dp(110))
        with badge.canvas.before:
            Color(*WHITE)
            self._circle = Ellipse(pos=badge.pos, size=(dp(104), dp(104)))
        badge.bind(pos=self._sync_circle, size=self._sync_circle)
        root.add_widget(badge)

        root.add_widget(
            Label(
                text="ArmanChat",
                font_size="30sp",
                bold=True,
                color=WHITE,
                size_hint_y=None,
                height=dp(46),
            )
        )
        root.add_widget(
            Label(
                text="Fast · Secure · Real-Time Messaging",
                font_size="14sp",
                color=(0.82, 0.92, 0.88, 1),
                size_hint_y=None,
                height=dp(28),
            )
        )
        root.add_widget(BoxLayout())
        self.add_widget(root)

    def _sync_circle(self, inst: Any, _val: Any) -> None:
        d = dp(104)
        self._circle.size = (d, d)
        self._circle.pos = (inst.center_x - d / 2, inst.center_y - d / 2)

    def on_enter(self, *_args: Any) -> None:
        Clock.schedule_once(lambda _dt: App.get_running_app().bootstrap_session(), 1.1)


class WelcomeScreen(Screen):
    """Green-and-white onboarding screen."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=dp(26), spacing=dp(16))
        with root.canvas.before:
            Color(*WHITE)
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=lambda i, _v: setattr(self._bg, "pos", i.pos))
        root.bind(size=lambda i, _v: setattr(self._bg, "size", i.size))

        root.add_widget(BoxLayout(size_hint_y=0.15))
        root.add_widget(
            Label(
                text="Welcome to ArmanChat",
                color=PRIMARY_DARK,
                font_size="26sp",
                bold=True,
                size_hint_y=None,
                height=dp(44),
            )
        )
        root.add_widget(
            Label(
                text=(
                    "Real-time 1-to-1 and group chats, image & file sharing,\n"
                    "voice & video calling, and instant notifications."
                ),
                color=TEXT_MUTED,
                font_size="14sp",
                halign="center",
                size_hint_y=None,
                height=dp(68),
            )
        )

        self.config_status_lbl = Label(
            text="",
            color=PRIMARY_TEAL,
            font_size="12sp",
            halign="center",
            size_hint_y=None,
            height=dp(44),
        )
        root.add_widget(self.config_status_lbl)
        root.add_widget(BoxLayout())

        start_btn = Button(
            text="Agree & Continue",
            size_hint_y=None,
            height=dp(52),
            background_normal="",
            background_color=PRIMARY_TEAL,
            color=WHITE,
            bold=True,
            font_size="16sp",
            on_release=lambda _x: setattr(App.get_running_app().sm, "current", "phone_login"),
        )
        root.add_widget(start_btn)
        self.add_widget(root)

    def on_pre_enter(self, *_args: Any) -> None:
        app = App.get_running_app()
        if app.config_obj.is_configured:
            self.config_status_lbl.text = f"Firebase Project: {app.config_obj.project_id}"
            self.config_status_lbl.color = PRIMARY_TEAL
        else:
            self.config_status_lbl.text = (
                "Add firebase_client_config.json before signing in."
            )
            self.config_status_lbl.color = DANGER_RED


class PhoneLoginScreen(Screen):
    """Phone number OTP login + standard Firebase Email/Password sign-in tab."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.auth_mode: str = "phone"
        self._build_ui()

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="vertical", padding=dp(22), spacing=dp(12))
        with root.canvas.before:
            Color(*WHITE)
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=lambda i, _v: setattr(self._bg, "pos", i.pos))
        root.bind(size=lambda i, _v: setattr(self._bg, "size", i.size))

        root.add_widget(
            Label(
                text="Sign in to ArmanChat",
                color=PRIMARY_DARK,
                font_size="22sp",
                bold=True,
                size_hint_y=None,
                height=dp(40),
            )
        )

        # Toggle between Phone OTP and Email/Password
        mode_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        self.phone_tab = Button(
            text="Phone OTP",
            background_normal="",
            background_color=PRIMARY_TEAL,
            color=WHITE,
            on_release=lambda _x: self._set_mode("phone"),
        )
        self.email_tab = Button(
            text="Email & Password",
            background_normal="",
            background_color=(0.88, 0.92, 0.90, 1),
            color=TEXT_DARK,
            on_release=lambda _x: self._set_mode("email"),
        )
        mode_row.add_widget(self.phone_tab)
        mode_row.add_widget(self.email_tab)
        root.add_widget(mode_row)

        self.form_box = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(230))
        root.add_widget(self.form_box)

        self.status_lbl = Label(
            text="",
            color=DANGER_RED,
            font_size="12sp",
            size_hint_y=None,
            height=dp(52),
            halign="center",
            text_size=(dp(320), None),
        )
        root.add_widget(self.status_lbl)

        root.add_widget(BoxLayout())

        self.phone_in = TextInput(hint_text="Phone with country code (e.g. +923001234567)", multiline=False, size_hint_y=None, height=dp(46))
        self.recaptcha_in = TextInput(
            hint_text="Firebase reCAPTCHA / App verification token",
            multiline=False,
            size_hint_y=None,
            height=dp(46),
        )
        self.email_in = TextInput(hint_text="Email address", multiline=False, size_hint_y=None, height=dp(46))
        self.pass_in = TextInput(hint_text="Password (min 6 chars)", password=True, multiline=False, size_hint_y=None, height=dp(46))

        self._render_form()
        self.add_widget(root)

    def _set_mode(self, mode: str) -> None:
        self.auth_mode = mode
        self.status_lbl.text = ""
        self.phone_tab.background_color = PRIMARY_TEAL if mode == "phone" else (0.88, 0.92, 0.90, 1)
        self.phone_tab.color = WHITE if mode == "phone" else TEXT_DARK
        self.email_tab.background_color = PRIMARY_TEAL if mode == "email" else (0.88, 0.92, 0.90, 1)
        self.email_tab.color = WHITE if mode == "email" else TEXT_DARK
        self._render_form()

    def _render_form(self) -> None:
        self.form_box.clear_widgets()
        if self.auth_mode == "phone":
            self.form_box.add_widget(
                Label(
                    text="Enter your phone number. Firebase requires a reCAPTCHA token for SMS OTP.",
                    color=TEXT_MUTED,
                    font_size="12sp",
                    size_hint_y=None,
                    height=dp(36),
                    text_size=(dp(320), None),
                )
            )
            self.form_box.add_widget(self.phone_in)
            self.form_box.add_widget(self.recaptcha_in)
            self.form_box.add_widget(
                Button(
                    text="Send OTP Code",
                    size_hint_y=None,
                    height=dp(48),
                    background_normal="",
                    background_color=PRIMARY_DARK,
                    color=WHITE,
                    bold=True,
                    on_release=lambda _x: self._submit_phone(),
                )
            )
        else:
            self.form_box.add_widget(
                Label(
                    text="Sign in or register instantly using Firebase Email & Password.",
                    color=TEXT_MUTED,
                    font_size="12sp",
                    size_hint_y=None,
                    height=dp(36),
                    text_size=(dp(320), None),
                )
            )
            self.form_box.add_widget(self.email_in)
            self.form_box.add_widget(self.pass_in)
            btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
            btn_row.add_widget(
                Button(
                    text="Sign In",
                    background_normal="",
                    background_color=PRIMARY_DARK,
                    color=WHITE,
                    bold=True,
                    on_release=lambda _x: self._submit_email(create=False),
                )
            )
            btn_row.add_widget(
                Button(
                    text="Create Account",
                    background_normal="",
                    background_color=ACCENT_GREEN,
                    color=(0.05, 0.15, 0.10, 1),
                    bold=True,
                    on_release=lambda _x: self._submit_email(create=True),
                )
            )
            self.form_box.add_widget(btn_row)

    def _submit_phone(self) -> None:
        app = App.get_running_app()
        self.status_lbl.text = "Requesting OTP from Firebase..."

        def on_sent(ok: bool, res: Any) -> None:
            if not ok:
                self.status_lbl.text = str(res)
                return
            self.status_lbl.text = ""
            app.sm.current = "otp_verify"

        app.auth.send_phone_otp(self.phone_in.text, self.recaptcha_in.text, on_sent)

    def _submit_email(self, create: bool) -> None:
        app = App.get_running_app()
        self.status_lbl.text = "Authenticating with Firebase..."

        def on_done(ok: bool, res: Any) -> None:
            if not ok:
                self.status_lbl.text = str(res)
                return
            self.status_lbl.text = ""
            app.on_authenticated()

        app.auth.sign_in_with_email(self.email_in.text, self.pass_in.text, create_account=create, callback=on_done)


class OTPVerificationScreen(Screen):
    """6-digit SMS OTP verification screen."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(14))
        with root.canvas.before:
            Color(*WHITE)
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=lambda i, _v: setattr(self._bg, "pos", i.pos))
        root.bind(size=lambda i, _v: setattr(self._bg, "size", i.size))

        root.add_widget(
            Label(
                text="Verify Phone Number",
                color=PRIMARY_DARK,
                font_size="22sp",
                bold=True,
                size_hint_y=None,
                height=dp(42),
            )
        )
        self.info_lbl = Label(
            text="Enter the 6-digit SMS code sent to your phone.",
            color=TEXT_MUTED,
            font_size="13sp",
            size_hint_y=None,
            height=dp(36),
        )
        root.add_widget(self.info_lbl)

        self.otp_in = TextInput(
            hint_text="6-digit OTP code",
            input_filter="int",
            multiline=False,
            font_size="20sp",
            halign="center",
            size_hint_y=None,
            height=dp(54),
        )
        root.add_widget(self.otp_in)

        self.status_lbl = Label(text="", color=DANGER_RED, size_hint_y=None, height=dp(36))
        root.add_widget(self.status_lbl)

        root.add_widget(
            Button(
                text="Verify & Continue",
                size_hint_y=None,
                height=dp(50),
                background_normal="",
                background_color=PRIMARY_TEAL,
                color=WHITE,
                bold=True,
                on_release=lambda _x: self.verify(),
            )
        )
        root.add_widget(
            Button(
                text="Change Phone Number",
                size_hint_y=None,
                height=dp(44),
                background_normal="",
                background_color=(0.90, 0.94, 0.92, 1),
                color=PRIMARY_DARK,
                on_release=lambda _x: setattr(App.get_running_app().sm, "current", "phone_login"),
            )
        )
        root.add_widget(BoxLayout())
        self.add_widget(root)

    def on_pre_enter(self, *_args: Any) -> None:
        app = App.get_running_app()
        if app.auth.pending_phone:
            self.info_lbl.text = f"Enter the 6-digit code sent to {app.auth.pending_phone}"

    def verify(self) -> None:
        app = App.get_running_app()
        self.status_lbl.text = "Verifying OTP..."

        def on_verified(ok: bool, res: Any) -> None:
            if not ok:
                self.status_lbl.text = str(res)
                return
            self.status_lbl.text = ""
            app.on_authenticated()

        app.auth.verify_phone_otp(self.otp_in.text, on_verified)


class HomeScreen(Screen):
    """Main ArmanChat shell with WhatsApp-style green top header and 5 tabs."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.active_tab: str = "chats"
        self.chats_view = ChatsView()
        self.groups_view = GroupsView()
        self.contacts_view = ContactsView()
        self.calls_view = CallHistoryView()
        self.settings_view = SettingsView()
        self.tab_buttons: Dict[str, Button] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*WHITE)
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=lambda i, _v: setattr(self._bg, "pos", i.pos))
        root.bind(size=lambda i, _v: setattr(self._bg, "size", i.size))

        # Branded green app bar
        header = BoxLayout(size_hint_y=None, height=dp(58), padding=[dp(16), dp(8)], spacing=dp(8))
        with header.canvas.before:
            Color(*PRIMARY_DARK)
            self._hbg = RoundedRectangle(pos=header.pos, size=header.size, radius=[0])
        header.bind(pos=lambda i, _v: setattr(self._hbg, "pos", i.pos))
        header.bind(size=lambda i, _v: setattr(self._hbg, "size", i.size))

        header.add_widget(
            Label(
                text="ArmanChat",
                color=WHITE,
                bold=True,
                font_size="20sp",
                halign="left",
                text_size=(dp(180), None),
            )
        )
        self.user_badge = Button(
            text="Profile",
            size_hint_x=None,
            width=dp(96),
            background_normal="",
            background_color=PRIMARY_TEAL,
            color=WHITE,
            on_release=lambda _x: setattr(App.get_running_app().sm, "current", "profile"),
        )
        header.add_widget(self.user_badge)
        root.add_widget(header)

        # Active content body
        self.content_area = BoxLayout()
        root.add_widget(self.content_area)

        # Bottom navigation bar
        nav = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(2))
        with nav.canvas.before:
            Color(0.95, 0.97, 0.96, 1)
            self._nbg = RoundedRectangle(pos=nav.pos, size=nav.size, radius=[0])
        nav.bind(pos=lambda i, _v: setattr(self._nbg, "pos", i.pos))
        nav.bind(size=lambda i, _v: setattr(self._nbg, "size", i.size))

        for key, title in (
            ("chats", "Chats"),
            ("groups", "Groups"),
            ("contacts", "Contacts"),
            ("calls", "Calls"),
            ("settings", "Settings"),
        ):
            btn = Button(
                text=title,
                background_normal="",
                background_color=PRIMARY_DARK if key == "chats" else (0.95, 0.97, 0.96, 1),
                color=WHITE if key == "chats" else TEXT_DARK,
                bold=(key == "chats"),
                font_size="13sp",
                on_release=lambda _x, k=key: self.select_tab(k),
            )
            self.tab_buttons[key] = btn
            nav.add_widget(btn)
        root.add_widget(nav)
        self.add_widget(root)
        self.select_tab("chats")

    def select_tab(self, key: str) -> None:
        self.active_tab = key
        for tab_key, btn in self.tab_buttons.items():
            active = tab_key == key
            btn.background_color = PRIMARY_DARK if active else (0.95, 0.97, 0.96, 1)
            btn.color = WHITE if active else TEXT_DARK
            btn.bold = active

        self.content_area.clear_widgets()
        if key == "chats":
            self.content_area.add_widget(self.chats_view)
            self.chats_view.load_chats()
        elif key == "groups":
            self.content_area.add_widget(self.groups_view)
            self.groups_view.load_groups()
        elif key == "contacts":
            self.content_area.add_widget(self.contacts_view)
            self.contacts_view.load_contacts()
        elif key == "calls":
            self.content_area.add_widget(self.calls_view)
            self.calls_view.load_history()
        elif key == "settings":
            self.content_area.add_widget(self.settings_view)

    def refresh_active(self) -> None:
        self.select_tab(self.active_tab)


class ArmanChatApp(App):
    """Main Kivy application coordinating Auth, Database, Notifications, and Screens."""

    title = "ArmanChat"

    def build(self) -> ScreenManager:
        request_android_permissions()
        self.config_obj = load_firebase_config()
        self.auth = FirebaseAuthManager(self.config_obj)
        self.db = FirebaseDatabase(self.config_obj)
        self.notifications = NotificationManager(self.db)
        self.current_profile: Dict[str, Any] = {}

        icon_path = os.path.join(APP_DIR, "assets", "icon.png")
        if os.path.exists(icon_path):
            self.icon = icon_path

        self.sm = ScreenManager(transition=FadeTransition(duration=0.15))
        self.sm.add_widget(SplashScreen(name="splash"))
        self.sm.add_widget(WelcomeScreen(name="welcome"))
        self.sm.add_widget(PhoneLoginScreen(name="phone_login"))
        self.sm.add_widget(OTPVerificationScreen(name="otp_verify"))
        self.sm.add_widget(ProfileSetupScreen(name="profile_setup"))
        self.home_screen = HomeScreen(name="home")
        self.sm.add_widget(self.home_screen)
        self.chat_room_screen = ChatRoomScreen(name="chat_room")
        self.sm.add_widget(self.chat_room_screen)
        self.sm.add_widget(ProfileScreen(name="profile"))
        self.call_screen = CallScreen(name="call")
        self.sm.add_widget(self.call_screen)
        self.sm.add_widget(AdminPanelScreen(name="admin"))
        return self.sm

    def reload_firebase_config(self) -> None:
        self.config_obj = load_firebase_config()
        self.auth.config = self.config_obj
        self.db.config = self.config_obj

    def bootstrap_session(self) -> None:
        if not self.auth.is_authenticated:
            self.sm.current = "welcome"
            return

        def on_refreshed(ok: bool, _res: Any) -> None:
            if ok:
                self.on_authenticated()
            else:
                self.auth.logout()
                self.sm.current = "welcome"

        self.auth.refresh_session(on_refreshed)

    def on_authenticated(self) -> None:
        self.db.set_credentials(self.auth.uid, self.auth.id_token)
        self.db.get_user_profile(self.auth.uid, self._handle_loaded_profile)

    def _handle_loaded_profile(self, ok: bool, data: Any) -> None:
        if ok and isinstance(data, dict) and data.get("name"):
            if data.get("blocked"):
                self.sign_out()
                return
            self.on_profile_ready(data)
        else:
            self.sm.current = "profile_setup"

    def on_profile_ready(self, profile: Dict[str, Any]) -> None:
        self.current_profile = profile
        self.db.update_presence(self.auth.uid, True)
        self.notifications.register_device_token(self.auth.uid)
        self.notifications.start_listening(self.auth.uid, on_incoming_call=self.handle_incoming_call)
        self.home_screen.user_badge.text = (profile.get("name") or "Profile")[:10]
        self.sm.current = "home"
        self.home_screen.select_tab("chats")

    def refresh_home_tabs(self) -> None:
        self.home_screen.refresh_active()

    def start_direct_chat(self, peer_user: Dict[str, Any]) -> None:
        peer_uid = peer_user.get("uid", "")
        peer_name = peer_user.get("name") or peer_user.get("phone") or "User"
        my_name = self.current_profile.get("name", "ArmanChat User")

        def on_ready(ok: bool, chat_id: Any) -> None:
            if ok and chat_id:
                self.open_chat_room(
                    room_id=str(chat_id),
                    title=peer_name,
                    is_group=False,
                    peer_uid=peer_uid,
                )

        self.db.ensure_direct_chat(
            self.auth.uid,
            peer_uid,
            my_name,
            peer_name,
            peer_avatar=peer_user.get("avatar_url", ""),
            callback=on_ready,
        )

    def open_chat_room(
        self,
        room_id: str,
        title: str,
        is_group: bool = False,
        peer_uid: str = "",
    ) -> None:
        self.chat_room_screen.load_room(
            room_id=room_id,
            title=title,
            is_group=is_group,
            peer_uid=peer_uid,
        )
        self.sm.current = "chat_room"

    def start_call(self, peer_uid: str, peer_name: str, call_type: str = "audio") -> None:
        if not peer_uid:
            return
        self.call_screen.start_outgoing_call(peer_uid, peer_name, call_type)
        self.sm.current = "call"

    def handle_incoming_call(self, call_payload: Dict[str, Any]) -> None:
        if self.sm.current == "call":
            return
        self.call_screen.open_incoming_call(call_payload)
        self.sm.current = "call"

    def sign_out(self) -> None:
        self.notifications.stop_listening()
        if self.auth.uid:
            self.db.update_presence(self.auth.uid, False)
        self.auth.logout()
        self.db.set_credentials(None, None)
        self.current_profile = {}
        self.sm.current = "welcome"

    def on_pause(self) -> bool:
        if self.auth.uid:
            self.db.update_presence(self.auth.uid, False)
        return True

    def on_resume(self) -> None:
        if self.auth.uid:
            self.db.update_presence(self.auth.uid, True)

    def on_stop(self) -> None:
        self.notifications.stop_listening()
        if self.auth.uid:
            self.db.update_presence(self.auth.uid, False)


if __name__ == "__main__":
    ArmanChatApp().run()
