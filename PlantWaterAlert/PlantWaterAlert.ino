/*
 * PlantWaterAlert.ino
 *
 * Monitors soil moisture with an Icstation HD-38 resistive hygrometer and sends
 * a WhatsApp message (via CallMeBot free API) when water is low.
 * Status messages are displayed on the Arduino Uno R4 WiFi 12×8 LED matrix.
 *
 * Target board : Arduino Uno R4 WiFi
 *
 * Required libraries (install via Arduino Library Manager):
 *   - Arduino_LED_Matrix   (built-in for Uno R4 WiFi)
 *   - ArduinoHttpClient
 *
 * Sensor wiring (Icstation HD-38):
 *   VCC  →  5 V   (use 5 V, not 3.3 V, for stable probe readings)
 *   GND  →  GND
 *   AO   →  A0    (analog output — more precise than the DO pin)
 *   DO   →  not used  (DO threshold set by blue trim-pot; irrelevant here)
 *
 * LED matrix status messages:
 *   "PLANT MON"  — startup banner
 *   "WIFI..."    — connecting to WiFi
 *   "WIFI OK"    — connected
 *   "NO WIFI"    — connection failed
 *   "OK"         — soil moisture is fine   (+ droplet icon)
 *   "DRY!"       — soil is dry, alert sent (+ warning icon)
 *   "WAPP..."    — sending WhatsApp via CallMeBot
 *   "WAPP OK"    — WhatsApp sent successfully
 *   "WAPP ERR"   — WhatsApp send failed
 *   "SENT!"      — alert delivered
 *   "GOVEE..."   — scanning for Govee device / sending command
 *   "GOVEE ON"   — Govee light turned on (dry alert)
 *   "GOVEE OK"   — Govee device found or IP set
 *   "NO GOVEE"   — scan found no device (alerts still sent)
 */

#include <WiFiS3.h>
#include <ArduinoHttpClient.h>
#include <Arduino_LED_Matrix.h>   // Built-in for Uno R4 WiFi
#include "config.h"
#include "Govee.h"

// ─── LED Matrix ───────────────────────────────────────────────────────────────
ArduinoLEDMatrix matrix;

// Static icon: water droplet — shown when soil is moist (OK)
// 12 cols × 8 rows, packed into 3 × uint32_t (MSB = row 0, col 0)
static const uint32_t ICON_DROPLET[3] = {
  0x0400E01F,   // row 0: ..X.........  row 1: .XXX........  row 2 (top 8): ..XXXXX.
  0x03F83F83,   // row 2 (bot 4): ....  row 3: .XXXXXXX.  row 4: .XXXXXXX.  row 5(top4): ..XX
  0xF81F0040    // row 5 (bot 8): XXXXX... row 6: ..XXXXX.  row 7: .....X..
};

// Static icon: exclamation mark — shown when soil is dry (ALERT)
static const uint32_t ICON_EXCLAIM[3] = {
  0x18181818,   // rows 0-1: ..XXX...  ..XXX...
  0x18001800,   // rows 2-3: ..XXX...  ........
  0x18001800    // rows 4-5: ..XXX...  ........  rows 6-7 mirrored
};

// ─── State ────────────────────────────────────────────────────────────────────
static unsigned long lastCheckTime  = 0;
static unsigned long lastAlertTime  = 0;
static bool          goveeAlertOn   = false;  // true while Govee is lit for a dry alert

// ─── Prototypes ───────────────────────────────────────────────────────────────
void    connectWiFi();
int     readMoisture();
bool    sendWhatsApp(int moistureValue);
void    showScroll(const char* msg, uint8_t speedMs = 80);
void    showIcon(const uint32_t frame[3]);
String  urlencode(const String& str);

