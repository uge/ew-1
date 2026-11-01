#!/usr/bin/env python3
"""Read-only host self-test for the Pi 5 corona HV board (N-layout-17).

Never drives a GPIO or writes a PD request. It probes the I2C bus, reads chip
IDs, takes one ADS1115 single-shot per channel, and samples the status inputs.
Runs with or without the HV board attached; missing devices are reported.

Usage:  python3 ew1_selftest.py [--bus 1]
"""
import argparse
import sys
import time

from smbus2 import SMBus

try:
    import gpiod
    from gpiod.line import Bias, Direction
except ImportError:  # python3-libgpiod not installed
    gpiod = None

ADDR_TSL2591 = 0x29   # U8, illumination mini board (J50/J51); absent if detached
ADDR_HUSB238A = 0x42  # U7 USB-PD sink, powered from Pi 3V3
ADDR_ADS1115 = 0x48   # U6, ADDR -> GND
ADDR_BME280 = 0x76    # U5, SDO -> GND

# ADS1115 channel -> (net, scale to engineering units, unit). Scales are nominal
# divider ratios from the schematic; calibrate HV sense before trusting kV.
ADS_CHANNELS = {
    0: ("HV_SENSE_ADC", 1.000164e9 / 164e3 / 1e3, "kV"),  # 1 GOhm / 164 kOhm, via U4
    1: ("HV_CURR_ADC", 1e6 / 10e3, "uA"),                 # R90 10 kOhm return shunt
    2: ("PD_VMON", 118e3 / 18e3, "V VBUS"),               # R10 100k / R11 18k
    3: ("BRIDGE_VMON", 110e3 / 10e3, "V bridge"),         # R108 100k / R109 10k
}

# BCM line -> (J2 pin, net, safe/idle expectation)
STATUS_INPUTS = {
    5: (29, "DRV_nFAULT", "high = no driver fault (R63 pull-up)"),
    6: (31, "EFUSE_FLT", "high = no eFuse fault (R107 pull-up)"),
    23: (16, "INTERLOCK_OK", "high = lid switches closed and coil fed"),
    26: (37, "HV_OV_TRIP_GPIO", "low = hardware OV trip not latched"),
}
OUTPUTS = {18: "DRV_IN1/PWM", 19: "DRV_IN2/PWM", 24: "DRV_SLEEP_CMD", 25: "BULK_CMD"}


def probe(bus, addr):
    try:
        bus.read_byte(addr)
        return True
    except OSError:
        return False


def ads_read(bus, ch):
    # OS=1, MUX=AINch vs GND, PGA=+/-4.096 V, single-shot, 128 SPS, comparator off
    msb = 0xC3 | (ch << 4)
    bus.write_i2c_block_data(ADDR_ADS1115, 0x01, [msb, 0x83])
    time.sleep(0.012)
    hi, lo = bus.read_i2c_block_data(ADDR_ADS1115, 0x00, 2)
    raw = (hi << 8) | lo
    if raw & 0x8000:
        raw -= 1 << 16
    return raw * 4.096 / 32768


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bus", type=int, default=1)
    args = ap.parse_args()
    failures = 0

    print(f"== I2C bus {args.bus}")
    with SMBus(args.bus) as bus:
        present = {a: probe(bus, a) for a in
                   (ADDR_TSL2591, ADDR_HUSB238A, ADDR_ADS1115, ADDR_BME280)}
        for a, ok in present.items():
            print(f"  0x{a:02x}: {'present' if ok else 'absent'}")

        if present[ADDR_BME280]:
            cid = bus.read_byte_data(ADDR_BME280, 0xD0)
            print(f"  BME280 chip id 0x{cid:02x} ({'ok' if cid == 0x60 else 'UNEXPECTED'})")
            failures += cid != 0x60
        if present[ADDR_TSL2591]:
            tid = bus.read_byte_data(ADDR_TSL2591, 0xA0 | 0x12)
            print(f"  TSL2591 id 0x{tid:02x} ({'ok' if tid == 0x50 else 'UNEXPECTED'})")
            failures += tid != 0x50
        if present[ADDR_HUSB238A]:
            # Unofficial map (see HUSB238A.md): CONTROL1 0x02, STATUS 0x63,
            # CONTRACT_STATUS0 0x67, VBUS_MEASUREMENT 0x87 (125 mV/LSB)
            c1 = bus.read_byte_data(ADDR_HUSB238A, 0x02)
            st = bus.read_byte_data(ADDR_HUSB238A, 0x63)
            cs0 = bus.read_byte_data(ADDR_HUSB238A, 0x67)
            vb = bus.read_byte_data(ADDR_HUSB238A, 0x87)
            print(f"  HUSB238A ENABLE={c1 >> 3 & 1} attached={st & 1} "
                  f"PD_CONTRACT=0x{cs0 >> 4:x} VBUS(chip)={vb * 0.125:.3f} V "
                  "(read only; details: husb238a.py status)")
        if present[ADDR_ADS1115]:
            print("  ADS1115 single-shot, +/-4.096 V:")
            for ch, (net, k, unit) in ADS_CHANNELS.items():
                v = ads_read(bus, ch)
                print(f"    AIN{ch} {net:<13} {v:+.4f} V  ~ {v * k:,.2f} {unit} (nominal)")

    print("== GPIO (gpiochip0 / RP1), inputs sampled without changing outputs")
    if gpiod is None:
        print("  python3-libgpiod missing; skipped")
        return 1 if failures else 0
    settings = gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.AS_IS)
    try:
        with gpiod.request_lines("/dev/gpiochip0", consumer="ew1-selftest",
                                 config={tuple(STATUS_INPUTS): settings}) as req:
            for line, (pin, net, meaning) in STATUS_INPUTS.items():
                val = req.get_value(line).value
                print(f"  GPIO{line:<2} J2.{pin:<2} {net:<16} = {val}   [{meaning}]")
    except OSError as exc:
        print(f"  could not request status lines: {exc}")
        failures += 1
    print("  outputs (not touched): " +
          ", ".join(f"GPIO{l} {n}" for l, n in OUTPUTS.items()) +
          " -- check with: pinctrl get 18,19,24,25")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
