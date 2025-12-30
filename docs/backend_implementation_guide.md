# Backend Implementation Guide

This guide describes how to implement a new backend (adapter) for CommonCast.
Adapters allow the library to support new protocols (e.g., AirPlay, DLNA,
SONOS).

## Architecture Overview

A backend consists of two main components:

1. **`BackendAdapter`**: Handles discovery and media session initialization.
2. **`MediaController`**: (Optional) Handles playback control for an active
   session.

## Implementing the Adapter

Your adapter must inherit from `commoncast.types.BackendAdapter`.

### 1. Initialization

Store a reference to the `Registry` to notify it of discovered devices.

```python
from commoncast.types import BackendAdapter
from commoncast.registry import Registry

class MyAdapter(BackendAdapter):
    def __init__(self, registry: Registry):
        self._registry = registry
        self._devices = {}
```

### 2. Discovery

Implement `start()` to begin discovery and `stop()` to clean up. Use
`registry.register_device()` and `registry.unregister_device()` to update
the central registry.

```python
from commoncast.types import Device, DeviceID, Capability

async def start(self):
    # Start your discovery logic (e.g., Zeroconf or SSDP)
    # When a device is found:
    device = Device(
        id=DeviceID("unique-id"),
        name="Friendly Name",
        model="Model X",
        transport="my-protocol",
        capabilities={Capability("video"), Capability("audio")},
        transport_info={"ip": "192.168.1.10"}
    )
    await self._registry.register_device(device)
```

### 3. Sending Media

Implement `send_media()` to handle playback requests. If your protocol
requires serving local files or bytes, use the registry's media server.

```python
import uuid
from commoncast.types import SendResult

async def send_media(self, device, media, **kwargs):
    url = media.url
    if not url:
        # Register with embedded server if it's local content
        payload_id = str(uuid.uuid4())
        url = self._registry.register_media_payload(payload_id, media)

    # Trigger playback on the physical device using your protocol
    # ...

    return SendResult(success=True, controller=MyController(device))
```

## Implementing the Media Controller

If the protocol supports it, implement `MediaController` to allow users to
control the session.

```python
from commoncast.types import MediaController

class MyController(MediaController):
    async def play(self): ...
    async def pause(self): ...
    async def stop(self): ...
    async def seek(self, position): ...
    async def set_volume(self, level): ...
    async def set_mute(self, mute): ...
```

## Registering the Backend

Currently, backends are registered in `commoncast.registry.Registry`. You
will need to:

1. Add your adapter to the `Registry._start_adapter` method.
2. Ensure any third-party dependencies are added to `pyproject.toml`.

## Best Practices

- **Thread Safety**: Use `asyncio.to_thread()` if using synchronous libraries
  for network communication or discovery.
- **Mime Types**: Use `mimetypes.guess_type()` if the `MediaPayload` doesn't
  provide a `mime_type`.
- **Error Handling**: Catch protocol-specific exceptions in `send_media` and
  return a `SendResult(success=False, reason=str(e))`.
