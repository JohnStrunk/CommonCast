"""Test to reproduce and verify fix for registry task leak."""
# pyright: reportPrivateUsage=false

import asyncio
from datetime import datetime, timezone

import pytest

import commoncast.event as _events
import commoncast.registry as _registry
import commoncast.types as _types


@pytest.mark.asyncio
async def test_registry_task_cleanup() -> None:
    """Verify that completed tasks are removed from the registry.

    :returns: None
    """
    registry = _registry.Registry()

    # Subscribe a dummy callback so tasks are created
    async def dummy_callback(event: _types.DeviceEvent) -> None:
        pass

    registry.subscribe(dummy_callback)

    # Publish many events
    for _ in range(100):
        # pylint: disable=protected-access
        await registry._publish_event(
            _events.DeviceHeartbeat(
                timestamp=datetime.now(timezone.utc), device_id=_types.DeviceID("dev1")
            )
        )

    # Give a slight yield to allow tasks to complete and callbacks to fire
    # Since add_done_callback is scheduled on the loop, we might need a few yields
    for _ in range(5):
        await asyncio.sleep(0.01)

    # Check the size of _tasks
    # pylint: disable=protected-access
    print(f"Number of tasks in registry: {len(registry._tasks)}")

    # It should be 0 or close to 0
    # pylint: disable=protected-access
    assert len(registry._tasks) < 5, (
        f"Registry._tasks should be cleaned up, but has {len(registry._tasks)}"
    )
