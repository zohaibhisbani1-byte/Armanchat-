# ArmanChat — Complete Android Chat Application (Python + Kivy + Firebase)

**App Name:** ArmanChat  
**Package Name:** `com.armanchat.armanchat` (or `com.armanchat.app` — see `buildozer.spec`)  
**Target Output:** `bin/armanchat-0.1-arm64-v8a-debug.apk`  
**Minimum Android:** Android 7.0 (API 24) · **Tested Target:** Android 12+ (API 31–33)

---

## 1. Project Files

- `main.py` — App entry point, green-and-white theme, `ScreenManager` (Splash, Welcome, Phone/Email Login, OTP, Profile Setup, Home, Chat Room, Profile, Call, Admin Panel)
- `buildozer.spec` — Android 12 ARM64 Buildozer specification with permissions & assets
- `requirements.txt` — Python-for-Android compatible dependencies
- `firebase_config.py` — Loads client-side Firebase config safely (no embedded secrets)
- `firebase_client_config.example.json` — Template to rename to `firebase_client_config.json`
- `database.py` — Firebase Realtime Database & Storage REST client (1-to-1, groups, read receipts, typing, online/last seen, delete, block/report)
- `auth.py` — Firebase Phone OTP & Email/Password authentication + session refresh + Android 12 runtime permissions
- `chat.py` — Chats, Contacts, Groups, ChatRoom UI, emoji picker, image/file sharing
- `profile.py` — Profile setup, avatar upload, settings, blocked user management
- `notifications.py` — Android NotificationChannel, `plyer` local notifications, incoming message/call listener
- `calls.py` — Outgoing, Incoming, Active audio/video CallScreen, Call History
- `webrtc_bridge.py` & `assets/webrtc_call.html` — Android WebView WebRTC peer-to-peer audio/video bridge + AudioManager speaker/mute control
- `admin_panel.py` — Admin dashboard (stats, user management, reports, group moderation)
- `admin_server.py` — Optional trusted server script (runs outside APK) to grant Admin custom claims and dispatch FCM pushes
- `firebase_rules.json` & `storage.rules` — Production Firebase security rules
- `.github/workflows/build-apk.yml` — One-tap cloud APK builder for users without a PC

---

## 2. Step-by-Step Firebase Setup (Can Be Done on Android Chrome)

