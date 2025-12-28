# CommonCast

CommonCast is a Python library that provides a unified API for discovering
and sending images to networked media renderers such as Chromecast,
DIAL-capable devices, and DLNA/UPnP renderers.

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
