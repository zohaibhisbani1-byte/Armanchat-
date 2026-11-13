"""Messaging screens for ArmanChat: Chats, Contacts, Groups, and ChatRoom."""

import os
import webbrowser
from typing import Any, Dict, List, Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from database import format_timestamp


PRIMARY_DARK = (0.027, 0.369, 0.329, 1)    # #075E54
PRIMARY_TEAL = (0.071, 0.549, 0.494, 1)    # #128C7E
ACCENT_GREEN = (0.145, 0.827, 0.400, 1)    # #25D366
OUTGOING_BG = (0.863, 0.973, 0.776, 1)     # #DCF8C6
INCOMING_BG = (1, 1, 1, 1)                 # #FFFFFF
WALLPAPER_BG = (0.925, 0.898, 0.867, 1)    # #ECE5DD
TEXT_DARK = (0.08, 0.12, 0.10, 1)
TEXT_MUTED = (0.38, 0.44, 0.42, 1)
WHITE = (1, 1, 1, 1)
READ_BLUE = (0.18, 0.56, 0.92, 1)
DANGER_RED = (0.86, 0.15, 0.15, 1)

EMOJI_LIST = [
    "😀", "😂", "😍", "🥳", "😎", "🙏",
    "👍", "❤️", "🔥", "🎉", "😢", "🤝",
    "👏", "💯", "✨", "📞", "📷", "📎",
]


def open_file_picker(on_selected: Any, filters: Optional[List[str]] = None) -> None:
    """Open native Android/desktop file picker, falling back to Kivy FileChooser."""
    try:
        from plyer import filechooser

        selection = filechooser.open_file(filters=filters or ["*"])
        if selection:
            on_selected(selection[0])
            return
    except Exception:
        pass

    # Built-in fallback popup for environments where plyer native chooser fails
    box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
    start_path = "/sdcard" if os.path.exists("/sdcard") else os.path.expanduser("~")
    chooser = FileChooserIconView(path=start_path)
    box.add_widget(chooser)
    btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
    popup = Popup(title="Select File", content=box, size_hint=(0.94, 0.82))

    def confirm(_btn: Any) -> None:
        if chooser.selection:
            popup.dismiss()
            on_selected(chooser.selection[0])

    btns.add_widget(Button(text="Cancel", on_release=lambda _x: popup.dismiss()))
    btns.add_widget(
        Button(
            text="Select",
            background_normal="",
            background_color=PRIMARY_TEAL,
            color=WHITE,
            on_release=confirm,
        )
    )
    box.add_widget(btns)
    popup.open()


