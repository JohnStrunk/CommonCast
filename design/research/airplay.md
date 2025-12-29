# AirPlay Research for CommonCast

## Overview

AirPlay is a proprietary protocol stack developed by Apple for wireless
streaming of audio, video, and photos between devices. It has two major
versions: AirPlay 1 (Legacy) and AirPlay 2 (Modern, Multi-room).

## Device Flow (AirPlay 1 vs AirPlay 2)

### 1. Device Discovery (mDNS)

- **Protocol:** Multicast DNS (mDNS) / Bonjour
- **Service Types:**
  - `_airplay._tcp`: Main AirPlay service (Control, Video, Photos).
  - `_raop._tcp`: Remote Audio Output Protocol (Audio-only, AirTunes).
- **Port:** Dynamic, but often published in the mDNS record (e.g., 7000, 5000).

**Interaction:**

1. **Browse:** Sender looks for `_airplay._tcp` or `_raop._tcp`.
2. **Identify:** The `TXT` record contains feature flags (`features`), model,
   and PK (Public Key) for pairing.

### 2. Pairing and Authentication

- **Encryption:** FairPlay (Apple's DRM) and AES.
- **AirPlay 1:** Often just a password or simple challenge-response.
- **AirPlay 2:** Requires more complex transient pairing (SRP - Secure Remote
  Password protocol) and Ed25519 signatures.

**Interaction:**

1. **Pair Setup:** Exchange of keys and authentication via HTTP/RTSP endpoints.
2. **Pair Verify:** Verifying the session is secure.

### 3. Media Streaming

#### AirPlay 1 (Legacy)

- **Video/Photo:** HTTP PUT/POST commands to the receiver (e.g., Apple TV).
  - `POST /play` with a URL (device fetches media).
  - `PUT /photo` with raw image data.
- **Audio (RAOP):** RTSP (Real-Time Streaming Protocol) setup, then RTP
  (Real-time Transport Protocol) over UDP for the audio stream.
  - **Latency:** Fixed 2-second buffer (usually).
  - **Format:** ALAC (Apple Lossless) encrypted with AES key.

#### AirPlay 2 (Modern)

- **Architecture:** File-transfer based rather than real-time stream. Better
  buffering.
- **Sync:** Uses PTP (Precision Time Protocol) for microsecond-level
  synchronization across multiple speakers.
- **Audio:** buffered streaming, faster response to controls.
- **Control:** Uses HomeKit/MRP (Media Remote Protocol) often tunneled over
  the connection.

## Technical Specifications

- **Transport:** TCP (Control/Metadata), UDP (Audio/Sync).
- **Ports:**
  - `554` (RTSP - sometimes).
  - `5000-5005` (RAOP AirPlay 1).
  - `7000` (AirPlay Control).
  - Dynamic high ports for data/timing.
- **Encryption:** ChaCha20-Poly1305 (AirPlay 2), AES-CBC/AES-CTR (AirPlay 1).

## Media Formats

- **Audio:** ALAC (Apple Lossless) 44.1kHz / 16-bit is standard. AAC/PCM
  support depends on the receiver capabilities.
- **Video:** H.264 (MP4/MOV).
- **Photos:** JPEG.

## Potential Challenges

- **Reverse Engineering:** The protocol is closed-source. Libraries rely on
  community reverse engineering which can break with tvOS updates.
- **Encryption:** AirPlay 2 pairing and encryption are complex (FairPlay) and
  strictly enforced on newer devices.
- **DRM:** Sending DRM-protected content (like Netflix) via AirPlay usually
  hands off the URL (like Chromecast), but direct streaming of protected
  content from a custom app is hard without an official entitlement.

## Python Libraries

- **pyatv:** The most comprehensive library. Supports:
  - Discovery (AirPlay & HomeKit).
  - Pairing (SRP, Legacy).
  - AirPlay 1 (Streaming local files).
  - AirPlay 2 (Experimental/Partial).
  - Remote Control (MRP, DMAP).
- **raop:** Older libraries for AirPlay 1 audio (often unmaintained).
- **openairplay/airplay2-receiver:** Experimental receiver implementation.

## Comparison with DLNA/Chromecast

- **Ecosystem:** Strictly Apple-centric vs Open (DLNA) or Google-centric
  (Cast).
- **Sync:** AirPlay 2 offers the best-in-class multi-room audio sync.
- **Video:** AirPlay video is often just "screen mirroring" or "URL handoff".
  Chromecast is "URL handoff". DLNA is "URL handoff" or "Push".

## References

- [Unofficial AirPlay Protocol Specification](https://openairplay.github.io/airplay-spec/)
- [pyatv Documentation](https://pyatv.dev/)
- [AirPlay 2 Reverse Engineering](https://github.com/openairplay/airplay2-receiver)
