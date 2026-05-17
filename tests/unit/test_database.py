import pytest
from unittest.mock import AsyncMock, patch


class TestConnectDb:

    @pytest.mark.asyncio
    async def test_successful_connection(self):
        mock_client = AsyncMock()
        mock_client.admin.command = AsyncMock(return_value={"ok": 1})

        with patch("app.database.db.AsyncIOMotorClient", return_value=mock_client):
            from app.database.db import connect_db
            await connect_db("mongodb://test:27017")

        mock_client.admin.command.assert_called_once_with("ping")


class TestCloseDb:

    @pytest.mark.asyncio
    async def test_close_cleans_up(self):
        mock_client = AsyncMock()
        mock_client.admin.command = AsyncMock(return_value={"ok": 1})

        with patch("app.database.db.AsyncIOMotorClient", return_value=mock_client):
            from app.database.db import connect_db, close_db
            await connect_db("mongodb://test:27017")
            await close_db()

        mock_client.close.assert_called_once()
