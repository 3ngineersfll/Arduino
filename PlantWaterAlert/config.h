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

// ─── SendGrid (Email) ─────────────────────────────────────────────────────────
// Sign up free at https://sendgrid.com  → Settings → API Keys
#define SENDGRID_API_KEY    "SG.YOUR_SENDGRID_API_KEY"
#define EMAIL_FROM          "alerts@yourdomain.com"
#define EMAIL_FROM_NAME     "Plant Monitor"
#define EMAIL_TO            "you@example.com"
#define EMAIL_SUBJECT       "Plant Needs Water!"

// ─── Twilio (SMS) ─────────────────────────────────────────────────────────────
// Sign up free at https://twilio.com → Console Dashboard
#define TWILIO_ACCOUNT_SID  "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
#define TWILIO_AUTH_TOKEN   "your_auth_token"
#define TWILIO_FROM_NUMBER  "+1XXXXXXXXXX"  // Your Twilio number
#define SMS_TO_NUMBER       "+1XXXXXXXXXX"  // Your phone number

// ─── LED Matrix scroll speed ──────────────────────────────────────────────────
// Milliseconds per pixel shift. Lower = faster scroll. Range: 50–200.
#define SCROLL_SPEED_MS   80

#endif // CONFIG_H
