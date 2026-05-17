import pytest
from unittest.mock import AsyncMock, patch

from app.main import app


class TestLifespan:

    @pytest.mark.asyncio
    async def test_startup_and_shutdown(self):
        with (
            patch("app.main.connect_db", new_callable=AsyncMock) as mock_connect,
            patch("app.main.init_database", new_callable=AsyncMock) as mock_init,
            patch("app.main.close_db", new_callable=AsyncMock) as mock_close,
        ):
            from app.main import lifespan
            async with lifespan(app):
                mock_connect.assert_awaited_once()
                mock_init.assert_awaited_once()
                mock_close.assert_not_awaited()

            mock_close.assert_awaited_once()
