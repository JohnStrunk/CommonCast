# Google Cast (Chromecast) Research for CommonCast

## Overview

Google Cast is a proprietary protocol developed by Google for playing
internet-streamed audio/video content on a compatible device (e.g., Chromecast,
Android TV, Google Home) controlled by a mobile device or computer.

## Device Flow

### 1. Device Discovery (mDNS)

- **Protocol:** Multicast DNS (mDNS) / Bonjour
- **Service Type:** `_googlecast._tcp`
- **Address:** `224.0.0.251` (IPv4) / `ff02::fb` (IPv6)
- **Port:** UDP `5353`

**Interaction:**

1. **Probe:** The sender broadcasts an mDNS query.
2. **Response:** Cast devices respond with their IP, port (usually 8009), and
   TXT records containing device friendly name, ID, and status.

### 2. Connection Establishment

- **Protocol:** TCP with TLS
- **Port:** `8009` (Standard control port)

**Interaction:**

1. **TCP Connect:** Sender initiates a TCP connection to port 8009.
2. **TLS Handshake:** The connection is immediately upgraded to TLS. The device
   presents a certificate.
3. **Authentication:** The sender validates the device's certificate (often
   signed by a trusted Google CA) to ensure authenticity.

### 3. CastV2 Protocol (Protobuf)

- **Format:** Protocol Buffers (protobuf)
- **Structure:** `[Length (4 bytes)] [Protobuf Message]`

**Interaction:**

1. **Virtual Connection:** Sender sends a `CONNECT` message to a specific
   "namespace" (e.g., `urn:x-cast:com.google.cast.tp.connection`).
2. **Channel Multiplexing:** Messages are routed to different "namespaces" or
   "destinations" over the single TLS socket.
   - **Heartbeat:** `urn:x-cast:com.google.cast.tp.heartbeat` (PING/PONG
     every ~5s).
   - **Receiver Control:** `urn:x-cast:com.google.cast.receiver` (Launch apps,
     check status).
   - **Media Control:** `urn:x-cast:com.google.cast.media` (Play, pause, seek).

### 4. Application Launch & Media Playback

- **Receiver Apps:** Cast devices run "Web Receiver" applications (HTML/JS)
  hosted online.
- **Default Media Receiver:** A generic player provided by Google (App ID:
  `CC1AD845`).

**Interaction:**

1. **Launch App:** Sender sends a `LAUNCH` command with an App ID (e.g.,
   `CC1AD845` for Default Media Receiver) to the Receiver namespace.
2. **Load Media:** Once the app is running, the sender connects to the app's
   transport channel and sends a `LOAD` command with the media URL and metadata.
3. **Playback:** The Cast device fetches the media directly from the internet
   (or local network URL) and renders it. The sender receives status updates
   (time, state) via the media channel.

## Technical Specifications

- **Transport:** TCP/TLS over IP.
- **Serialization:** Google Protocol Buffers (protobuf). Payload often contains
  JSON strings.
- **Encryption:** TLS 1.2+.
- **Ports:**
  - `8009` (TCP): Main control channel.
  - `8008` (HTTP): Legacy/Auxiliary API.
  - `32768-61000` (UDP): RTP streaming (for mirroring).

## Media Formats

Formats are dependent on the Chromecast generation and the Receiver Application
(usually Chrome-based).

- **Video:** H.264, H.265 (HEVC), VP8, VP9.
- **Audio:** AAC, MP3, Vorbis, Opus, FLAC, AC-3 (Passthrough).
- **Containers:** MP4, WebM.
- **Images:** BMP, GIF, JPEG, PNG, WEBP.
- **Streaming:** DASH, HLS, SmoothStreaming.

## Potential Challenges

- **Proprietary Protocol:** The protobuf definitions are not officially
  documented for 3rd party senders (though well-reversed).
- **Authentication:** Validating the "Auth Token" requires communicating with
  Google servers if strict authentication is needed.
- **CORS:** The media URL must support Cross-Origin Resource Sharing (CORS)
  because the receiver app runs in a browser sandbox.
- **HTTPS:** Modern Cast receivers often require media content to be served
  over HTTPS.

## Python Libraries

- **pychromecast:** The gold standard library. Handles discovery (via
  `zeroconf`), connection, protobuf serialization, and provides high-level APIs
  for media control.
- **pycast:** Older/Alternative implementation (less active).

## Comparison with DLNA

- **Intelligence:** Cast loads a web app on the device; DLNA just pushes a
  stream.
- **Flexibility:** Cast is more flexible (custom UI on TV, DRM support via web
  app) but requires internet for the receiver app (usually). DLNA works fully
  offline.
- **Discovery:** Both use multicast (mDNS vs SSDP).

## References

- [Google Cast SDK](https://developers.google.com/cast)
- [PyChromecast Repository](https://github.com/home-assistant-libs/pychromecast)
- [Cast V2 Protocol Docs (Unofficial)](https://github.com/thibauts/node-castv2)
