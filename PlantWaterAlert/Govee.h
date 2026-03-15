/*
 * Govee.h — Govee LAN Control (UDP) for Arduino Uno R4 WiFi
 *
 * Commands are sent via UDP to the device on port 4003.
 * Discovery uses a UDP multicast to 239.255.255.250:4001;
 * the device responds from port 4002.
 *
 * Prerequisites:
 *   - LAN Control must be enabled in the Govee Home App:
 *     Device → ⚙ Settings → LAN Control  (toggle ON)
 *   - Arduino must be on the same LAN subnet as the Govee device.
 *
 * Public API:
 *   goveeInit()                — call once after WiFi connects
 *   goveeSetIP("192.168.x.y") — skip scan, use a known IP
 *   goveeScan(timeoutMs)      — auto-discover first device; returns true if found
 *   goveeOn() / goveeOff()    — power
 *   goveeColor(r, g, b)       — solid RGB color (0–255 each)
 *   goveeBrightness(pct)      — brightness 1–100
 *   goveeIsReady()            — true once a device IP is known
 */

#pragma once

#include <WiFiS3.h>

// ─── Ports ────────────────────────────────────────────────────────────────────
static const uint16_t GOVEE_CMD_PORT  = 4003;
static const uint16_t GOVEE_SCAN_PORT = 4001;
static const uint16_t GOVEE_RESP_PORT = 4002;
static const char     GOVEE_MULTICAST[] = "239.255.255.250";

// ─── Internal state ───────────────────────────────────────────────────────────
static WiFiUDP   _goveeUdp;
static IPAddress _goveeIP;
static bool      _goveeFound = false;

// ─── Helpers ──────────────────────────────────────────────────────────────────
static void _goveeSend(const char* json) {
  if (!_goveeFound) {
    Serial.println(F("Govee: no device — command skipped"));
    return;
  }
  _goveeUdp.beginPacket(_goveeIP, GOVEE_CMD_PORT);
  _goveeUdp.print(json);
  _goveeUdp.endPacket();
}

// ─── Public API ───────────────────────────────────────────────────────────────

// Call once after WiFi is connected.
inline void goveeInit() {
  _goveeUdp.begin(GOVEE_RESP_PORT);
}

// Returns true once a device IP has been set (by scan or goveeSetIP).
inline bool goveeIsReady() { return _goveeFound; }

// Skip scan — use a known static IP (e.g. from your router's DHCP table).
inline void goveeSetIP(const char* ip) {
  _goveeIP.fromString(ip);
  _goveeFound = true;
  Serial.print(F("Govee IP set: "));
  Serial.println(_goveeIP);
}

// Multicast scan; returns true if a device responds within timeoutMs.
bool goveeScan(unsigned long timeoutMs = 4000) {
  Serial.println(F("Govee: scanning..."));

  // Send discovery broadcast
  WiFiUDP scanUdp;
  scanUdp.beginPacket(GOVEE_MULTICAST, GOVEE_SCAN_PORT);
  scanUdp.print(
    "{\"msg\":{\"cmd\":\"scan\",\"data\":{\"account_topic\":\"reserve\"}}}");
  scanUdp.endPacket();

  char buf[256];
  unsigned long deadline = millis() + timeoutMs;

  while (millis() < deadline) {
    int pktLen = _goveeUdp.parsePacket();
    if (pktLen > 0) {
      int readLen = min(pktLen, (int)sizeof(buf) - 1);
      _goveeUdp.read(buf, readLen);
      buf[readLen] = '\0';

      _goveeIP    = _goveeUdp.remoteIP();
      _goveeFound = true;

      Serial.print(F("Govee found at "));
      Serial.print(_goveeIP);
      Serial.print(F("  resp: "));
      Serial.println(buf);
      return true;
    }
    delay(50);
  }

  Serial.println(F("Govee: no device found in scan window"));
  return false;
}

// Power on / off
inline void goveeOn()  { _goveeSend("{\"msg\":{\"cmd\":\"turn\",\"data\":{\"value\":1}}}"); }
inline void goveeOff() { _goveeSend("{\"msg\":{\"cmd\":\"turn\",\"data\":{\"value\":0}}}"); }

// Brightness: 1–100
inline void goveeBrightness(uint8_t pct) {
  char buf[64];
  snprintf(buf, sizeof(buf),
    "{\"msg\":{\"cmd\":\"brightness\",\"data\":{\"value\":%d}}}", pct);
  _goveeSend(buf);
}

// Solid RGB color (0–255 each channel)
inline void goveeColor(uint8_t r, uint8_t g, uint8_t b) {
  char buf[96];
  snprintf(buf, sizeof(buf),
    "{\"msg\":{\"cmd\":\"color\","
    "\"data\":{\"color\":{\"r\":%d,\"g\":%d,\"b\":%d}}}}",
    r, g, b);
  _goveeSend(buf);
}