class ChatsView(BoxLayout):
    """Chats list with live search, unread indicator, and tap-to-open room."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(10), **kwargs)
        self.all_chats: List[Dict[str, Any]] = []

        search_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.search_input = TextInput(
            hint_text="Search conversations...",
            multiline=False,
            size_hint_x=0.78,
        )
        self.search_input.bind(text=lambda _i, _v: self._render_list())
        search_row.add_widget(self.search_input)
        refresh_btn = Button(
            text="Sync",
            size_hint_x=0.22,
            background_normal="",
            background_color=PRIMARY_TEAL,
            color=WHITE,
            on_release=lambda _x: self.load_chats(),
        )
        search_row.add_widget(refresh_btn)
        self.add_widget(search_row)

        self.scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        self.add_widget(self.scroll)

    def load_chats(self) -> None:
        app = App.get_running_app()
        if not app.auth.uid:
            return

        def on_loaded(ok: bool, data: Any) -> None:
            if ok and isinstance(data, list):
                self.all_chats = data
                self._render_list()

        app.db.get_user_chats(app.auth.uid, on_loaded)

    def _render_list(self) -> None:
        self.list_box.clear_widgets()
        q = self.search_input.text.strip().lower()
        filtered = [
            c
            for c in self.all_chats
            if not q
            or q in (c.get("title") or "").lower()
            or q in (c.get("last_message") or "").lower()
        ]
        if not filtered:
            self.list_box.add_widget(
                Label(
                    text="No conversations yet. Go to Contacts to start chatting.",
                    color=TEXT_MUTED,
                    size_hint_y=None,
                    height=dp(64),
                )
            )
            return

        app = App.get_running_app()
        for chat in filtered:
            row = BoxLayout(size_hint_y=None, height=dp(68), padding=dp(8), spacing=dp(10))
            with row.canvas.before:
                Color(0.97, 0.99, 0.98, 1)
                bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(10)])
            row.bind(pos=lambda inst, _v, r=bg: setattr(r, "pos", inst.pos))
            row.bind(size=lambda inst, _v, r=bg: setattr(r, "size", inst.size))

            info = BoxLayout(orientation="vertical", spacing=dp(2))
            title = chat.get("title") or "ArmanChat User"
            last_msg = chat.get("last_message") or "Tap to open chat"
            unread = int(chat.get("unread", 0))
            ts_str = format_timestamp(chat.get("updated_at"))

            top_line = BoxLayout(size_hint_y=None, height=dp(24))
            top_line.add_widget(
                Label(
                    text=title,
                    color=TEXT_DARK,
                    bold=True,
                    font_size="15sp",
                    halign="left",
                    text_size=(dp(190), None),
                )
            )
            top_line.add_widget(
                Label(
                    text=f"{ts_str}  ({unread} new)" if unread else ts_str,
                    color=PRIMARY_TEAL if unread else TEXT_MUTED,
                    font_size="11sp",
                    halign="right",
                    size_hint_x=None,
                    width=dp(110),
                )
            )
            info.add_widget(top_line)
            info.add_widget(
                Label(
                    text=last_msg[:52],
                    color=TEXT_MUTED,
                    font_size="13sp",
                    halign="left",
                    text_size=(dp(240), None),
                )
            )
            row.add_widget(info)

            open_btn = Button(
                text="Open",
                size_hint_x=None,
                width=dp(68),
                background_normal="",
                background_color=PRIMARY_DARK,
                color=WHITE,
                on_release=lambda _x, c=chat: app.open_chat_room(
                    room_id=c["chat_id"],
                    title=c.get("title", "Chat"),
                    is_group=False,
                    peer_uid=c.get("peer_uid", ""),
                ),
            )
            row.add_widget(open_btn)
            self.list_box.add_widget(row)


class ContactsView(BoxLayout):
    """Directory of registered ArmanChat users with Chat, Audio & Video call actions."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(10), **kwargs)
        self.users: List[Dict[str, Any]] = []

        bar = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.search_input = TextInput(
            hint_text="Search contacts by name or phone...",
            multiline=False,
            size_hint_x=0.78,
        )
        self.search_input.bind(text=lambda _i, _v: self._render())
        bar.add_widget(self.search_input)
        bar.add_widget(
            Button(
                text="Sync",
                size_hint_x=0.22,
                background_normal="",
                background_color=PRIMARY_TEAL,
                color=WHITE,
                on_release=lambda _x: self.load_contacts(),
            )
        )
        self.add_widget(bar)

        self.scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        self.add_widget(self.scroll)

    def load_contacts(self) -> None:
        app = App.get_running_app()

        def on_users(ok: bool, data: Any) -> None:
            if ok and isinstance(data, list):
                self.users = [u for u in data if u.get("uid") != app.auth.uid]
                self._render()

        app.db.get_all_users(on_users)

    def _render(self) -> None:
        self.list_box.clear_widgets()
        q = self.search_input.text.strip().lower()
        filtered = [
            u
            for u in self.users
            if not q
            or q in (u.get("name") or "").lower()
            or q in (u.get("phone") or "").lower()
        ]
        if not filtered:
            self.list_box.add_widget(
                Label(
                    text="No contacts found.",
                    color=TEXT_MUTED,
                    size_hint_y=None,
                    height=dp(60),
                )
            )
            return

        app = App.get_running_app()
        for user in filtered:
            row = BoxLayout(size_hint_y=None, height=dp(68), padding=dp(8), spacing=dp(6))
            with row.canvas.before:
                Color(0.97, 0.99, 0.98, 1)
                bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(10)])
            row.bind(pos=lambda inst, _v, r=bg: setattr(r, "pos", inst.pos))
            row.bind(size=lambda inst, _v, r=bg: setattr(r, "size", inst.size))

            info = BoxLayout(orientation="vertical")
            name = user.get("name") or user.get("phone") or "User"
            status_txt = "Online" if user.get("online") else f"Last seen {format_timestamp(user.get('last_seen')) or 'recently'}"
            if user.get("blocked"):
                status_txt = "Account suspended"
            info.add_widget(
                Label(
                    text=name,
                    color=TEXT_DARK,
                    bold=True,
                    font_size="15sp",
                    halign="left",
                    text_size=(dp(160), None),
                )
            )
            info.add_widget(
                Label(
                    text=f"{user.get('phone', '')} · {status_txt}",
                    color=PRIMARY_TEAL if user.get("online") else TEXT_MUTED,
                    font_size="11sp",
                    halign="left",
                    text_size=(dp(170), None),
                )
            )
            row.add_widget(info)

            chat_btn = Button(
                text="Chat",
                size_hint_x=None,
                width=dp(58),
                background_normal="",
                background_color=PRIMARY_DARK,
                color=WHITE,
                on_release=lambda _x, u=user: app.start_direct_chat(u),
            )
            voice_btn = Button(
                text="Call",
                size_hint_x=None,
                width=dp(54),
                background_normal="",
                background_color=ACCENT_GREEN,
                color=(0.05, 0.15, 0.10, 1),
                on_release=lambda _x, u=user: app.start_call(
                    u["uid"], u.get("name", "Contact"), "audio"
                ),
            )
            video_btn = Button(
                text="Vid",
                size_hint_x=None,
                width=dp(50),
                background_normal="",
                background_color=PRIMARY_TEAL,
                color=WHITE,
                on_release=lambda _x, u=user: app.start_call(
                    u["uid"], u.get("name", "Contact"), "video"
                ),
            )
            row.add_widget(chat_btn)
            row.add_widget(voice_btn)
            row.add_widget(video_btn)
            self.list_box.add_widget(row)


