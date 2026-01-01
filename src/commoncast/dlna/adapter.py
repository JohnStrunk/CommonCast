"""DLNA adapter for CommonCast.

This module implements the DLNA backend using async-upnp-client.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

import aiohttp
from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.const import SsdpSource
from async_upnp_client.profiles.dlna import DmrDevice
from async_upnp_client.ssdp_listener import SsdpDevice, SsdpListener

import commoncast.types as _types

if TYPE_CHECKING:
    import commoncast.types as _types_mod
    from commoncast.registry import Registry

_LOGGER = logging.getLogger(__name__)

DISCOVERY_INTERVAL = 60.0  # Seconds between periodic searches


class DlnaMediaController(_types.MediaController):
    """Implementation of MediaController for DLNA devices."""

    def __init__(self, dmr_device: DmrDevice) -> None:
        """Initialize the controller.

        :param dmr_device: The DmrDevice object from async_upnp_client.
        """
        self._device = dmr_device

    async def play(self) -> None:
        """Resume playback.

        :returns: None
        """
        if self._device.can_play:
            await self._device.async_play()

    async def pause(self) -> None:
        """Pause playback.

        :returns: None
        """
        if self._device.can_pause:
            await self._device.async_pause()

    async def stop(self) -> None:
        """Stop playback and clear the session.

        :returns: None
        """
        if self._device.can_stop:
            await self._device.async_stop()

    async def seek(self, position: float) -> None:
        """Seek to a specific position in seconds.

        :param position: Target position in seconds.
        :returns: None
        """
        # DLNA expects timedelta for relative seek
        td = timedelta(seconds=position)
        if self._device.can_seek_rel_time:
            await self._device.async_seek_rel_time(td)

    async def set_volume(self, level: float) -> None:
        """Set the volume level.

        :param level: Volume level between 0.0 and 1.0.
        :returns: None
        """
        if self._device.has_volume_level:
            await self._device.async_set_volume_level(level)

    async def set_mute(self, mute: bool) -> None:
        """Mute or unmute the device.

        :param mute: True to mute, False to unmute.
        :returns: None
        """
        if self._device.has_volume_mute:
            await self._device.async_mute_volume(mute)


class DlnaAdapter(_types.BackendAdapter):
    """Adapter for DLNA devices."""

    def __init__(self, registry: Registry) -> None:
        """Initialize the adapter.

        :param registry: The CommonCast registry instance.
        """
        self._registry = registry
        self._ssdp_listener: SsdpListener | None = None
        self._upnp_factory: UpnpFactory | None = None
        self._discovered_devices: dict[str, DmrDevice] = {}
        self._requester: AiohttpSessionRequester | None = None
        self._session: aiohttp.ClientSession | None = None
        self._discovery_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start DLNA discovery.

        :returns: None
        """
        if self._ssdp_listener:
            return

        _LOGGER.info("Starting DLNA discovery")

        self._session = aiohttp.ClientSession()
        self._requester = AiohttpSessionRequester(self._session)
        self._upnp_factory = UpnpFactory(self._requester)

        self._ssdp_listener = SsdpListener(async_callback=self._on_device_found)
        await self._ssdp_listener.async_start()

        # Start periodic discovery task
        self._discovery_task = asyncio.create_task(self._periodic_discovery())

    async def stop(self) -> None:
        """Stop DLNA discovery.

        :returns: None
        """
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
            self._discovery_task = None

        if self._ssdp_listener:
            await self._ssdp_listener.async_stop()
            self._ssdp_listener = None

        self._discovered_devices.clear()
        self._requester = None
        self._upnp_factory = None

        if self._session:
            await self._session.close()
            self._session = None

    async def _periodic_discovery(self) -> None:
        """Periodically trigger SSDP search.

        :returns: None
        """
        # Wait for the registry to be fully started before sending probes.
        # This ensures the overall system is ready and avoids race conditions
        # during rapid startup/shutdown.
        await self._registry.wait_until_ready()

        while True:
            try:
                if self._ssdp_listener:
                    _LOGGER.debug("Triggering DLNA SSDP search")
                    await self._ssdp_listener.async_search()
            except Exception:
                _LOGGER.exception("Error during periodic DLNA discovery")

            await asyncio.sleep(DISCOVERY_INTERVAL)

    async def _on_device_found(
        self, device: SsdpDevice, dtype: str, source: SsdpSource
    ) -> None:
        """Handle new device found via SSDP.

        :param device: The SSDP device object.
        :param dtype: Device type string.
        :param source: Source of the advertisement.
        """
        if source == SsdpSource.ADVERTISEMENT_BYEBYE:
            if device.udn in self._discovered_devices:
                _LOGGER.info("DLNA device lost: %s", device.udn)
                self._discovered_devices.pop(device.udn)
                await self._registry.unregister_device(
                    _types.DeviceID(device.udn), reason="lost"
                )
            return

        # We assume 'location' property exists or we iterate locations
        location = device.location
        if not location:
            return

        # Check if we already know this UDN
        if device.udn in self._discovered_devices:
            return

        try:
            # We filter for MediaRenderers
            # The dtype might be 'urn:schemas-upnp-org:device:MediaRenderer:1' etc.
            if "MediaRenderer" not in dtype:
                return

            if self._upnp_factory is None:
                return

            upnp_device = await self._upnp_factory.async_create_device(location)

            # Check for DLNA compliance via X_DLNADOC
            dlna_doc: str | None = None
            try:
                if hasattr(upnp_device, "xml"):
                    root = upnp_device.xml
                    # Handle namespaces. DLNA namespace is typically urn:schemas-dlna-org:device-1-0
                    namespaces = {"dlna": "urn:schemas-dlna-org:device-1-0"}
                    # The X_DLNADOC element is usually under the device element
                    # We look for it recursively or just in the device description
                    for doc in root.findall(".//dlna:X_DLNADOC", namespaces):
                        if doc.text:
                            dlna_doc = doc.text.strip()
                            break
            except Exception:
                _LOGGER.debug("Failed to parse device XML for X_DLNADOC", exc_info=True)

            # Wrap in DmrDevice
            # DmrDevice init: (device: UpnpDevice, event_handler: UpnpEventHandler | None)
            dmr = DmrDevice(upnp_device, None)
            self._discovered_devices[device.udn] = dmr

            await self._register_device(dmr, location, dlna_doc)

        except Exception:
            _LOGGER.exception("Error creating UPnP device from %s", location)

    async def _register_device(
        self, dmr: DmrDevice, location: str, dlna_doc: str | None = None
    ) -> None:
        """Register device with CommonCast registry.

        :param dmr: The DmrDevice wrapper.
        :param location: The location URL of the device description.
        :param dlna_doc: The value of the X_DLNADOC element, if present.
        """
        device = dmr.device

        capabilities = {_types.Capability("video"), _types.Capability("audio")}

        # Extract supported media types from protocol info
        media_types: set[str] = set()
        # supported_protocols can be a list of strings
        supported_protocols: list[str] = cast(
            list[str], getattr(dmr, "supported_protocols", [])
        )
        for protocol_info in supported_protocols:
            # Protocol info format: protocol:network:contentFormat:additionalInfo
            parts: list[str] = protocol_info.split(":")
            if len(parts) > 2:  # noqa: PLR2004
                mime_type: str = parts[2]
                if mime_type and mime_type != "*":
                    media_types.add(mime_type)

        # Construct transport info
        transport_info = {
            "udn": device.udn,
            "location": location,
            "friendly_name": device.friendly_name,
            "model_name": device.model_name,
        }
        if dlna_doc:
            transport_info["dlna_doc"] = dlna_doc

        cc_device = _types.Device(
            id=_types.DeviceID(device.udn),
            name=device.friendly_name,
            model=device.model_name,
            transport="dlna",
            capabilities=capabilities,
            transport_info=transport_info,
            media_types=media_types,
        )

        await self._registry.register_device(cc_device)

    async def send_media(
        self,
        device: _types.Device,
        media: _types_mod.MediaPayload,
        *,
        format: str | None = None,
        timeout: float = 30.0,
        options: dict[str, Any] | None = None,
    ) -> _types.SendResult:
        """Send media to a DLNA device.

        :param device: The target Device.
        :param media: The MediaPayload to send.
        :param format: Optional format hint.
        :param timeout: Timeout in seconds.
        :param options: Optional transport-specific options.
        :returns: SendResult.
        """
        udn = str(device.transport_info.get("udn"))
        dmr = self._discovered_devices.get(udn)

        if not dmr:
            return _types.SendResult(success=False, reason="device_not_found")

        try:
            url = media.url
            if not url:
                payload_id = str(uuid.uuid4())
                url = self._registry.register_media_payload(payload_id, media)
                if not url:
                    return _types.SendResult(
                        success=False, reason="media_server_not_available"
                    )

            # DLNA 10.1.3.10.1: References to content binaries must be absolute URIs
            if not (url.startswith("http://") or url.startswith("https://")):
                _LOGGER.warning(
                    "Media URL '%s' does not appear to be an absolute HTTP URI, "
                    "which may fail on DLNA devices.",
                    url,
                )

            mime_type = media.mime_type or "application/octet-stream"
            if not media.mime_type and media.path:
                mime_type, _ = mimetypes.guess_type(str(media.path))
                mime_type = mime_type or "application/octet-stream"

            title = (
                media.metadata.title
                if (media.metadata and media.metadata.title)
                else "CommonCast Media"
            )

            # Construct metadata with explicit mime type
            metadata = await dmr.construct_play_media_metadata(
                url, media_title=title, override_mime_type=mime_type
            )

            await dmr.async_set_transport_uri(  # type: ignore[reportUnknownMemberType]
                url, media_title=title, meta_data=metadata
            )

            # Wait briefly for state transition if needed, then play
            await dmr.async_play()

            return _types.SendResult(
                success=True,
                controller=DlnaMediaController(dmr),
            )

        except Exception as e:
            _LOGGER.exception("Failed to send media to DLNA device")
            return _types.SendResult(success=False, reason=str(e))
