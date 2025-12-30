"""Chromecast adapter for CommonCast.

This module implements the Chromecast backend using the pychromecast library.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import uuid
from typing import TYPE_CHECKING, Any, cast

import pychromecast  # type: ignore

import commoncast.types as _types

if TYPE_CHECKING:
    import commoncast.types as _types_mod
    from commoncast.registry import Registry

_LOGGER = logging.getLogger(__name__)


class ChromecastMediaController(_types.MediaController):
    """Implementation of MediaController for Chromecast devices."""

    def __init__(self, cast_device: Any) -> None:
        """Initialize the controller.

        :param cast_device: The pychromecast Chromecast object.
        """
        self._cast = cast_device
        self._media_controller: Any = cast_device.media_controller

    async def play(self) -> None:
        """Resume playback.

        :returns: None
        """
        await asyncio.to_thread(self._media_controller.play)

    async def pause(self) -> None:
        """Pause playback.

        :returns: None
        """
        await asyncio.to_thread(self._media_controller.pause)

    async def stop(self) -> None:
        """Stop playback and clear the session.

        :returns: None
        """
        await asyncio.to_thread(self._media_controller.stop)

    async def seek(self, position: float) -> None:
        """Seek to a specific position in seconds.

        :param position: Target position in seconds.
        :returns: None
        """
        await asyncio.to_thread(self._media_controller.seek, position)

    async def set_volume(self, level: float) -> None:
        """Set the volume level.

        :param level: Volume level between 0.0 and 1.0.
        :returns: None
        """
        await asyncio.to_thread(self._cast.set_volume, level)

    async def set_mute(self, mute: bool) -> None:
        """Mute or unmute the device.

        :param mute: True to mute, False to unmute.
        :returns: None
        """
        await asyncio.to_thread(self._cast.set_volume_muted, mute)


class ChromecastAdapter(_types.BackendAdapter):
    """Adapter for Chromecast devices."""

    def __init__(self, registry: Registry) -> None:
        """Initialize the adapter.

        :param registry: The CommonCast registry instance.
        """
        self._registry = registry
        self._browser: Any | None = None
        self._discovered_casts: dict[uuid.UUID, Any] = {}

    async def start(self) -> None:
        """Start Chromecast discovery.

        :returns: None
        """
        if self._browser is not None:
            return

        _LOGGER.info("Starting Chromecast discovery")

        # pychromecast.get_chromecasts is synchronous and starts discovery
        # We'll use the browser for continuous discovery
        self._browser = pychromecast.CastBrowser(
            pychromecast.SimpleCastListener(
                self._on_device_found, self._on_device_lost, self._on_device_updated
            )
        )
        self._browser.start_discovery()

    async def stop(self) -> None:
        """Stop Chromecast discovery.

        :returns: None
        """
        if self._browser:
            self._browser.stop_discovery()
            self._browser = None
        self._discovered_casts.clear()

    def _on_device_found(self, uuid_val: uuid.UUID, name: str) -> None:
        """Handle new device found by the browser.

        :param uuid_val: Unique identifier of the device.
        :param name: Name of the device.
        """
        _LOGGER.info("Chromecast found: %s (%s)", name, uuid_val)
        if self._browser:
            cast_device = self._browser.devices[uuid_val]
            self._discovered_casts[uuid_val] = cast(
                Any, pychromecast
            ).get_chromecast_from_cast_info(cast_device, self._browser.zc)
            self._register_device(uuid_val)

    def _on_device_lost(self, uuid_val: uuid.UUID, name: str) -> None:
        """Handle device lost.

        :param uuid_val: Unique identifier of the device.
        :param name: Name of the device.
        """
        _LOGGER.info("Chromecast lost: %s (%s)", name, uuid_val)
        self._discovered_casts.pop(uuid_val, None)

        # Notify registry
        self._registry.schedule_task(
            self._registry.unregister_device(
                _types.DeviceID(str(uuid_val)), reason="lost"
            )
        )

    def _on_device_updated(self, uuid_val: uuid.UUID, name: str) -> None:
        """Handle device updated.

        :param uuid_val: Unique identifier of the device.
        :param name: Name of the device.
        """
        _LOGGER.debug("Chromecast updated: %s (%s)", name, uuid_val)
        # Re-register if needed
        self._register_device(uuid_val)

    def _register_device(self, uuid_val: uuid.UUID) -> None:
        """Register or update a device in the registry.

        :param uuid_val: Unique identifier of the device.
        """
        cast_device = self._discovered_casts.get(uuid_val)
        if not cast_device:
            return

        capabilities = {_types.Capability("video"), _types.Capability("audio")}
        # In a real implementation, we'd check cast_device.cast_type
        # for more specific capabilities (e.g. Audio only for Chromecast Audio)
        if cast_device.cast_type == "audio":
            capabilities = {_types.Capability("audio")}

        device = _types.Device(
            id=_types.DeviceID(str(uuid_val)),
            name=cast_device.name,
            model=cast_device.model_name,
            transport="chromecast",
            capabilities=capabilities,
            transport_info={"uuid": str(uuid_val)},
        )

        self._registry.schedule_task(self._registry.register_device(device))

    async def send_media(
        self,
        device: _types.Device,
        media: _types_mod.MediaPayload,
        *,
        format: str | None = None,
        timeout: float = 30.0,
        options: dict[str, Any] | None = None,
    ) -> _types.SendResult:
        """Send media to a Chromecast device.

        :param device: The target Device.
        :param media: The MediaPayload to send.
        :param format: Optional format hint.
        :param timeout: Timeout in seconds.
        :param options: Optional transport-specific options.
        :returns: SendResult.
        """
        cast_uuid = uuid.UUID(device.transport_info["uuid"])
        cast_device = self._discovered_casts.get(cast_uuid)

        if not cast_device:
            return _types.SendResult(success=False, reason="device_not_found")

        try:
            # Wait for connection
            await asyncio.to_thread(cast_device.wait)

            url = media.url
            if not url:
                # Use the embedded server
                payload_id = str(uuid.uuid4())
                url = self._registry.register_media_payload(payload_id, media)
                if not url:
                    return _types.SendResult(
                        success=False, reason="media_server_not_available"
                    )

            mime_type = media.mime_type or "application/octet-stream"
            # Default mime types if not provided
            if not media.mime_type and media.path:
                mime_type, _ = mimetypes.guess_type(str(media.path))
                mime_type = mime_type or "application/octet-stream"

            title = media.metadata.title if media.metadata else "CommonCast Media"

            # Start the default media receiver
            await asyncio.to_thread(
                cast_device.media_controller.play_media, url, mime_type, title=title
            )

            return _types.SendResult(
                success=True,
                controller=ChromecastMediaController(cast_device),
            )
        except Exception as e:
            _LOGGER.exception("Failed to send media to Chromecast")
            return _types.SendResult(success=False, reason=str(e))
