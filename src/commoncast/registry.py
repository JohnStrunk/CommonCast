"""Registry implementation for CommonCast.

This module contains the Registry class that manages discovered devices,
subscriptions, backends, and event publication.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, TypedDict, cast

import commoncast.chromecast.adapter as _chromecast_adapter
import commoncast.event as _events
import commoncast.server as _server
import commoncast.types as _types

_LOGGER = logging.getLogger(__name__)


class BackendInfo(TypedDict, total=False):
    """Configuration for a backend adapter."""

    enabled: bool


def _safe_call_sync(
    cb: Callable[[_events.DeviceEvent], None], ev: _events.DeviceEvent
) -> None:
    """Call a synchronous subscriber safely on a background thread.

    Exceptions are swallowed to avoid propagating user errors into the
    registry internals.

    :param cb: Synchronous callback accepting a DeviceEvent.
    :param ev: The event to deliver.
    :returns: None
    """
    try:
        cb(ev)
    except Exception:
        # Swallow exceptions from user callbacks to avoid crashing the threadpool.
        pass


class Registry:
    """Device registry used by the public API.

    The registry maintains a snapshot of discovered devices and provides both
    push (subscriptions) and pull (async iterator) models for events.
    """

    def __init__(self) -> None:
        """Create a new Registry instance.

        Initializes internal state used to track devices and subscribers.

        :returns: None
        """
        self._devices: dict[_events.DeviceID, _types.Device] = {}
        self._event_queue: asyncio.Queue[_events.DeviceEvent] = asyncio.Queue()
        self._subscribers: list[Callable[[_events.DeviceEvent], Awaitable[None]]] = []
        self._subscribers_sync: list[Callable[[_events.DeviceEvent], None]] = []
        self._backends: dict[str, BackendInfo] = {}
        self._adapters: dict[str, _types.BackendAdapter] = {}
        self._media_server: _server.MediaServer | None = None
        # Use a set to hold strong references to background tasks
        self._tasks: set[asyncio.Task[None]] = set()
        self._running = False
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def list_devices(self) -> list[_types.Device]:
        """Return a snapshot list of currently-known devices.

        :returns: List of Device objects currently tracked by the registry.
        """
        return list(self._devices.values())

    def subscribe(
        self, callback: Callable[[_events.DeviceEvent], Awaitable[None]]
    ) -> _types.Subscription:
        """Register an async callback to receive DeviceEvent objects.

        The callback is scheduled on the running event loop for each event.

        :param callback: Async callable that accepts a DeviceEvent.
        :returns: Subscription handle with an unsubscribe() method.
        """
        self._subscribers.append(callback)

        def _unsubscribe() -> None:
            try:
                self._subscribers.remove(callback)
            except ValueError:
                pass

        return _types.Subscription(_unsubscribe)

    def subscribe_sync(
        self, callback: Callable[[_events.DeviceEvent], None]
    ) -> _types.Subscription:
        """Register a synchronous callback executed on a threadpool for each event.

        :param callback: Synchronous callable that accepts a DeviceEvent.
        :returns: Subscription handle with an unsubscribe() method.
        """
        self._subscribers_sync.append(callback)

        def _unsubscribe() -> None:
            try:
                self._subscribers_sync.remove(callback)
            except ValueError:
                pass

        return _types.Subscription(_unsubscribe)

    async def events(self) -> AsyncIterator[_events.DeviceEvent]:
        """Async iterator that yields DeviceEvent objects as they occur.

        Use this for pull-style consumption of registry events.
        :returns: Async iterator over DeviceEvent objects.
        """
        while True:
            ev = await self._event_queue.get()
            yield ev

    async def start(
        self, *, media_host: str | None = "0.0.0.0", media_port: int = 0
    ) -> None:
        """Start background discovery and optional media server.

        Start adapters and (optionally) an embedded media server so discovery
        can begin.

        :param media_host: Host interface to bind the media server to, or None to
            disable the embedded server.
        :param media_port: Port to bind the media server to (0 selects a free port).
        :returns: None
        """
        async with self._lock:
            if self._running:
                return
            self._running = True
            self._loop = asyncio.get_running_loop()

            if media_host is not None:
                self._media_server = _server.MediaServer(
                    host=media_host, port=media_port
                )
                await self._media_server.start()

            # Enable chromecast by default if not explicitly disabled
            if self._backends.get("chromecast", {}).get("enabled", True):
                await self._start_adapter("chromecast")

            for name, info in self._backends.items():
                if name == "chromecast":
                    continue
                if info.get("enabled"):
                    await self._start_adapter(name)

    async def _start_adapter(self, name: str) -> None:
        """Start a named adapter if it exists and is not already running.

        :param name: The name of the adapter to start.
        """
        if name in self._adapters:
            return

        if name == "chromecast":
            adapter = _chromecast_adapter.ChromecastAdapter(self)
            self._adapters[name] = adapter
            await adapter.start()

    async def stop(self) -> None:
        """Stop discovery, shut down adapters and clear tracked devices.

        Stop adapters and emit DeviceRemoved events for any devices that are
        no longer reachable as a result.

        :returns: None
        """
        async with self._lock:
            if not self._running:
                return
            self._running = False

            # Stop all adapters
            for adapter in self._adapters.values():
                await adapter.stop()
            self._adapters.clear()

            if self._media_server:
                await self._media_server.stop()
                self._media_server = None

            # Emit DeviceRemoved for all devices
            now = datetime.now(timezone.utc)
            for device_id in list(self._devices.keys()):
                ev = _events.DeviceRemoved(
                    timestamp=now, device_id=device_id, reason="shutdown"
                )
                await self._publish_event(ev)
            self._devices.clear()

            # Wait for all background tasks to finish (e.g. event delivery)
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
                self._tasks.clear()

            self._loop = None

    def start_sync(
        self, *, media_host: str | None = "0.0.0.0", media_port: int = 0
    ) -> None:
        """Start the registry synchronously.

        Convenience wrapper for start() for consumers that prefer blocking APIs.

        :param media_host: Host interface to bind the media server to, or None to
            disable the embedded server.
        :param media_port: Port to bind the media server to (0 selects a free port).
        :returns: None
        """
        asyncio.run(self.start(media_host=media_host, media_port=media_port))

    def stop_sync(self) -> None:
        """Stop the registry synchronously.

        Convenience wrapper for stop() for consumers that prefer blocking APIs.

        :returns: None
        """
        asyncio.run(self.stop())

    def enable_backend(self, name: str) -> None:
        """Enable a named protocol backend.

        :param name: Backend identifier to enable.
        :returns: None
        """
        info = self._backends.setdefault(name, {})
        info.setdefault("enabled", True)
        info["enabled"] = True

    def disable_backend(self, name: str) -> None:
        """Disable a named protocol backend.

        :param name: Backend identifier to disable.
        :returns: None
        """
        info = self._backends.setdefault(name, {})
        info["enabled"] = False

    def list_backends(self) -> dict[str, BackendInfo]:
        """Return a mapping of backend names to their state information.

        :returns: Dictionary mapping backend names to their status info.
        """
        return dict(self._backends)

    async def _publish_event(self, ev: _events.DeviceEvent) -> None:
        """Publish an event to subscribers and the async iterator queue.

        :param ev: The DeviceEvent to publish.
        :returns: None
        """
        # Put on queue for async pull consumers
        await self._event_queue.put(ev)
        # Dispatch to async subscribers
        for cb in list(self._subscribers):
            try:
                # schedule but don't await to avoid blocking; store task to avoid GC
                # Use ensure_future to handle general Awaitables
                task: asyncio.Task[None] = asyncio.ensure_future(cb(ev))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            except Exception:
                pass
        # Dispatch to sync subscribers on threadpool
        loop = asyncio.get_running_loop()
        for cb in list(self._subscribers_sync):
            loop.run_in_executor(None, _safe_call_sync, cb, ev)

    async def send_media(
        self,
        device: _types.Device,
        media: _types.MediaPayload,
        *,
        format: str | None = None,
        timeout: float = 30.0,
        options: dict[str, Any] | None = None,
    ) -> _types.SendResult:
        """Send media to a device by delegating to adapters.

        :param device: Target Device.
        :param media: MediaPayload to send.
        :param format: Optional format hint.
        :param timeout: Operation timeout in seconds.
        :param options: Optional transport-specific options.
        :returns: SendResult describing the outcome.
        """
        if device.id not in self._devices:
            return _types.SendResult(success=False, reason="device_unknown")

        adapter = self._adapters.get(device.transport)
        if not adapter:
            return _types.SendResult(success=False, reason="adapter_not_available")

        return await adapter.send_media(
            device, media, format=format, timeout=timeout, options=options
        )

    def schedule_task(self, coro: Awaitable[None]) -> None:
        """Schedule a coroutine to run on the registry's event loop (thread-safe).

        :param coro: The coroutine to schedule.
        :returns: None
        """
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(
                lambda: self._tasks.add(asyncio.ensure_future(coro))
            )
        else:
            _LOGGER.warning("Attempted to schedule task but loop is not running")
            if asyncio.iscoroutine(coro):
                cast(Any, coro).close()

    def register_media_payload(
        self, payload_id: str, media: _types.MediaPayload
    ) -> str | None:
        """Register a media payload with the embedded media server.

        :param payload_id: Unique identifier for the payload.
        :param media: The media payload to register.
        :returns: The URL to the payload if successful, else None.
        """
        if self._media_server:
            return self._media_server.register_payload(payload_id, media)
        return None

    async def register_device(self, device: _types.Device) -> None:
        """Inject a device into the registry.

        :param device: Device to add into the registry.
        :returns: None
        """
        self._devices[device.id] = device
        ev = _events.DeviceAdded(timestamp=datetime.now(timezone.utc), device=device)
        await self._publish_event(ev)

    async def unregister_device(
        self, device_id: _events.DeviceID, reason: str = "lost"
    ) -> None:
        """Remove a device from the registry.

        :param device_id: Identifier of the device to remove.
        :param reason: Reason for removal.
        :returns: None
        """
        if device_id in self._devices:
            self._devices.pop(device_id)
            ev = _events.DeviceRemoved(
                timestamp=datetime.now(timezone.utc),
                device_id=device_id,
                reason=reason,
            )
            await self._publish_event(ev)


default_registry = Registry()

__all__ = ["BackendInfo", "Registry", "default_registry"]
