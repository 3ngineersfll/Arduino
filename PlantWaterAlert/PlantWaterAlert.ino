/*
 * PlantWaterAlert.ino
 *
 * Monitors soil moisture with a HiLetgo LM393 resistive sensor and sends
 * an email (via SendGrid) and SMS (via Twilio) when water is low.
 * Status messages are displayed on the Arduino Uno R4 WiFi 12×8 LED matrix.
 *
 * Target board : Arduino Uno R4 WiFi
 *
 * Required libraries (install via Arduino Library Manager):
 *   - Arduino_LED_Matrix   (built-in for Uno R4 WiFi)
 *   - ArduinoGraphics      (dependency of Arduino_LED_Matrix)
 *   - ArduinoHttpClient
 *   - ArduinoJson
 *
 * Sensor wiring (LM393):
 *   VCC  →  3.3 V or 5 V
 *   GND  →  GND
 *   AO   →  A0   (analog — more precise than digital DO pin)
 *   DO   →  not used
 *
 * LED matrix status messages:
 *   "PLANT MON"  — startup banner
 *   "WIFI..."    — connecting to WiFi
 *   "WIFI OK"    — connected
 *   "NO WIFI"    — connection failed
 *   "OK"         — soil moisture is fine   (+ droplet icon)
 *   "DRY!"       — soil is dry, alert sent (+ warning icon)
 *   "EMAIL..."   — sending email via SendGrid
 *   "EMAIL OK"   — email sent successfully
 *   "EMAIL ERR"  — email failed
 *   "SMS..."     — sending SMS via Twilio
 *   "SMS OK"     — SMS sent successfully
 *   "SMS ERR"    — SMS failed
 *   "SENT!"      — at least one alert delivered
 *   "BOTH ERR"   — both email and SMS failed
 */

#include <WiFiS3.h>
#include <ArduinoHttpClient.h>
#include <ArduinoJson.h>
#include <Arduino_LED_Matrix.h>   // Built-in for Uno R4 WiFi
#include <ArduinoGraphics.h>      // Required for text rendering on the matrix
#include "config.h"

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
static unsigned long lastCheckTime = 0;
static unsigned long lastAlertTime = 0;

// ─── Prototypes ───────────────────────────────────────────────────────────────
void    connectWiFi();
int     readMoisture();
bool    sendEmail(int moistureValue);
bool    sendSMS(int moistureValue);
void    showScroll(const char* msg, uint8_t speedMs = 80);
void    showIcon(const uint32_t frame[3]);
String  base64Encode(const String& input);
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
}

// ─────────────────────────────────────────────────────────────────────────────
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("WiFi lost — reconnecting..."));
    connectWiFi();
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
    // Show droplet icon and "OK"
    showIcon(ICON_DROPLET);
    delay(2000);
    showScroll("OK", 80);
    return;
  }

  // ── Soil is dry ─────────────────────────────────────────────────────────────
  showIcon(ICON_EXCLAIM);
  delay(1500);
  showScroll("DRY!", 80);

  // Respect cooldown to avoid spam
  if (lastAlertTime != 0 && (now - lastAlertTime < ALERT_COOLDOWN_MS)) {
    Serial.println(F("In cooldown — skipping alert."));
    return;
  }

  // ── Send email ──────────────────────────────────────────────────────────────
  showScroll("EMAIL...", 80);
  Serial.println(F("Sending email..."));
  bool emailOk = sendEmail(moisture);
  showScroll(emailOk ? "EMAIL OK" : "EMAIL ERR", 80);

  // ── Send SMS ────────────────────────────────────────────────────────────────
  showScroll("SMS...", 80);
  Serial.println(F("Sending SMS..."));
  bool smsOk = sendSMS(moisture);
  showScroll(smsOk ? "SMS OK" : "SMS ERR", 80);

  // ── Result ──────────────────────────────────────────────────────────────────
  if (emailOk || smsOk) {
    lastAlertTime = now;
    showScroll("SENT!", 70);
    Serial.println(F("Alert sent. Next alert in 1 hour."));
  } else {
    showScroll("BOTH ERR", 80);
    Serial.println(F("Both alerts failed — will retry next cycle."));
  }
}

// ─── LED Matrix helpers ───────────────────────────────────────────────────────

