# Muse Brainwave LCD Display

Display real-time brainwave data from a Muse headband on a 16x2 LCD screen using Arduino.

## Features

- Real-time display of 5 brainwave bands (Delta, Theta, Alpha, Beta, Gamma)
- Multiple display modes (toggle with button):
  - **All Bands**: Overview of all bands with mental state indicator
  - **Delta/Theta**: Detailed view with bar graphs
  - **Alpha/Beta**: Detailed view with bar graphs
  - **Gamma/Focus**: Gamma band with calculated focus score
  - **Bar Graph**: Visual representation of all bands
- Mental state detection (Sleep, Drowsy, Relaxed, Active, Focused)
- Auto-timeout with "No Signal" indicator

## Hardware Requirements

- Arduino Uno, Nano, or Mega
- 16x2 LCD display with I2C backpack (recommended) or direct connection
- Push button (optional, for mode switching)
- USB cable for computer connection
- Muse headband (Muse 2 or Muse S recommended)

## Wiring

### I2C LCD Connection (Recommended)

| LCD Pin | Arduino Pin |
|---------|-------------|
| VCC     | 5V          |
| GND     | GND         |
| SDA     | A4 (Uno) / 20 (Mega) |
| SCL     | A5 (Uno) / 21 (Mega) |

### Mode Button (Optional)

| Button | Arduino Pin |
|--------|-------------|
| One leg | Pin 2      |
| Other leg | GND      |

### Direct LCD Connection (Without I2C)

If not using I2C backpack, see comments in the sketch for pin assignments.

## Software Setup

### 1. Arduino Setup

1. Install the Arduino IDE from [arduino.cc](https://www.arduino.cc/en/software)

2. Install required library:
   - Open Arduino IDE
   - Go to **Sketch > Include Library > Manage Libraries**
   - Search for "LiquidCrystal I2C" by Frank de Brabander
   - Click Install

3. Upload the sketch:
   - Open `MuseBrainwaveLCD.ino`
   - Select your board: **Tools > Board > Arduino Uno** (or your board)
   - Select port: **Tools > Port > COMx** (Windows) or **/dev/ttyUSB0** (Linux)
   - Click Upload

4. If your LCD doesn't display anything:
   - Try changing `LCD_ADDRESS` from `0x27` to `0x3F` in the sketch
   - Run an I2C scanner sketch to find the correct address

### 2. Computer Setup

1. Install Python 3.7+ from [python.org](https://www.python.org/)

2. Install required Python packages:
   ```bash
   pip install pylsl pyserial numpy
   ```

3. Install Muse streaming software (choose one):

   **Option A: muselsl (Recommended for all platforms)**
   ```bash
   pip install muselsl
   ```

   **Option B: BlueMuse (Windows only)**
   - Download from [github.com/kowalej/BlueMuse](https://github.com/kowalej/BlueMuse)

   **Option C: Muse Direct (iOS/Android)**
   - Install from App Store / Play Store
   - Enable LSL streaming in settings

## Usage

### Step 1: Start Muse Streaming

**Using muselsl:**
```bash
# Find your Muse headband
muselsl list

# Start streaming (replace with your Muse's address if needed)
muselsl stream
```

**Using BlueMuse:**
1. Launch BlueMuse
2. Click "Start Streaming" for your Muse device

### Step 2: Run the Bridge Script

```bash
# Windows
python muse_arduino_bridge.py --port COM3

# Linux
python muse_arduino_bridge.py --port /dev/ttyUSB0

# macOS
python muse_arduino_bridge.py --port /dev/cu.usbmodem14201

# List available ports
python muse_arduino_bridge.py --list
```

### Step 3: View Brainwaves on LCD

The LCD will display your brainwave data. Press the mode button to cycle through display modes.

## Testing Without a Muse

Use the test script to verify your Arduino setup:

```bash
python test_without_muse.py --port COM3
```

This sends simulated brainwave data that cycles through different mental states.

## Display Modes

### Mode 1: All Bands
```
D:45 T:32 A:67
B:28 G:15  Rlx
```
Shows all bands as percentages with mental state abbreviation.

### Mode 2: Delta/Theta Detail
```
Delta: 0.45  [#]
Theta: 0.32  [#]
```

### Mode 3: Alpha/Beta Detail
```
Alpha: 0.67  [#]
Beta:  0.28  [#]
```

### Mode 4: Gamma/Focus
```
Gamma: 0.15  [#]
Focus: 0.42  [#]
```

### Mode 5: Bar Graph
```
 D  T  A  B  G
 #  #  #  #  #
```

## Mental State Abbreviations

| Abbr | State | Dominant Band |
|------|-------|---------------|
| Slp  | Sleep | Delta |
| Drm  | Dreamy/Drowsy | Theta |
| Rlx  | Relaxed | Alpha |
| Act  | Active | Beta |
| Fcs  | Focused | Gamma |

## Brainwave Bands

| Band | Frequency | Associated State |
|------|-----------|------------------|
| Delta | 0.5-4 Hz | Deep sleep, healing |
| Theta | 4-8 Hz | Drowsiness, meditation, creativity |
| Alpha | 8-12 Hz | Relaxed, calm, present |
| Beta | 12-30 Hz | Active thinking, problem solving |
| Gamma | 30-100 Hz | Higher cognitive functions, focus |

## Troubleshooting

### LCD shows "No Signal"
- Ensure Muse is streaming via LSL
- Check that the bridge script is running
- Verify the correct serial port

### LCD is blank or shows garbage
- Check I2C address (try 0x27 or 0x3F)
- Verify wiring connections
- Adjust LCD contrast potentiometer

### "No Muse EEG stream found"
- Start muselsl or BlueMuse first
- Ensure Muse is paired and connected
- Check that LSL stream is active

### Serial port errors
- Close Arduino IDE Serial Monitor (it locks the port)
- Try a different USB port
- Check USB cable

## Customization

### Change Update Rate
```bash
python muse_arduino_bridge.py --port COM3 --rate 10  # 10 updates/second
```

### Change Baud Rate
Modify both the Arduino sketch and Python script:
- Arduino: Change `SERIAL_BAUD` define
- Python: Use `--baud` argument

### Add More Display Modes
Edit the Arduino sketch and add new cases in `updateDisplay()`.

## License

MIT License - Feel free to use and modify for your projects.

## Contributing

Contributions welcome! Please open an issue or pull request.
