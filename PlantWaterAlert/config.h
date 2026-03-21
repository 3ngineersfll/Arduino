#ifndef CONFIG_H
#define CONFIG_H

// ─── WiFi ────────────────────────────────────────────────────────────────────
#define WIFI_SSID       "YOUR_WIFI_SSID"
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"

// ─── Sensor (Icstation HD-38 Resistive Soil Hygrometer) ─────────────────────
// Module board: HD-38 (LM393 comparator + blue trim-pot for DO threshold)
// Wiring:  VCC → 5V,  GND → GND,  AO → A0  (analog; ignore DO pin)
// Note: power from 5V, not 3.3V — the probe needs full rail for stable readings.
// Dry soil = HIGH ADC (~700-1023), Wet soil = LOW ADC (~200-500).
// To calibrate: open Serial Monitor, push probe in dry soil → note value (DRY),
//               then in soaked soil → note value (WET). Set threshold between them.
// The blue trim-pot on the board only affects the DO pin — ignore it for AO use.
#define MOISTURE_SENSOR_PIN     A0
#define DRY_THRESHOLD           650   // ADC value above this = LOW WATER alert
#define CHECK_INTERVAL_MS       30000UL   // Check every 30 seconds
#define ALERT_COOLDOWN_MS       3600000UL // Re-alert at most once per hour

// ─── CallMeBot (WhatsApp) ────────────────────────────────────────────────────
// To get your free API key:
//   1. Add +34 644 60 49 86 to your WhatsApp contacts (name it "CallMeBot")
//   2. Send this message to that contact:
//        I allow callmebot to send me messages
//   3. CallMeBot will reply with your API key — copy it below.
// Reference: https://www.callmebot.com/blog/free-api-whatsapp-messages/
#define CALLMEBOT_PHONE     "+1XXXXXXXXXX"   // Your number in international format (e.g. +14155552671)
#define CALLMEBOT_APIKEY    "YOUR_APIKEY"    // API key received from CallMeBot via WhatsApp

// ─── Govee LAN Control ────────────────────────────────────────────────────────
// Enable in Govee Home App: open device → ⚙ Settings → LAN Control (toggle ON)
// GOVEE_DEVICE_IP: set to the device IP (e.g. "192.168.1.50") to skip auto-scan,
//                  or leave as "" to auto-scan on every boot.
#define GOVEE_DEVICE_IP   ""          // "" = auto-scan, or e.g. "192.168.1.50"
#define GOVEE_ALERT_R     255         // Alert color: orange-red
#define GOVEE_ALERT_G     80
#define GOVEE_ALERT_B     0
#define GOVEE_BRIGHTNESS  80          // Alert brightness % (1–100)

// ─── LED Matrix scroll speed ──────────────────────────────────────────────────
// Milliseconds per pixel shift. Lower = faster scroll. Range: 50–200.
#define SCROLL_SPEED_MS   80

#endif // CONFIG_H
