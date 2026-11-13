"""Optional Trusted Server Script for ArmanChat Admin & FCM Push Dispatch.

RUN THIS ONLY IN A TRUSTED CLOUD SERVER OR GOOGLE CLOUD SHELL — NEVER BUNDLE
`serviceAccountKey.json` INTO THE ANDROID APK!

Install dependencies on your cloud host:
    pip install firebase-admin
"""

import argparse
import os
import time

import firebase_admin
from firebase_admin import auth, credentials, db, messaging


def init_firebase(service_account_path: str, database_url: str) -> None:
    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred, {"databaseURL": database_url})


def grant_admin(uid: str) -> None:
    """Grant admin custom claim and write /admins/<uid>: true."""
    auth.set_custom_user_claims(uid, {"admin": True})
    db.reference(f"admins/{uid}").set(True)
    print(f"Granted ArmanChat admin privileges to UID: {uid}")


def dispatch_pending_notifications() -> None:
    """Poll /notifications_queue and deliver real FCM push notifications."""
    queue_ref = db.reference("notifications_queue")
    print("ArmanChat FCM notification dispatcher running...")
    while True:
        items = queue_ref.get() or {}
        for notif_id, payload in items.items():
            recipient_uid = payload.get("recipient_id")
            if not recipient_uid:
                queue_ref.child(notif_id).delete()
                continue
            token = db.reference(f"users/{recipient_uid}/fcm_token").get()
            if token and not str(token).startswith("android_"):
                msg = messaging.Message(
                    notification=messaging.Notification(
                        title=payload.get("sender_name", "ArmanChat"),
                        body=payload.get("preview", "New message"),
                    ),
                    token=token,
                )
                try:
                    messaging.send(msg)
                except Exception as exc:
                    print(f"FCM send failed for {notif_id}: {exc}")
            queue_ref.child(notif_id).delete()
        time.sleep(2.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ArmanChat Trusted Server Tools")
    parser.add_argument("--key", default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json"))
    parser.add_argument("--db-url", required=True, help="Firebase RTDB URL")
    parser.add_argument("--grant-admin", help="Firebase UID to promote to Admin")
    parser.add_argument("--run-fcm", action="store_true", help="Run FCM notification worker")
    args = parser.parse_args()

    init_firebase(args.key, args.db_url)
    if args.grant_admin:
        grant_admin(args.grant_admin)
    if args.run_fcm:
        dispatch_pending_notifications()
