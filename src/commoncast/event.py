"""Event types for the CommonCast public API.

This module defines device lifecycle and media status events.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import commoncast.types as _types

if TYPE_CHECKING:
    import commoncast.types as _types

# Re-export DeviceID and DeviceEvent for convenience
DeviceID = _types.DeviceID
DeviceEvent = _types.DeviceEvent


@dataclass
class DeviceAdded(DeviceEvent):
    """Event indicating a device was discovered or added to the registry.

    :param device: The Device instance that was added.
    """

    device: _types.Device


@dataclass
class DeviceUpdated(DeviceEvent):
    """Event indicating an existing device has updated properties.

    :param device: The Device instance that was updated.
    :param changes: Mapping of attribute names to new values describing the
        change set.
    """

    device: _types.Device
    changes: Mapping[str, Any]


@dataclass
class DeviceRemoved(DeviceEvent):
    """Event indicating a device was removed from the registry.

    :param device_id: The stable identifier of the removed device.
    :param reason: Optional human-readable reason for removal.
    """

    device_id: DeviceID
    reason: str | None


@dataclass
class DeviceHeartbeat(DeviceEvent):
    """Periodic heartbeat event emitted by adapters for a device.

    :param device_id: The stable identifier of the device sending the
        heartbeat.
    """

    device_id: DeviceID


@dataclass
class MediaStatusUpdated(DeviceEvent):
    """Event indicating a change in media playback status.

    :param device_id: The identifier of the device.
    :param status: The new status (e.g., 'playing', 'paused', 'buffering', 'idle').
    :param media_session_id: Optional session identifier.
    :param position: Optional current playback position in seconds.
    """

    device_id: DeviceID
    status: str
    media_session_id: str | None = None
    position: float | None = None


@dataclass
class VolumeUpdated(DeviceEvent):
    """Event indicating a change in device volume.

    :param device_id: The identifier of the device.
    :param volume_level: Current volume level (0.0 to 1.0).
    :param is_muted: True if the device is muted.
    """

    device_id: DeviceID
    volume_level: float
    is_muted: bool


__all__ = [
    "DeviceAdded",
    "DeviceEvent",
    "DeviceHeartbeat",
    "DeviceID",
    "DeviceRemoved",
    "DeviceUpdated",
    "MediaStatusUpdated",
    "VolumeUpdated",
]
