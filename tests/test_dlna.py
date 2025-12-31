"""Tests for the DLNA backend."""

from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from async_upnp_client.const import SsdpSource

import commoncast.dlna.adapter as _dlna_adapter
import commoncast.registry as _registry
import commoncast.types as _types


@pytest.fixture
def registry() -> _registry.Registry:
    """Create a registry instance for testing.

    :returns: A Registry instance.
    """
    return _registry.Registry()


@pytest.fixture
def mock_dmr() -> MagicMock:
    """Create a mock DmrDevice object.

    :returns: A MagicMock simulating a DmrDevice.
    """
    dmr = MagicMock()
    dmr.device.udn = "uuid:test-udn"
    dmr.device.friendly_name = "Test DLNA Device"
    dmr.device.model_name = "Test Model"

    # Mock high-level methods
    dmr.async_play = AsyncMock()
    dmr.async_pause = AsyncMock()
    dmr.async_stop = AsyncMock()
    dmr.async_seek_rel_time = AsyncMock()
    dmr.async_set_volume_level = AsyncMock()
    dmr.async_mute_volume = AsyncMock()
    dmr.async_set_transport_uri = AsyncMock()
    dmr.construct_play_media_metadata = AsyncMock(return_value="<xml>metadata</xml>")

    return dmr


@pytest.mark.asyncio
async def test_adapter_discovery(
    registry: _registry.Registry, mock_dmr: MagicMock
) -> None:
    """Test DLNA adapter discovery process.

    :param registry: The Registry fixture.
    :param mock_dmr: The mock_dmr fixture.
    :returns: None
    """
    adapter = _dlna_adapter.DlnaAdapter(registry)

    with (
        patch("commoncast.dlna.adapter.SsdpListener") as mock_ssdp_class,
        patch("commoncast.dlna.adapter.UpnpFactory") as mock_factory_class,
        patch("commoncast.dlna.adapter.AiohttpSessionRequester"),
        patch("commoncast.dlna.adapter.DmrDevice") as mock_dmr_class,
        patch("aiohttp.ClientSession") as mock_session_class,
    ):
        mock_ssdp = mock_ssdp_class.return_value
        mock_ssdp.async_start = AsyncMock()
        mock_ssdp.async_search = AsyncMock()
        mock_ssdp.async_stop = AsyncMock()

        mock_session = mock_session_class.return_value
        mock_session.close = AsyncMock()

        mock_factory = mock_factory_class.return_value
        mock_factory.async_create_device = AsyncMock()

        # Setup device creation mock
        mock_device = MagicMock()
        mock_device.udn = "uuid:test-udn"
        mock_device.friendly_name = "Test DLNA Device"
        mock_device.model_name = "Test Model"
        mock_factory.async_create_device.return_value = mock_device

        mock_dmr_class.return_value = mock_dmr
        mock_dmr.device = mock_device

        await adapter.start()

        # Simulate device found
        mock_ssdp_device = MagicMock()
        mock_ssdp_device.location = "http://192.168.1.10:8080/desc.xml"
        mock_ssdp_device.udn = "uuid:test-udn"

        await adapter._on_device_found(  # type: ignore[reportPrivateUsage]
            mock_ssdp_device, "urn:schemas-upnp-org:device:MediaRenderer:1", MagicMock()
        )

        devices = registry.list_devices()
        assert len(devices) == 1
        assert devices[0].name == "Test DLNA Device"
        assert devices[0].transport == "dlna"

        await adapter.stop()


@pytest.mark.asyncio
async def test_send_media(registry: _registry.Registry, mock_dmr: MagicMock) -> None:
    """Test sending media to a DLNA device.

    :param registry: The Registry fixture.
    :param mock_dmr: The mock_dmr fixture.
    :returns: None
    """
    adapter = _dlna_adapter.DlnaAdapter(registry)
    adapter._discovered_devices["uuid:test-udn"] = mock_dmr  # type: ignore[reportPrivateUsage]

    device = _types.Device(
        id=_types.DeviceID("uuid:test-udn"),
        name="Test Device",
        model="Test Model",
        transport="dlna",
        capabilities=set(),
        transport_info={"udn": "uuid:test-udn"},
    )

    payload = _types.MediaPayload.from_url("http://example.com/media.mp4")

    result = await adapter.send_media(device, payload)

    assert result.success
    assert result.controller is not None

    mock_dmr.construct_play_media_metadata.assert_called_once()
    mock_dmr.async_set_transport_uri.assert_called_once()
    mock_dmr.async_play.assert_called_once()


