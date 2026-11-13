"""User profile setup, profile editor, settings, and Firebase config editor."""

from typing import Any, Dict

from kivy.app import App
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput

from chat import open_file_picker
from firebase_config import FirebaseConfig, save_firebase_config


PRIMARY_DARK = (0.027, 0.369, 0.329, 1)
PRIMARY_TEAL = (0.071, 0.549, 0.494, 1)
ACCENT_GREEN = (0.145, 0.827, 0.400, 1)
TEXT_DARK = (0.08, 0.12, 0.10, 1)
TEXT_MUTED = (0.38, 0.44, 0.42, 1)
WHITE = (1, 1, 1, 1)
DANGER_RED = (0.86, 0.15, 0.15, 1)


class ProfileSetupScreen(Screen):
    """First-time profile onboarding after Phone OTP or Email authentication."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.avatar_url: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(14))
        with root.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=lambda i, _v: setattr(self._bg, "pos", i.pos))
        root.bind(size=lambda i, _v: setattr(self._bg, "size", i.size))

        root.add_widget(
            Label(
                text="Set Up Your ArmanChat Profile",
                color=PRIMARY_DARK,
                font_size="22sp",
                bold=True,
                size_hint_y=None,
                height=dp(44),
            )
        )
        root.add_widget(
            Label(
                text="Add your name, phone number, and optional photo so friends can find you.",
                color=TEXT_MUTED,
                font_size="13sp",
                size_hint_y=None,
                height=dp(40),
            )
        )

        self.name_input = TextInput(hint_text="Display Name (e.g. Arman Khan)", multiline=False, size_hint_y=None, height=dp(46))
        self.phone_input = TextInput(hint_text="Phone Number (e.g. +923001234567)", multiline=False, size_hint_y=None, height=dp(46))
        self.bio_input = TextInput(
            hint_text="About (e.g. Hey there! I am using ArmanChat.)",
            text="Hey there! I am using ArmanChat.",
            multiline=False,
            size_hint_y=None,
            height=dp(46),
        )
        root.add_widget(self.name_input)
        root.add_widget(self.phone_input)
        root.add_widget(self.bio_input)

        self.photo_btn = Button(
            text="Upload Profile Photo (Optional)",
            size_hint_y=None,
            height=dp(44),
            background_normal="",
            background_color=(0.90, 0.94, 0.92, 1),
            color=PRIMARY_DARK,
            on_release=lambda _x: self._pick_avatar(),
        )
        root.add_widget(self.photo_btn)

        self.status_lbl = Label(text="", color=DANGER_RED, size_hint_y=None, height=dp(32))
        root.add_widget(self.status_lbl)

        root.add_widget(BoxLayout())

        save_btn = Button(
            text="Continue to ArmanChat",
            size_hint_y=None,
            height=dp(52),
            background_normal="",
            background_color=PRIMARY_TEAL,
            color=WHITE,
            bold=True,
            on_release=lambda _x: self.save_profile(),
        )
        root.add_widget(save_btn)
        self.add_widget(root)

    def on_pre_enter(self, *_args: Any) -> None:
        app = App.get_running_app()
        if app.auth.phone_number and not self.phone_input.text:
            self.phone_input.text = app.auth.phone_number

    def _pick_avatar(self) -> None:
        def on_file(path: str) -> None:
            app = App.get_running_app()
            self.status_lbl.text = "Uploading avatar..."
            app.db.upload_file(
                path,
                f"avatars/{app.auth.uid}",
                callback=lambda ok, res: self._on_uploaded(ok, res),
            )

        open_file_picker(on_file, filters=["*.png", "*.jpg", "*.jpeg"])

    def _on_uploaded(self, ok: bool, res: Any) -> None:
        if ok and isinstance(res, dict):
            self.avatar_url = res.get("url", "")
            self.photo_btn.text = "Profile Photo Uploaded"
            self.status_lbl.text = ""
        else:
            self.status_lbl.text = str(res)

    def save_profile(self) -> None:
        name = self.name_input.text.strip()
        if not name:
            self.status_lbl.text = "Please enter your display name."
            return
        app = App.get_running_app()
        profile = {
            "name": name,
            "phone": self.phone_input.text.strip() or app.auth.phone_number,
            "email": app.auth.email,
            "bio": self.bio_input.text.strip() or "Hey there! I am using ArmanChat.",
            "avatar_url": self.avatar_url,
            "online": True,
            "blocked": False,
        }

        def on_saved(ok: bool, res: Any) -> None:
            if not ok:
                self.status_lbl.text = str(res)
                return
            app.on_profile_ready(profile)

        app.db.save_user_profile(app.auth.uid, profile, on_saved)


class ProfileScreen(Screen):
    """View and update user profile details & avatar."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.avatar_url: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=lambda i, _v: setattr(self._bg, "pos", i.pos))
        root.bind(size=lambda i, _v: setattr(self._bg, "size", i.size))

        header = BoxLayout(size_hint_y=None, height=dp(58), padding=dp(8), spacing=dp(8))
        with header.canvas.before:
            Color(*PRIMARY_DARK)
            self._hbg = RoundedRectangle(pos=header.pos, size=header.size, radius=[0])
        header.bind(pos=lambda i, _v: setattr(self._hbg, "pos", i.pos))
        header.bind(size=lambda i, _v: setattr(self._hbg, "size", i.size))

        header.add_widget(
            Button(
                text="< Back",
                size_hint_x=None,
                width=dp(80),
                background_normal="",
                background_color=PRIMARY_DARK,
                color=WHITE,
                on_release=lambda _x: setattr(App.get_running_app().sm, "current", "home"),
            )
        )
        header.add_widget(Label(text="My Profile", color=WHITE, bold=True, font_size="18sp"))
        root.add_widget(header)

        form = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
        self.avatar_img = AsyncImage(source="", size_hint_y=None, height=dp(110))
        form.add_widget(self.avatar_img)

        form.add_widget(
            Button(
                text="Change Avatar Photo",
                size_hint_y=None,
                height=dp(42),
                background_normal="",
                background_color=(0.90, 0.94, 0.92, 1),
                color=PRIMARY_DARK,
                on_release=lambda _x: self._pick_avatar(),
            )
        )

        self.name_in = TextInput(hint_text="Display Name", multiline=False, size_hint_y=None, height=dp(46))
        self.phone_in = TextInput(hint_text="Phone Number", multiline=False, size_hint_y=None, height=dp(46))
        self.bio_in = TextInput(hint_text="About / Bio", multiline=False, size_hint_y=None, height=dp(46))
        self.uid_lbl = Label(text="", color=TEXT_MUTED, font_size="11sp", size_hint_y=None, height=dp(28))
        self.feedback_lbl = Label(text="", color=PRIMARY_TEAL, size_hint_y=None, height=dp(28))

        form.add_widget(self.name_in)
        form.add_widget(self.phone_in)
        form.add_widget(self.bio_in)
        form.add_widget(self.uid_lbl)
        form.add_widget(self.feedback_lbl)
        form.add_widget(BoxLayout())
        form.add_widget(
            Button(
                text="Save Changes",
                size_hint_y=None,
                height=dp(50),
                background_normal="",
                background_color=PRIMARY_TEAL,
                color=WHITE,
                bold=True,
                on_release=lambda _x: self.save_changes(),
            )
        )
        root.add_widget(form)
        self.add_widget(root)

    def on_pre_enter(self, *_args: Any) -> None:
        app = App.get_running_app()
        p = app.current_profile
        self.name_in.text = p.get("name", "")
        self.phone_in.text = p.get("phone", "")
        self.bio_in.text = p.get("bio", "")
        self.avatar_url = p.get("avatar_url", "")
        self.avatar_img.source = self.avatar_url
        self.uid_lbl.text = f"User ID: {app.auth.uid}"
        self.feedback_lbl.text = ""

    def _pick_avatar(self) -> None:
        def on_file(path: str) -> None:
            app = App.get_running_app()
            self.feedback_lbl.text = "Uploading..."
            app.db.upload_file(
                path,
                f"avatars/{app.auth.uid}",
                callback=lambda ok, res: self._on_uploaded(ok, res),
            )

        open_file_picker(on_file, filters=["*.png", "*.jpg", "*.jpeg"])

    def _on_uploaded(self, ok: bool, res: Any) -> None:
        if ok and isinstance(res, dict):
            self.avatar_url = res.get("url", "")
            self.avatar_img.source = self.avatar_url
            self.feedback_lbl.text = "Avatar uploaded. Tap Save Changes."
        else:
            self.feedback_lbl.text = str(res)

    def save_changes(self) -> None:
        app = App.get_running_app()
        updated = {
            "name": self.name_in.text.strip(),
            "phone": self.phone_in.text.strip(),
            "bio": self.bio_in.text.strip(),
            "avatar_url": self.avatar_url,
        }

        def on_saved(ok: bool, res: Any) -> None:
            if ok:
                app.current_profile.update(updated)
                self.feedback_lbl.text = "Profile saved!"
            else:
                self.feedback_lbl.text = str(res)

        app.db.save_user_profile(app.auth.uid, updated, on_saved)


