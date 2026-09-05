# Police mobile application

Stage 11 implements the POLICE portion of the existing Flutter SafeZone application. It uses the
FastAPI JWT and patrol-assignment endpoints; no assignment, routing, or risk decisions are made in
Flutter.

## Local Android emulator setup

Start PostgreSQL and the backend from one PowerShell terminal:

```powershell
cd C:\Users\onlyl\Desktop\SafeZone\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Start the Android emulator. In a second terminal:

```powershell
cd C:\Users\onlyl\Desktop\SafeZone\mobile\safezone_app
flutter pub get
flutter run --dart-define=SAFEZONE_API_BASE_URL=http://10.0.2.2:8000
```

`10.0.2.2` is the Android emulator route to the Windows host. For a physical Android device, use a
reachable development-machine LAN address and configure the backend host/firewall appropriately.
Never embed a password, JWT, signing secret, or precise operational location in `--dart-define`.

## Security and permissions

- Tokens are stored with `flutter_secure_storage`, are never printed, and are removed after a `401`,
  role rejection, or explicit sign-out.
- `/auth/me` must return an active `POLICE` role before police navigation is shown.
- Android requests coarse/fine location only when the assignment screen needs current position.
  Denied, permanently denied, disabled-service, timeout, and unavailable-GPS states are visible.
- Exact PRP coordinates are displayed only inside the authenticated Police module.
- Opening navigation is an explicit officer action that hands the destination to a compatible device
  navigation application.
- Cleartext HTTP is enabled only in the Android debug manifest for local development. Release builds
  should use an HTTPS backend URL.

## Current API boundaries

The current backend returns user identity but does not expose the officer badge/profile or a POLICE
availability-update endpoint. The app therefore labels availability as command-managed and disables
“Mark unavailable” with a clear explanation. The backend also has no authenticated route-estimate
endpoint, so the app labels locally calculated distance as straight-line proximity and does not
fabricate road distance or ETA.

## Verification

```powershell
flutter analyze
flutter test
flutter build apk --debug --dart-define=SAFEZONE_API_BASE_URL=http://10.0.2.2:8000
```