@pytest.mark.asyncio
async def test_media_controller(mock_dmr: MagicMock) -> None:
    """Test the DLNA media controller.

    :param mock_dmr: The mock_dmr fixture.
    :returns: None
    """
    controller = _dlna_adapter.DlnaMediaController(mock_dmr)

    mock_dmr.can_play = True
    await controller.play()
    mock_dmr.async_play.assert_called_once()

    mock_dmr.can_pause = True
    await controller.pause()
    mock_dmr.async_pause.assert_called_once()

    mock_dmr.can_stop = True
    await controller.stop()
    mock_dmr.async_stop.assert_called_once()

    mock_dmr.can_seek_rel_time = True
    await controller.seek(65.0)
    # Check if called with timedelta
    mock_dmr.async_seek_rel_time.assert_called_with(timedelta(seconds=65.0))

    mock_dmr.has_volume_level = True
    await controller.set_volume(0.5)
    mock_dmr.async_set_volume_level.assert_called_with(0.5)

    mock_dmr.has_volume_mute = True
    await controller.set_mute(True)
    mock_dmr.async_mute_volume.assert_called_with(True)


@pytest.mark.asyncio
async def test_media_controller_no_caps(mock_dmr: MagicMock) -> None:
    """Test the DLNA media controller when capabilities are missing.

    :param mock_dmr: The mock_dmr fixture.
    :returns: None
    """
    controller = _dlna_adapter.DlnaMediaController(mock_dmr)

    mock_dmr.can_play = False
    await controller.play()
    mock_dmr.async_play.assert_not_called()

    mock_dmr.can_pause = False
    await controller.pause()
    mock_dmr.async_pause.assert_not_called()

    mock_dmr.can_stop = False
    await controller.stop()
    mock_dmr.async_stop.assert_not_called()

    mock_dmr.can_seek_rel_time = False
    await controller.seek(65.0)
    mock_dmr.async_seek_rel_time.assert_not_called()

    mock_dmr.has_volume_level = False
    await controller.set_volume(0.5)
    mock_dmr.async_set_volume_level.assert_not_called()

    mock_dmr.has_volume_mute = False
    await controller.set_mute(True)
    mock_dmr.async_mute_volume.assert_not_called()


@pytest.mark.asyncio
async def test_adapter_start_stop_edge_cases(registry: _registry.Registry) -> None:
    """Test start/stop edge cases for DlnaAdapter.

    :param registry: The Registry fixture.
    :returns: None
    """
    adapter = _dlna_adapter.DlnaAdapter(registry)

    with (
        patch("commoncast.dlna.adapter.SsdpListener") as mock_ssdp_class,
        patch("commoncast.dlna.adapter.UpnpFactory"),
        patch("commoncast.dlna.adapter.AiohttpSessionRequester"),
        patch("aiohttp.ClientSession") as mock_session_class,
    ):
        mock_ssdp = mock_ssdp_class.return_value
        mock_ssdp.async_start = AsyncMock()
        mock_ssdp.async_search = AsyncMock()
        mock_ssdp.async_stop = AsyncMock()
        mock_session = mock_session_class.return_value
        mock_session.close = AsyncMock()

        # Start once
        await adapter.start()
        assert adapter._ssdp_listener is not None  # type: ignore[reportPrivateUsage]

        # Start again - should return early
        await adapter.start()
        mock_ssdp_class.assert_called_once()

        # Stop
        await adapter.stop()
        assert adapter._ssdp_listener is None  # type: ignore[reportPrivateUsage]
        mock_ssdp.async_stop.assert_called_once()
        mock_session.close.assert_called_once()

        # Stop again - should handle safely
        await adapter.stop()


@pytest.mark.asyncio
async def test_on_device_found_edge_cases(
    registry: _registry.Registry, mock_dmr: MagicMock
) -> None:
    """Test edge cases in _on_device_found.

    :param registry: The Registry fixture.
    :param mock_dmr: The mock_dmr fixture.
    :returns: None
    """
    adapter = _dlna_adapter.DlnaAdapter(registry)
    adapter._upnp_factory = MagicMock()  # type: ignore[reportPrivateUsage]
    adapter._upnp_factory.async_create_device = AsyncMock()  # type: ignore[reportPrivateUsage]

    # Case: No location
    device = MagicMock()
    device.location = None
    await adapter._on_device_found(device, "dtype", MagicMock())  # type: ignore[reportPrivateUsage]
    assert len(adapter._discovered_devices) == 0  # type: ignore[reportPrivateUsage]

    # Case: Already discovered
    device.location = "http://loc"
    device.udn = "uuid:1"
    adapter._discovered_devices["uuid:1"] = mock_dmr  # type: ignore[reportPrivateUsage]
    await adapter._on_device_found(device, "dtype", MagicMock())  # type: ignore[reportPrivateUsage]
    # Should not call async_create_device again
    adapter._upnp_factory.async_create_device.assert_not_called()  # type: ignore[reportPrivateUsage]

    # Case: Not a MediaRenderer
    device.udn = "uuid:2"
    await adapter._on_device_found(device, "urn:other", MagicMock())  # type: ignore[reportPrivateUsage]
    assert "uuid:2" not in adapter._discovered_devices  # type: ignore[reportPrivateUsage]

    # Case: UpnpFactory is None
    adapter._upnp_factory = None  # type: ignore[reportPrivateUsage]
    await adapter._on_device_found(  # type: ignore[reportPrivateUsage]
        device, "urn:schemas-upnp-org:device:MediaRenderer:1", MagicMock()
    )

    # Case: Exception during device creation
    adapter._upnp_factory = MagicMock()  # type: ignore[reportPrivateUsage]
    adapter._upnp_factory.async_create_device = AsyncMock(side_effect=Exception("fail"))  # type: ignore[reportPrivateUsage]
    await adapter._on_device_found(  # type: ignore[reportPrivateUsage]
        device, "urn:schemas-upnp-org:device:MediaRenderer:1", MagicMock()
    )