// ─────────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 4000);

  matrix.begin();

  // Startup banner
  showScroll("PLANT MON", 80);

  Serial.println(F("\n=== Plant Water Alert ==="));
  Serial.print(F("Dry threshold (ADC): "));
  Serial.println(DRY_THRESHOLD);

  connectWiFi();

  // ── Govee LAN init ──────────────────────────────────────────────────────────
  if (WiFi.status() == WL_CONNECTED) {
    goveeInit();
    if (strlen(GOVEE_DEVICE_IP) > 0) {
      goveeSetIP(GOVEE_DEVICE_IP);
      showScroll("GOVEE OK", 80);
    } else {
      showScroll("GOVEE...", 80);
      showScroll(goveeScan() ? "GOVEE OK" : "NO GOVEE", 80);
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("WiFi lost — reconnecting..."));
    connectWiFi();
    // Re-init Govee UDP socket after reconnect
    if (WiFi.status() == WL_CONNECTED) {
      goveeInit();
      if (!goveeIsReady()) {
        showScroll("GOVEE...", 80);
        showScroll(goveeScan() ? "GOVEE OK" : "NO GOVEE", 80);
      }
    }
  }

  unsigned long now = millis();
  if (now - lastCheckTime < CHECK_INTERVAL_MS) return;
  lastCheckTime = now;

  // ── Read sensor ─────────────────────────────────────────────────────────────
  int  moisture = readMoisture();
  bool isDry    = (moisture > DRY_THRESHOLD);

  Serial.print(F("Moisture ADC: "));
  Serial.print(moisture);
  Serial.print(F("  ->  "));
  Serial.println(isDry ? F("DRY!") : F("OK"));

  if (!isDry) {
    // If the Govee was on for a dry alert, turn it off now that soil is moist
    if (goveeAlertOn) {
      goveeOff();
      goveeAlertOn = false;
      Serial.println(F("Govee alert light OFF — soil is moist"));
    }
    showIcon(ICON_DROPLET);
    delay(2000);
    showScroll("OK", 80);
    return;
  }

  // ── Soil is dry ─────────────────────────────────────────────────────────────
  showIcon(ICON_EXCLAIM);
  delay(1500);
  showScroll("DRY!", 80);

  // Turn on Govee alert light the first time we detect dry (stays on until watered)
  if (!goveeAlertOn && goveeIsReady()) {
    showScroll("GOVEE...", 80);
    goveeOn();
    goveeColor(GOVEE_ALERT_R, GOVEE_ALERT_G, GOVEE_ALERT_B);
    goveeBrightness(GOVEE_BRIGHTNESS);
    goveeAlertOn = true;
    showScroll("GOVEE ON", 80);
    Serial.println(F("Govee alert light ON"));
  }

  // Respect cooldown to avoid spam
  if (lastAlertTime != 0 && (now - lastAlertTime < ALERT_COOLDOWN_MS)) {
    Serial.println(F("In cooldown — skipping alert."));
    return;
  }

  // ── Send WhatsApp via CallMeBot ─────────────────────────────────────────────
  showScroll("WAPP...", 80);
  Serial.println(F("Sending WhatsApp..."));
  bool wappOk = sendWhatsApp(moisture);
  showScroll(wappOk ? "WAPP OK" : "WAPP ERR", 80);

  // ── Result ──────────────────────────────────────────────────────────────────
  if (wappOk) {
    lastAlertTime = now;
    showScroll("SENT!", 70);
    Serial.println(F("Alert sent. Next alert in 1 hour."));
  } else {
    Serial.println(F("WhatsApp failed — will retry next cycle."));
  }
}

// ─── LED Matrix helpers ───────────────────────────────────────────────────────
//
// Self-contained 3×5 bitmap font + manual scrolling via loadFrame().
// No ArduinoGraphics dependency — works with all Arduino_LED_Matrix versions.
//
// Font format: each character = 3 bytes (one per pixel column, left to right).
// Within each byte: bit 4 = top row, bit 0 = bottom row (5 rows used).
// Characters are indexed as (ASCII - 0x20), covering 0x20 (' ') through 0x5A ('Z').