class GroupsView(BoxLayout):
    """Group chat list and group creation modal."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(10), **kwargs)
        top = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        top.add_widget(
            Label(
                text="Your Groups",
                color=TEXT_DARK,
                font_size="17sp",
                bold=True,
                halign="left",
            )
        )
        new_btn = Button(
            text="+ New Group",
            size_hint_x=None,
            width=dp(120),
            background_normal="",
            background_color=ACCENT_GREEN,
            color=(0.05, 0.15, 0.10, 1),
            bold=True,
            on_release=lambda _x: self.open_create_group_popup(),
        )
        top.add_widget(new_btn)
        self.add_widget(top)

        self.scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        self.add_widget(self.scroll)

    def load_groups(self) -> None:
        app = App.get_running_app()
        if not app.auth.uid:
            return
        app.db.get_user_groups(app.auth.uid, self._render_groups)

    def _render_groups(self, ok: bool, data: Any) -> None:
        self.list_box.clear_widgets()
        groups: List[Dict[str, Any]] = data if ok and isinstance(data, list) else []
        if not groups:
            self.list_box.add_widget(
                Label(
                    text="No groups yet. Tap '+ New Group' to create one.",
                    color=TEXT_MUTED,
                    size_hint_y=None,
                    height=dp(60),
                )
            )
            return

        app = App.get_running_app()
        for grp in groups:
            row = BoxLayout(size_hint_y=None, height=dp(64), padding=dp(8), spacing=dp(8))
            with row.canvas.before:
                Color(0.97, 0.99, 0.98, 1)
                bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(10)])
            row.bind(pos=lambda inst, _v, r=bg: setattr(r, "pos", inst.pos))
            row.bind(size=lambda inst, _v, r=bg: setattr(r, "size", inst.size))

            info = BoxLayout(orientation="vertical")
            info.add_widget(
                Label(
                    text=grp.get("name", "Group"),
                    color=TEXT_DARK,
                    bold=True,
                    font_size="15sp",
                    halign="left",
                    text_size=(dp(210), None),
                )
            )
            info.add_widget(
                Label(
                    text=grp.get("last_message", ""),
                    color=TEXT_MUTED,
                    font_size="12sp",
                    halign="left",
                    text_size=(dp(210), None),
                )
            )
            row.add_widget(info)
            row.add_widget(
                Button(
                    text="Open",
                    size_hint_x=None,
                    width=dp(72),
                    background_normal="",
                    background_color=PRIMARY_DARK,
                    color=WHITE,
                    on_release=lambda _x, g=grp: app.open_chat_room(
                        room_id=g["group_id"],
                        title=g.get("name", "Group"),
                        is_group=True,
                    ),
                )
            )
            self.list_box.add_widget(row)

    def open_create_group_popup(self) -> None:
        app = App.get_running_app()
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        name_input = TextInput(hint_text="Group name (e.g. Family)", multiline=False, size_hint_y=None, height=dp(44))
        desc_input = TextInput(hint_text="Group description", multiline=False, size_hint_y=None, height=dp(44))
        content.add_widget(name_input)
        content.add_widget(desc_input)
        content.add_widget(Label(text="Select Members:", size_hint_y=None, height=dp(26), color=WHITE))

        selected_uids: set = set()
        members_scroll = ScrollView()
        members_list = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        members_list.bind(minimum_height=members_list.setter("height"))
        members_scroll.add_widget(members_list)
        content.add_widget(members_scroll)

        status_lbl = Label(text="Loading contacts...", size_hint_y=None, height=dp(24), color=MUTED_LIGHT)
        content.add_widget(status_lbl)

        popup = Popup(title="Create ArmanChat Group", content=content, size_hint=(0.92, 0.85))

        def on_users(ok: bool, users: Any) -> None:
            members_list.clear_widgets()
            if not ok or not isinstance(users, list):
                status_lbl.text = "Could not load contacts."
                return
            others = [u for u in users if u.get("uid") != app.auth.uid]
            status_lbl.text = f"{len(others)} contacts available"
            for u in others:
                line = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
                cb = CheckBox(size_hint_x=None, width=dp(36))

                def on_check(_inst: Any, active: bool, target_uid: str = u["uid"]) -> None:
                    if active:
                        selected_uids.add(target_uid)
                    else:
                        selected_uids.discard(target_uid)

                cb.bind(active=on_check)
                line.add_widget(cb)
                line.add_widget(Label(text=u.get("name") or u.get("phone") or "User", color=WHITE, halign="left"))
                members_list.add_widget(line)

        app.db.get_all_users(on_users)

        btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        btns.add_widget(Button(text="Cancel", on_release=lambda _x: popup.dismiss()))

        def create_action(_x: Any) -> None:
            gname = name_input.text.strip()
            if not gname:
                status_lbl.text = "Enter a group name."
                return
            app.db.create_group(
                app.auth.uid,
                gname,
                list(selected_uids),
                description=desc_input.text,
                callback=lambda ok, res: (
                    popup.dismiss() if ok else setattr(status_lbl, "text", str(res)),
                    self.load_groups() if ok else None,
                ),
            )

        btns.add_widget(
            Button(
                text="Create",
                background_normal="",
                background_color=ACCENT_GREEN,
                color=(0.05, 0.15, 0.10, 1),
                bold=True,
                on_release=create_action,
            )
        )
        content.add_widget(btns)
        popup.open()


MUTED_LIGHT = (0.85, 0.9, 0.88, 1)


class ChatRoomScreen(Screen):
    """Full 1-to-1 and Group chat room with emoji, media, read receipts, typing, delete, block/report."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.room_id: str = ""
        self.room_title: str = "Chat"
        self.is_group: bool = False
        self.peer_uid: str = ""
        self.member_uids: List[str] = []
        self.is_blocked: bool = False
        self._poll_ev = None
        self._typing_clear_ev = None
        self._last_msg_signature: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*WALLPAPER_BG)
            self._wall_bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[0])
        root.bind(pos=lambda i, _v: setattr(self._wall_bg, "pos", i.pos))
        root.bind(size=lambda i, _v: setattr(self._wall_bg, "size", i.size))

        # Top WhatsApp-inspired green header
        header = BoxLayout(size_hint_y=None, height=dp(60), padding=[dp(8), dp(6)], spacing=dp(6))
        with header.canvas.before:
            Color(*PRIMARY_DARK)
            self._hdr_bg = RoundedRectangle(pos=header.pos, size=header.size, radius=[0])
        header.bind(pos=lambda i, _v: setattr(self._hdr_bg, "pos", i.pos))
        header.bind(size=lambda i, _v: setattr(self._hdr_bg, "size", i.size))

        header.add_widget(
            Button(
                text="<",
                size_hint_x=None,
                width=dp(42),
                background_normal="",
                background_color=PRIMARY_DARK,
                color=WHITE,
                bold=True,
                font_size="18sp",
                on_release=lambda _x: self.go_back(),
            )
        )

        title_col = BoxLayout(orientation="vertical")
        self.title_lbl = Label(
            text="Chat",
            color=WHITE,
            bold=True,
            font_size="16sp",
            halign="left",
            text_size=(dp(160), None),
        )
        self.subtitle_lbl = Label(
            text="Connecting...",
            color=MUTED_LIGHT,
            font_size="11sp",
            halign="left",
            text_size=(dp(160), None),
        )
        title_col.add_widget(self.title_lbl)
        title_col.add_widget(self.subtitle_lbl)
        header.add_widget(title_col)

        self.audio_call_btn = Button(
            text="Call",
            size_hint_x=None,
            width=dp(50),
            background_normal="",
            background_color=PRIMARY_TEAL,
            color=WHITE,
            on_release=lambda _x: self._initiate_call("audio"),
        )
        self.video_call_btn = Button(
            text="Vid",
            size_hint_x=None,
            width=dp(46),
            background_normal="",
            background_color=PRIMARY_TEAL,
            color=WHITE,
            on_release=lambda _x: self._initiate_call("video"),
        )
        self.menu_btn = Button(
            text="...",
            size_hint_x=None,
            width=dp(40),
            background_normal="",
            background_color=PRIMARY_DARK,
            color=WHITE,
            bold=True,
            on_release=lambda _x: self.open_room_menu(),
        )
        header.add_widget(self.audio_call_btn)
        header.add_widget(self.video_call_btn)
        header.add_widget(self.menu_btn)
        root.add_widget(header)

        # Scrollable messages canvas
        self.scroll = ScrollView()
        self.msg_container = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=[dp(10), dp(12)],
        )
        self.msg_container.bind(minimum_height=self.msg_container.setter("height"))
        self.scroll.add_widget(self.msg_container)
        root.add_widget(self.scroll)

        # Composer bar
        composer = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(8), dp(6)], spacing=dp(6))
        with composer.canvas.before:
            Color(0.96, 0.97, 0.96, 1)
            self._comp_bg = RoundedRectangle(pos=composer.pos, size=composer.size, radius=[0])
        composer.bind(pos=lambda i, _v: setattr(self._comp_bg, "pos", i.pos))
        composer.bind(size=lambda i, _v: setattr(self._comp_bg, "size", i.size))

        composer.add_widget(
            Button(
                text=":)",
                size_hint_x=None,
                width=dp(40),
                background_normal="",
                background_color=(0.88, 0.92, 0.90, 1),
                color=TEXT_DARK,
                on_release=lambda _x: self.open_emoji_picker(),
            )
        )
        self.msg_input = TextInput(
            hint_text="Message",
            multiline=False,
        )
        self.msg_input.bind(text=self._on_typing_change)
        self.msg_input.bind(on_text_validate=lambda _x: self.send_text_message())
        composer.add_widget(self.msg_input)

        composer.add_widget(
            Button(
                text="Img",
                size_hint_x=None,
                width=dp(44),
                background_normal="",
                background_color=(0.88, 0.92, 0.90, 1),
                color=TEXT_DARK,
                on_release=lambda _x: self.pick_and_send_media("image"),
            )
        )
        composer.add_widget(
            Button(
                text="File",
                size_hint_x=None,
                width=dp(44),
                background_normal="",
                background_color=(0.88, 0.92, 0.90, 1),
                color=TEXT_DARK,
                on_release=lambda _x: self.pick_and_send_media("file"),
            )
        )
        composer.add_widget(
            Button(
                text="Send",
                size_hint_x=None,
                width=dp(62),
                background_normal="",
                background_color=PRIMARY_TEAL,
                color=WHITE,
                bold=True,
                on_release=lambda _x: self.send_text_message(),
            )
        )
        root.add_widget(composer)
        self.add_widget(root)

    def load_room(
        self,
        room_id: str,
        title: str,
        is_group: bool = False,
        peer_uid: str = "",
    ) -> None:
        self.room_id = room_id
        self.room_title = title
        self.is_group = is_group
        self.peer_uid = peer_uid
        self.member_uids = []
        self._last_msg_signature = ""
        self.title_lbl.text = title
        self.subtitle_lbl.text = "Group chat" if is_group else "Checking status..."
        self.audio_call_btn.disabled = is_group
        self.video_call_btn.disabled = is_group
        self.audio_call_btn.opacity = 0 if is_group else 1
        self.video_call_btn.opacity = 0 if is_group else 1
        self.msg_container.clear_widgets()

        app = App.get_running_app()
        if is_group:
            app.db.get_group_details(
                room_id,
                lambda ok, g: self._set_group_meta(g) if ok and isinstance(g, dict) else None,
            )
        elif peer_uid:
            app.db.get_blocked_users(
                app.auth.uid,
                lambda ok, b: setattr(self, "is_blocked", bool(ok and isinstance(b, dict) and peer_uid in b)),
            )

        self.refresh_room()
        self._start_polling()

    def _set_group_meta(self, group_data: Dict[str, Any]) -> None:
        members = group_data.get("members") or {}
        self.member_uids = list(members.keys())
        self.subtitle_lbl.text = f"{len(self.member_uids)} members"

    def go_back(self) -> None:
        self._stop_polling()
        app = App.get_running_app()
        app.db.set_typing(self.room_id, app.auth.uid, False)
        app.sm.current = "home"
        app.refresh_home_tabs()

    def _start_polling(self) -> None:
        self._stop_polling()
        self._poll_ev = Clock.schedule_interval(lambda _dt: self.refresh_room(), 2.5)

    def _stop_polling(self) -> None:
        if self._poll_ev is not None:
            self._poll_ev.cancel()
            self._poll_ev = None

    def refresh_room(self) -> None:
        app = App.get_running_app()
        if not self.room_id:
            return

        # 1. Messages
        app.db.get_messages(self.room_id, is_group=self.is_group, callback=self._on_messages)

        # 2. Typing indicator
        def on_typing(ok: bool, active_uids: Any) -> None:
            if ok and isinstance(active_uids, list) and active_uids:
                self.subtitle_lbl.text = "typing..."
            elif not self.is_group and self.peer_uid:
                app.db.get_user_profile(
                    self.peer_uid,
                    lambda ok_p, p: self._update_peer_status(p) if ok_p and isinstance(p, dict) else None,
                )
            elif self.is_group:
                self.subtitle_lbl.text = f"{len(self.member_uids)} members"

        app.db.get_typing_users(self.room_id, app.auth.uid, on_typing)

    def _update_peer_status(self, peer: Dict[str, Any]) -> None:
        if peer.get("online"):
            self.subtitle_lbl.text = "online"
        else:
            ts = format_timestamp(peer.get("last_seen"))
            self.subtitle_lbl.text = f"last seen {ts}" if ts else "offline"

    def _on_messages(self, ok: bool, data: Any) -> None:
        if not ok or not isinstance(data, list):
            return
        app = App.get_running_app()
        sig = "|".join(
            f"{m.get('message_id')}:{m.get('status')}:{m.get('deleted')}" for m in data
        )
        if sig == self._last_msg_signature:
            return
        self._last_msg_signature = sig
        app.db.mark_messages_read(self.room_id, app.auth.uid, data, is_group=self.is_group)

        self.msg_container.clear_widgets()
        for msg in data:
            self.msg_container.add_widget(self._build_bubble(msg))

        Clock.schedule_once(lambda _dt: setattr(self.scroll, "scroll_y", 0), 0.05)

    def _build_bubble(self, msg: Dict[str, Any]) -> BoxLayout:
        app = App.get_running_app()
        is_mine = msg.get("sender_id") == app.auth.uid
        is_deleted = bool(msg.get("deleted"))

        wrapper = BoxLayout(size_hint_y=None, padding=[dp(40) if is_mine else 0, 0, 0 if is_mine else dp(40), 0])
        bubble = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(10), spacing=dp(4))

        bg_color = OUTGOING_BG if is_mine else INCOMING_BG
        with bubble.canvas.before:
            Color(*bg_color)
            rect = RoundedRectangle(pos=bubble.pos, size=bubble.size, radius=[dp(12)])
        bubble.bind(pos=lambda inst, _v, r=rect: setattr(r, "pos", inst.pos))
        bubble.bind(size=lambda inst, _v, r=rect: setattr(r, "size", inst.size))

        height_acc = dp(20)
        if self.is_group and not is_mine:
            sender_lbl = Label(
                text=msg.get("sender_name", "Member"),
                color=PRIMARY_DARK,
                bold=True,
                font_size="12sp",
                size_hint_y=None,
                height=dp(18),
                halign="left",
                text_size=(dp(230), None),
            )
            bubble.add_widget(sender_lbl)
            height_acc += dp(22)

        msg_type = msg.get("type", "text")
        if msg_type == "image" and msg.get("media_url") and not is_deleted:
            img = AsyncImage(
                source=msg["media_url"],
                size_hint_y=None,
                height=dp(150),
                allow_stretch=True,
            )
            bubble.add_widget(img)
            height_acc += dp(156)

        if msg_type == "file" and msg.get("media_url") and not is_deleted:
            fname = msg.get("file_name") or "Attachment"
            file_btn = Button(
                text=f"Download: {fname}",
                size_hint_y=None,
                height=dp(36),
                background_normal="",
                background_color=PRIMARY_TEAL,
                color=WHITE,
                on_release=lambda _x, u=msg["media_url"]: webbrowser.open(u),
            )
            bubble.add_widget(file_btn)
            height_acc += dp(42)

        body_text = msg.get("text", "")
        if body_text:
            body_lbl = Label(
                text=body_text,
                color=TEXT_MUTED if is_deleted else TEXT_DARK,
                italic=is_deleted,
                font_size="14sp",
                size_hint_y=None,
                halign="left",
                valign="top",
                text_size=(dp(230), None),
            )
            body_lbl.bind(texture_size=lambda inst, sz: setattr(inst, "height", sz[1] + dp(4)))
            bubble.add_widget(body_lbl)
            est_lines = max(1, (len(body_text) // 28) + 1)
            height_acc += dp(22 * est_lines)

        # Footer: timestamp + sent/read ticks + optional delete button for own messages
        footer = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(6))
        ts_str = format_timestamp(msg.get("timestamp"))
        ticks = ""
        tick_color = TEXT_MUTED
        if is_mine and not is_deleted:
            read_by = msg.get("read_by") or {}
            others_read = any(k != app.auth.uid and v for k, v in read_by.items())
            if others_read or msg.get("status") == "read":
                ticks = "✓✓"
                tick_color = READ_BLUE
            else:
                ticks = "✓"
        footer.add_widget(
            Label(
                text=ts_str,
                color=TEXT_MUTED,
                font_size="10sp",
                halign="right",
            )
        )
        if ticks:
            footer.add_widget(
                Label(
                    text=ticks,
                    color=tick_color,
                    bold=True,
                    font_size="11sp",
                    size_hint_x=None,
                    width=dp(24),
                )
            )
        if is_mine and not is_deleted:
            footer.add_widget(
                Button(
                    text="Del",
                    size_hint_x=None,
                    width=dp(36),
                    font_size="10sp",
                    background_normal="",
                    background_color=(0.9, 0.85, 0.85, 1),
                    color=DANGER_RED,
                    on_release=lambda _x, mid=msg.get("message_id", ""): self._delete_message(mid),
                )
            )
        bubble.add_widget(footer)
        height_acc += dp(24)

        bubble.height = max(dp(56), height_acc)
        wrapper.height = bubble.height
        wrapper.add_widget(bubble)
        return wrapper

    def _delete_message(self, message_id: str) -> None:
        if not message_id:
            return
        app = App.get_running_app()
        app.db.delete_message(
            self.room_id,
            message_id,
            is_group=self.is_group,
            callback=lambda ok, _r: self.refresh_room() if ok else None,
        )

    def _on_typing_change(self, _instance: Any, value: str) -> None:
        app = App.get_running_app()
        if not self.room_id or not app.auth.uid:
            return
        is_typing = bool(value.strip())
        app.db.set_typing(self.room_id, app.auth.uid, is_typing)
        if self._typing_clear_ev is not None:
            self._typing_clear_ev.cancel()
        if is_typing:
            self._typing_clear_ev = Clock.schedule_once(
                lambda _dt: app.db.set_typing(self.room_id, app.auth.uid, False),
                4.0,
            )

    def send_text_message(self) -> None:
        text = self.msg_input.text.strip()
        if not text:
            return
        if self.is_blocked:
            self.subtitle_lbl.text = "Unblock user to send messages"
            return
        app = App.get_running_app()
        self.msg_input.text = ""
        app.db.set_typing(self.room_id, app.auth.uid, False)
        app.db.send_message(
            room_id=self.room_id,
            sender_uid=app.auth.uid,
            sender_name=app.current_profile.get("name", "User"),
            text=text,
            msg_type="text",
            is_group=self.is_group,
            peer_uid=self.peer_uid or None,
            member_uids=self.member_uids,
            callback=lambda ok, _res: self.refresh_room() if ok else None,
        )

    def pick_and_send_media(self, kind: str) -> None:
        filters = ["*.png", "*.jpg", "*.jpeg"] if kind == "image" else ["*"]

        def on_file(path: str) -> None:
            app = App.get_running_app()
            self.subtitle_lbl.text = "Uploading..."
            app.db.upload_file(
                path,
                f"chat_media/{self.room_id}",
                callback=lambda ok, res: self._after_upload(ok, res, kind),
            )

        open_file_picker(on_file, filters=filters)

    def _after_upload(self, ok: bool, res: Any, kind: str) -> None:
        if not ok or not isinstance(res, dict):
            self.subtitle_lbl.text = str(res)
            return
        app = App.get_running_app()
        app.db.send_message(
            room_id=self.room_id,
            sender_uid=app.auth.uid,
            sender_name=app.current_profile.get("name", "User"),
            text="" if kind == "image" else res.get("file_name", "Attachment"),
            msg_type=kind,
            media_url=res.get("url", ""),
            file_name=res.get("file_name", ""),
            is_group=self.is_group,
            peer_uid=self.peer_uid or None,
            member_uids=self.member_uids,
            callback=lambda ok_s, _r: self.refresh_room() if ok_s else None,
        )

    def open_emoji_picker(self) -> None:
        grid = GridLayout(cols=6, spacing=dp(6), padding=dp(10))
        popup = Popup(title="Insert Emoji", content=grid, size_hint=(0.88, 0.42))
        for em in EMOJI_LIST:
            btn = Button(
                text=em,
                font_size="22sp",
                on_release=lambda _x, e=em: (
                    setattr(self.msg_input, "text", self.msg_input.text + e),
                    popup.dismiss(),
                ),
            )
            grid.add_widget(btn)
        popup.open()

    def _initiate_call(self, call_type: str) -> None:
        if self.is_group or not self.peer_uid:
            return
        app = App.get_running_app()
        app.start_call(self.peer_uid, self.room_title, call_type)

    def open_room_menu(self) -> None:
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
        popup = Popup(title="Conversation Options", content=box, size_hint=(0.84, 0.45))
        app = App.get_running_app()

        if not self.is_group and self.peer_uid:
            block_label = "Unblock User" if self.is_blocked else "Block User"

            def toggle_block(_x: Any) -> None:
                if self.is_blocked:
                    app.db.unblock_user(
                        app.auth.uid,
                        self.peer_uid,
                        callback=lambda ok, _r: (
                            setattr(self, "is_blocked", False) if ok else None,
                            popup.dismiss(),
                        ),
                    )
                else:
                    app.db.block_user(
                        app.auth.uid,
                        self.peer_uid,
                        callback=lambda ok, _r: (
                            setattr(self, "is_blocked", True) if ok else None,
                            popup.dismiss(),
                        ),
                    )

            box.add_widget(
                Button(
                    text=block_label,
                    background_normal="",
                    background_color=DANGER_RED,
                    color=WHITE,
                    on_release=toggle_block,
                )
            )

            reason_in = TextInput(hint_text="Report reason (optional)", multiline=False)
            box.add_widget(reason_in)
            box.add_widget(
                Button(
                    text="Report Account",
                    background_normal="",
                    background_color=(0.85, 0.45, 0.05, 1),
                    color=WHITE,
                    on_release=lambda _x: (
                        app.db.report_user(
                            app.auth.uid,
                            self.peer_uid,
                            reason_in.text or "Spam or abuse",
                        ),
                        popup.dismiss(),
                    ),
                )
            )
        else:
            box.add_widget(Label(text=f"Group ID: {self.room_id}", color=WHITE))

        box.add_widget(Button(text="Close", on_release=lambda _x: popup.dismiss()))
        popup.open()
