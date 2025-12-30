"""Tests for the Chromecast backend."""

import asyncio
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import commoncast.chromecast.adapter as _chromecast_adapter
import commoncast.registry as _registry
import commoncast.types as _types


@pytest.fixture
def registry() -> _registry.Registry:
    """Create a registry instance for testing.

    :returns: A Registry instance.
    """
    return _registry.Registry()


@pytest.fixture
def mock_cast() -> MagicMock:
    """Create a mock pychromecast object.

    :returns: A MagicMock simulating a Chromecast.
    """
    cast_obj = MagicMock()
    cast_obj.uuid = uuid.uuid4()
    cast_obj.name = "Test Chromecast"
    cast_obj.model_name = "Chromecast Ultra"
    cast_obj.cast_type = "cast"
    cast_obj.media_controller = MagicMock()
    return cast_obj


@pytest.mark.asyncio
async def test_adapter_discovery(
    registry: _registry.Registry, mock_cast: MagicMock
) -> None:
    """Test Chromecast adapter discovery process.

    :param registry: The Registry fixture.
    :param mock_cast: The mock_cast fixture.
    :returns: None
    """
    adapter = _chromecast_adapter.ChromecastAdapter(registry)
    registry._loop = asyncio.get_running_loop()  # type: ignore[reportPrivateUsage]

    with (
        patch("pychromecast.CastBrowser") as mock_browser_class,
        patch("pychromecast.get_chromecast_from_cast_info") as mock_get_cast,
    ):
        mock_browser = mock_browser_class.return_value
        mock_get_cast.return_value = mock_cast
        mock_browser.devices = {mock_cast.uuid: MagicMock()}

        await adapter.start()

        # Simulate device found
        adapter._on_device_found(mock_cast.uuid, mock_cast.name)  # type: ignore[reportPrivateUsage]

        # Give some time for the thread-safe call to process
        await asyncio.sleep(0.1)

        devices = registry.list_devices()
        assert len(devices) == 1
        assert devices[0].name == "Test Chromecast"
        assert devices[0].transport == "chromecast"

        # Simulate device lost
        adapter._on_device_lost(mock_cast.uuid, mock_cast.name)  # type: ignore[reportPrivateUsage]
        await asyncio.sleep(0.1)

        devices = registry.list_devices()
        assert len(devices) == 0

        await adapter.stop()


@pytest.mark.asyncio
async def test_adapter_updated(
    registry: _registry.Registry, mock_cast: MagicMock
) -> None:
    """Test Chromecast adapter device update process.

    :param registry: The Registry fixture.
    :param mock_cast: The mock_cast fixture.
    :returns: None
    """
    adapter = _chromecast_adapter.ChromecastAdapter(registry)
    registry._loop = asyncio.get_running_loop()  # type: ignore[reportPrivateUsage]

    with (
        patch("pychromecast.CastBrowser") as mock_browser_class,
        patch("pychromecast.get_chromecast_from_cast_info") as mock_get_cast,
    ):
        mock_browser = mock_browser_class.return_value
        mock_get_cast.return_value = mock_cast
        mock_browser.devices = {mock_cast.uuid: MagicMock()}

        await adapter.start()

        # Simulate device found
        adapter._on_device_found(mock_cast.uuid, mock_cast.name)  # type: ignore[reportPrivateUsage]
        await asyncio.sleep(0.1)

        # Simulate device updated
        adapter._on_device_updated(mock_cast.uuid, mock_cast.name)  # type: ignore[reportPrivateUsage]
        await asyncio.sleep(0.1)

        devices = registry.list_devices()
        assert len(devices) == 1

        await adapter.stop()


@pytest.mark.asyncio
async def test_adapter_audio_only(
    registry: _registry.Registry, mock_cast: MagicMock
) -> None:
    """Test Chromecast adapter with an audio-only device.

    :param registry: The Registry fixture.
    :param mock_cast: The mock_cast fixture.
    :returns: None
    """
    mock_cast.cast_type = "audio"
    adapter = _chromecast_adapter.ChromecastAdapter(registry)
    registry._loop = asyncio.get_running_loop()  # type: ignore[reportPrivateUsage]

    with (
        patch("pychromecast.CastBrowser") as mock_browser_class,
        patch("pychromecast.get_chromecast_from_cast_info") as mock_get_cast,
    ):
        mock_browser = mock_browser_class.return_value
        mock_get_cast.return_value = mock_cast
        mock_browser.devices = {mock_cast.uuid: MagicMock()}

        await adapter.start()
        adapter._on_device_found(mock_cast.uuid, mock_cast.name)  # type: ignore[reportPrivateUsage]
        await asyncio.sleep(0.1)

        devices = registry.list_devices()
        assert len(devices) == 1
        assert _types.Capability("audio") in devices[0].capabilities
        assert _types.Capability("video") not in devices[0].capabilities

        await adapter.stop()