static const uint8_t FONT3x5[][3] = {
  {0x00,0x00,0x00}, // ' ' 0x20
  {0x00,0x1D,0x00}, // '!' 0x21
  {0x00,0x00,0x00}, // '"' 0x22
  {0x00,0x00,0x00}, // '#' 0x23
  {0x00,0x00,0x00}, // '$' 0x24
  {0x00,0x00,0x00}, // '%' 0x25
  {0x00,0x00,0x00}, // '&' 0x26
  {0x00,0x00,0x00}, // ''' 0x27
  {0x00,0x00,0x00}, // '(' 0x28
  {0x00,0x00,0x00}, // ')' 0x29
  {0x00,0x00,0x00}, // '*' 0x2A
  {0x00,0x00,0x00}, // '+' 0x2B
  {0x00,0x00,0x00}, // ',' 0x2C
  {0x00,0x04,0x00}, // '-' 0x2D
  {0x00,0x01,0x00}, // '.' 0x2E
  {0x00,0x00,0x00}, // '/' 0x2F
  {0x0E,0x11,0x0E}, // '0' 0x30
  {0x09,0x1F,0x01}, // '1' 0x31
  {0x13,0x15,0x09}, // '2' 0x32
  {0x11,0x15,0x1F}, // '3' 0x33
  {0x1C,0x04,0x1F}, // '4' 0x34
  {0x1D,0x15,0x17}, // '5' 0x35
  {0x1F,0x15,0x17}, // '6' 0x36
  {0x10,0x17,0x18}, // '7' 0x37
  {0x1F,0x15,0x1F}, // '8' 0x38
  {0x1D,0x15,0x1F}, // '9' 0x39
  {0x00,0x00,0x00}, // ':' 0x3A
  {0x00,0x00,0x00}, // ';' 0x3B
  {0x00,0x00,0x00}, // '<' 0x3C
  {0x00,0x00,0x00}, // '=' 0x3D
  {0x00,0x00,0x00}, // '>' 0x3E
  {0x00,0x00,0x00}, // '?' 0x3F
  {0x00,0x00,0x00}, // '@' 0x40
  {0x0F,0x14,0x0F}, // 'A' 0x41
  {0x1F,0x15,0x0A}, // 'B' 0x42
  {0x1F,0x11,0x11}, // 'C' 0x43
  {0x1F,0x11,0x0E}, // 'D' 0x44
  {0x1F,0x15,0x11}, // 'E' 0x45
  {0x1F,0x14,0x10}, // 'F' 0x46
  {0x1F,0x11,0x17}, // 'G' 0x47
  {0x1F,0x04,0x1F}, // 'H' 0x48
  {0x11,0x1F,0x11}, // 'I' 0x49
  {0x03,0x11,0x1E}, // 'J' 0x4A
  {0x1F,0x04,0x1B}, // 'K' 0x4B
  {0x1F,0x01,0x01}, // 'L' 0x4C
  {0x1F,0x08,0x1F}, // 'M' 0x4D
  {0x1F,0x0C,0x1F}, // 'N' 0x4E
  {0x0E,0x11,0x0E}, // 'O' 0x4F
  {0x1F,0x14,0x08}, // 'P' 0x50
  {0x0E,0x13,0x0F}, // 'Q' 0x51
  {0x1F,0x16,0x09}, // 'R' 0x52
  {0x1D,0x15,0x17}, // 'S' 0x53
  {0x10,0x1F,0x10}, // 'T' 0x54
  {0x1F,0x01,0x1F}, // 'U' 0x55
  {0x1E,0x03,0x1E}, // 'V' 0x56
  {0x1F,0x02,0x1F}, // 'W' 0x57
  {0x1B,0x0E,0x1B}, // 'X' 0x58
  {0x18,0x0F,0x18}, // 'Y' 0x59
  {0x13,0x15,0x19}, // 'Z' 0x5A
};

// Pack a pixel on/off into the uint32_t[3] frame format used by loadFrame().
// Pixel (row, col): row 0..7 top to bottom, col 0..11 left to right.
// Bit layout: pixel index = row*12+col; bit position in 96-bit stream = 95-index;
// frame[0]=bits95-64, frame[1]=bits63-32, frame[2]=bits31-0.
static void setPixel(uint32_t frame[3], int row, int col) {
  int idx  = row * 12 + col;
  int fi   = idx / 32;
  int bi   = 31 - (idx % 32);
  frame[fi] |= (1UL << bi);
}

