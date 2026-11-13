"""WebRTC media bridge for ArmanChat on Android 12 and Desktop.

Kivy does not ship a native C++ WebRTC PeerConnection engine. On Android,
this bridge launches an embedded native Android WebView (or Chrome WebRTC
session) with microphone/camera permissions granted and controls Android's
AudioManager for speakerphone and microphone muting.
"""

import os
import urllib.parse
import webbrowser
from typing import Optional

from kivy.utils import platform

from firebase_config import APP_DIR, FirebaseConfig


WEBRTC_HTML_PATH = os.path.join(APP_DIR, "assets", "webrtc_call.html")


class AndroidWebRTCBridge:
    """Controls native Android AudioManager & WebRTC WebView session."""

    def __init__(self, config: FirebaseConfig) -> None:
        self.config = config
        self._webview = None
        self._dialog = None
        self._mic_muted = False
        self._speaker_on = False
        self._camera_on = True

    def build_room_url(
        self,
        call_id: str,
        role: str,
        call_type: str,
        id_token: str,
    ) -> str:
        params = urllib.parse.urlencode(
            {
                "callId": call_id,
                "role": role,
                "callType": call_type,
                "dbUrl": self.config.clean_database_url,
                "token": id_token,
                "turnUrl": self.config.turn_server_url,
                "turnUser": self.config.turn_username,
                "turnPass": self.config.turn_credential,
            }
        )
        return f"file://{WEBRTC_HTML_PATH}#{params}"

    def start_media_session(
        self,
        call_id: str,
        role: str,
        call_type: str,
        id_token: str,
    ) -> str:
        """Open the WebRTC peer connection room. Returns status note."""
        room_url = self.build_room_url(call_id, role, call_type, id_token)
        self._camera_on = call_type == "video"
        self.set_speaker(call_type == "video")

        if platform == "android":
            try:
                self._launch_android_webview(room_url)
                return "WebRTC media active via Android WebView"
            except Exception as exc:
                return f"WebRTC WebView error: {exc}"

        try:
            webbrowser.open(room_url)
            return "WebRTC room opened in browser"
        except Exception as exc:
            return f"Browser launch failed: {exc}"

    def _launch_android_webview(self, url: str) -> None:
        from android.runnable import run_on_ui_thread
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        WebView = autoclass("android.webkit.WebView")
        WebViewClient = autoclass("android.webkit.WebViewClient")
        Dialog = autoclass("android.app.Dialog")
        LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")

        @run_on_ui_thread
        def _create() -> None:
            activity = PythonActivity.mActivity
            wv = WebView(activity)
            settings = wv.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setMediaPlaybackRequiresUserGesture(False)
            settings.setAllowFileAccess(True)
            settings.setAllowFileAccessFromFileURLs(True)
            settings.setAllowUniversalAccessFromFileURLs(True)
            wv.setWebViewClient(WebViewClient())
            wv.loadUrl(url)

            dlg = Dialog(activity)
            dlg.setContentView(wv, LayoutParams(LayoutParams.MATCH_PARENT, 620))
            dlg.setCancelable(True)
            dlg.show()
            self._webview = wv
            self._dialog = dlg

        _create()

    def set_mic_muted(self, muted: bool) -> None:
        self._mic_muted = muted
        if platform == "android":
            try:
                from jnius import autoclass

                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                Context = autoclass("android.content.Context")
                am = PythonActivity.mActivity.getSystemService(Context.AUDIO_SERVICE)
                am.setMicrophoneMute(bool(muted))
            except Exception:
                pass
            self._eval_js(f"window.armanSetMic && window.armanSetMic({str(not muted).lower()});")

    def set_speaker(self, speaker_on: bool) -> None:
        self._speaker_on = speaker_on
        if platform == "android":
            try:
                from jnius import autoclass

                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                Context = autoclass("android.content.Context")
                AudioManager = autoclass("android.media.AudioManager")
                am = PythonActivity.mActivity.getSystemService(Context.AUDIO_SERVICE)
                am.setMode(AudioManager.MODE_IN_COMMUNICATION)
                am.setSpeakerphoneOn(bool(speaker_on))
            except Exception:
                pass

    def set_camera_enabled(self, enabled: bool) -> None:
        self._camera_on = enabled
        self._eval_js(f"window.armanSetCam && window.armanSetCam({str(enabled).lower()});")

    def _eval_js(self, script: str) -> None:
        if platform != "android" or self._webview is None:
            return
        try:
            from android.runnable import run_on_ui_thread

            @run_on_ui_thread
            def _run() -> None:
                if self._webview is not None:
                    self._webview.evaluateJavascript(script, None)

            _run()
        except Exception:
            pass

    def stop_media_session(self) -> None:
        if platform == "android":
            try:
                from android.runnable import run_on_ui_thread
                from jnius import autoclass

                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                Context = autoclass("android.content.Context")
                AudioManager = autoclass("android.media.AudioManager")
                am = PythonActivity.mActivity.getSystemService(Context.AUDIO_SERVICE)
                am.setMicrophoneMute(False)
                am.setSpeakerphoneOn(False)
                am.setMode(AudioManager.MODE_NORMAL)

                @run_on_ui_thread
                def _cleanup() -> None:
                    if self._webview is not None:
                        self._webview.loadUrl("about:blank")
                        self._webview.destroy()
                        self._webview = None
                    if self._dialog is not None:
                        self._dialog.dismiss()
                        self._dialog = None

                _cleanup()
            except Exception:
                pass
