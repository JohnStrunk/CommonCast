# DLNA Research for CommonCast

## Overview

The Digital Living Network Alliance (DLNA) protocol facilitates sharing and
streaming of digital media content among multimedia devices. It is built upon
Universal Plug and Play (UPnP) and uses standard networking protocols like IP,
HTTP, and XML.

## Device Flow

The typical flow involves a **Digital Media Controller (DMC)** (e.g.,
CommonCast) discovering a **Digital Media Renderer (DMR)** (e.g., Smart TV,
Speaker) and instructing it to play media from a **Digital Media Server (DMS)**
(or a direct HTTP URL).

### 1. Device Discovery (SSDP)

- **Protocol:** Simple Service Discovery Protocol (SSDP)
- **Transport:** UDP Multicast
- **Address:** `239.255.255.250`
- **Port:** `1900`

**Interaction:**

1. **M-SEARCH:** The Controller sends an SSDP M-SEARCH multicast request to
   discover available devices.
   - Target (`ST` header): `urn:schemas-upnp-org:device:MediaRenderer:1` (or
     similar).
2. **NOTIFY/Response:** Devices respond with a Unicast UDP packet containing
   their location (URL to the device description XML).

### 2. Device Description (UPnP)

- **Protocol:** HTTP
- **Format:** XML

**Interaction:**

1. **Get Description:** The Controller performs an HTTP GET request to the URL
   provided in the SSDP response.
2. **Parse XML:** The Controller parses the XML to find the `AVTransport`
   service control URL. This service is responsible for media playback control.

### 3. Media Playback Control (UPnP SOAP)

- **Protocol:** SOAP over HTTP
- **Service:** `AVTransport`

**Interaction:**

1. **SetAVTransportURI:** The Controller sends a SOAP action
   `SetAVTransportURI` to the DMR's `AVTransport` control URL.
   - **Parameters:** `InstanceID` (usually 0), `CurrentURI` (URL of the media
     to play), `CurrentURIMetaData` (DIDL-Lite XML metadata describing the
     media).
2. **Play:** The Controller sends a SOAP action `Play` to the DMR.
   - **Parameters:** `InstanceID` (usually 0), `Speed` (usually "1").

### 4. Media Streaming (HTTP)

- **Protocol:** HTTP

**Interaction:**

1. **Get Media:** The DMR initiates an HTTP GET request to the `CurrentURI`
   specified by the Controller to fetch and render the media stream.

## Technical Specifications

### Protocols Used

- **SSDP:** Device discovery.
- **HTTP:** Device description retrieval, SOAP control messaging, media
  streaming.
- **XML (UPnP):** Device and service descriptions.
- **SOAP:** Remote procedure calls for device control.
- **DIDL-Lite:** XML format for media metadata.

### Media Formats

DLNA defines "Profiles" for interoperability, but support varies.

- **Images:** JPEG, PNG, GIF.
- **Audio:** MP3, AAC, WMA, LPCM.
- **Video:** MPEG-2, MPEG-4 (AVC/H.264), WMV.
- **Containers:** MP4, AVI, MKV (often supported but not strictly mandated by
  base DLNA).

## Potential Challenges and Limitations

1. **Codec Compatibility:** Devices are picky about codecs and containers.
   Transcoding might be required if the source format doesn't match the
   renderer's capabilities.
2. **Network Reliability:** Multicast (SSDP) can be unreliable on some Wi-Fi
   networks or blocked by firewalls/routers.
3. **State Management:** Keeping track of playback state (TransportState)
   requires polling or subscribing to UPnP events (GENA), which adds
   complexity.
4. **Metadata:** Constructing correct DIDL-Lite metadata is often required for
   the renderer to accept the URI.

## Python Libraries

- **Cohen3:** Comprehensive framework for DLNA/UPnP (Server and Client).
- **async-upnp-client:** Modern, `asyncio`-based UPnP client library. Good for
   building a custom controller.
- **nano-dlna:** Lightweight tool to play media on DLNA devices. Good reference
   for minimal implementation.
- **gupnp:** Python bindings for GUPnP (requires GObject/GLib).

## References

- [UPnP Device Architecture 1.1](http://upnp.org/specs/arch/UPnP-arch-DeviceArchitecture-v1.1.pdf)
- [DLNA Guidelines](https://www.dlna.org/guidelines)
- [nano-dlna Source Code](https://github.com/daddy-bones/nano-dlna)