class SettingsView(BoxLayout):
    """Embedded Settings tab: Profile, Notifications, Blocked Users, Firebase Config, Admin, Logout."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", padding=dp(14), spacing=dp(10), **kwargs)
        self.scroll = ScrollView()
        self.col = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10))
        self.col.bind(minimum_height=self.col.setter("height"))
        self.scroll.add_widget(self.col)
        self.add_widget(self.scroll)
        self._build_items()

    def _build_items(self) -> None:
        app = App.get_running_app()
        self.col.clear_widgets()

        self.col.add_widget(
            Label(
                text="Account & App Settings",
                color=PRIMARY_DARK,
                bold=True,
                font_size="18sp",
                size_hint_y=None,
                height=dp(36),
                halign="left",
            )
        )

        self.col.add_widget(
            Button(
                text="Edit My Profile & Avatar",
                size_hint_y=None,
                height=dp(48),
                background_normal="",
                background_color=(0.94, 0.97, 0.95, 1),
                color=TEXT_DARK,
                on_release=lambda _x: setattr(app.sm, "current", "profile"),
            )
        )

        notif_row = BoxLayout(size_hint_y=None, height=dp(48), padding=[dp(8), 0])
        notif_row.add_widget(Label(text="Message & Call Notifications", color=TEXT_DARK, halign="left"))
        notif_sw = Switch(active=True, size_hint_x=None, width=dp(80))
        notif_sw.bind(active=lambda _inst, val: setattr(app.notifications, "enabled", bool(val)))
        notif_row.add_widget(notif_sw)
        self.col.add_widget(notif_row)

        self.col.add_widget(
            Button(
                text="Manage Blocked Users",
                size_hint_y=None,
                height=dp(48),
                background_normal="",
                background_color=(0.94, 0.97, 0.95, 1),
                color=TEXT_DARK,
                on_release=lambda _x: self.open_blocked_popup(),
            )
        )

        self.col.add_widget(
            Button(
                text="Firebase Client Configuration",
                size_hint_y=None,
                height=dp(48),
                background_normal="",
                background_color=(0.94, 0.97, 0.95, 1),
                color=TEXT_DARK,
                on_release=lambda _x: self.open_firebase_config_popup(),
            )
        )

        self.col.add_widget(
            Button(
                text="Admin Panel (Authorized Admins Only)",
                size_hint_y=None,
                height=dp(48),
                background_normal="",
                background_color=PRIMARY_DARK,
                color=WHITE,
                on_release=lambda _x: setattr(app.sm, "current", "admin"),
            )
        )

        self.col.add_widget(
            Button(
                text="Sign Out",
                size_hint_y=None,
                height=dp(48),
                background_normal="",
                background_color=DANGER_RED,
                color=WHITE,
                bold=True,
                on_release=lambda _x: app.sign_out(),
            )
        )

    def open_blocked_popup(self) -> None:
        app = App.get_running_app()
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        list_box.bind(minimum_height=list_box.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(list_box)
        box.add_widget(scroll)
        popup = Popup(title="Blocked Accounts", content=box, size_hint=(0.9, 0.65))

        def on_loaded(ok: bool, data: Any) -> None:
            list_box.clear_widgets()
            blocked: Dict[str, Any] = data if ok and isinstance(data, dict) else {}
            if not blocked:
                list_box.add_widget(Label(text="No blocked users.", color=WHITE, size_hint_y=None, height=dp(44)))
                return
            for target_uid in blocked.keys():
                row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
                row.add_widget(Label(text=target_uid, color=WHITE))
                row.add_widget(
                    Button(
                        text="Unblock",
                        size_hint_x=None,
                        width=dp(90),
                        background_normal="",
                        background_color=ACCENT_GREEN,
                        color=(0.05, 0.15, 0.10, 1),
                        on_release=lambda _x, u=target_uid: (
                            app.db.unblock_user(app.auth.uid, u),
                            popup.dismiss(),
                        ),
                    )
                )
                list_box.add_widget(row)

        app.db.get_blocked_users(app.auth.uid, on_loaded)
        box.add_widget(Button(text="Close", size_hint_y=None, height=dp(44), on_release=lambda _x: popup.dismiss()))
        popup.open()

    def open_firebase_config_popup(self) -> None:
        app = App.get_running_app()
        cfg = app.config_obj
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(12))
        api_in = TextInput(text=cfg.api_key, hint_text="apiKey", multiline=False, size_hint_y=None, height=dp(40))
        db_in = TextInput(text=cfg.database_url, hint_text="databaseURL", multiline=False, size_hint_y=None, height=dp(40))
        proj_in = TextInput(text=cfg.project_id, hint_text="projectId", multiline=False, size_hint_y=None, height=dp(40))
        bucket_in = TextInput(text=cfg.storage_bucket, hint_text="storageBucket", multiline=False, size_hint_y=None, height=dp(40))
        auth_in = TextInput(text=cfg.auth_domain, hint_text="authDomain", multiline=False, size_hint_y=None, height=dp(40))
        for w in (api_in, db_in, proj_in, bucket_in, auth_in):
            box.add_widget(w)

        popup = Popup(title="Firebase Client Config", content=box, size_hint=(0.94, 0.72))

        def save_cfg(_x: Any) -> None:
            new_cfg = FirebaseConfig(
                api_key=api_in.text,
                auth_domain=auth_in.text,
                database_url=db_in.text,
                project_id=proj_in.text,
                storage_bucket=bucket_in.text,
                messaging_sender_id=cfg.messaging_sender_id,
                app_id=cfg.app_id,
                recaptcha_site_key=cfg.recaptcha_site_key,
                turn_server_url=cfg.turn_server_url,
                turn_username=cfg.turn_username,
                turn_credential=cfg.turn_credential,
            )
            save_firebase_config(new_cfg)
            app.reload_firebase_config()
            popup.dismiss()

        btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        btns.add_widget(Button(text="Cancel", on_release=lambda _x: popup.dismiss()))
        btns.add_widget(
            Button(
                text="Save Config",
                background_normal="",
                background_color=PRIMARY_TEAL,
                color=WHITE,
                on_release=save_cfg,
            )
        )
        box.add_widget(btns)
        popup.open()
