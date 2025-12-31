"""Tests for the DIAL backend."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from async_upnp_client.const import SsdpSource

import commoncast.dial.adapter as _dial_adapter
import commoncast.registry as _registry
import commoncast.types as _types


@pytest.fixture
def registry() -> _registry.Registry:
    """Create a registry instance for testing.

    :returns: A Registry instance.
    """
    return _registry.Registry()


@pytest.mark.asyncio
async def test_adapter_discovery(registry: _registry.Registry) -> None:
    """Test DIAL adapter discovery process.

    :param registry: The Registry fixture.
    :returns: None
    """
    adapter = _dial_adapter.DialAdapter(registry)

    with (
        patch("commoncast.dial.adapter.SsdpListener") as mock_ssdp_class,
        patch("commoncast.dial.adapter.UpnpFactory") as mock_factory_class,
        patch("commoncast.dial.adapter.AiohttpSessionRequester"),
        patch("aiohttp.ClientSession") as mock_session_class,
    ):
        mock_ssdp = mock_ssdp_class.return_value
        mock_ssdp.async_start = AsyncMock()
        mock_ssdp.async_search = AsyncMock()
        mock_ssdp.async_stop = AsyncMock()

        mock_session = mock_session_class.return_value
        mock_session.close = AsyncMock()
        mock_session.get = MagicMock()

        mock_factory = mock_factory_class.return_value
        mock_factory.async_create_device = AsyncMock()

        # Setup device creation mock
        mock_device = MagicMock()
        mock_device.friendly_name = "Test DIAL Device"
        mock_device.model_name = "Test Model"
        mock_factory.async_create_device.return_value = mock_device

        await adapter.start()

        # Simulate device found
        mock_ssdp_device = MagicMock()
        mock_ssdp_device.location = "http://192.168.1.10:8008/ssdp/device-desc.xml"
        mock_ssdp_device.udn = "uuid:test-dial-udn"
        # Mock headers in SsdpDevice
        mock_ssdp_device.search_headers = {
            _dial_adapter.DIAL_SERVICE_TYPE: {
                "Application-URL": "http://192.168.1.10:8008/apps/"
            }
        }
        mock_ssdp_device.advertisement_headers = {}

        await adapter._on_device_found(  # type: ignore[reportPrivateUsage]
            mock_ssdp_device, _dial_adapter.DIAL_SERVICE_TYPE, MagicMock()
        )

        devices = registry.list_devices()
        assert len(devices) == 1
        assert devices[0].name == "Test DIAL Device"
        assert devices[0].transport == "dial"
        assert devices[0].transport_info["app_url"] == "http://192.168.1.10:8008/apps/"

        await adapter.stop()


@pytest.mark.asyncio
async def test_send_media(registry: _registry.Registry) -> None:
    """Test sending media to a DIAL device.

    :param registry: The Registry fixture.
    :returns: None
    """
    adapter = _dial_adapter.DialAdapter(registry)

    # Mock session
    mock_session = MagicMock()
    adapter._session = mock_session  # type: ignore[reportPrivateUsage]

    device = _types.Device(
        id=_types.DeviceID("uuid:test-dial-udn"),
        name="Test Device",
        model="Test Model",
        transport="dial",
        capabilities=set(),
        transport_info={
            "udn": "uuid:test-dial-udn",
            "app_url": "http://192.168.1.10:8008/apps/",
        },
    )

    payload = _types.MediaPayload.from_url("http://example.com/media.mp4")

    # Mock POST response
    mock_response = MagicMock()
    mock_response.status = 201
    mock_response.headers = {"Location": "http://192.168.1.10:8008/apps/YouTube/run"}

    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    result = await adapter.send_media(device, payload)

    assert result.success
    assert result.controller is not None

    # Check POST was called with correct URL and data
    mock_session.post.assert_called_once_with(
        "http://192.168.1.10:8008/apps/YouTube", data="http://example.com/media.mp4"
    )


@pytest.mark.asyncio
async def test_media_controller(registry: _registry.Registry) -> None:
    """Test the DIAL media controller.

    :param registry: The Registry fixture.
    :returns: None
    """
    mock_session = MagicMock()
    instance_url = "http://192.168.1.10:8008/apps/YouTube/run"
    controller = _dial_adapter.DialMediaController(mock_session, instance_url)

    # Test stop
    mock_response = MagicMock()
    mock_response.status = 200
    mock_session.delete.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session.delete.return_value.__aexit__ = AsyncMock(return_value=None)

    await controller.stop()
    mock_session.delete.assert_called_once_with(instance_url)

    # Test other methods (should be no-ops/warnings)
    await controller.play()
    await controller.pause()
    await controller.seek(10.0)
    await controller.set_volume(0.5)
    await controller.set_mute(True)


@pytest.mark.asyncio
async def test_on_device_lost(registry: _registry.Registry) -> None:
    """Test handling of device removal.

    :param registry: The Registry fixture.
    :returns: None
    """
    adapter = _dial_adapter.DialAdapter(registry)
    adapter._discovered_devices["uuid:test-dial-udn"] = {"udn": "uuid:test-dial-udn"}  # type: ignore[reportPrivateUsage]

    device = _types.Device(
        id=_types.DeviceID("uuid:test-dial-udn"),
        name="Test Device",
        model="Test Model",
        transport="dial",
        capabilities=set(),
        transport_info={"udn": "uuid:test-dial-udn"},
    )
    await registry.register_device(device)
    assert len(registry.list_devices()) == 1

    mock_ssdp_device = MagicMock()
    mock_ssdp_device.udn = "uuid:test-dial-udn"

    await adapter._on_device_found(  # type: ignore[reportPrivateUsage]
        mock_ssdp_device, "any", SsdpSource.ADVERTISEMENT_BYEBYE
    )

    assert "uuid:test-dial-udn" not in adapter._discovered_devices  # type: ignore[reportPrivateUsage]
    assert len(registry.list_devices()) == 0


@pytest.mark.asyncio
async def test_adapter_discovery_via_http_header(registry: _registry.Registry) -> None:
    """Test DIAL discovery when Application-URL is only in HTTP headers.

    :param registry: The Registry fixture.
    :returns: None
    """
    adapter = _dial_adapter.DialAdapter(registry)

    with (
        patch("commoncast.dial.adapter.SsdpListener") as mock_ssdp_class,
        patch("commoncast.dial.adapter.UpnpFactory") as mock_factory_class,
        patch("commoncast.dial.adapter.AiohttpSessionRequester"),
        patch("aiohttp.ClientSession") as mock_session_class,
    ):
        mock_ssdp = mock_ssdp_class.return_value
        mock_ssdp.async_start = AsyncMock()
        mock_ssdp.async_search = AsyncMock()
        mock_ssdp.async_stop = AsyncMock()

        mock_session = mock_session_class.return_value
        mock_session.close = AsyncMock()
        mock_session.get = MagicMock()

        # Mock GET response for location URL
        mock_get_response = MagicMock()
        mock_get_response.headers = {
            "Application-URL": "http://192.168.1.10:8008/apps/"
        }
        mock_session.get.return_value.__aenter__ = AsyncMock(
            return_value=mock_get_response
        )
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_factory = mock_factory_class.return_value
        mock_device = MagicMock()
        mock_device.friendly_name = "HTTP Header Device"
        mock_device.model_name = "Model"
        mock_factory.async_create_device = AsyncMock(return_value=mock_device)

        await adapter.start()

        mock_ssdp_device = MagicMock()
        mock_ssdp_device.location = "http://192.168.1.10:8008/ssdp/device-desc.xml"
        mock_ssdp_device.udn = "uuid:http-header-udn"
        mock_ssdp_device.search_headers = {}
        mock_ssdp_device.advertisement_headers = {}

        await adapter._on_device_found(  # type: ignore[reportPrivateUsage]
            mock_ssdp_device, _dial_adapter.DIAL_SERVICE_TYPE, SsdpSource.SEARCH_ALIVE
        )

        devices = registry.list_devices()
        assert len(devices) == 1
        assert devices[0].transport_info["app_url"] == "http://192.168.1.10:8008/apps/"

        await adapter.stop()


@pytest.mark.asyncio
async def test_send_media_relative_location(registry: _registry.Registry) -> None:
    """Test sending media with a relative Location header in response.

    :param registry: The Registry fixture.
    :returns: None
    """
    adapter = _dial_adapter.DialAdapter(registry)
    mock_session = MagicMock()
    adapter._session = mock_session  # type: ignore[reportPrivateUsage]

    device = _types.Device(
        id=_types.DeviceID("uuid:test-dial-udn"),
        name="Test Device",
        model="Test Model",
        transport="dial",
        capabilities=set(),
        transport_info={
            "udn": "uuid:test-dial-udn",
            "app_url": "http://192.168.1.10:8008/apps/",
        },
    )

    payload = _types.MediaPayload.from_url("http://example.com/media.mp4")

    # Mock POST response with relative Location
    mock_response = MagicMock()
    mock_response.status = 201
    mock_response.headers = {"Location": "run/123"}

    mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

    result = await adapter.send_media(device, payload, options={"app_name": "TestApp"})

    assert result.success
    assert result.controller is not None
    # Resolved URL: http://192.168.1.10:8008/apps/TestApp/run/123
    assert (
        result.controller._instance_url  # type: ignore[reportPrivateUsage]
        == "http://192.168.1.10:8008/apps/TestApp/run/123"
    )

    mock_session.post.assert_called_once_with(
        "http://192.168.1.10:8008/apps/TestApp", data="http://example.com/media.mp4"
    )


@pytest.mark.asyncio
async def test_send_media_via_media_server(registry: _registry.Registry) -> None:
    """Test sending media when it needs to be served by the internal server.

    :param registry: The Registry fixture.
    :returns: None
    """
    adapter = _dial_adapter.DialAdapter(registry)
    mock_session = MagicMock()
    adapter._session = mock_session  # type: ignore[reportPrivateUsage]

    # Mock registry's register_media_payload
    with patch.object(
        registry,
        "register_media_payload",
        return_value="http://127.0.0.1:12345/media/123",
    ):
        device = _types.Device(
            id=_types.DeviceID("uuid:test-dial-udn"),
            name="Test Device",
            model="Test Model",
            transport="dial",
            capabilities=set(),
            transport_info={
                "udn": "uuid:test-dial-udn",
                "app_url": "http://192.168.1.10:8008/apps/",
            },
        )

        # Payload without URL
        payload = _types.MediaPayload(
            mime_type="video/mp4",
            data=b"dummy",
        )

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_session.post.return_value.__aenter__ = AsyncMock(
            return_value=mock_response
        )
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await adapter.send_media(device, payload)

        assert result.success
        mock_session.post.assert_called_once_with(
            "http://192.168.1.10:8008/apps/YouTube",
            data="http://127.0.0.1:12345/media/123",
        )
