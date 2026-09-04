# Admin dashboard

The Stage 10 React + Vite dashboard is the authorized browser interface for current SafeZone
backend capabilities. It uses a central API client and never performs crime scoring, candidate
generation, PRP optimization, or patrol allocation in the browser.

## Run locally

Start the backend at `http://127.0.0.1:8000`, then open a second PowerShell terminal:

```powershell
cd C:\Users\onlyl\Desktop\SafeZone\admin-dashboard
npm install
Copy-Item .env.example .env.local
npm run dev
```

Open `http://localhost:5173`. The backend CORS configuration must include this origin. Only an
existing active ADMIN account can enter the dashboard. Access tokens and the safe user profile are
held in browser session storage and cleared on sign-out or an API `401` response.

`VITE_API_BASE_URL` is a public service location, not a secret. Never put JWT signing keys,
database credentials, Firebase credentials, or other secrets in a `VITE_` variable.

## Available modules

- Overview uses crime, active PRP, and assignment APIs. SOS and available-patrol cards remain
  explicitly unavailable until corresponding backend ADMIN endpoints exist.
- Crime management supports filters, pagination, create/edit, retention-safe deactivation, and CSV
  import summaries with rejected rows.
- SafeZone Map uses React Leaflet and OpenStreetMap. Crime severity evidence, active PRP coverage,
  last proposed PRPs, and assignment-linked deployments are ADMIN-only layers.
- PRP optimization configures shift, patrol capacity, and radius. Stage 6/7 optimizer input JSON is
  passed to the backend unchanged because the current API does not yet expose pipeline generation
  from crime records. Results show coverage, weighted risk, uncovered high-risk points, solver
  metadata, approval, and activation.
- Patrol assignments support automatic allocation from an approved run, current status inspection,
  manual override, and cancellation.

## Known API-bound limitations

The existing backend has no ADMIN SOS count/list endpoint and no patrol-unit inventory endpoint, so
the dashboard does not fabricate those values. It also has no endpoint to list arbitrary historical
optimization runs; the latest generated run is retained only for the current browser session.