// Scroll a text message across the 12×8 matrix.
// speedMs: milliseconds per pixel shift (lower = faster).
void showScroll(const char* msg, uint8_t speedMs) {
  matrix.beginDraw();
    matrix.stroke(0xFFFFFFFF);
    matrix.textScrollSpeed(speedMs);
    matrix.textFont(Font_4x6);
    matrix.beginText(0, 1, 0xFFFFFF);
      matrix.println(msg);
    matrix.endText(SCROLL_LEFT);
  matrix.endDraw();

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

// ─── Email via SendGrid REST API ─────────────────────────────────────────────
bool sendEmail(int moistureValue) {
  WiFiSSLClient sslClient;
  HttpClient http(sslClient, "api.sendgrid.com", 443);

  StaticJsonDocument<512> doc;
  JsonArray personalizations = doc.createNestedArray("personalizations");
  JsonObject p   = personalizations.createNestedObject();
  JsonArray  to  = p.createNestedArray("to");
  JsonObject toObj = to.createNestedObject();
  toObj["email"] = EMAIL_TO;

  JsonObject from = doc.createNestedObject("from");
  from["email"] = EMAIL_FROM;
  from["name"]  = EMAIL_FROM_NAME;

  doc["subject"] = EMAIL_SUBJECT;

  char body[200];
  snprintf(body, sizeof(body),
    "Your plant needs water!\n\n"
    "Soil moisture reading: %d / 1023\n"
    "(Dry threshold: %d)\n\n"
    "Please water your plant soon.",
    moistureValue, DRY_THRESHOLD);

  JsonArray  content  = doc.createNestedArray("content");
  JsonObject textPart = content.createNestedObject();
  textPart["type"]  = "text/plain";
  textPart["value"] = body;

  String payload;
  serializeJson(doc, payload);

  http.beginRequest();
  http.post("/v3/mail/send");
  http.sendHeader("Authorization", String("Bearer ") + SENDGRID_API_KEY);
  http.sendHeader("Content-Type",  "application/json");
  http.sendHeader("Content-Length", payload.length());
  http.beginBody();
  http.print(payload);
  http.endRequest();

  int statusCode = http.responseStatusCode();
  Serial.print(F("SendGrid: "));
  Serial.println(statusCode);
  if (statusCode < 200 || statusCode > 299) {
    Serial.println(http.responseBody());
    return false;
  }
  return true;
}

// ─── SMS via Twilio REST API ──────────────────────────────────────────────────
bool sendSMS(int moistureValue) {
  WiFiSSLClient sslClient;
  HttpClient http(sslClient, "api.twilio.com", 443);

  String credentials = base64Encode(
    String(TWILIO_ACCOUNT_SID) + ":" + String(TWILIO_AUTH_TOKEN));

  char msgBuf[140];
  snprintf(msgBuf, sizeof(msgBuf),
    "Plant alert! Soil moisture ADC: %d (dry > %d). Time to water!",
    moistureValue, DRY_THRESHOLD);

  String formBody = "To="   + urlencode(SMS_TO_NUMBER)
                  + "&From=" + urlencode(TWILIO_FROM_NUMBER)
                  + "&Body=" + urlencode(String(msgBuf));

  String path = "/2010-04-01/Accounts/";
  path += TWILIO_ACCOUNT_SID;
  path += "/Messages.json";

  http.beginRequest();
  http.post(path);
  http.sendHeader("Authorization", String("Basic ") + credentials);
  http.sendHeader("Content-Type",  "application/x-www-form-urlencoded");
  http.sendHeader("Content-Length", formBody.length());
  http.beginBody();
  http.print(formBody);
  http.endRequest();

  int statusCode = http.responseStatusCode();
  Serial.print(F("Twilio: "));
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

String base64Encode(const String& input) {
  static const char table[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  String output;
  int i = 0;
  unsigned char c3[3], c4[4];
  unsigned int len = input.length();

  while (len--) {
    c3[i++] = (unsigned char)input[input.length() - len - 1];
    if (i == 3) {
      c4[0] = (c3[0] & 0xfc) >> 2;
      c4[1] = ((c3[0] & 0x03) << 4) | ((c3[1] & 0xf0) >> 4);
      c4[2] = ((c3[1] & 0x0f) << 2) | ((c3[2] & 0xc0) >> 6);
      c4[3] = c3[2] & 0x3f;
      for (i = 0; i < 4; i++) output += table[c4[i]];
      i = 0;
    }
  }
  if (i) {
    for (int j = i; j < 3; j++) c3[j] = 0;
    c4[0] = (c3[0] & 0xfc) >> 2;
    c4[1] = ((c3[0] & 0x03) << 4) | ((c3[1] & 0xf0) >> 4);
    c4[2] = ((c3[1] & 0x0f) << 2) | ((c3[2] & 0xc0) >> 6);
    for (int j = 0; j < i + 1; j++) output += table[c4[j]];
    while (i++ < 3) output += '=';
  }
  return output;
}
