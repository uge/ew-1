#!/usr/bin/env python3
"""Re-synchronise PWM IN1 (GPIO18) and IN2 (GPIO19) so they share one counter phase. Run as root.

Supports both:
- Pi 5 (RP1 PWM0 @ 0x1f00098000, ch2/ch3, SYS_RIO0 @ 0x1f000e0000)
- Pi Zero 2W (BCM2835/BCM2710 PWM0 @ 0x3f20c000, ch0/ch1, GPIO GPLEV0 @ 0x3f200034)

Why: channels enabled by separate sysfs writes start with a random relative phase, so the
complementary drive amplitude was random run to run (2026-11-01: 2.5-98 % complementary
measured via a single SYS_RIO0 read). Clearing and re-setting both enable bits in ONE
register write restarts them together: 8/8 trials 100 %.

Usage: rp1_pwm_sync.py [--verify-only]
Preconditions (refuses otherwise): GPIO24 = 0 and GPIO25 = 0 (driver asleep, bridge off),
IN1 and IN2 channels enabled via sysfs at duty 50 %, IN2 polarity inversed.
Exit 0 only if complementary (IN1 != IN2) >= 99 % after the resync.

Register map verified 2026-11-01 (pwm0 @ 0x1f00098000): GLOBAL_CTRL 0x000 (bit n = chan n enable,
bit 31 = SET_UPDATE); CHANn CTRL 0x14+0x10n (bit 3 = INVERT), RANGE 0x18+0x10n, PHASE 0x1c+0x10n,
DUTY 0x20+0x10n. SYS_RIO0 @ 0x1f000e0000, +0x08 = input levels (bit 18 = IN1, bit 19 = IN2).
BCM2835 PWM0 @ 0x3f20c000: CTL 0x00 (bit 0 = PWEN1, bit 4 = POLA1, bit 8 = PWEN2, bit 12 = POLA2),
RNG1 0x10, DAT1 0x14, RNG2 0x20, DAT2 0x24; GPIO @ 0x3f200000, +0x34 = GPLEV0 (bits 18/19).
"""
import mmap, os, struct, subprocess, sys, time

RP1_PWM0, RP1_RIO0 = 0x1f00098000, 0x1f000e0000
UPD, CH23 = 1 << 31, (1 << 2) | (1 << 3)

BCM_PWM0, BCM_GPIO = 0x3f20c000, 0x3f200000
PWEN12, POLA1, POLA2 = (1 << 0) | (1 << 8), 1 << 4, 1 << 12

def sh(*a): return subprocess.run(a, capture_output=True, text=True).stdout.strip()

def sync_rp1(fd):
    pwm = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=RP1_PWM0)
    rio = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=RP1_RIO0)
    rd = lambda m, o: struct.unpack_from("<I", m, o)[0]
    g = rd(pwm, 0)
    c2, c3 = rd(pwm, 0x34), rd(pwm, 0x44)
    r2, r3, d2, d3 = rd(pwm, 0x38), rd(pwm, 0x48), rd(pwm, 0x40), rd(pwm, 0x50)
    if (g & CH23) != CH23 or (c2 & 8) or not (c3 & 8) or r2 != r3 or abs(d2 * 2 - r2) > 2 or abs(d3 * 2 - r3) > 2:
        print(f"REFUSED: unexpected state GLOBAL=0x{g:08x} CTRL2=0x{c2:x} CTRL3=0x{c3:x} RANGE={r2}/{r3} DUTY={d2}/{d3}"); return 2
    if "--verify-only" not in sys.argv:
        struct.pack_into("<I", pwm, 0, (g & ~CH23) | UPD)
        struct.pack_into("<I", pwm, 0, (g | CH23) | UPD)
    n = 20000; diff = both = 0
    for _ in range(n):
        v = rd(rio, 8); a, b = (v >> 18) & 1, (v >> 19) & 1
        diff += a != b; both += a & b
    comp = diff / n * 100
    print(f"rp1_pwm_sync: complementary {comp:.1f}%  overlap(11) {both/n*100:.1f}%  GLOBAL 0x{rd(pwm, 0):08x}")
    return 0 if comp >= 99.0 else 1

def sync_bcm2835(fd):
    pwm = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=BCM_PWM0)
    gpio = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=BCM_GPIO)
    rd = lambda m, o: struct.unpack_from("<I", m, o)[0]
    ctl = rd(pwm, 0x00)
    r1, d1, r2, d2 = rd(pwm, 0x10), rd(pwm, 0x14), rd(pwm, 0x20), rd(pwm, 0x24)
    if (ctl & PWEN12) != PWEN12 or (ctl & POLA1) or not (ctl & POLA2) or r1 != r2 or abs(d1 * 2 - r1) > 2 or abs(d2 * 2 - r2) > 2:
        print(f"REFUSED: unexpected state CTL=0x{ctl:08x} RNG={r1}/{r2} DAT={d1}/{d2}"); return 2
    if "--verify-only" not in sys.argv:
        struct.pack_into("<I", pwm, 0x00, ctl & ~PWEN12)
        time.sleep(0.0001)
        struct.pack_into("<I", pwm, 0x00, ctl | PWEN12)
        time.sleep(0.0001)
    n = 20000; diff = both = 0
    for _ in range(n):
        v = rd(gpio, 0x34); a, b = (v >> 18) & 1, (v >> 19) & 1
        diff += a != b; both += a & b
    comp = diff / n * 100
    print(f"bcm2835_pwm_sync: complementary {comp:.1f}%  overlap(11) {both/n*100:.1f}%  CTL 0x{rd(pwm, 0x00):08x}")
    return 0 if comp >= 99.0 else 1

def main():
    if os.geteuid() != 0: print("must run as root"); return 2
    if sh("pinctrl", "lev", "24") != "0" or sh("pinctrl", "lev", "25") != "0":
        print("REFUSED: GPIO24/25 must be low (driver asleep, bridge off)"); return 2
    dev = os.path.realpath("/sys/class/pwm/pwmchip0/device")
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    if "1f00098000" in dev:
        return sync_rp1(fd)
    if "3f20c000" in dev:
        return sync_bcm2835(fd)
    print(f"REFUSED: unrecognised pwmchip0 device {dev}")
    return 2

if __name__ == "__main__":
    sys.exit(main())
