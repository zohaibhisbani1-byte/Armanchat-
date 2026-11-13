[app]

# Application display name
title = ArmanChat

# Package name (determines APK output: bin/armanchat-0.1-arm64-v8a-debug.apk)
package.name = armanchat

# Package domain (full Android applicationId becomes com.armanchat.armanchat;
# to use com.armanchat.app as applicationId, set package.name = app and rename output APK)
package.domain = com.armanchat

# Source directory
source.dir = .

# Source files to include
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,html,js,css,ttf

# Exclude build artifacts and local secrets
source.exclude_exts = spec,pyc,pyo
source.exclude_dirs = tests,bin,.buildozer,.git,__pycache__
source.exclude_patterns = user_session.json,serviceAccountKey.json

# Application versioning
version = 0.1

# Pure-Python + p4a-native recipes compatible with Android 12 ARM64
requirements = python3,kivy==2.3.0,requests,urllib3,certifi,chardet,idna,pillow,plyer,pyjnius,android

# Custom splash & icon assets
presplash.filename = %(source.dir)s/assets/presplash.png
icon.filename = %(source.dir)s/assets/icon.png

# Portrait orientation for mobile chat
orientation = portrait

# Keep Android status bar visible for natural chat experience
fullscreen = 0

# Soft keyboard adjusts layout so message input stays visible above keyboard
android.softinput_mode = adjustResize

# Android API & NDK configuration (compatible with Android 12 / API 31-32 and Android 13+)
android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.accept_sdk_license = True

# Target 64-bit ARM architecture required by Android 12 phones
android.archs = arm64-v8a

# Permissions for messaging, media sharing, camera, mic calls, Bluetooth audio, notifications
android.permissions = INTERNET, ACCESS_NETWORK_STATE, CAMERA, RECORD_AUDIO, MODIFY_AUDIO_SETTINGS, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, READ_MEDIA_IMAGES, POST_NOTIFICATIONS, VIBRATE, WAKE_LOCK, BLUETOOTH, BLUETOOTH_CONNECT

# Allow backup to be false for private chat session safety
android.allow_backup = False

# Enable AndroidX support libraries
android.enable_androidx = True

# Logcat filter during adb debugging
android.logcat_filters = *:S python:D

# Copy libraries cleanly
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1
