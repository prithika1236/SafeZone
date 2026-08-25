import asyncio

from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


def test_health_endpoint_reports_running_api() -> None:
    application = create_app(Settings(_env_file=None, APP_ENV="test"))

    async def request_health():
        async with application.router.lifespan_context(application):
            async with AsyncClient(
                transport=ASGITransport(app=application), base_url="http://testserver"
            ) as client:
                return await client.get("/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "SafeZone API",
        "message": "API is running",
    }


def test_cors_uses_configured_origin() -> None:
    application = create_app(
        Settings(
            _env_file=None,
            APP_ENV="test",
            ALLOWED_FRONTEND_ORIGINS=["https://admin.safezone.example"],
        )
    )

    async def request_preflight():
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as client:
            return await client.options(
                "/health",
                headers={
                    "Origin": "https://admin.safezone.example",
                    "Access-Control-Request-Method": "GET",
                },
            )

    response = asyncio.run(request_preflight())

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://admin.safezone.example"