@pytest.mark.asyncio
async def test_send_media_missing_server(
    registry: _registry.Registry, mock_cast: MagicMock
) -> None:
    """Test sending media without a media server available.

    :param registry: The Registry fixture.
    :param mock_cast: The mock_cast fixture.
    :returns: None
    """
    adapter = _chromecast_adapter.ChromecastAdapter(registry)
    registry._loop = asyncio.get_running_loop()  # type: ignore[reportPrivateUsage]
    registry._media_server = None  # type: ignore[reportPrivateUsage]

    # Pre-populate discovered casts
    adapter._discovered_casts[mock_cast.uuid] = mock_cast  # type: ignore[reportPrivateUsage]

    device = _types.Device(
        id=_types.DeviceID(str(mock_cast.uuid)),
        name=mock_cast.name,
        model=mock_cast.model_name,
        transport="chromecast",
        capabilities=set(),
        transport_info={"uuid": str(mock_cast.uuid)},
    )

    payload = _types.MediaPayload.from_bytes(b"data")

    def _sync_to_thread(f: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return f(*args, **kwargs)

    with patch("asyncio.to_thread", side_effect=_sync_to_thread):
        result = await adapter.send_media(device, payload)

        assert not result.success
        assert result.reason == "media_server_not_available"


@pytest.mark.asyncio
async def test_send_media_chromecast(
    registry: _registry.Registry, mock_cast: MagicMock
) -> None:
    """Test sending media to a Chromecast device.

    :param registry: The Registry fixture.
    :param mock_cast: The mock_cast fixture.
    :returns: None
    """
    adapter = _chromecast_adapter.ChromecastAdapter(registry)
    registry._loop = asyncio.get_running_loop()  # type: ignore[reportPrivateUsage]
    registry._media_server = MagicMock()  # type: ignore[reportPrivateUsage]
    registry._media_server.register_payload.return_value = "http://fake/media"  # type: ignore[reportPrivateUsage]

    # Pre-populate discovered casts
    adapter._discovered_casts[mock_cast.uuid] = mock_cast  # type: ignore[reportPrivateUsage]

    device = _types.Device(
        id=_types.DeviceID(str(mock_cast.uuid)),
        name=mock_cast.name,
        model=mock_cast.model_name,
        transport="chromecast",
        capabilities=set(),
        transport_info={"uuid": str(mock_cast.uuid)},
    )

    payload = _types.MediaPayload.from_bytes(b"data", mime_type="image/png")

    def _sync_to_thread(f: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return f(*args, **kwargs)

    with patch("asyncio.to_thread", side_effect=_sync_to_thread):
        result = await adapter.send_media(device, payload)

        assert result.success
        assert result.controller is not None
        mock_cast.media_controller.play_media.assert_called_once_with(
            "http://fake/media", "image/png", title="CommonCast Media"
        )


@pytest.mark.asyncio
async def test_send_media_exception(
    registry: _registry.Registry, mock_cast: MagicMock
) -> None:
    """Test send_media handling an exception.

    :param registry: The Registry fixture.
    :param mock_cast: The mock_cast fixture.
    :returns: None
    """
    adapter = _chromecast_adapter.ChromecastAdapter(registry)
    registry._loop = asyncio.get_running_loop()  # type: ignore[reportPrivateUsage]

    # Pre-populate discovered casts
    adapter._discovered_casts[mock_cast.uuid] = mock_cast  # type: ignore[reportPrivateUsage]

    device = _types.Device(
        id=_types.DeviceID(str(mock_cast.uuid)),
        name=mock_cast.name,
        model=mock_cast.model_name,
        transport="chromecast",
        capabilities=set(),
        transport_info={"uuid": str(mock_cast.uuid)},
    )

    payload = _types.MediaPayload.from_url("http://example.com/media.mp4")

    with patch("asyncio.to_thread", side_effect=Exception("connection error")):
        result = await adapter.send_media(device, payload)

        assert not result.success
        assert result.reason == "connection error"


@pytest.mark.asyncio
async def test_send_media_device_not_found(
    registry: _registry.Registry, mock_cast: MagicMock
) -> None:
    """Test send_media with a device that hasn't been discovered.

    :param registry: The Registry fixture.
    :param mock_cast: The mock_cast fixture.
    :returns: None
    """
    adapter = _chromecast_adapter.ChromecastAdapter(registry)

    device = _types.Device(
        id=_types.DeviceID(str(mock_cast.uuid)),
        name=mock_cast.name,
        model=mock_cast.model_name,
        transport="chromecast",
        capabilities=set(),
        transport_info={"uuid": str(mock_cast.uuid)},
    )

    payload = _types.MediaPayload.from_url("http://example.com/media.mp4")
    result = await adapter.send_media(device, payload)

    assert not result.success
    assert result.reason == "device_not_found"


@pytest.mark.asyncio
async def test_adapter_reentrant_start(
    registry: _registry.Registry, mock_cast: MagicMock
) -> None:
    """Test calling start() multiple times.

    :param registry: The Registry fixture.
    :param mock_cast: The mock_cast fixture.
    :returns: None
    """
    adapter = _chromecast_adapter.ChromecastAdapter(registry)
    with patch("pychromecast.CastBrowser") as mock_browser_class:
        await adapter.start()
        await adapter.start()
        assert mock_browser_class.call_count == 1
        await adapter.stop()


@pytest.mark.asyncio
async def test_register_device_missing(registry: _registry.Registry) -> None:
    """Test _register_device with missing device.

    :param registry: The Registry fixture.
    :returns: None
    """
    adapter = _chromecast_adapter.ChromecastAdapter(registry)
    # Should return early without calling registry
    with patch.object(registry, "schedule_task") as mock_schedule:
        adapter._register_device(uuid.uuid4())  # type: ignore[reportPrivateUsage]
        mock_schedule.assert_not_called()


@pytest.mark.asyncio
async def test_send_media_guess_mime(
    registry: _registry.Registry, mock_cast: MagicMock, tmp_path: Path
) -> None:
    """Test send_media guessing mime type from path.

    :param registry: The Registry fixture.
    :param mock_cast: The mock_cast fixture.
    :param tmp_path: The tmp_path fixture.
    :returns: None
    """
    adapter = _chromecast_adapter.ChromecastAdapter(registry)
    adapter._discovered_casts[mock_cast.uuid] = mock_cast  # type: ignore[reportPrivateUsage]

    test_file = tmp_path / "test.mp4"
    test_file.write_bytes(b"data")

    device = _types.Device(
        id=_types.DeviceID(str(mock_cast.uuid)),
        name=mock_cast.name,
        model=mock_cast.model_name,
        transport="chromecast",
        capabilities=set(),
        transport_info={"uuid": str(mock_cast.uuid)},
    )

    payload = _types.MediaPayload.from_path(test_file)

    def _sync_to_thread(f: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return f(*args, **kwargs)

    with (
        patch("asyncio.to_thread", side_effect=_sync_to_thread),
        patch.object(registry, "register_media_payload", return_value="http://fake"),
    ):
        await adapter.send_media(device, payload)
        mock_cast.media_controller.play_media.assert_called_once()
        args, _ = mock_cast.media_controller.play_media.call_args
        assert args[1] == "video/mp4"


@pytest.mark.asyncio
async def test_on_device_lost_no_browser(
    registry: _registry.Registry, mock_cast: MagicMock
) -> None:
    """Test _on_device_lost when browser is None.

    :param registry: The Registry fixture.
    :param mock_cast: The mock_cast fixture.
    :returns: None
    """
    adapter = _chromecast_adapter.ChromecastAdapter(registry)
    # browser is None by default
    adapter._discovered_casts[mock_cast.uuid] = mock_cast  # type: ignore[reportPrivateUsage]
    adapter._on_device_lost(mock_cast.uuid, "Lost")  # type: ignore[reportPrivateUsage]
    assert mock_cast.uuid not in adapter._discovered_casts  # type: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_media_controller(mock_cast: MagicMock) -> None:
    """Test the Chromecast media controller.

    :param mock_cast: The mock_cast fixture.
    :returns: None
    """
    controller = _chromecast_adapter.ChromecastMediaController(mock_cast)

    def _sync_to_thread(f: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return f(*args, **kwargs)

    with patch("asyncio.to_thread", side_effect=_sync_to_thread):
        await controller.play()
        mock_cast.media_controller.play.assert_called_once()

        await controller.pause()
        mock_cast.media_controller.pause.assert_called_once()

        await controller.stop()
        mock_cast.media_controller.stop.assert_called_once()

        await controller.seek(10.0)
        mock_cast.media_controller.seek.assert_called_once_with(10.0)

        await controller.set_volume(0.5)
        mock_cast.set_volume.assert_called_once_with(0.5)

        await controller.set_mute(True)
        mock_cast.set_volume_muted.assert_called_once_with(True)
