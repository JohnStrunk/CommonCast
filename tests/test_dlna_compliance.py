"""Tests for DLNA compliance features."""

import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import commoncast.dlna.adapter as _dlna_adapter
import commoncast.registry as _registry
import commoncast.types as _types


@pytest.fixture
def registry() -> _registry.Registry:
    """Create a registry instance for testing.

    :returns: A Registry instance.
    """
    return _registry.Registry()


@pytest.mark.asyncio
async def test_x_dlnadoc_discovery(registry: _registry.Registry) -> None:
    """Test that X_DLNADOC is parsed from device XML."""
    adapter = _dlna_adapter.DlnaAdapter(registry)

    # Mock XML with X_DLNADOC
    xml_content = """
    <root xmlns="urn:schemas-upnp-org:device-1-0" xmlns:dlna="urn:schemas-dlna-org:device-1-0">
        <device>
            <dlna:X_DLNADOC>DMR-1.50</dlna:X_DLNADOC>
            <friendlyName>Test DLNA Device</friendlyName>
            <UDN>uuid:test-udn</UDN>
        </device>
    </root>
    """

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

        # Mock UpnpDevice
        mock_device = MagicMock()
        mock_device.udn = "uuid:test-udn"
        mock_device.friendly_name = "Test DLNA Device"
        mock_device.model_name = "Test Model"
        mock_device.xml = ET.fromstring(xml_content)
        mock_factory.async_create_device = AsyncMock(return_value=mock_device)

        # Mock DmrDevice wrapper
        mock_dmr = MagicMock()
        mock_dmr.device = mock_device
        mock_dmr_class.return_value = mock_dmr

        await adapter.start()

        # Simulate finding the device
        mock_ssdp_device = MagicMock()
        mock_ssdp_device.location = "http://192.168.1.10:8080/desc.xml"
        mock_ssdp_device.udn = "uuid:test-udn"

        await adapter._on_device_found(  # type: ignore[reportPrivateUsage]
            mock_ssdp_device, "urn:schemas-upnp-org:device:MediaRenderer:1", MagicMock()
        )

        devices = registry.list_devices()
        assert len(devices) == 1
        assert devices[0].transport_info.get("dlna_doc") == "DMR-1.50"

        await adapter.stop()


@pytest.mark.asyncio
async def test_send_media_url_warning(registry: _registry.Registry) -> None:
    """Test that send_media logs a warning for non-absolute HTTP URIs."""
    adapter = _dlna_adapter.DlnaAdapter(registry)

    # Mock a discovered device
    mock_dmr = MagicMock()
    mock_dmr.construct_play_media_metadata = AsyncMock(return_value="<xml/>")
    mock_dmr.async_set_transport_uri = AsyncMock()
    mock_dmr.async_play = AsyncMock()

    adapter._discovered_devices["uuid:test"] = mock_dmr  # type: ignore[reportPrivateUsage]

    device = _types.Device(
        id=_types.DeviceID("uuid:test"),
        name="Test",
        model="Model",
        transport="dlna",
        capabilities=set(),
        transport_info={"udn": "uuid:test"},
    )

    # Payload with relative URL (invalid for DLNA)
    payload = _types.MediaPayload(url="relative/path/movie.mp4")

    with patch("commoncast.dlna.adapter._LOGGER") as mock_logger:
        await adapter.send_media(device, payload)

        # Verify warning was logged
        warning_calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "absolute HTTP URI" in call[0][0]
        ]
        assert len(warning_calls) > 0
