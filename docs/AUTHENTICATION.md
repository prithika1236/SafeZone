# SafeZone Authentication and RBAC

## Scope

Stage 3 implements local email/password authentication, short-lived JWT access tokens, current-user retrieval, active-account enforcement, and reusable role dependencies. Social login, refresh tokens, password recovery, multifactor authentication, and privileged-user management APIs are intentionally outside this stage.

## Security model

- Passwords are hashed with pwdlib's recommended Argon2 configuration and are never stored or returned in plaintext.
- Unknown-email login attempts perform a dummy Argon2 verification to reduce timing-based email enumeration.
- Emails are normalized with Unicode case folding before lookup and storage.
- PostgreSQL enforces case-insensitive email uniqueness through `uq_users_email_lower`.
- JWT access tokens use `HS256`, a configurable secret, issuer, audience, and expiration.
- Tokens include subject, persisted role, token type, issuer, audience, issued/not-before/expiry timestamps, and a unique token identifier.
- Every authenticated request reloads the user from PostgreSQL. A token cannot keep using a disabled account or a stale role.
- Password hashes and JWT secrets are excluded from response schemas and logs.

## Public endpoints

### `POST /auth/register/citizen`

Accepts JSON:

```json
{
  "name": "Citizen Name",
  "email": "citizen@example.com",
  "password": "a-user-provided-strong-password"
}
```

The endpoint always creates the role `CITIZEN`. The request has no role field, so public callers cannot create `ADMIN` or `POLICE` accounts. Duplicate normalized emails return `409 Conflict`.

### `POST /auth/login`

Uses the OAuth2 password form encoding expected by FastAPI/OpenAPI:

```text
username=citizen@example.com
password=<user password>
```

`username` contains the email for OAuth2 compatibility. Successful login returns:

```json
{
  "access_token": "<signed JWT>",
  "token_type": "bearer",
  "expires_in": 1800
}
```

Incorrect credentials return the same generic `401` response. Inactive accounts return `403` and receive no token.

### `GET /auth/me`

Requires:

```text
Authorization: Bearer <access_token>
```

Returns the safe current-user profile without `password_hash`.

Interactive OpenAPI documentation is available at `/docs` when the backend runs.

## Reusable authorization dependencies

Routes in later approved stages should depend on centralized helpers from `app/core/authorization.py`:

- `require_citizen`
- `require_police`
- `require_admin`
- `require_admin_or_police`
- `require_roles(...)` for a genuinely different approved combination

Routes must not duplicate raw string or enum role comparisons.

## Privileged account creation

There is deliberately no public ADMIN or POLICE registration endpoint. A later administrator-management workflow must require an already authenticated active administrator, create police identity/profile records transactionally, record audit information, and never accept privileged role selection through the citizen registration schema.

Until that workflow is implemented, initial administrator provisioning must be an explicit operational procedure rather than a public API.

## Configuration

Required environment variables:

```text
JWT_SECRET_KEY=<at least 32 random characters>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_ISSUER=safezone-api
JWT_AUDIENCE=safezone-clients
```

Generate a development secret locally and keep it only in `.env`. Never copy a real secret into `.env.example`, documentation, source code, chat, or Git.
