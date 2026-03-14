#ifndef CONFIG_H
#define CONFIG_H

// ─── WiFi ────────────────────────────────────────────────────────────────────
#define WIFI_SSID       "YOUR_WIFI_SSID"
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"

// ─── Sensor (HiLetgo LM393 Resistive Soil Moisture) ─────────────────────────
// Wiring:  VCC → 3.3V or 5V,  GND → GND,  AO → A0  (use analog for precision)
// Dry soil = HIGH ADC (~700-1023), Wet soil = LOW ADC (~200-500).
// To calibrate: open Serial Monitor, push probe in dry soil → note value (DRY),
//               then in soaked soil → note value (WET). Set threshold between them.
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

// ─── Hardware ────────────────────────────────────────────────────────────────
#define LED_OK_PIN      LED_BUILTIN   // On = soil is moist
#define LED_ALERT_PIN   2             // Connect external LED; on = dry/alert

#endif // CONFIG_H
