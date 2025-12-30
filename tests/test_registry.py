"""Unit tests for commoncast.registry module."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

import commoncast.event as _events
import commoncast.registry as _registry
import commoncast.types as _types


@pytest.fixture
def registry() -> _registry.Registry:
    """Fixture to provide a fresh Registry instance.

    :returns: A fresh Registry instance.
    """
    return _registry.Registry()


@pytest.fixture
def device() -> _types.Device:
    """Fixture to provide a sample Device instance.

    :returns: A sample Device instance.
    """
    return _types.Device(
        id=_types.DeviceID("dev1"),
        name="Test Device",
        model="TestModel",
        transport="test",
        capabilities={_types.Capability("video")},
        transport_info={},
    )


@pytest.mark.asyncio
async def test_add_list_devices(
    registry: _registry.Registry, device: _types.Device
) -> None:
    """Test adding and listing devices.

    :param registry: The registry fixture.
    :param device: The device fixture.
    :returns: None
    """
    assert registry.list_devices() == []
    await registry.register_device(device)
    devices = registry.list_devices()
    assert len(devices) == 1
    assert devices[0].id == device.id


@pytest.mark.asyncio
async def test_subscribe_async(
    registry: _registry.Registry, device: _types.Device
) -> None:
    """Test async subscription.

    :param registry: The registry fixture.
    :param device: The device fixture.
    :returns: None
    """
    events: list[_types.DeviceEvent] = []

    async def callback(ev: _types.DeviceEvent) -> None:
        events.append(ev)

    sub = registry.subscribe(callback)
    await registry.register_device(device)

    # Wait for event to propagate
    await asyncio.sleep(0.01)

    assert len(events) == 1
    assert isinstance(events[0], _events.DeviceAdded)
    assert events[0].device.id == device.id

    sub.unsubscribe()
    # Unsubscribe again should be safe
    sub.unsubscribe()

    # Should not receive next event
    await registry._publish_event(  # type: ignore[reportPrivateUsage]
        _events.DeviceHeartbeat(
            timestamp=datetime.now(timezone.utc), device_id=device.id
        )
    )
    await asyncio.sleep(0.01)
    assert len(events) == 1


def test_subscribe_sync(registry: _registry.Registry, device: _types.Device) -> None:
    """Test synchronous subscription.

    :param registry: The registry fixture.
    :param device: The device fixture.
    :returns: None
    """
    events: list[_types.DeviceEvent] = []

    def callback(ev: _types.DeviceEvent) -> None:
        events.append(ev)

    sub = registry.subscribe_sync(callback)

    async def trigger() -> None:
        await registry.register_device(device)
        await asyncio.sleep(0.1)  # Wait for threadpool execution

    asyncio.run(trigger())

    assert len(events) == 1
    assert isinstance(events[0], _events.DeviceAdded)

    sub.unsubscribe()
    # Unsubscribe again should be safe
    sub.unsubscribe()


@pytest.mark.asyncio
async def test_events_iterator(
    registry: _registry.Registry, device: _types.Device
) -> None:
    """Test events async iterator.

    :param registry: The registry fixture.
    :param device: The device fixture.
    :returns: None
    """
    # We need to run the iterator consumption concurrently
    events_received: list[_types.DeviceEvent] = []

    async def consumer() -> None:
        async for ev in registry.events():
            events_received.append(ev)
            if len(events_received) >= 1:
                break

    task = asyncio.create_task(consumer())
    await registry.register_device(device)
    await task

    assert len(events_received) == 1
    assert isinstance(events_received[0], _events.DeviceAdded)


@pytest.mark.asyncio
async def test_lifecycle_stop_clears_devices(
    registry: _registry.Registry, device: _types.Device
) -> None:
    """Test that stop() clears devices and emits removal events.

    :param registry: The registry fixture.
    :param device: The device fixture.
    :returns: None
    """
    await registry.start()

    # Start again should be no-op
    await registry.start()

    await registry.register_device(device)
    assert len(registry.list_devices()) == 1

    events: list[_types.DeviceEvent] = []

    async def cb(ev: _types.DeviceEvent) -> None:
        events.append(ev)

    registry.subscribe(cb)

    await registry.stop()

    # Stop again should be no-op
    await registry.stop()

    assert len(registry.list_devices()) == 0
    await asyncio.sleep(0.01)
    # Check for DeviceRemoved event
    removed_events = [e for e in events if isinstance(e, _events.DeviceRemoved)]
    assert len(removed_events) == 1
    assert removed_events[0].device_id == device.id


def test_backend_management(registry: _registry.Registry) -> None:
    """Test enabling and disabling backends.

    :param registry: The registry fixture.
    :returns: None
    """
    registry.enable_backend("chromecast")
    backends = registry.list_backends()
    assert backends["chromecast"].get("enabled") is True

    registry.disable_backend("chromecast")
    backends = registry.list_backends()
    assert backends["chromecast"].get("enabled") is False


@pytest.mark.asyncio
async def test_send_media(registry: _registry.Registry, device: _types.Device) -> None:
    """Test sending media.

    :param registry: The registry fixture.
    :param device: The device fixture.
    :returns: None
    """
    # Unknown device
    res = await registry.send_media(device, _types.MediaPayload.from_bytes(b""))
    assert not res.success
    assert res.reason == "device_unknown"

    # Known device but no adapter
    await registry.register_device(device)
    res = await registry.send_media(device, _types.MediaPayload.from_bytes(b""))
    assert not res.success
    assert res.reason == "adapter_not_available"


@pytest.mark.asyncio
async def test_chromecast_enabled_by_default(registry: _registry.Registry) -> None:
    """Test that chromecast backend is enabled by default.

    :param registry: The registry fixture.
    :returns: None
    """
    # We need to mock ChromecastAdapter.start to avoid real discovery
    with patch(
        "commoncast.chromecast.adapter.ChromecastAdapter.start",
        return_value=asyncio.Future(),
    ):
        # We need to set the result of the future
        mock_start = MagicMock(return_value=asyncio.Future())
        mock_start.value = None  # Just to avoid warnings
        mock_start.return_value.set_result(None)

        with patch("commoncast.chromecast.adapter.ChromecastAdapter.start", mock_start):
            await registry.start(media_host=None)
            assert "chromecast" in registry._adapters  # type: ignore[reportPrivateUsage]
            await registry.stop()


@pytest.mark.asyncio
async def test_chromecast_can_be_disabled(registry: _registry.Registry) -> None:
    """Test that chromecast backend can be disabled.

    :param registry: The registry fixture.
    :returns: None
    """
    registry.disable_backend("chromecast")
    await registry.start(media_host=None)
    assert "chromecast" not in registry._adapters  # type: ignore[reportPrivateUsage]
    await registry.stop()


def test_safe_call_sync_exception() -> None:
    """Test that _safe_call_sync swallows exceptions.

    :returns: None
    """

    def failing_cb(ev: _types.DeviceEvent) -> None:
        raise Exception("test failure")

    ev = _events.DeviceHeartbeat(
        timestamp=datetime.now(timezone.utc), device_id=_types.DeviceID("dev")
    )
    # Should not raise
    _registry._safe_call_sync(failing_cb, ev)  # type: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_publish_event_async_exception(registry: _registry.Registry) -> None:
    """Test that _publish_event handles async subscriber exceptions.

    :param registry: The registry fixture.
    :returns: None
    """

    async def failing_cb(ev: _types.DeviceEvent) -> None:
        raise Exception("test failure")

    registry.subscribe(failing_cb)
    ev = _events.DeviceHeartbeat(
        timestamp=datetime.now(timezone.utc), device_id=_types.DeviceID("dev")
    )

    # Should not raise
    await registry._publish_event(ev)  # type: ignore[reportPrivateUsage]
    # Give it a chance to run
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_remove_device(
    registry: _registry.Registry, device: _types.Device
) -> None:
    """Test removing a device from the registry.

    :param registry: The registry fixture.
    :param device: The device fixture.
    :returns: None
    """
    await registry.register_device(device)
    assert len(registry.list_devices()) == 1

    await registry.unregister_device(device.id)
    assert len(registry.list_devices()) == 0

    # Removing again should be safe
    await registry.unregister_device(device.id)