// Scroll a text message across the 12×8 matrix using only loadFrame().
// speedMs: milliseconds per pixel column shift (lower = faster scroll).
// Characters are 3px wide + 1px gap = 4px per character.
// Text is vertically centered in rows 1–5 of the 8-row display.
void showScroll(const char* msg, uint8_t speedMs) {
  const int CHAR_W  = 4;   // glyph width (3) + gap (1)
  const int GLYPH_W = 3;
  const int GLYPH_H = 5;
  const int ROW_OFF = 1;   // top padding so glyphs sit in rows 1-5

  int msgLen      = (int)strlen(msg);
  int totalFrames = 12 + msgLen * CHAR_W; // 12-col blank lead-in, then text scrolls out

  uint32_t frame[3];

  for (int offset = 0; offset < totalFrames; offset++) {
    frame[0] = frame[1] = frame[2] = 0;

    for (int col = 0; col < 12; col++) {
      int textCol  = (offset + col) - 12; // position in text pixel stream
      if (textCol < 0) continue;

      int charIdx  = textCol / CHAR_W;
      int glyphCol = textCol % CHAR_W;
      if (charIdx >= msgLen || glyphCol >= GLYPH_W) continue;

      char c = msg[charIdx];
      if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A'); // fold to uppercase
      int fi = (uint8_t)c - 0x20;
      if (fi < 0 || fi >= (int)(sizeof(FONT3x5) / 3)) continue;

      uint8_t colData = FONT3x5[fi][glyphCol];
      for (int row = 0; row < GLYPH_H; row++) {
        if ((colData >> (GLYPH_H - 1 - row)) & 1)
          setPixel(frame, ROW_OFF + row, col);
      }
    }

    matrix.loadFrame(frame);
    delay(speedMs);
  }

  Serial.print(F("[LED] "));
  Serial.println(msg);
}

// Display a static 12×8 icon frame.
void showIcon(const uint32_t frame[3]) {
  matrix.loadFrame(frame);
}

// ─── WiFi ──────────────────────────────────────────────────────────────────────
void connectWiFi() {
  showScroll("WIFI...", 80);
  Serial.print(F("Connecting to "));
  Serial.println(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print('.');
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    showScroll("WIFI OK", 80);
    Serial.print(F("\nIP: "));
    Serial.println(WiFi.localIP());
  } else {
    showScroll("NO WIFI", 80);
    Serial.println(F("\nWiFi FAILED — will retry on next check."));
  }
}

// ─── Sensor ───────────────────────────────────────────────────────────────────
// Averages 10 readings to reduce noise from the resistive probe.
int readMoisture() {
  long sum = 0;
  for (int i = 0; i < 10; i++) {
    sum += analogRead(MOISTURE_SENSOR_PIN);
    delay(10);
  }
  return (int)(sum / 10);
}

// ─── WhatsApp via CallMeBot free API ─────────────────────────────────────────
// GET https://api.callmebot.com/whatsapp.php?phone=PHONE&text=TEXT&apikey=KEY
// Reference: https://www.callmebot.com/blog/free-api-whatsapp-messages/
bool sendWhatsApp(int moistureValue) {
  char msgBuf[160];
  snprintf(msgBuf, sizeof(msgBuf),
    "Plant alert! Soil moisture ADC: %d (dry > %d). Time to water!",
    moistureValue, DRY_THRESHOLD);

  String path = "/whatsapp.php?phone=" + urlencode(String(CALLMEBOT_PHONE))
              + "&text="  + urlencode(String(msgBuf))
              + "&apikey=" + urlencode(String(CALLMEBOT_APIKEY));

  WiFiSSLClient sslClient;
  HttpClient http(sslClient, "api.callmebot.com", 443);
  http.get(path);

  int statusCode = http.responseStatusCode();
  Serial.print(F("CallMeBot: "));
  Serial.println(statusCode);
  if (statusCode < 200 || statusCode > 299) {
    Serial.println(http.responseBody());
    return false;
  }
  return true;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
String urlencode(const String& str) {
  String encoded;
  for (unsigned int i = 0; i < str.length(); i++) {
    char c = str[i];
    if (isAlphaNumeric(c) || c == '-' || c == '_' || c == '.' || c == '~') {
      encoded += c;
    } else {
      char buf[4];
      snprintf(buf, sizeof(buf), "%%%02X", (unsigned char)c);
      encoded += buf;
    }
  }
  return encoded;
}

