#!/usr/bin/env python3
"""
Muse to Arduino Bridge

This script receives brainwave data from a Muse headband via LSL (Lab Streaming Layer)
and sends it to an Arduino over serial for LCD display.

Requirements:
    pip install pylsl pyserial numpy

Usage:
    1. Start streaming Muse data using one of these methods:
       - BlueMuse (Windows): https://github.com/kowalej/BlueMuse
       - muse-lsl (cross-platform): pip install muselsl && muselsl stream
       - Muse Direct app with LSL output enabled

    2. Run this script:
       python muse_arduino_bridge.py --port COM3  # Windows
       python muse_arduino_bridge.py --port /dev/ttyUSB0  # Linux
       python muse_arduino_bridge.py --port /dev/cu.usbmodem*  # macOS

Author: Arduino Muse LCD Project
License: MIT
"""

import argparse
import sys
import time
import signal
from typing import Optional
import numpy as np

try:
    from pylsl import StreamInlet, resolve_byprop
except ImportError:
    print("Error: pylsl not installed. Install with: pip install pylsl")
    sys.exit(1)

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: pyserial not installed. Install with: pip install pyserial")
    sys.exit(1)


class MuseArduinoBridge:
    """Bridge between Muse LSL stream and Arduino serial."""

    # Frequency bands (Hz)
    BANDS = {
        'delta': (0.5, 4),
        'theta': (4, 8),
        'alpha': (8, 12),
        'beta': (12, 30),
        'gamma': (30, 100)
    }

    def __init__(self, serial_port: str, baud_rate: int = 9600, timeout: float = 1.0):
        """Initialize the bridge.

        Args:
            serial_port: Arduino serial port (e.g., 'COM3' or '/dev/ttyUSB0')
            baud_rate: Serial baud rate (default 9600)
            timeout: Serial timeout in seconds
        """
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.arduino: Optional[serial.Serial] = None
        self.inlet: Optional[StreamInlet] = None
        self.running = False
        self.sample_rate = 256  # Muse default sample rate
        self.buffer_size = 256  # 1 second of data

        # Buffer for EEG samples
        self.eeg_buffer = []

    def connect_arduino(self) -> bool:
        """Connect to Arduino via serial.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            print(f"Connecting to Arduino on {self.serial_port}...")
            self.arduino = serial.Serial(
                port=self.serial_port,
                baudrate=self.baud_rate,
                timeout=self.timeout
            )
            time.sleep(2)  # Wait for Arduino to reset
            print("Arduino connected successfully!")
            return True
        except serial.SerialException as e:
            print(f"Error connecting to Arduino: {e}")
            return False

    def connect_muse(self, timeout: float = 10.0) -> bool:
        """Connect to Muse LSL stream.

        Args:
            timeout: Timeout for finding stream in seconds

        Returns:
            True if connection successful, False otherwise
        """
        print("Looking for Muse EEG stream...")
        streams = resolve_byprop('type', 'EEG', timeout=timeout)

        if not streams:
            print("No Muse EEG stream found!")
            print("\nMake sure you have one of these running:")
            print("  - BlueMuse (Windows)")
            print("  - muselsl stream (cross-platform)")
            print("  - Muse Direct with LSL enabled")
            return False

        print(f"Found {len(streams)} EEG stream(s)")
        self.inlet = StreamInlet(streams[0])

        # Get stream info
        info = self.inlet.info()
        self.sample_rate = int(info.nominal_srate())
        self.buffer_size = self.sample_rate  # 1 second buffer

        print(f"Connected to: {info.name()}")
        print(f"Sample rate: {self.sample_rate} Hz")
        print(f"Channels: {info.channel_count()}")

        return True

    def compute_band_powers(self, eeg_data: np.ndarray) -> dict:
        """Compute power in each frequency band using FFT.

        Args:
            eeg_data: EEG samples array (samples x channels)

        Returns:
            Dictionary with normalized power for each band
        """
        if len(eeg_data) < self.buffer_size // 2:
            return None

        # Use first 4 channels (TP9, AF7, AF8, TP10)
        # Average across channels for simplicity
        data = np.array(eeg_data)
        if data.shape[1] > 4:
            data = data[:, :4]

        # Average across channels
        signal_avg = np.mean(data, axis=1)

        # Apply Hanning window
        window = np.hanning(len(signal_avg))
        windowed = signal_avg * window

        # Compute FFT
        fft_vals = np.abs(np.fft.rfft(windowed))
        fft_freqs = np.fft.rfftfreq(len(windowed), 1.0 / self.sample_rate)

        # Compute power in each band
        band_powers = {}
        total_power = 0

        for band_name, (low_freq, high_freq) in self.BANDS.items():
            # Find frequency indices
            idx = np.where((fft_freqs >= low_freq) & (fft_freqs <= high_freq))[0]
            if len(idx) > 0:
                band_powers[band_name] = np.mean(fft_vals[idx] ** 2)
                total_power += band_powers[band_name]
            else:
                band_powers[band_name] = 0

        # Normalize to 0-1 range (relative power)
        if total_power > 0:
            for band_name in band_powers:
                band_powers[band_name] = band_powers[band_name] / total_power
                # Apply some smoothing/scaling for better display
                band_powers[band_name] = min(1.0, band_powers[band_name] * 2)

        return band_powers

    def send_to_arduino(self, band_powers: dict) -> bool:
        """Send band powers to Arduino via serial.

        Args:
            band_powers: Dictionary with power values for each band

        Returns:
            True if send successful, False otherwise
        """
        if not self.arduino or not band_powers:
            return False

        # Format: "delta,theta,alpha,beta,gamma\n"
        message = "{:.3f},{:.3f},{:.3f},{:.3f},{:.3f}\n".format(
            band_powers['delta'],
            band_powers['theta'],
            band_powers['alpha'],
            band_powers['beta'],
            band_powers['gamma']
        )

        try:
            self.arduino.write(message.encode())
            # Read acknowledgment (optional)
            if self.arduino.in_waiting:
                response = self.arduino.readline().decode().strip()
                if response == "OK":
                    return True
            return True
        except serial.SerialException as e:
            print(f"Serial error: {e}")
            return False

    def run(self, update_rate: float = 4.0):
        """Main loop to read Muse data and send to Arduino.

        Args:
            update_rate: How many times per second to update Arduino (default 4)
        """
        self.running = True
        update_interval = 1.0 / update_rate
        last_update = 0
        samples_collected = 0

        print("\nStarting brainwave streaming to Arduino...")
        print("Press Ctrl+C to stop\n")

        while self.running:
            try:
                # Pull samples from LSL stream
                sample, timestamp = self.inlet.pull_sample(timeout=0.1)

                if sample:
                    self.eeg_buffer.append(sample)
                    samples_collected += 1

                    # Keep buffer at fixed size
                    if len(self.eeg_buffer) > self.buffer_size:
                        self.eeg_buffer.pop(0)

                # Update Arduino at specified rate
                current_time = time.time()
                if current_time - last_update >= update_interval:
                    if len(self.eeg_buffer) >= self.buffer_size // 2:
                        band_powers = self.compute_band_powers(self.eeg_buffer)
                        if band_powers:
                            self.send_to_arduino(band_powers)

                            # Print to console
                            print(f"\rD:{band_powers['delta']:.2f} "
                                  f"T:{band_powers['theta']:.2f} "
                                  f"A:{band_powers['alpha']:.2f} "
                                  f"B:{band_powers['beta']:.2f} "
                                  f"G:{band_powers['gamma']:.2f}", end='')

                    last_update = current_time

            except Exception as e:
                print(f"\nError: {e}")
                time.sleep(0.1)

    def stop(self):
        """Stop the bridge and clean up."""
        self.running = False
        if self.arduino:
            self.arduino.close()
            print("\nArduino disconnected")


def list_serial_ports():
    """List available serial ports."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found!")
        return

    print("\nAvailable serial ports:")
    for port in ports:
        print(f"  {port.device}: {port.description}")


def main():
    parser = argparse.ArgumentParser(
        description='Bridge Muse brainwave data to Arduino LCD display',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --port COM3                    # Windows
  %(prog)s --port /dev/ttyUSB0            # Linux
  %(prog)s --port /dev/cu.usbmodem14201   # macOS
  %(prog)s --list                         # List available ports
        """
    )

    parser.add_argument('--port', '-p', type=str,
                        help='Arduino serial port')
    parser.add_argument('--baud', '-b', type=int, default=9600,
                        help='Serial baud rate (default: 9600)')
    parser.add_argument('--rate', '-r', type=float, default=4.0,
                        help='Update rate in Hz (default: 4)')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List available serial ports')

    args = parser.parse_args()

    if args.list:
        list_serial_ports()
        return

    if not args.port:
        print("Error: --port is required")
        list_serial_ports()
        return

    # Create bridge
    bridge = MuseArduinoBridge(args.port, args.baud)

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n\nStopping...")
        bridge.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Connect to devices
    if not bridge.connect_arduino():
        return

    if not bridge.connect_muse():
        return

    # Run main loop
    bridge.run(args.rate)


if __name__ == '__main__':
    main()
