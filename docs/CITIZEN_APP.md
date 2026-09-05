# Citizen mobile application

Stage 12 adds the Citizen experience to the existing role-based Flutter application.

## Capabilities

- Public Citizen registration and Citizen JWT login.
- Role-based routing to the Citizen or Police home after authentication.
- Citizen home with an intentionally inactive SOS preparation control, location readiness, emergency status, and contacts shortcut.
- Owner-scoped emergency-contact create, list, edit, and soft-delete operations.
- Explicit handling for disabled location services, denied permission, permanently denied permission, timeout, and unavailable location.

## Privacy and stage boundary

The Citizen application never requests or displays PRP endpoints or operational patrol coordinates. Stage 12 does not create SOS requests, dispatch patrols, or continuously transmit device location. The SOS control explains this boundary until Stage 13 connects the reviewed dispatch workflow.

## Local run

Start the backend on the development machine, start the Android emulator, then run:

```powershell
cd C:\Users\onlyl\Desktop\SafeZone\mobile\safezone_app
flutter run -d emulator-5554 --dart-define=SAFEZONE_API_BASE_URL=http://10.0.2.2:8000
```

`10.0.2.2` is the Android emulator alias for the host machine. A physical device needs a reachable development-machine address and appropriate network configuration.
