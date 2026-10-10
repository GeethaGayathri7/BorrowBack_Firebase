# BorrowBack — Firebase / Firestore edition

This version replaces the API's MySQL storage with **Firebase Cloud Firestore**. The Flutter interface continues to call the FastAPI backend, so an APK can share cloud data with other phones when the backend is deployed online.

## Project structure
- `frontend/` — existing Flutter application
- `backend/app.py` — FastAPI endpoints using Firestore
- `backend/migrate_mysql_to_firestore.py` — optional one-time data importer
- `database/` — original MySQL schema kept for reference / migration only

## Before starting
You need Flutter SDK, Python 3.10+, a Firebase account, and Android Studio (for building APKs).

## 1. Create Firebase project and Firestore database
1. Open https://console.firebase.google.com/ and create a project.
2. Open **Build → Firestore Database → Create database**.
3. Choose a region close to your users. Start in production mode.
4. Open **Project settings → Service accounts → Generate new private key**. Download the JSON file.
5. Put that file at `backend/serviceAccountKey.json`. Do not commit or share this key.
6. Copy `backend/.env.example` to `backend/.env` and set `FIREBASE_PROJECT_ID` to your Firebase project ID and `FIREBASE_SERVICE_ACCOUNT=serviceAccountKey.json`.

The backend uses the Firebase Admin SDK, so it accesses Firestore with server credentials. Do not put the service-account JSON in Flutter or inside the APK.

## 2. Start the Firebase-backed API locally
Windows PowerShell:
```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and add your Firebase project ID and SMTP settings if needed.
# Copy serviceAccountKey.json into backend/
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```
Test `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/docs`.

## 3. Optional: copy existing MySQL records to Firestore
If you want to keep existing MySQL data, back up the database first. Configure `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE` in `backend/.env`. Install the migration dependency:
```powershell
pip install mysql-connector-python
python migrate_mysql_to_firestore.py
```
Run this script once before switching the app. It imports users, items, borrow requests, notifications and ratings. It preserves document IDs and initializes ID counters. Verify the imported data in Firebase Console. Do not run repeatedly unless you intend to overwrite documents with matching IDs. Existing password hashes are retained, so existing users can continue logging in.

If you do not need old records, skip the migration and register new accounts in the app.

## 4. Deploy the API online (required for phones outside your Wi-Fi)
The APK cannot directly reach `localhost` on your computer. Deploy the `backend/` folder to a Python hosting service (for example, Render or Railway) with:
- Build/install command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Environment variables: `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT` (prefer a secret file or provider secret mechanism), plus optional SMTP values.

**Important:** configure the service account securely using your host's secret-file support or a protected environment variable mechanism. Do not upload `serviceAccountKey.json` to a public repository. Ensure the hosting platform's runtime can read the key file. Copy the deployed HTTPS API URL for the next step.

## 5. Build APK
In PowerShell:
```powershell
cd frontend
flutter pub get
flutter build apk --release --dart-define=API_BASE_URL=https://YOUR-DEPLOYED-API-URL
```
Replace `https://YOUR-DEPLOYED-API-URL` with the actual HTTPS URL of your deployed API (no trailing slash). APK output:
`frontend/build/app/outputs/flutter-apk/app-release.apk`

Copy that APK to your phone and install it. Any phone with internet access can use the same cloud data, provided the API is deployed and running. If you only want to test locally on a physical phone, use your computer's LAN IP for `API_BASE_URL`; this only works on the same Wi-Fi and is not suitable for sharing the APK publicly.

## Email notifications
SMTP is optional. Set the SMTP values in `.env` / hosting environment variables. For Gmail, use an App Password, not your normal Gmail password.

## Security limitations — read before public use
This preserves the original MVP's `X-User-Id` request-header identity mechanism to keep the existing Flutter UI compatible. That is not production-grade authentication: users could potentially impersonate another account if they obtain its ID. Before public deployment with real student data, implement Firebase Authentication ID-token verification, strict per-user authorization, rate limiting, and tighter CORS rules. The Admin SDK bypasses Firestore client security rules, so the API itself must enforce authorization. Use synthetic data for demos until this is fixed.

The backend uses Firestore collections: `users`, `items`, `borrow_requests`, `notifications`, `user_ratings`, and `_counters`. Firestore indexes may be suggested by the Firebase console if you later add compound queries.