@pytest.mark.asyncio
async def test_send_media_failures(registry: _registry.Registry) -> None:
    """Test failure cases in send_media.

    :param registry: The Registry fixture.
    :returns: None
    """
    adapter = _dlna_adapter.DlnaAdapter(registry)
    device = _types.Device(
        id=_types.DeviceID("uuid:none"),
        name="None",
        model="None",
        transport="dlna",
        capabilities=set(),
        transport_info={"udn": "uuid:none"},
    )
    payload = _types.MediaPayload.from_url("http://url")

    # Case: Device not found in discovered devices
    result = await adapter.send_media(device, payload)
    assert not result.success
    assert result.reason == "device_not_found"

    # Case: No URL and register_media_payload fails
    mock_dmr = MagicMock()
    adapter._discovered_devices["uuid:fail"] = mock_dmr  # type: ignore[reportPrivateUsage]
    device_fail = _types.Device(
        id=_types.DeviceID("uuid:fail"),
        name="Fail",
        model="Fail",
        transport="dlna",
        capabilities=set(),
        transport_info={"udn": "uuid:fail"},
    )
    payload.url = None
    payload.path = None

    with patch.object(registry, "register_media_payload", return_value=None):
        result = await adapter.send_media(device_fail, payload)
        assert not result.success
        assert result.reason == "media_server_not_available"

    # Case: Exception during send
    mock_dmr.construct_play_media_metadata = AsyncMock(
        side_effect=Exception("send_fail")
    )
    payload.url = "http://url"
    result = await adapter.send_media(device_fail, payload)
    assert not result.success
    assert result.reason == "send_fail"


@pytest.mark.asyncio
async def test_send_media_with_local_file(
    registry: _registry.Registry, mock_dmr: MagicMock
) -> None:
    """Test sending media with a local file path.

    :param registry: The Registry fixture.
    :param mock_dmr: The mock_dmr fixture.
    :returns: None
    """
    adapter = _dlna_adapter.DlnaAdapter(registry)
    adapter._discovered_devices["uuid:test-udn"] = mock_dmr  # type: ignore[reportPrivateUsage]

    device = _types.Device(
        id=_types.DeviceID("uuid:test-udn"),
        name="Test Device",
        model="Test Model",
        transport="dlna",
        capabilities=set(),
        transport_info={"udn": "uuid:test-udn"},
    )

    # Payload with path but no URL or mime_type
    payload = _types.MediaPayload(path=Path("test.mp4"))

    with patch.object(
        registry, "register_media_payload", return_value="http://local/test.mp4"
    ):
        result = await adapter.send_media(device, payload)

    assert result.success
    assert mock_dmr.async_set_transport_uri.called
    # Check that mime_type was guessed
    _, kwargs = mock_dmr.construct_play_media_metadata.call_args
    assert kwargs["override_mime_type"] == "video/mp4"


@pytest.mark.asyncio
async def test_on_device_lost(
    registry: _registry.Registry, mock_dmr: MagicMock
) -> None:
    """Test handling of BYEBYE messages.

    :param registry: The Registry fixture.
    :param mock_dmr: The mock_dmr fixture.
    :returns: None
    """
    adapter = _dlna_adapter.DlnaAdapter(registry)
    adapter._discovered_devices["uuid:test-udn"] = mock_dmr  # type: ignore[reportPrivateUsage]

    # Register it in registry too to see if it gets removed
    device = _types.Device(
        id=_types.DeviceID("uuid:test-udn"),
        name="Test Device",
        model="Test Model",
        transport="dlna",
        capabilities=set(),
        transport_info={"udn": "uuid:test-udn"},
    )
    await registry.register_device(device)
    assert len(registry.list_devices()) == 1

    mock_ssdp_device = MagicMock()
    mock_ssdp_device.udn = "uuid:test-udn"

    await adapter._on_device_found(  # type: ignore[reportPrivateUsage]
        mock_ssdp_device, "any", SsdpSource.ADVERTISEMENT_BYEBYE
    )

    assert "uuid:test-udn" not in adapter._discovered_devices  # type: ignore[reportPrivateUsage]
    assert len(registry.list_devices()) == 0
