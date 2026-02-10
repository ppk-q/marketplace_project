from __future__ import annotations

import pytest

from app.constants_api import HEALTH_PATH, HEALTH_STATUS_KEY, HEALTH_STATUS_OK


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok(client) -> None:
    response = await client.get(HEALTH_PATH)

    assert response.status_code == 200
    assert response.json() == {HEALTH_STATUS_KEY: HEALTH_STATUS_OK}
