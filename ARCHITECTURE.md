# CommonCast System Architecture

This document describes the system architecture of CommonCast and the
interfaces that protocol backends (adapters) must adhere to.

## Overview

CommonCast is designed as a modular library for discovering and controlling
media rendering devices (e.g., Chromecast, AirPlay, DLNA) through a unified API.

The architecture consists of three main layers:

1. **Public API**: The `Registry` and `Device` classes used by consumers.
2. **Core Logic**: Event management, device tracking, and an embedded
   `MediaServer`.
3. **Backends (Adapters)**: Protocol-specific implementations that handle
   discovery and device communication.

---

## Component Diagram

```text
+---------------------------------------+
|              Application              |
+-------------------|-------------------+
                    |
          +---------v----------+
          |      Registry      |
          +---------|----------+
                    |
    +---------------|-------------------+
    |               |                   |
+---v---+       +---v---+           +---v---+
|Adapter|       |Adapter|           |Adapter|
|(Cast) |       |(DIAL) |           |(...)  |
+-------+       +-------+           +-------+
```

---

## Core Components

### Registry

The central hub of the library. It:

- Manages the lifecycle of adapters.
- Maintains a list of discovered `Device` objects.
- Dispatches `DeviceEvent`s to subscribers.
- Proxies `send_media` calls to the appropriate adapter.
- Manages the embedded `MediaServer`.

### Adapters

Protocol-specific modules (e.g., `commoncast.chromecast.adapter`). They:

- Implement discovery for a specific protocol.
- Register/unregister devices with the `Registry`.
- Handle the low-level communication to play media.
- Provide a `MediaController` for active sessions.

### MediaServer

An embedded HTTP server (using `aiohttp`) that allows serving local content
(files or raw bytes) to remote devices that only support URL-based playback.

---

## Event System

CommonCast uses an event-driven model to notify consumers about device
lifecycle and state changes.

### Event Types

All events inherit from `DeviceEvent` and include a UTC `timestamp`.

- **`DeviceAdded`**: Emitted when a new device is discovered.
- **`DeviceUpdated`**: Emitted when device properties change.
- **`DeviceRemoved`**: Emitted when a device is no longer reachable.
- **`MediaStatusUpdated`**: Emitted when playback state changes.
- **`VolumeUpdated`**: Emitted when volume or mute state changes.

### Subscription Model

Users can consume events in two ways:

1. **Callbacks**: Register async or sync callbacks with `registry.subscribe()`
   or `registry.subscribe_sync()`.
2. **Async Iterator**: Use `await for event in registry.events()` for a
   pull-style interface.

---

## Backend Interface Specification

Every backend must implement an "Adapter" class. While not strictly enforced by
a base class yet, it should follow this pattern:

### 1. Adapter Lifecycle

#### `__init__(self, registry: Registry)`

Initializes the adapter with a reference to the central registry.

#### `async start(self) -> None`

Starts discovery and any background tasks required by the protocol.

#### `async stop(self) -> None`

Stops discovery and cleans up resources.

### 2. Device Management

Adapters are responsible for discovering devices and notifying the registry
using internal methods:

- `await self._registry._add_device(device: Device)`: When a new device is
  found or updated.
- `await self._registry._remove_device(device_id: DeviceID)`: When a device
  is lost.

### 3. Media Playback

#### `async send_media(self, device: Device, media: MediaPayload, **kwargs)`

This is the primary method for playing media.

- **Parameters**:
  - `device`: The target `Device` object.
  - `media`: A `MediaPayload` containing the content (URL, Path, or Bytes).
  - `format`: Optional transport-specific format hint.
  - `timeout`: Operation timeout in seconds.
  - `options`: Dictionary of transport-specific options.
- **Returns**: A `SendResult` object.

### 4. Media Control

If the protocol supports playback control, the `SendResult` should include a
`MediaController` implementation.

#### `MediaController` Protocol

Backends should implement this interface to allow users to control the session:

- `async play()`
- `async pause()`
- `async stop()`
- `async seek(position: float)`
- `async set_volume(level: float)`
- `async set_mute(mute: bool)`

---

## Data Schemas (Types)

### Device

Represents a discovered renderer.

- `id`: Stable unique identifier.
- `name`: Human-readable name.
- `model`: Optional model string.
- `transport`: The name of the adapter (e.g., "chromecast").
- `capabilities`: Set of supported features (`video`, `audio`, etc.).
- `transport_info`: Internal dictionary for connection details.

### MediaPayload

Container for media to be sent.

- `url`: Remote URL.
- `path`: Local filesystem path.
- `data`: Raw bytes.
- `mime_type`: Content type hint.
- `metadata`: `MediaMetadata` object.

### MediaMetadata

Rich metadata for media content.

- `title`: Content title.
- `subtitle`: Subtitle or description.
- `artist`: Artist name.
- `album`: Album name.
- `images`: List of `MediaImage` (URL, width, height).
- `type`: Generic type hint (e.g., `movie`, `music`).

### SendResult

The result of a `send_media` operation.

- `success`: Boolean indicating if the operation succeeded.
- `reason`: Optional failure reason.
- `controller`: Optional `MediaController` instance for the session.
- `metadata`: Optional transport-specific metadata.

---

## Communication Protocols

- **Internal**: All internal communication is asynchronous using `asyncio`.
- **Discovery**: Protocols typically use mDNS/DNS-SD (e.g., Zeroconf) or SSDP.
- **Media Serving**: The `MediaServer` listens on a local interface and
  provides HTTP access to registered payloads.
