"""CommonCast public API.

This module implements the user-facing API for CommonCast. It provides a
small, async-first surface with synchronous convenience wrappers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping

import commoncast.event as _event
import commoncast.registry as _registry
import commoncast.types as _types

# Re-export types for public API
BackendInfo = _registry.BackendInfo
Capability = _types.Capability
Device = _types.Device
DeviceID = _types.DeviceID
MediaController = _types.MediaController
MediaImage = _types.MediaImage
MediaMetadata = _types.MediaMetadata
MediaPayload = _types.MediaPayload
SendResult = _types.SendResult
Subscription = _types.Subscription

# Re-export events for public API
DeviceAdded = _event.DeviceAdded
DeviceEvent = _types.DeviceEvent
DeviceHeartbeat = _event.DeviceHeartbeat
DeviceRemoved = _event.DeviceRemoved
DeviceUpdated = _event.DeviceUpdated
MediaStatusUpdated = _event.MediaStatusUpdated
VolumeUpdated = _event.VolumeUpdated


def list_devices() -> list[_types.Device]:
    """Return a snapshot list of known devices (non-blocking).

    :returns: List of discovered Device instances.
    """
    return _registry.default_registry.list_devices()


def subscribe(
    callback: Callable[[_event.DeviceEvent], Awaitable[None]],
) -> _types.Subscription:
    """Register an async callback to receive DeviceEvent objects.

    The callback will be scheduled on the running event loop for each event.

    :param callback: Async callable that accepts a DeviceEvent.
    :returns: Subscription handle with an unsubscribe() method.
    """
    return _registry.default_registry.subscribe(callback)


def subscribe_sync(
    callback: Callable[[_event.DeviceEvent], None],
) -> _types.Subscription:
    """Register a synchronous callback executed on a threadpool for each event.

    :param callback: Synchronous callable that accepts a DeviceEvent.
    :returns: Subscription handle with an unsubscribe() method.
    """
    return _registry.default_registry.subscribe_sync(callback)


def events() -> AsyncIterator[_event.DeviceEvent]:
    """Return an async iterator that yields DeviceEvent objects as they occur.

    :returns: Async iterator yielding DeviceEvent objects.
    """
    return _registry.default_registry.events()


async def start(*, media_host: str | None = "0.0.0.0", media_port: int = 0) -> None:
    """Start background discovery and (optionally) the embedded media server.

    If media_host is None the embedded media server is not started.

    :param media_host: Host interface to bind the media server to, or None to
        disable the embedded server.
    :param media_port: Port to bind the media server to (0 selects a free port).
    :returns: None
    """
    await _registry.default_registry.start(media_host=media_host, media_port=media_port)


async def stop() -> None:
    """Stop background discovery and shut down adapters and media server.

    :returns: None
    """
    await _registry.default_registry.stop()


def start_sync(*, media_host: str | None = "0.0.0.0", media_port: int = 0) -> None:
    """Start the system synchronously (convenience wrapper for start()).

    :param media_host: Host interface to bind the media server to, or None to
        disable the embedded server.
    :param media_port: Port to bind the media server to (0 selects a free port).
    :returns: None
    """
    _registry.default_registry.start_sync(media_host=media_host, media_port=media_port)


def stop_sync() -> None:
    """Stop the system synchronously (convenience wrapper for stop()).

    :returns: None
    """
    _registry.default_registry.stop_sync()


def enable_backend(name: str) -> None:
    """Enable a named protocol backend (e.g., 'chromecast').

    :param name: Backend name to enable.
    :returns: None
    """
    _registry.default_registry.enable_backend(name)


def disable_backend(name: str) -> None:
    """Disable a named protocol backend.

    :param name: Backend name to disable.
    :returns: None
    """
    _registry.default_registry.disable_backend(name)


def list_backends() -> Mapping[str, BackendInfo]:
    """Return a mapping of available backends to their state information.

    :returns: Mapping of backend name to status information.
    """
    return _registry.default_registry.list_backends()


__all__ = [
    "BackendInfo",
    "Capability",
    "Device",
    "DeviceAdded",
    "DeviceEvent",
    "DeviceHeartbeat",
    "DeviceID",
    "DeviceRemoved",
    "DeviceUpdated",
    "MediaController",
    "MediaImage",
    "MediaMetadata",
    "MediaPayload",
    "MediaStatusUpdated",
    "SendResult",
    "Subscription",
    "VolumeUpdated",
    "disable_backend",
    "enable_backend",
    "events",
    "list_backends",
    "list_devices",
    "start",
    "start_sync",
    "stop",
    "stop_sync",
    "subscribe",
    "subscribe_sync",
]
