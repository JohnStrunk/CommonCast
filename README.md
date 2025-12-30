# CommonCast

CommonCast is a Python library that provides a unified API for discovering
and sending images to networked media renderers such as Chromecast,
DIAL-capable devices, and DLNA/UPnP renderers.

## Features

- **Unified API**: Control different types of devices through a single
  interface.
- **Automatic Discovery**: Find devices on your local network using mDNS and
  other protocols.
- **Local Content Support**: Embedded HTTP server to serve local files and raw
  bytes to remote devices.
- **Event-Driven**: Subscribe to device discovery and state changes.
- **Extensible**: Easily add support for new protocols by implementing custom
  backends.

## Documentation

- [User Guide](docs/user_guide.md): Instructions and code examples for using
  the library.
- [Backend Implementation Guide](docs/backend_implementation_guide.md): Learn
  how to implement new backends for CommonCast.
- [Architecture](ARCHITECTURE.md): Detailed technical overview of the system.

## Quick Start

```python
import asyncio
import commoncast

async def main():
    await commoncast.start()
    await asyncio.sleep(5)

    devices = commoncast.list_devices()
    if devices:
        # Send a URL to the first found device
        payload = commoncast.types.MediaPayload.from_url("https://example.com/video.mp4")
        await devices[0].send_media(payload)

    await commoncast.stop()

asyncio.run(main())
```

## Development

### Release procedure

- Update the version in `pyproject.toml`

  ```console
  # Bump the version string
  uv version --bump {major|minor|patch|alpha|beta|stable}
  # or specify the version directly
  uv version X.Y.Z
  ```

- Commit changes to `main`
- Tag the repo with the new version: `vX.Y.Z`

---

License: [LGPL-3.0-only](LICENSE)
