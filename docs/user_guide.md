# CommonCast User Guide

CommonCast is a Python library that provides a unified API for discovering
and sending media to various networked devices like Chromecasts, DIAL, and
DLNA renderers.

## Installation

CommonCast uses `uv` for dependency management. To add it to your project:

```bash
uv add commoncast
```

## Basic Usage

### Starting the Registry

The `Registry` is the central hub for discovery and device management. You
must start it to begin finding devices.

```python
import asyncio
import commoncast

async def main():
    # Start discovery and the embedded media server
    await commoncast.start()

    # Give it a few seconds to discover devices
    await asyncio.sleep(5)

    # List discovered devices
    devices = commoncast.list_devices()
    for device in devices:
        print(f"Found {device.name} ({device.model}) at {device.id}")

    # Stop discovery when done
    await commoncast.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## Sending Media

CommonCast supports sending media from URLs, local files, or raw bytes.

### Sending a URL

```python
from commoncast.types import MediaPayload, MediaMetadata

async def play_url(device, url):
    payload = MediaPayload.from_url(
        url,
        mime_type="video/mp4",
        metadata=MediaMetadata(title="My Video")
    )
    result = await device.send_media(payload)
    if result.success:
        print("Playback started!")
```

### Sending a Local File

When sending a local file, CommonCast automatically uses its embedded media
server to serve the file to the remote device.

```python
from pathlib import Path
from commoncast.types import MediaPayload

async def play_file(device, file_path):
    payload = MediaPayload.from_path(Path(file_path))
    result = await device.send_media(payload)
```

### Sending Raw Bytes

```python
from commoncast.types import MediaPayload

async def play_bytes(device, data, mime_type):
    payload = MediaPayload.from_bytes(data, mime_type=mime_type)
    result = await device.send_media(payload)
```

## Controlling Playback

If a device supports playback control, the `SendResult` will contain a
`MediaController`.

```python
result = await device.send_media(payload)
if result.success and result.controller:
    controller = result.controller

    await controller.pause()
    await asyncio.sleep(2)
    await controller.play()

    # Seek to 30 seconds
    await controller.seek(30.0)

    # Volume (0.0 to 1.0)
    await controller.set_volume(0.5)

    await controller.stop()
```

## Handling Events

You can react to device discovery and state changes using events.

### Using an Async Iterator

```python
async def watch_events():
    async for event in commoncast.events():
        if isinstance(event, commoncast.DeviceAdded):
            print(f"New device: {event.device.name}")
        elif isinstance(event, commoncast.DeviceRemoved):
            print(f"Device lost: {event.device_id}")
```

### Using Callbacks

```python
async def on_event(event):
    print(f"Received event: {type(event).__name__}")

subscription = commoncast.subscribe(on_event)

# To unsubscribe later:
subscription.unsubscribe()
```
