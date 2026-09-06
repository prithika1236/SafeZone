# Live emergency communication

Stage 14 adds narrowly scoped live infrastructure around the Stage 13 SOS lifecycle. Ordinary authentication, contacts, assignments, and management operations remain REST APIs.

## SOS WebSocket

Authenticated Citizen and Police mobile sessions connect to `/ws/sos` and send their JWT in the first WebSocket message. The server publishes only an event name, SOS ID, and status. The client then reads the authorized REST representation, preserving the different Citizen and Police privacy scopes. No token is placed in the URL or logs.

The current broker is process-local and appropriate for the single-process MVP. A multi-worker deployment must replace it with a shared broker such as Redis; this interface boundary is intentionally isolated in `realtime_service.py`.

## Police location interval

`POST /live/police/location` is POLICE-only and accepts locations only during an active shift. The default minimum interval is 15 seconds, while the mobile client submits at most every 30 seconds and only when an assignment or SOS is active. Low-quality coordinates beyond the configured accuracy threshold are rejected. Updates are stored in the existing PostGIS-backed `location_updates` history and linked to an active SOS when applicable.

Configuration:

- `POLICE_LOCATION_MINIMUM_INTERVAL_SECONDS`
- `POLICE_LOCATION_MAXIMUM_ACCURACY_METERS`

## Push notifications

`notification_service.py` defines a push-provider interface, a Firebase Cloud Messaging adapter, and a safe development adapter. Set `NOTIFICATION_ADAPTER=firebase`, `FIREBASE_PROJECT_ID`, and `FIREBASE_CREDENTIALS_PATH` to enable FCM. Credentials are read from the server filesystem and must never be committed. With the default `auto` mode and no credentials, delivery is a non-sensitive development log event.

Mobile device tokens can be registered through `POST /notifications/devices`. Notification text contains no emergency, patrol, or PRP coordinates. Delivery failure never rolls back an SOS state change.

## Emergency contacts

`EmergencyContactAdapter` is the boundary for future SMS or email delivery. Stage 14 deliberately supplies an unconfigured adapter rather than selecting or pretending to use a paid provider. Connecting a provider requires an implementation, credentials, consent/opt-out handling, delivery audit policy, and retry rules.
