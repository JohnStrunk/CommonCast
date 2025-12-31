"""DIAL adapter for CommonCast.

This module implements the DIAL (Discovery and Launch) backend.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urljoin

import aiohttp
from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.const import SsdpSource
from async_upnp_client.ssdp_listener import SsdpDevice, SsdpListener

import commoncast.types as _types

if TYPE_CHECKING:
    import commoncast.types as _types_mod
    from commoncast.registry import Registry

_LOGGER = logging.getLogger(__name__)

DIAL_SERVICE_TYPE = "urn:dial-multiscreen-org:service:dial:1"


class DialMediaController(_types.MediaController):
    """Implementation of MediaController for DIAL devices.

    DIAL itself only supports discovery and launching apps. Playback control
    is usually app-specific. This controller provides a basic implementation
    that supports stopping the app instance if it was tracked.
    """

    def __init__(
        self, session: aiohttp.ClientSession, instance_url: str | None
    ) -> None:
        """Initialize the controller.

        :param session: aiohttp ClientSession for making requests.
        :param instance_url: The URL of the app instance, used for stopping.
        """
        self._session = session
        self._instance_url = instance_url

    async def play(self) -> None:
        """Resume playback. (Not supported by generic DIAL).

        :returns: None
        """
        _LOGGER.warning("play() is not supported by generic DIAL")

    async def pause(self) -> None:
        """Pause playback. (Not supported by generic DIAL).

        :returns: None
        """
        _LOGGER.warning("pause() is not supported by generic DIAL")

    async def stop(self) -> None:
        """Stop playback by deleting the app instance.

        :returns: None
        """
        if not self._instance_url:
            _LOGGER.warning("No instance URL available to stop")
            return

        try:
            async with self._session.delete(self._instance_url) as response:
                if response.status not in (200, 204):
                    _LOGGER.error("Failed to stop DIAL instance: %s", response.status)
        except Exception:
            _LOGGER.exception("Error stopping DIAL instance")

    async def seek(self, position: float) -> None:
        """Seek to a specific position. (Not supported by generic DIAL).

        :param position: Target position in seconds.
        :returns: None
        """
        _LOGGER.warning("seek() is not supported by generic DIAL")

    async def set_volume(self, level: float) -> None:
        """Set the volume level. (Not supported by generic DIAL).

        :param level: Volume level between 0.0 and 1.0.
        :returns: None
        """
        _LOGGER.warning("set_volume() is not supported by generic DIAL")

    async def set_mute(self, mute: bool) -> None:
        """Mute or unmute the device. (Not supported by generic DIAL).

        :param mute: True to mute, False to unmute.
        :returns: None
        """
        _LOGGER.warning("set_mute() is not supported by generic DIAL")


class DialAdapter(_types.BackendAdapter):
    """Adapter for DIAL devices."""

    def __init__(self, registry: Registry) -> None:
        """Initialize the adapter.

        :param registry: The CommonCast registry instance.
        """
        self._registry = registry
        self._ssdp_listener: SsdpListener | None = None
        self._upnp_factory: UpnpFactory | None = None
        self._discovered_devices: dict[str, dict[str, Any]] = {}
        self._session: aiohttp.ClientSession | None = None
        self._requester: AiohttpSessionRequester | None = None

    async def start(self) -> None:
        """Start DIAL discovery.

        :returns: None
        """
        if self._ssdp_listener:
            return

        _LOGGER.info("Starting DIAL discovery")

        self._session = aiohttp.ClientSession()
        self._requester = AiohttpSessionRequester(self._session)
        self._upnp_factory = UpnpFactory(self._requester)
        self._ssdp_listener = SsdpListener(
            async_callback=self._on_device_found, search_target=DIAL_SERVICE_TYPE
        )
        await self._ssdp_listener.async_start()

        # Search for DIAL service
        await self._ssdp_listener.async_search()

    async def stop(self) -> None:
        """Stop DIAL discovery.

        :returns: None
        """
        if self._ssdp_listener:
            await self._ssdp_listener.async_stop()
            self._ssdp_listener = None

        self._discovered_devices.clear()
        self._upnp_factory = None
        self._requester = None

        if self._session:
            await self._session.close()
            self._session = None

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
                _LOGGER.info("DIAL device lost: %s", device.udn)
                self._discovered_devices.pop(device.udn)
                await self._registry.unregister_device(
                    _types.DeviceID(device.udn), reason="lost"
                )
            return

        if DIAL_SERVICE_TYPE not in dtype:
            return

        location = device.location
        if not location:
            return

        if device.udn in self._discovered_devices:
            return

        try:
            # We need to find the Application-URL.
            # It might be in the SSDP headers.
            app_url: str | None = None
            headers = cast(
                Mapping[Any, Any],
                device.search_headers.get(dtype)
                or device.advertisement_headers.get(dtype),
            )
            if headers:
                # Case-insensitive check for Application-URL
                for key, value in headers.items():
                    if str(key).lower() == "application-url":
                        app_url = str(value)
                        break

            friendly_name = "DIAL Device"
            model_name = "Generic DIAL"

            # Fetch device description for friendly name and potentially Application-URL
            if self._upnp_factory:
                upnp_device = await self._upnp_factory.async_create_device(location)
                friendly_name = upnp_device.friendly_name
                model_name = upnp_device.model_name

                if not app_url and self._session:
                    # If not in SSDP headers, we must fetch it from the Location URL headers.
                    async with self._session.get(location) as response:
                        app_url = response.headers.get("Application-URL")

            if not app_url:
                _LOGGER.debug("Could not find Application-URL for %s", location)
                return

            self._discovered_devices[device.udn] = {
                "udn": device.udn,
                "location": location,
                "app_url": app_url,
            }

            await self._register_device(device.udn, friendly_name, model_name, app_url)

        except Exception:
            _LOGGER.exception("Error processing DIAL device from %s", location)

    async def _register_device(
        self, udn: str, name: str, model: str, app_url: str
    ) -> None:
        """Register device with CommonCast registry.

        :param udn: Unique device name.
        :param name: Friendly name.
        :param model: Model name.
        :param app_url: DIAL Application-URL.
        """
        device = _types.Device(
            id=_types.DeviceID(udn),
            name=name,
            model=model,
            transport="dial",
            capabilities={_types.Capability("video"), _types.Capability("audio")},
            transport_info={
                "udn": udn,
                "app_url": app_url,
            },
        )
        await self._registry.register_device(device)

    async def send_media(
        self,
        device: _types.Device,
        media: _types_mod.MediaPayload,
        *,
        format: str | None = None,
        timeout: float = 30.0,
        options: dict[str, Any] | None = None,
    ) -> _types.SendResult:
        """Send media to a DIAL device.

        :param device: The target Device.
        :param media: The MediaPayload to send.
        :param format: Optional format hint.
        :param timeout: Timeout in seconds.
        :param options: Optional transport-specific options.
        :returns: SendResult.
        """
        app_url = device.transport_info.get("app_url")
        if not app_url:
            return _types.SendResult(success=False, reason="missing_app_url")

        if self._session is None:
            return _types.SendResult(success=False, reason="no_session")

        # Options can specify the app name. Default to "YouTube" as a common one,
        # or maybe we should have a better default.
        app_name = (options or {}).get("app_name", "YouTube")

        # Construct launch URL: [Application-URL]/[appName]
        if not app_url.endswith("/"):
            app_url += "/"
        launch_url = app_url + app_name

        try:
            url = media.url
            if not url:
                payload_id = str(uuid.uuid4())
                url = self._registry.register_media_payload(payload_id, media)
                if not url:
                    return _types.SendResult(
                        success=False, reason="media_server_not_available"
                    )

            # DIAL launch payload is app-specific.
            # For YouTube, it's often v=[videoId]
            # For a generic media player, it might be the URL itself.
            # We'll try sending the URL as the POST body.

            async with self._session.post(launch_url, data=url) as response:
                if response.status in (200, 201, 204):
                    instance_url = response.headers.get("Location")
                    # If instance_url is relative, resolve it against launch_url
                    if instance_url and not instance_url.startswith("http"):
                        instance_url = urljoin(launch_url + "/", instance_url)

                    return _types.SendResult(
                        success=True,
                        controller=DialMediaController(self._session, instance_url),
                    )
                else:
                    return _types.SendResult(
                        success=False,
                        reason=f"Failed to launch app: {response.status}",
                    )

        except Exception as e:
            _LOGGER.exception("Failed to send media via DIAL")
            return _types.SendResult(success=False, reason=str(e))
