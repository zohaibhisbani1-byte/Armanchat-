"""ArmanChat Admin Panel — protected by Firebase Auth & Realtime Database rules.

Security Note:
Administrator privileges are NEVER hardcoded in the APK. Access requires signing
in with a Firebase account whose UID is registered under /admins/<uid>: true
or carries a custom claim `admin: true` set by the trusted admin_server.py script.
"""

from typing import Any, Dict, List

from kivy.app import App
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from database import format_timestamp


PRIMARY_DARK = (0.027, 0.369, 0.329, 1)
PRIMARY_TEAL = (0.071, 0.549, 0.494, 1)
ACCENT_GREEN = (0.145, 0.827, 0.400, 1)
TEXT_DARK = (0.08, 0.12, 0.10, 1)
TEXT_MUTED = (0.38, 0.44, 0.42, 1)
WHITE = (1, 1, 1, 1)
DANGER_RED = (0.86, 0.15, 0.15, 1)


class AdminPanelScreen(Screen):
    """Moderation dashboard: stats, user management, reports, and groups."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.current_tab: str = "stats"
        self.dashboard_data: Dict[str, Any] = {}
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
                width=dp(76),
                background_normal="",
                background_color=PRIMARY_DARK,
                color=WHITE,
                on_release=lambda _x: setattr(App.get_running_app().sm, "current", "home"),
            )
        )
        header.add_widget(Label(text="ArmanChat Admin", color=WHITE, bold=True, font_size="18sp"))
        header.add_widget(
            Button(
                text="Refresh",
                size_hint_x=None,
                width=dp(76),
                background_normal="",
                background_color=PRIMARY_TEAL,
                color=WHITE,
                on_release=lambda _x: self.verify_and_load(),
            )
        )
        root.add_widget(header)

        # Navigation tabs
        tabs = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4), padding=[dp(8), dp(4)])
        for key, label in (
            ("stats", "Stats"),
            ("users", "Users"),
            ("reports", "Reports"),
            ("groups", "Groups"),
        ):
            tabs.add_widget(
                Button(
                    text=label,
                    background_normal="",
                    background_color=PRIMARY_TEAL,
                    color=WHITE,
                    on_release=lambda _x, k=key: self._switch_tab(k),
                )
            )
        root.add_widget(tabs)

        self.status_lbl = Label(
            text="Verifying administrator authorization...",
            color=TEXT_MUTED,
            size_hint_y=None,
            height=dp(32),
            font_size="13sp",
        )
        root.add_widget(self.status_lbl)

        self.scroll = ScrollView()
        self.body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=dp(12))
        self.body.bind(minimum_height=self.body.setter("height"))
        self.scroll.add_widget(self.body)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def on_pre_enter(self, *_args: Any) -> None:
        self.verify_and_load()

    def _switch_tab(self, key: str) -> None:
        self.current_tab = key
        self._render_current_tab()

    def verify_and_load(self) -> None:
        app = App.get_running_app()
        self.body.clear_widgets()
        if not app.auth.is_authenticated:
            self.status_lbl.text = "Sign in first to access Admin Panel."
            return

        self.status_lbl.text = "Checking Firebase /admins authorization..."

        def on_checked(_ok: bool, is_admin: Any) -> None:
            if not is_admin:
                self.status_lbl.text = (
                    "Access denied. Add your UID under /admins/<uid>: true in Firebase Console."
                )
                self.body.clear_widgets()
                self.body.add_widget(
                    Label(
                        text=f"Your UID:\n{app.auth.uid}\n\nGrant admin access via Firebase Console or admin_server.py.",
                        color=DANGER_RED,
                        size_hint_y=None,
                        height=dp(100),
                        halign="center",
                    )
                )
                return

            self.status_lbl.text = "Admin verified. Loading ArmanChat metrics..."
            app.db.admin_fetch_dashboard(self._on_dashboard)

        app.db.check_is_admin(app.auth.uid, on_checked)

    def _on_dashboard(self, ok: bool, data: Any) -> None:
        if not ok or not isinstance(data, dict):
            self.status_lbl.text = str(data)
            return
        self.dashboard_data = data
        self.status_lbl.text = "Connected to Firebase Admin Data"
        self._render_current_tab()

    def _render_current_tab(self) -> None:
        self.body.clear_widgets()
        if not self.dashboard_data:
            return
        if self.current_tab == "stats":
            self._render_stats()
        elif self.current_tab == "users":
            self._render_users()
        elif self.current_tab == "reports":
            self._render_reports()
        elif self.current_tab == "groups":
            self._render_groups()

    def _render_stats(self) -> None:
        stats = self.dashboard_data.get("stats", {})
        cards = [
            ("Total Registered Users", stats.get("total_users", 0)),
            ("Currently Online", stats.get("online_users", 0)),
            ("Suspended / Blocked Users", stats.get("blocked_users", 0)),
            ("Active Groups", stats.get("total_groups", 0)),
            ("Open Abuse Reports", stats.get("open_reports", 0)),
        ]
        for label, value in cards:
            row = BoxLayout(size_hint_y=None, height=dp(60), padding=dp(12))
            with row.canvas.before:
                Color(0.95, 0.98, 0.96, 1)
                bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(10)])
            row.bind(pos=lambda i, _v, r=bg: setattr(r, "pos", i.pos))
            row.bind(size=lambda i, _v, r=bg: setattr(r, "size", i.size))
            row.add_widget(Label(text=label, color=TEXT_DARK, halign="left", bold=True))
            row.add_widget(
                Label(
                    text=str(value),
                    color=PRIMARY_DARK,
                    font_size="20sp",
                    bold=True,
                    size_hint_x=None,
                    width=dp(70),
                )
            )
            self.body.add_widget(row)

    def _render_users(self) -> None:
        app = App.get_running_app()
        users: List[Dict[str, Any]] = self.dashboard_data.get("users", [])
        if not users:
            self.body.add_widget(Label(text="No users found.", color=TEXT_MUTED, size_hint_y=None, height=dp(44)))
            return
        for u in users:
            uid = u.get("uid", "")
            blocked = bool(u.get("blocked"))
            row = BoxLayout(size_hint_y=None, height=dp(64), padding=dp(8), spacing=dp(8))
            with row.canvas.before:
                Color(0.96, 0.98, 0.97, 1)
                bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(8)])
            row.bind(pos=lambda i, _v, r=bg: setattr(r, "pos", i.pos))
            row.bind(size=lambda i, _v, r=bg: setattr(r, "size", i.size))

            info = BoxLayout(orientation="vertical")
            info.add_widget(
                Label(
                    text=f"{u.get('name', 'Unnamed')} ({'BLOCKED' if blocked else 'Active'})",
                    color=DANGER_RED if blocked else TEXT_DARK,
                    bold=True,
                    font_size="14sp",
                    halign="left",
                    text_size=(dp(190), None),
                )
            )
            info.add_widget(
                Label(
                    text=f"{u.get('phone') or u.get('email') or uid}",
                    color=TEXT_MUTED,
                    font_size="11sp",
                    halign="left",
                    text_size=(dp(190), None),
                )
            )
            row.add_widget(info)
            row.add_widget(
                Button(
                    text="Unblock" if blocked else "Block",
                    size_hint_x=None,
                    width=dp(82),
                    background_normal="",
                    background_color=ACCENT_GREEN if blocked else DANGER_RED,
                    color=(0.05, 0.15, 0.10, 1) if blocked else WHITE,
                    on_release=lambda _x, t_uid=uid, b=not blocked: app.db.admin_set_user_blocked(
                        t_uid,
                        b,
                        callback=lambda _ok, _r: self.verify_and_load(),
                    ),
                )
            )
            self.body.add_widget(row)

    def _render_reports(self) -> None:
        app = App.get_running_app()
        reports: List[Dict[str, Any]] = self.dashboard_data.get("reports", [])
        if not reports:
            self.body.add_widget(Label(text="No reported accounts.", color=TEXT_MUTED, size_hint_y=None, height=dp(44)))
            return
        for rep in reports:
            rid = rep.get("report_id", "")
            reported_uid = rep.get("reported_uid", "")
            row = BoxLayout(size_hint_y=None, height=dp(84), padding=dp(8), spacing=dp(6))
            with row.canvas.before:
                Color(0.99, 0.96, 0.96, 1)
                bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(8)])
            row.bind(pos=lambda i, _v, r=bg: setattr(r, "pos", i.pos))
            row.bind(size=lambda i, _v, r=bg: setattr(r, "size", i.size))

            info = BoxLayout(orientation="vertical")
            info.add_widget(
                Label(
                    text=f"Reported: {reported_uid[:16]} · {rep.get('status', 'open').upper()}",
                    color=TEXT_DARK,
                    bold=True,
                    font_size="13sp",
                    halign="left",
                    text_size=(dp(170), None),
                )
            )
            info.add_widget(
                Label(
                    text=f"Reason: {rep.get('reason', '')} ({format_timestamp(rep.get('created_at'))})",
                    color=TEXT_MUTED,
                    font_size="11sp",
                    halign="left",
                    text_size=(dp(170), None),
                )
            )
            row.add_widget(info)
            row.add_widget(
                Button(
                    text="Block",
                    size_hint_x=None,
                    width=dp(64),
                    background_normal="",
                    background_color=DANGER_RED,
                    color=WHITE,
                    on_release=lambda _x, u=reported_uid, r_id=rid: (
                        app.db.admin_set_user_blocked(u, True),
                        app.db.admin_resolve_report(r_id, "actioned", lambda _o, _res: self.verify_and_load()),
                    ),
                )
            )
            row.add_widget(
                Button(
                    text="Dismiss",
                    size_hint_x=None,
                    width=dp(68),
                    background_normal="",
                    background_color=PRIMARY_TEAL,
                    color=WHITE,
                    on_release=lambda _x, r_id=rid: app.db.admin_resolve_report(
                        r_id,
                        "dismissed",
                        lambda _o, _res: self.verify_and_load(),
                    ),
                )
            )
            self.body.add_widget(row)

    def _render_groups(self) -> None:
        app = App.get_running_app()
        groups: List[Dict[str, Any]] = self.dashboard_data.get("groups", [])
        if not groups:
            self.body.add_widget(Label(text="No groups found.", color=TEXT_MUTED, size_hint_y=None, height=dp(44)))
            return
        for grp in groups:
            gid = grp.get("group_id", "")
            row = BoxLayout(size_hint_y=None, height=dp(62), padding=dp(8), spacing=dp(8))
            with row.canvas.before:
                Color(0.96, 0.98, 0.97, 1)
                bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(8)])
            row.bind(pos=lambda i, _v, r=bg: setattr(r, "pos", i.pos))
            row.bind(size=lambda i, _v, r=bg: setattr(r, "size", i.size))

            members_count = len(grp.get("members") or {})
            row.add_widget(
                Label(
                    text=f"{grp.get('name', 'Group')} ({members_count} members)",
                    color=TEXT_DARK,
                    bold=True,
                    halign="left",
                    text_size=(dp(200), None),
                )
            )
            row.add_widget(
                Button(
                    text="Delete",
                    size_hint_x=None,
                    width=dp(76),
                    background_normal="",
                    background_color=DANGER_RED,
                    color=WHITE,
                    on_release=lambda _x, g=gid: app.db.admin_delete_group(
                        g,
                        callback=lambda _o, _r: self.verify_and_load(),
                    ),
                )
            )
            self.body.add_widget(row)
