# DIAL (DIscovery And Launch) — sending media to end devices

This document summarizes how to use the DIAL protocol to discover
devices, launch receiver apps, and instruct them to play media.
DIAL itself handles discovery and app lifecycle; actual media is
streamed directly from the content server to the device. The device
uses its own media playback capabilities.

## 1. Discovery

- Mechanism: DIAL relies on SSDP (part of UPnP) for discovery.
- Clients send an SSDP M-SEARCH or listen for NOTIFY broadcasts to
  find DIAL-capable devices.
- Service type: look for `urn:dial-multiscreen-org:service:dial:1`
  in SSDP responses.
- The SSDP reply includes the device description URL (Location
  header) and the service list.
- Device description: fetch the device description XML (the
  Location URL) to find the DIAL service and the application
  control URL used for REST operations.

Example SSDP M-SEARCH:

M-SEARCH * HTTP/1.1
HOST: 239.255.255.250:1900
MAN: "ssdp:discover"
ST: urn:dial-multiscreen-org:service:dial:1
MX: 3

## 2. Connection & Launch (App lifecycle)

- Probe app state: GET `/apps/<appName>` on the device's DIAL
  application endpoint returns whether the app is installed or
  running and may include an instance resource link.

- Launch app: POST `/apps/<appName>` to request the device launch
  the named app. The POST may include optional launch parameters
  (formats and semantics are app-specific).
  - Responses include:
    - `201 Created` when a new instance is started (Location header
      points to the instance resource)
    - `200 OK` if already running
    - `404 Not Found` if the app is not available

- Instance resource: the Location returned (for example,
  `/apps/<appName>/<instanceId>`) is used to query state and
  control the launched app. Sending `DELETE` to that instance
  typically stops the app.

Example launch request (generic):

POST /apps/YouTube HTTP/1.1
Host: 192.0.2.10:8008
Content-Type: text/plain

{ "payload": "optional app-specific data" }

## 3. Media sending flow

Important: DIAL is not a media transport. Typical flow:

1. Discover and select a device (SSDP).
2. Query the target app (GET `/apps/<appName>`) to see if it is
   available and running.
3. Launch or wake the app (POST `/apps/<appName>`) if needed. Obtain
   the app instance resource from the Location header.
4. Use the app's control API (often exposed via the instance
   resource or an app-specific endpoint) to instruct playback. This
   usually means sending the content URL and optional metadata
   (title, start time, autoplay flag) to the app's control endpoint.
5. The device fetches the media directly from the content URL and
   plays it. The sender becomes a controller (remote) rather than
   the media proxy.
6. Optionally poll or subscribe to the instance resource to monitor
   playback state, stop (`DELETE`) the instance, or send app- specific
   control commands.

Typical app control methods:

- POST the media URL and metadata to the app's control endpoint
  (app-specific REST or WebSocket).
- Some apps accept a launch payload containing the media URL during
  the initial POST to `/apps/<appName>`.

Example control step (conceptual):

POST /apps/YouTube/instances/1234/play HTTP/1.1
Host: 192.0.2.10:8008
Content-Type: application/json

{
  "url": "<https://cdn.example.com/video.mp4>",
  "title": "Episode 1"
}

## 4. State, errors and lifecycle

- Poll the app instance resource (GET) to read state: running,
  stopped, playback position, last command, etc.
- Handle HTTP status codes: `201` (created), `200` (OK), `404`
  (app not found), `503` (service unavailable), and app-specific
  error bodies.
- Cleanly stop apps (`DELETE` instance resource) when a session
  ends to free device resources.

## 5. Security and pairing

- DIAL implementations may require pairing (PIN entry), OAuth, or
  TLS depending on device and app. The DIAL spec leaves control
  semantics to the app, so pairing and policy are app-specific.
- Prefer HTTPS for control payloads where supported. Validate tokens
  and origin when exchanging sensitive control commands.

## 6. Implementation notes and caveats

- Not all devices implement the same payload format for launch or
  control. After launching, expect to use an app-specific REST or
  socket API.
- Because the device pulls media directly, the content URL must be
  reachable by the device (publicly accessible or on the same
  network). CORS and ACLs on the content server must permit device
  access when required.
- DIAL is ideal for "second-screen" workflows: the sender discovers
  and launches a receiver and then controls playback while the
  receiver streams content from the origin.

## 7. Comparison with DLNA

While both DIAL and DLNA enable media experiences on networked devices, they
solve different problems:

| Feature | DIAL (Discovery And Launch) | DLNA (Digital Living Network Alliance) |
| :--- | :--- | :--- |
| **Primary Goal** | Launching first-screen applications (e.g., Netflix, YouTube) from a second screen. | Streaming media content (video, audio, images) directly to a renderer. |
| **Media Transport** | Handled by the launched application (e.g., the TV app fetches the stream). | Handled by the DLNA protocol (HTTP streaming from DMS/URL to DMR). |
| **Control** | Discovery and App Launch only. Post-launch control is app-specific. | Standardized control for Play, Pause, Stop, Seek, Volume via UPnP AVTransport. |
| **Flexibility** | High. Any app can be launched; the app defines its own UI and playback logic. | Lower. Restricted to media formats and containers supported by the renderer. |
| **Use Case** | "Cast" style experience (start Netflix on TV). | Media Server experience (play local file on TV). |

## Python libraries

Below is a short list of Python libraries useful when implementing
a DIAL controller (discovery, app lifecycle, and control). Each
entry includes a repository link and a short note on maintenance.

- [requests](https://github.com/psf/requests) — A ubiquitous
  synchronous HTTP client for Python. Useful for simple REST calls
  to device app endpoints (GET/POST/DELETE). Well maintained.

- [httpx](https://github.com/encode/httpx) — Modern HTTP client with
  sync and async APIs; good for async control flows or HTTP/2
  features. Actively maintained by the Encode project.

- [aiohttp](https://github.com/aio-libs/aiohttp) — Async HTTP client
  and server library; useful for building async controllers or when
  integrating SSDP/UPnP discovery with an event loop. Widely used.

- [async_upnp_client](https://github.com/StevenLooman/async_upnp_client)
  — An async UPnP/SSDP client library (used by Home Assistant)
  that simplifies discovery and interaction with DIAL-capable
  devices. Well regarded and actively maintained.

- [pychromecast](https://github.com/home-assistant-libs/pychromecast)
  — While primarily for Google Cast, this library often uses DIAL
  discovery mechanisms for legacy support or initial device finding.
  A good reference for real-world usage.

## Python DIAL implementations

There are few widely-adopted, dedicated DIAL-only Python libraries.
In practice most implementations are small: use an SSDP/UPnP library
(e.g., `async_upnp_client`) for discovery and a lightweight HTTP
client (`httpx`, `aiohttp`, or `requests`) to probe/launch apps and
control instances. If a community DIAL-specific project is found,
evaluate its activity and issues before relying on it.

Notes:

- For discovery, prefer an async UPnP/SSDP client (e.g.,
  `async_upnp_client`) to reliably receive SSDP NOTIFY messages and
  perform M-SEARCH probes.
- Use `httpx` or `aiohttp` for async control flows; `requests` is a
  simple choice for synchronous implementations or tooling.

## References

- [DIAL specification and implementation notes (DIAL Multiscreen)](https://github.com/DIAL-Multiscreen/DIAL)
- [SSDP / UPnP discovery (Simple Service Discovery Protocol)](https://en.wikipedia.org/wiki/Simple_Service_Discovery_Protocol)
