/*
 * Muse Brainwave LCD Display
 *
 * This Arduino sketch receives brainwave data from a Muse headband
 * (via serial from a Python bridge) and displays the values on a 16x2 LCD.
 *
 * Brainwave bands displayed:
 *   - Delta (0.5-4 Hz): Deep sleep
 *   - Theta (4-8 Hz): Drowsiness, meditation
 *   - Alpha (8-12 Hz): Relaxed, calm
 *   - Beta (12-30 Hz): Active thinking
 *   - Gamma (30-100 Hz): Higher cognitive functions
 *
 * Hardware:
 *   - Arduino Uno/Nano/Mega
 *   - 16x2 LCD with I2C backpack (or direct connection)
 *   - USB connection to computer running Muse bridge script
 *
 * Serial Protocol:
 *   Receives CSV format: "delta,theta,alpha,beta,gamma\n"
 *   Values are floats from 0.0 to 1.0 (normalized)
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// LCD Configuration - adjust address if needed (common: 0x27 or 0x3F)
#define LCD_ADDRESS 0x27
#define LCD_COLS 16
#define LCD_ROWS 2

// Serial Configuration
#define SERIAL_BAUD 9600
#define MAX_INPUT_LENGTH 64

// Display modes
#define MODE_ALL_BANDS 0      // Show all bands summary
#define MODE_DELTA_THETA 1    // Show Delta and Theta details
#define MODE_ALPHA_BETA 2     // Show Alpha and Beta details
#define MODE_GAMMA_FOCUS 3    // Show Gamma and Focus score
#define MODE_BAR_GRAPH 4      // Show bar graph visualization
#define NUM_MODES 5

// Button pin for cycling display modes (optional)
#define MODE_BUTTON_PIN 2

// Initialize LCD
LiquidCrystal_I2C lcd(LCD_ADDRESS, LCD_COLS, LCD_ROWS);

// Brainwave data storage
struct BrainwaveData {
  float delta;
  float theta;
  float alpha;
  float beta;
  float gamma;
  bool valid;
  unsigned long lastUpdate;
};

BrainwaveData brainwaves = {0, 0, 0, 0, 0, false, 0};

// Display state
int currentMode = MODE_ALL_BANDS;
unsigned long lastModeChange = 0;
unsigned long lastDisplayUpdate = 0;
const unsigned long DISPLAY_UPDATE_INTERVAL = 250;  // Update display every 250ms
const unsigned long DATA_TIMEOUT = 3000;            // Show "No Signal" after 3 seconds

// Custom characters for bar graph
byte barChars[8][8] = {
  {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F},  // 1 bar
  {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F},  // 2 bars
  {0x00, 0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F},  // 3 bars
  {0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F},  // 4 bars
  {0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F},  // 5 bars
  {0x00, 0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F},  // 6 bars
  {0x00, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F},  // 7 bars
  {0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F}   // 8 bars (full)
};

// Input buffer for serial data
char inputBuffer[MAX_INPUT_LENGTH];
int inputIndex = 0;

void setup() {
  // Initialize serial communication
  Serial.begin(SERIAL_BAUD);

  // Initialize LCD
  lcd.init();
  lcd.backlight();

  // Create custom characters for bar graph
  for (int i = 0; i < 8; i++) {
    lcd.createChar(i, barChars[i]);
  }

  // Setup mode button with internal pullup
  pinMode(MODE_BUTTON_PIN, INPUT_PULLUP);

  // Display startup message
  lcd.setCursor(0, 0);
  lcd.print("Muse Brainwave");
  lcd.setCursor(0, 1);
  lcd.print("LCD Monitor v1.0");

  delay(2000);
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("Waiting for");
  lcd.setCursor(0, 1);
  lcd.print("Muse data...");
}

void loop() {
  // Read serial data
  readSerialData();

  // Check mode button
  checkModeButton();

  // Update display periodically
  if (millis() - lastDisplayUpdate >= DISPLAY_UPDATE_INTERVAL) {
    updateDisplay();
    lastDisplayUpdate = millis();
  }
}

void readSerialData() {
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      if (inputIndex > 0) {
        inputBuffer[inputIndex] = '\0';
        parseData(inputBuffer);
        inputIndex = 0;
      }
    } else if (inputIndex < MAX_INPUT_LENGTH - 1) {
      inputBuffer[inputIndex++] = c;
    }
  }
}

void parseData(const char* data) {
  // Parse CSV format: "delta,theta,alpha,beta,gamma"
  float values[5];
  int valueIndex = 0;
  char* token;
  char dataCopy[MAX_INPUT_LENGTH];

  strncpy(dataCopy, data, MAX_INPUT_LENGTH - 1);
  dataCopy[MAX_INPUT_LENGTH - 1] = '\0';

  token = strtok(dataCopy, ",");
  while (token != NULL && valueIndex < 5) {
    values[valueIndex++] = atof(token);
    token = strtok(NULL, ",");
  }

  if (valueIndex == 5) {
    brainwaves.delta = constrain(values[0], 0.0, 1.0);
    brainwaves.theta = constrain(values[1], 0.0, 1.0);
    brainwaves.alpha = constrain(values[2], 0.0, 1.0);
    brainwaves.beta = constrain(values[3], 0.0, 1.0);
    brainwaves.gamma = constrain(values[4], 0.0, 1.0);
    brainwaves.valid = true;
    brainwaves.lastUpdate = millis();

    // Send acknowledgment
    Serial.println("OK");
  }
}

void checkModeButton() {
  static bool lastButtonState = HIGH;
  static unsigned long lastDebounceTime = 0;
  const unsigned long debounceDelay = 50;

  bool currentState = digitalRead(MODE_BUTTON_PIN);

  if (currentState != lastButtonState) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (currentState == LOW && lastButtonState == HIGH) {
      // Button pressed - cycle to next mode
      currentMode = (currentMode + 1) % NUM_MODES;
      lastModeChange = millis();
      lcd.clear();
    }
  }

  lastButtonState = currentState;
}

void updateDisplay() {
  // Check for data timeout
  if (millis() - brainwaves.lastUpdate > DATA_TIMEOUT) {
    brainwaves.valid = false;
  }

  if (!brainwaves.valid) {
    displayNoSignal();
    return;
  }

  switch (currentMode) {
    case MODE_ALL_BANDS:
      displayAllBands();
      break;
    case MODE_DELTA_THETA:
      displayDeltaTheta();
      break;
    case MODE_ALPHA_BETA:
      displayAlphaBeta();
      break;
    case MODE_GAMMA_FOCUS:
      displayGammaFocus();
      break;
    case MODE_BAR_GRAPH:
      displayBarGraph();
      break;
  }
}

void displayNoSignal() {
  lcd.setCursor(0, 0);
  lcd.print("  No Signal!    ");
  lcd.setCursor(0, 1);
  lcd.print("Check Muse conn.");
}

void displayAllBands() {
  // Line 1: D:xx T:xx A:xx
  lcd.setCursor(0, 0);
  lcd.print("D:");
  lcd.print(percentValue(brainwaves.delta));
  lcd.print(" T:");
  lcd.print(percentValue(brainwaves.theta));
  lcd.print(" A:");
  lcd.print(percentValue(brainwaves.alpha));

  // Line 2: B:xx G:xx [state]
  lcd.setCursor(0, 1);
  lcd.print("B:");
  lcd.print(percentValue(brainwaves.beta));
  lcd.print(" G:");
  lcd.print(percentValue(brainwaves.gamma));
  lcd.print(" ");
  lcd.print(getMentalState());
}

void displayDeltaTheta() {
  lcd.setCursor(0, 0);
  lcd.print("Delta: ");
  lcd.print(brainwaves.delta, 2);
  lcd.print("  ");
  printBarSmall(brainwaves.delta, 14);

  lcd.setCursor(0, 1);
  lcd.print("Theta: ");
  lcd.print(brainwaves.theta, 2);
  lcd.print("  ");
  printBarSmall(brainwaves.theta, 14);
}

void displayAlphaBeta() {
  lcd.setCursor(0, 0);
  lcd.print("Alpha: ");
  lcd.print(brainwaves.alpha, 2);
  lcd.print("  ");
  printBarSmall(brainwaves.alpha, 14);

  lcd.setCursor(0, 1);
  lcd.print("Beta:  ");
  lcd.print(brainwaves.beta, 2);
  lcd.print("  ");
  printBarSmall(brainwaves.beta, 14);
}

void displayGammaFocus() {
  float focus = calculateFocus();

  lcd.setCursor(0, 0);
  lcd.print("Gamma: ");
  lcd.print(brainwaves.gamma, 2);
  lcd.print("  ");
  printBarSmall(brainwaves.gamma, 14);

  lcd.setCursor(0, 1);
  lcd.print("Focus: ");
  lcd.print(focus, 2);
  lcd.print("  ");
  printBarSmall(focus, 14);
}

void displayBarGraph() {
  // Line 1: Labels
  lcd.setCursor(0, 0);
  lcd.print(" D  T  A  B  G  ");

  // Line 2: Bar graphs
  lcd.setCursor(0, 1);
  lcd.print(" ");
  printBarChar(brainwaves.delta);
  lcd.print("  ");
  printBarChar(brainwaves.theta);
  lcd.print("  ");
  printBarChar(brainwaves.alpha);
  lcd.print("  ");
  printBarChar(brainwaves.beta);
  lcd.print("  ");
  printBarChar(brainwaves.gamma);
  lcd.print(" ");
}

void printBarSmall(float value, int col) {
  lcd.setCursor(col, lcd.getCursorRow());
  if (value > 0.5) {
    lcd.write(byte(7));  // Full bar
  } else if (value > 0.25) {
    lcd.write(byte(4));  // Half bar
  } else {
    lcd.write(byte(1));  // Low bar
  }
}

void printBarChar(float value) {
  int barLevel = (int)(value * 8);
  barLevel = constrain(barLevel, 0, 7);
  lcd.write(byte(barLevel));
}

String percentValue(float value) {
  int percent = (int)(value * 99);
  if (percent < 10) {
    return "0" + String(percent);
  }
  return String(percent);
}

float calculateFocus() {
  // Focus score: higher beta and gamma relative to theta and delta
  // indicates better focus/concentration
  float focusSignals = (brainwaves.beta + brainwaves.gamma) / 2.0;
  float relaxSignals = (brainwaves.theta + brainwaves.delta) / 2.0;

  if (relaxSignals < 0.01) relaxSignals = 0.01;  // Prevent division by zero

  float focus = focusSignals / (focusSignals + relaxSignals);
  return constrain(focus, 0.0, 1.0);
}

String getMentalState() {
  // Determine dominant mental state based on brainwave ratios
  float maxVal = brainwaves.delta;
  String state = "Slp";  // Sleep

  if (brainwaves.theta > maxVal) {
    maxVal = brainwaves.theta;
    state = "Drm";  // Dreamy/Drowsy
  }
  if (brainwaves.alpha > maxVal) {
    maxVal = brainwaves.alpha;
    state = "Rlx";  // Relaxed
  }
  if (brainwaves.beta > maxVal) {
    maxVal = brainwaves.beta;
    state = "Act";  // Active
  }
  if (brainwaves.gamma > maxVal) {
    maxVal = brainwaves.gamma;
    state = "Fcs";  // Focused
  }

  return state;
}

/*
 * Alternative LCD connection without I2C:
 *
 * If not using I2C backpack, replace the LCD initialization with:
 *
 * #include <LiquidCrystal.h>
 *
 * // LCD pins: RS, EN, D4, D5, D6, D7
 * const int rs = 12, en = 11, d4 = 5, d5 = 4, d6 = 3, d7 = 2;
 * LiquidCrystal lcd(rs, en, d4, d5, d6, d7);
 *
 * And in setup(), use:
 * lcd.begin(16, 2);
 *
 * Note: Adjust MODE_BUTTON_PIN if using direct LCD connection
 */
