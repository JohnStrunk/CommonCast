"""Common data types and models for CommonCast.

This module contains the core data structures used throughout the library
to avoid circular import issues.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, NewType, cast

# Strongly-typed device identifier
DeviceID = NewType("DeviceID", str)
# Stable unique identifier for a discovered device.

Capability = NewType("Capability", str)
# Representation of a device capability.


@dataclass
class DeviceEvent:
    """Base class for device lifecycle events emitted by the registry.

    :param timestamp: Time the event was observed (timezone-aware UTC).
    """

    timestamp: datetime


@dataclass
class MediaImage:
    """Representation of a media image (e.g., album art).

    :param url: URL of the image.
    :param width: Optional width in pixels.
    :param height: Optional height in pixels.
    """

    url: str
    width: int | None = None
    height: int | None = None


@dataclass
class MediaMetadata:
    """Rich metadata for media content.

    :param title: Content title.
    :param subtitle: Content subtitle or description.
    :param artist: Artist name (music).
    :param album: Album name (music).
    :param images: List of associated images.
    :param type: Generic type hint (e.g., 'movie', 'music', 'photo').
    :param extra: Transport-specific extra metadata.
    """

    title: str | None = None
    subtitle: str | None = None
    artist: str | None = None
    album: str | None = None
    images: list[MediaImage] = field(default_factory=lambda: cast(list[MediaImage], []))
    type: str | None = None
    extra: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))


class MediaController(ABC):
    """Abstract base class for controlling active media playback."""

    @abstractmethod
    async def play(self) -> None:
        """Resume playback.

        :returns: None
        """
        ...

    @abstractmethod
    async def pause(self) -> None:
        """Pause playback.

        :returns: None
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop playback and clear the session.

        :returns: None
        """
        ...

    @abstractmethod
    async def seek(self, position: float) -> None:
        """Seek to a specific position in seconds.

        :param position: Target position in seconds from the beginning.
        :returns: None
        """
        ...

    @abstractmethod
    async def set_volume(self, level: float) -> None:
        """Set the volume level.

        :param level: Volume level between 0.0 and 1.0.
        :returns: None
        """
        ...

    @abstractmethod
    async def set_mute(self, mute: bool) -> None:
        """Mute or unmute the device.

        :param mute: True to mute, False to unmute.
        :returns: None
        """
        ...


@dataclass(init=False)
class SendResult:
    """Result describing outcome of a send_media operation."""

    success: bool
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))
    controller: MediaController | None = None

    def __init__(
        self,
        success: bool,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        controller: MediaController | None = None,
    ) -> None:
        """Initialize a SendResult.

        :param success: True when the send completed successfully.
        :param reason: Optional human-readable failure reason when success is False.
        :param metadata: Optional additional metadata returned by the transport.
        :param controller: Optional MediaController if a session was established.
        :returns: None
        """
        self.success = success
        self.reason = reason
        self.metadata = metadata or {}
        self.controller = controller


@dataclass(init=False)
class MediaPayload:
    """A container representing media to send to a device."""

    data: bytes | None
    path: Path | None
    url: str | None
    mime_type: str | None = None
    size: int | None = None
    metadata: MediaMetadata | None = None

    def __init__(  # noqa: PLR0913
        self,
        data: bytes | None = None,
        path: Path | None = None,
        url: str | None = None,
        mime_type: str | None = None,
        size: int | None = None,
        metadata: MediaMetadata | None = None,
    ) -> None:
        """Initialize a MediaPayload.

        :param data: Raw bytes for the payload when available.
        :param path: Local filesystem path to the media when used.
        :param url: Remote URL referencing the media when used.
        :param mime_type: Optional mime-type hint.
        :param size: Optional size in bytes.
        :param metadata: Optional rich metadata for the media.
        :returns: None
        """
        self.data = data
        self.path = path
        self.url = url
        self.mime_type = mime_type
        self.size = size
        self.metadata = metadata

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        mime_type: str | None = None,
        metadata: MediaMetadata | None = None,
    ) -> MediaPayload:
        """Create a MediaPayload from raw bytes.

        :param data: Raw bytes for the payload.
        :param mime_type: Optional mime-type hint.
        :param metadata: Optional rich metadata.
        :returns: MediaPayload instance containing the bytes.
        """
        return cls(
            data=data,
            path=None,
            url=None,
            mime_type=mime_type,
            size=len(data),
            metadata=metadata,
        )

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        mime_type: str | None = None,
        metadata: MediaMetadata | None = None,
    ) -> MediaPayload:
        """Create a MediaPayload from a local filesystem path.

        :param path: Path to the local media file.
        :param mime_type: Optional mime-type hint.
        :param metadata: Optional rich metadata.
        :returns: MediaPayload referencing the path.
        """
        p = Path(path)
        return cls(
            data=None,
            path=p,
            url=None,
            mime_type=mime_type,
            size=p.stat().st_size if p.exists() else None,
            metadata=metadata,
        )

    @classmethod
    def from_url(
        cls,
        url: str,
        mime_type: str | None = None,
        metadata: MediaMetadata | None = None,
    ) -> MediaPayload:
        """Create a MediaPayload referencing a remote URL.

        :param url: Remote URL for the media.
        :param mime_type: Optional mime-type hint.
        :param metadata: Optional rich metadata.
        :returns: MediaPayload referencing the URL.
        """
        return cls(
            data=None,
            path=None,
            url=url,
            mime_type=mime_type,
            size=None,
            metadata=metadata,
        )


@dataclass(init=False)
class Device:
    """Representation of a discovered renderer device."""

    id: DeviceID
    name: str
    model: str | None
    transport: str
    capabilities: set[Capability]
    transport_info: Mapping[str, Any]

    def __init__(  # noqa: PLR0913
        self,
        id: DeviceID,
        name: str,
        model: str | None,
        transport: str,
        capabilities: set[Capability],
        transport_info: Mapping[str, Any],
    ) -> None:
        """Initialize a Device instance.

        :param id: Stable device identifier.
        :param name: Human-friendly device name.
        :param model: Optional model string reported by the device.
        :param transport: Underlying transport name (e.g., "chromecast").
        :param capabilities: Declared device capabilities.
        :param transport_info: Transport-specific connection details.
        :returns: None
        """
        self.id = id
        self.name = name
        self.model = model
        self.transport = transport
        self.capabilities = capabilities
        self.transport_info = transport_info

    async def send_media(
        self,
        media: MediaPayload,
        *,
        title: str | None = None,
        format: str | None = None,
        timeout: float = 30.0,
        options: dict[str, Any] | None = None,
    ) -> SendResult:
        """Send media to this device (async).

        :param media: MediaPayload describing the content to send.
        :param title: Optional user-visible title (deprecated, use media.metadata).
        :param format: Optional transport-specific format hint.
        :param timeout: Operation timeout in seconds.
        :param options: Optional transport-specific launch options (e.g. app_id).
        :returns: SendResult describing success or failure, optionally containing
                  a MediaController.
        """
        # Lazy import to avoid circular dependencies
        import commoncast.registry as _registry  # noqa: PLC0415

        # Backfill legacy title into metadata if not present
        if title and not media.metadata:
            media.metadata = MediaMetadata(title=title)
        elif title and media.metadata and not media.metadata.title:
            media.metadata.title = title

        return await _registry.default_registry.send_media(
            self, media, format=format, timeout=timeout, options=options
        )

    def send_media_sync(
        self,
        media: MediaPayload,
        *,
        title: str | None = None,
        format: str | None = None,
        timeout: float = 30.0,
        options: dict[str, Any] | None = None,
    ) -> SendResult:
        """Run the async send_media in a synchronous context.

        :param media: MediaPayload describing the content to send.
        :param title: Optional user-visible title.
        :param format: Optional transport-specific format hint.
        :param timeout: Operation timeout in seconds.
        :param options: Optional transport-specific launch options.
        :returns: SendResult describing success or failure.

        Note: This calls asyncio.run and must not be used from inside an
        already-running event loop.
        """
        return asyncio.run(
            self.send_media(
                media, title=title, format=format, timeout=timeout, options=options
            )
        )


class Subscription:
    """Lightweight handle for an event subscription with an unsubscribe method.

    :param unsubscribe: Callable invoked to cancel the subscription.
    """

    def __init__(self, unsubscribe: Callable[[], None]):
        """Create a Subscription that calls the provided unsubscribe function.

        :param unsubscribe: Callable invoked to cancel the subscription.
        :returns: None
        """
        self._unsubscribe = unsubscribe

    def unsubscribe(self) -> None:
        """Cancel the subscription and stop receiving events.

        :returns: None
        """
        self._unsubscribe()


class BackendAdapter(ABC):
    """Abstract base class for backend adapters."""

    @abstractmethod
    async def start(self) -> None:
        """Start the backend adapter.

        :returns: None
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the backend adapter.

        :returns: None
        """
        ...

    @abstractmethod
    async def send_media(
        self,
        device: Device,
        media: MediaPayload,
        *,
        format: str | None = None,
        timeout: float = 30.0,
        options: dict[str, Any] | None = None,
    ) -> SendResult:
        """Send media to a device.

        :param device: Target Device.
        :param media: MediaPayload to send.
        :param format: Optional format hint.
        :param timeout: Operation timeout in seconds.
        :param options: Optional transport-specific options.
        :returns: SendResult describing the outcome.
        """
        ...


__all__ = [
    "BackendAdapter",
    "Capability",
    "Device",
    "DeviceEvent",
    "DeviceID",
    "MediaController",
    "MediaImage",
    "MediaMetadata",
    "MediaPayload",
    "SendResult",
    "Subscription",
]
