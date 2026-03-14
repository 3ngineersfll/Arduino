/*
 * PlantWaterAlert.ino
 *
 * Monitors soil moisture with a HiLetgo LM393 resistive sensor and sends
 * an email (via SendGrid) and SMS (via Twilio) when water is low.
 *
 * Target board : Arduino Uno R4 WiFi (WiFiS3 + WiFiSSLClient)
 * Also works   : Arduino MKR WiFi 1010 / Nano 33 IoT — change WiFiS3.h
 *                to WiFiNINA.h and WiFiSSLClient to WiFiSSLClient (same name,
 *                different library). All other code stays identical.
 *
 * Required libraries (install via Arduino Library Manager):
 *   - WiFiS3          (built-in for Uno R4 WiFi)
 *   - ArduinoHttpClient
 *   - ArduinoJson
 *
 * Sensor wiring (LM393):
 *   VCC  → 3.3 V or 5 V
 *   GND  → GND
 *   AO   → A0   (analog — more precise than DO)
 *   DO   → not used (threshold set by on-board potentiometer; optional)
 */

#include <WiFiS3.h>          // Arduino Uno R4 WiFi
#include <ArduinoHttpClient.h>
#include <ArduinoJson.h>
#include "config.h"

// ─── State ───────────────────────────────────────────────────────────────────
static unsigned long lastCheckTime  = 0;
static unsigned long lastAlertTime  = 0;
static bool          wifiConnected  = false;

// ─── Prototypes ──────────────────────────────────────────────────────────────
void     connectWiFi();
int      readMoisture();
bool     sendEmail(int moistureValue);
bool     sendSMS(int moistureValue);
String   base64Encode(const String& input);

// ─────────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 4000);   // wait up to 4 s for Serial Monitor

  pinMode(LED_OK_PIN,    OUTPUT);
  pinMode(LED_ALERT_PIN, OUTPUT);
  digitalWrite(LED_OK_PIN,    LOW);
  digitalWrite(LED_ALERT_PIN, LOW);

  Serial.println(F("\n=== Plant Water Alert ==="));
  Serial.print(F("Dry threshold (ADC): "));
  Serial.println(DRY_THRESHOLD);

  connectWiFi();
}

// ─────────────────────────────────────────────────────────────────────────────
void loop() {
  // Reconnect WiFi if dropped
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("WiFi lost — reconnecting…"));
    connectWiFi();
  }

  unsigned long now = millis();
  if (now - lastCheckTime < CHECK_INTERVAL_MS) return;
  lastCheckTime = now;

  // ── Read sensor ────────────────────────────────────────────────────────────
  int moisture = readMoisture();
  bool isDry   = (moisture > DRY_THRESHOLD);

  // Update indicator LEDs
  digitalWrite(LED_OK_PIN,    isDry ? LOW  : HIGH);
  digitalWrite(LED_ALERT_PIN, isDry ? HIGH : LOW);

  Serial.print(F("Moisture ADC: "));
  Serial.print(moisture);
  Serial.print(F("  →  "));
  Serial.println(isDry ? F("DRY — needs water!") : F("OK"));

  // ── Alert (with cooldown) ──────────────────────────────────────────────────
  if (isDry && (now - lastAlertTime >= ALERT_COOLDOWN_MS || lastAlertTime == 0)) {
    Serial.println(F("Sending alerts…"));

    bool emailOk = sendEmail(moisture);
    bool smsOk   = sendSMS(moisture);

    if (emailOk || smsOk) {
      lastAlertTime = now;
      Serial.println(F("Alerts sent. Next alert in 1 hour."));
    } else {
      Serial.println(F("Both alerts failed — will retry next cycle."));
    }
  }
}

// ─── WiFi ─────────────────────────────────────────────────────────────────────
void connectWiFi() {
  Serial.print(F("Connecting to "));
  Serial.print(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print('.');
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(F("\nWiFi connected!"));
    Serial.print(F("IP: "));
    Serial.println(WiFi.localIP());
    wifiConnected = true;
  } else {
    Serial.println(F("\nWiFi connection FAILED. Will retry next cycle."));
    wifiConnected = false;
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

// ─── Email via SendGrid REST API ──────────────────────────────────────────────
bool sendEmail(int moistureValue) {
  WiFiSSLClient sslClient;
  HttpClient http(sslClient, "api.sendgrid.com", 443);

  // Build JSON payload
  StaticJsonDocument<512> doc;
  JsonArray personalizations = doc.createNestedArray("personalizations");
  JsonObject p = personalizations.createNestedObject();
  JsonArray to = p.createNestedArray("to");
  JsonObject toObj = to.createNestedObject();
  toObj["email"] = EMAIL_TO;

  JsonObject from = doc.createNestedObject("from");
  from["email"] = EMAIL_FROM;
  from["name"]  = EMAIL_FROM_NAME;

  doc["subject"] = EMAIL_SUBJECT;

  JsonArray content  = doc.createNestedArray("content");
  JsonObject textPart = content.createNestedObject();
  textPart["type"]  = "text/plain";

  char body[200];
  snprintf(body, sizeof(body),
    "Your plant needs water!\n\n"
    "Soil moisture reading: %d / 1023\n"
    "(Dry threshold: %d)\n\n"
    "Please water your plant soon.",
    moistureValue, DRY_THRESHOLD);
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
  String response = http.responseBody();

  Serial.print(F("SendGrid status: "));
  Serial.println(statusCode);
  if (statusCode < 200 || statusCode > 299) {
    Serial.println(response);
    return false;
  }
  return true;
}

// ─── SMS via Twilio REST API ───────────────────────────────────────────────────
bool sendSMS(int moistureValue) {
  WiFiSSLClient sslClient;

  String host = String("api.twilio.com");
  HttpClient http(sslClient, host, 443);

  // Twilio uses HTTP Basic auth: AccountSID:AuthToken → Base64
  String credentials = base64Encode(
    String(TWILIO_ACCOUNT_SID) + ":" + String(TWILIO_AUTH_TOKEN));

  char msgBuf[140];
  snprintf(msgBuf, sizeof(msgBuf),
    "Plant alert! Soil moisture ADC: %d (dry > %d). Time to water!",
    moistureValue, DRY_THRESHOLD);

  // URL-encode the form body
  String body = "To=" + urlencode(SMS_TO_NUMBER)
              + "&From=" + urlencode(TWILIO_FROM_NUMBER)
              + "&Body=" + urlencode(String(msgBuf));

  String path = "/2010-04-01/Accounts/";
  path += TWILIO_ACCOUNT_SID;
  path += "/Messages.json";

  http.beginRequest();
  http.post(path);
  http.sendHeader("Authorization", String("Basic ") + credentials);
  http.sendHeader("Content-Type",  "application/x-www-form-urlencoded");
  http.sendHeader("Content-Length", body.length());
  http.beginBody();
  http.print(body);
  http.endRequest();

  int statusCode = http.responseStatusCode();
  String response = http.responseBody();

  Serial.print(F("Twilio status: "));
  Serial.println(statusCode);
  if (statusCode < 200 || statusCode > 299) {
    Serial.println(response);
    return false;
  }
  return true;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

// URL-encode a string (for Twilio form body)
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

// Base64 encode (needed for Twilio Basic auth)
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
