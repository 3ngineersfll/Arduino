// Scrolling Rainbow Colors for WS2812B 8x8 LED Panel
// Hardware: Arduino Uno R4 + BTF-LIGHTING WS2812B ECO 8x8 (64 LEDs)
//
// Wiring:
//   Panel VCC (RED)   -> 5V external power supply (NOT Arduino 5V pin - panel draws up to 19.2W)
//   Panel GND (WHITE) -> GND (shared with Arduino GND)
//   Panel DI  (GREEN) -> Arduino pin 6
//   Panel DO           -> leave unconnected (or chain to next panel)
//
// Requires: Adafruit NeoPixel library (install via Library Manager)

#include <Adafruit_NeoPixel.h>

#define LED_PIN    6
#define NUM_LEDS   64
#define MATRIX_W   8
#define MATRIX_H   8
#define BRIGHTNESS 30   // 0-255, keep low to limit current draw

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

// Convert x,y to pixel index for typical serpentine/zigzag wiring
uint16_t xyToIndex(uint8_t x, uint8_t y) {
  if (y % 2 == 0) {
    return y * MATRIX_W + x;          // even rows: left to right
  } else {
    return y * MATRIX_W + (MATRIX_W - 1 - x);  // odd rows: right to left
  }
}

// Wheel function: input 0-255, returns a color that transitions R->G->B->R
uint32_t colorWheel(uint8_t pos) {
  pos = 255 - pos;
  if (pos < 85) {
    return strip.Color(255 - pos * 3, 0, pos * 3);
  } else if (pos < 170) {
    pos -= 85;
    return strip.Color(0, pos * 3, 255 - pos * 3);
  } else {
    pos -= 170;
    return strip.Color(pos * 3, 255 - pos * 3, 0);
  }
}

uint16_t offset = 0;

void setup() {
  strip.begin();
  strip.setBrightness(BRIGHTNESS);
  strip.show();
}

void loop() {
  // Diagonal rainbow scroll across the 8x8 matrix
  for (uint8_t y = 0; y < MATRIX_H; y++) {
    for (uint8_t x = 0; x < MATRIX_W; x++) {
      // Spread the hue across both axes + animate with offset
      uint8_t hue = (x * 16) + (y * 16) + offset;
      strip.setPixelColor(xyToIndex(x, y), colorWheel(hue));
    }
  }
  strip.show();
  offset += 2;  // speed of scroll — increase for faster
  delay(30);
}
