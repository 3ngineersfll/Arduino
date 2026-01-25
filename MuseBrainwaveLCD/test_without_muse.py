#!/usr/bin/env python3
"""
Test Script - Simulate Muse Data for Arduino LCD

Use this script to test the Arduino LCD display without a real Muse headband.
It sends simulated brainwave data that cycles through different mental states.

Usage:
    python test_without_muse.py --port COM3  # Windows
    python test_without_muse.py --port /dev/ttyUSB0  # Linux
"""

import argparse
import math
import sys
import time
import signal

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: pyserial not installed. Install with: pip install pyserial")
    sys.exit(1)


def list_serial_ports():
    """List available serial ports."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found!")
        return []

    print("\nAvailable serial ports:")
    for port in ports:
        print(f"  {port.device}: {port.description}")
    return [p.device for p in ports]


def generate_wave(t, period, min_val=0.1, max_val=0.9):
    """Generate a smooth wave between min and max values."""
    return min_val + (max_val - min_val) * (0.5 + 0.5 * math.sin(2 * math.pi * t / period))


def generate_brainwaves(t):
    """Generate simulated brainwave patterns.

    Cycles through different mental states:
    - Relaxed (high alpha)
    - Focused (high beta/gamma)
    - Drowsy (high theta)
    - Deep relaxation (high delta)
    """
    cycle_period = 30  # Complete cycle every 30 seconds
    phase = (t % cycle_period) / cycle_period

    # Base values with some randomness
    import random
    noise = lambda: random.uniform(-0.05, 0.05)

    if phase < 0.25:
        # Relaxed state - high alpha
        delta = 0.15 + noise()
        theta = 0.20 + noise()
        alpha = 0.50 + 0.2 * math.sin(t * 0.5) + noise()
        beta = 0.25 + noise()
        gamma = 0.10 + noise()
    elif phase < 0.5:
        # Focused state - high beta and gamma
        delta = 0.10 + noise()
        theta = 0.15 + noise()
        alpha = 0.25 + noise()
        beta = 0.55 + 0.15 * math.sin(t * 0.7) + noise()
        gamma = 0.45 + 0.15 * math.sin(t * 0.8) + noise()
    elif phase < 0.75:
        # Drowsy state - high theta
        delta = 0.25 + noise()
        theta = 0.55 + 0.2 * math.sin(t * 0.3) + noise()
        alpha = 0.35 + noise()
        beta = 0.15 + noise()
        gamma = 0.08 + noise()
    else:
        # Deep relaxation - elevated delta
        delta = 0.45 + 0.15 * math.sin(t * 0.2) + noise()
        theta = 0.35 + noise()
        alpha = 0.30 + noise()
        beta = 0.12 + noise()
        gamma = 0.05 + noise()

    # Clamp values
    delta = max(0.0, min(1.0, delta))
    theta = max(0.0, min(1.0, theta))
    alpha = max(0.0, min(1.0, alpha))
    beta = max(0.0, min(1.0, beta))
    gamma = max(0.0, min(1.0, gamma))

    return delta, theta, alpha, beta, gamma


def get_state_name(delta, theta, alpha, beta, gamma):
    """Get the dominant mental state name."""
    max_val = max(delta, theta, alpha, beta, gamma)
    if delta == max_val:
        return "Deep Relaxation"
    elif theta == max_val:
        return "Drowsy"
    elif alpha == max_val:
        return "Relaxed"
    elif beta == max_val:
        return "Active"
    else:
        return "Focused"


def main():
    parser = argparse.ArgumentParser(
        description='Test Arduino LCD with simulated Muse data'
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

    # Connect to Arduino
    print(f"Connecting to Arduino on {args.port}...")
    try:
        arduino = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            timeout=1.0
        )
        time.sleep(2)  # Wait for Arduino reset
        print("Connected!")
    except serial.SerialException as e:
        print(f"Error: {e}")
        return

    running = True

    def signal_handler(sig, frame):
        nonlocal running
        running = False
        print("\n\nStopping...")

    signal.signal(signal.SIGINT, signal_handler)

    print("\nSending simulated brainwave data...")
    print("Press Ctrl+C to stop\n")

    start_time = time.time()
    update_interval = 1.0 / args.rate

    try:
        while running:
            t = time.time() - start_time
            delta, theta, alpha, beta, gamma = generate_brainwaves(t)

            # Send to Arduino
            message = f"{delta:.3f},{theta:.3f},{alpha:.3f},{beta:.3f},{gamma:.3f}\n"
            arduino.write(message.encode())

            # Get state name
            state = get_state_name(delta, theta, alpha, beta, gamma)

            # Print to console
            print(f"\rD:{delta:.2f} T:{theta:.2f} A:{alpha:.2f} "
                  f"B:{beta:.2f} G:{gamma:.2f} [{state:^16}]", end='')

            time.sleep(update_interval)

    finally:
        arduino.close()
        print("\nDone!")


if __name__ == '__main__':
    main()
