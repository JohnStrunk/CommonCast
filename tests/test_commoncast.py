"""Tests for CommonCast public API."""

from unittest.mock import AsyncMock, patch

import pytest

import commoncast
import commoncast.event as _event


def test_can_import_commoncast() -> None:
    """Ensure the commoncast package can be imported."""
    assert commoncast is not None


@pytest.mark.asyncio
async def test_public_start_stop() -> None:
    """Test public start and stop functions."""
    with (
        patch(
            "commoncast.registry.default_registry.start", new_callable=AsyncMock
        ) as mock_start,
        patch(
            "commoncast.registry.default_registry.stop", new_callable=AsyncMock
        ) as mock_stop,
    ):
        await commoncast.start(media_host="1.2.3.4", media_port=1234)
        mock_start.assert_called_once_with(media_host="1.2.3.4", media_port=1234)

        await commoncast.stop()
        mock_stop.assert_called_once()


def test_public_start_stop_sync() -> None:
    """Test public start_sync and stop_sync functions."""
    with (
        patch("commoncast.registry.default_registry.start_sync") as mock_start_sync,
        patch("commoncast.registry.default_registry.stop_sync") as mock_stop_sync,
    ):
        commoncast.start_sync(media_host="1.2.3.4", media_port=1234)
        mock_start_sync.assert_called_once_with(media_host="1.2.3.4", media_port=1234)

        commoncast.stop_sync()
        mock_stop_sync.assert_called_once()


def test_public_list_devices() -> None:
    """Test public list_devices function."""
    with patch(
        "commoncast.registry.default_registry.list_devices", return_value=[]
    ) as mock_list:
        assert commoncast.list_devices() == []
        mock_list.assert_called_once()


def test_public_backend_management() -> None:
    """Test public backend management functions."""
    with (
        patch("commoncast.registry.default_registry.enable_backend") as mock_enable,
        patch("commoncast.registry.default_registry.disable_backend") as mock_disable,
        patch(
            "commoncast.registry.default_registry.list_backends", return_value={}
        ) as mock_list,
    ):
        commoncast.enable_backend("test")
        mock_enable.assert_called_once_with("test")

        commoncast.disable_backend("test")
        mock_disable.assert_called_once_with("test")

        assert commoncast.list_backends() == {}
        mock_list.assert_called_once()


@pytest.mark.asyncio
async def test_public_subscriptions() -> None:
    """Test public subscription functions."""

    async def async_cb(ev: _event.DeviceEvent) -> None:
        pass

    def sync_cb(ev: _event.DeviceEvent) -> None:
        pass

    with (
        patch("commoncast.registry.default_registry.subscribe") as mock_sub,
        patch("commoncast.registry.default_registry.subscribe_sync") as mock_sub_sync,
        patch("commoncast.registry.default_registry.events") as mock_events,
    ):
        commoncast.subscribe(async_cb)
        mock_sub.assert_called_once_with(async_cb)

        commoncast.subscribe_sync(sync_cb)
        mock_sub_sync.assert_called_once_with(sync_cb)

        commoncast.events()
        mock_events.assert_called_once()