1. Open [console.firebase.google.com](https://console.firebase.google.com) in Chrome on your phone (enable **Desktop site** in Chrome menu if needed).
2. Tap **Create a project** -> name it `armanchat` -> create.
3. **Authentication**:
   - Open **Build -> Authentication -> Get started**.
   - Enable **Phone** sign-in (and optionally **Email/Password** for quick testing without SMS limits).
   - Under **Phone -> Phone numbers for testing**, you can add a test phone + 6-digit OTP code while testing.
   - Note: Real Phone OTP via REST requires a Google reCAPTCHA token (`recaptchaSiteKey`). For production Android SMS auto-verification without manual reCAPTCHA, register your SHA-1/SHA-256 keystore fingerprint in Firebase Project Settings.
4. **Realtime Database**:
   - Open **Build -> Realtime Database -> Create Database** -> choose region -> **Start in locked mode**.
   - Open the **Rules** tab, paste the entire contents of `firebase_rules.json`, and tap **Publish**.
5. **Firebase Storage**:
   - Open **Build -> Storage -> Get started**.
   - Open the **Rules** tab, paste `storage.rules`, and tap **Publish**.
6. **Get Your Client Configuration**:
   - Go to **Project Settings (gear icon) -> General -> Your apps -> Web app (`</>`)**.
   - Register `ArmanChat` and copy the `firebaseConfig` fields (`apiKey`, `authDomain`, `databaseURL`, `projectId`, `storageBucket`, `messagingSenderId`, `appId`).
   - Copy `firebase_client_config.example.json` to `firebase_client_config.json` and paste your values (or enter them inside the app under **Settings -> Firebase Client Configuration**).
7. **Grant Yourself Admin Access (Securely)**:
   - Sign up once in ArmanChat to get your **User ID (UID)** (shown in **My Profile**).
   - In Firebase Console -> **Realtime Database -> Data**, add:
     `admins` -> `<YOUR_UID>` -> `true`.
   - Or run `python admin_server.py --key serviceAccountKey.json --db-url https://... --grant-admin <YOUR_UID>` from Google Cloud Shell.

---

## 3. How to Build the APK Using ONLY an Android 12 Phone (No PC Required)

### Method A (Recommended): GitHub Mobile + GitHub Actions (100% Free Cloud Build)

Buildozer needs ~15 GB of Linux disk space for Android SDK/NDK, which fails on most phones directly. GitHub Actions builds the APK for free on Ubuntu in the cloud:

1. Download **ArmanChat Project (.zip)** from ArmanChat Studio or create a new repository on [github.com](https://github.com) using Chrome on Android.
2. Extract the zip on your phone (using Android **Files** or **ZArchiver**) and upload the files inside `armanchat/` (including the hidden `.github/workflows/build-apk.yml` folder) to your GitHub repo.
   - Include your `firebase_client_config.json` (remember: client config keys are public identifiers protected by `firebase_rules.json` — NEVER upload `serviceAccountKey.json`!).
3. In GitHub on your phone, tap the **Actions** tab -> **Build ArmanChat Android APK** -> **Run workflow**.
4. Wait ~15 minutes for the green checkmark.
5. Scroll down to **Artifacts** -> tap **armanchat-debug-apk** to download `armanchat-0.1-arm64-v8a-debug.apk` directly to your Android 12 phone!

### Method B: Google Cloud Shell or Google Colab (In Chrome on Android)

1. Open [shell.cloud.google.com](https://shell.cloud.google.com) or [colab.research.google.com](https://colab.research.google.com) in Chrome.
2. Upload your `armanchat` folder or clone your GitHub repo.
3. Run:
   ```bash
   sudo apt-get update && sudo apt-get install -y git zip unzip openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev libncurses5-dev cmake libffi-dev libssl-dev
   pip install buildozer==1.5.0 cython==0.29.36
   buildozer android debug
   ```
4. Download `bin/armanchat-0.1-arm64-v8a-debug.apk` from the file browser to your phone.

---

## 4. Installing & Testing on Android 12

1. Open the downloaded `armanchat-0.1-arm64-v8a-debug.apk` in your phone's **Files** app.
2. If prompted **"For your security, your phone isn't allowed to install unknown apps from this source"**, tap **Settings** -> toggle **Allow from this source** -> go back and tap **Install**.
3. Open **ArmanChat** and grant **Camera**, **Microphone**, **Files/Media**, and **Notifications** permissions when requested.
4. Create two test accounts (e.g., on two devices or via Email/Password sign-up) and verify:
   - Real-time messaging, timestamps, sent/read ticks, typing indicator
   - Image and file uploads to Firebase Storage
   - Group creation and group chat
   - Voice & video calls (WebRTC uses free Google STUN servers; symmetric mobile carrier NATs may require configuring a TURN server like Metered/Twilio in `firebase_client_config.json`)
   - Admin Panel after adding your UID to `/admins/<uid>: true`.

---

## 5. Troubleshooting

- **Buildozer fails with `Cython` or `kivy` compile error**: Ensure `cython==0.29.36` and `openjdk-17-jdk` are installed (already pinned in `.github/workflows/build-apk.yml`).
- **`Permission denied` from Firebase**: Verify you pasted `firebase_rules.json` into Realtime Database Rules and `storage.rules` into Storage Rules, and that the user is signed in.
- **Phone OTP error `MISSING_RECAPTCHA_TOKEN`**: Firebase REST Phone Auth requires a valid reCAPTCHA token. Use a Firebase Console test phone number with reCAPTCHA or sign in with Email & Password during development.
- **Video call shows black screen on cellular network**: Mobile carriers often block peer-to-peer UDP without a TURN relay. Add `turnServerUrl`, `turnUsername`, and `turnCredential` to `firebase_client_config.json`.
- **App crashes on launch on Android 12**: Check `adb logcat -s python` if connected via USB, or ensure `assets/icon.png` and `assets/presplash.png` exist before running `buildozer android debug`.
