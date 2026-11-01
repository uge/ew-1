#!/usr/bin/env python3
"""Re-synchronise RP1 PWM0 ch2 (IN1) and ch3 (IN2) so they share one counter phase. Run as root.

Why: channels enabled by separate sysfs writes start with a random relative phase, so the
complementary drive amplitude was random run to run (2026-11-01: 2.5-98 % complementary
measured via a single SYS_RIO0 read). Clearing and re-setting both enable bits in ONE
GLOBAL_CTRL write with SET_UPDATE (bit 31) restarts them together: 8/8 trials 100 %.

Usage: rp1_pwm_sync.py [--verify-only]
Preconditions (refuses otherwise): GPIO24 = 0 and GPIO25 = 0 (driver asleep, bridge off),
ch2 and ch3 enabled via sysfs at duty 50 %, ch3 polarity inversed.
Exit 0 only if complementary (IN1 != IN2) >= 99 % after the resync.

Register map verified 2026-11-01 (pwm0 @ 0x1f00098000): GLOBAL_CTRL 0x000 (bit n = chan n enable,
bit 31 = SET_UPDATE); CHANn CTRL 0x14+0x10n (bit 3 = INVERT), RANGE 0x18+0x10n, PHASE 0x1c+0x10n,
DUTY 0x20+0x10n. SYS_RIO0 @ 0x1f000e0000, +0x08 = input levels (bit 18 = IN1, bit 19 = IN2).
"""
import mmap, os, struct, subprocess, sys

PWM0, RIO0 = 0x1f00098000, 0x1f000e0000
UPD, CH23 = 1 << 31, (1 << 2) | (1 << 3)

def sh(*a): return subprocess.run(a, capture_output=True, text=True).stdout.strip()

def main():
    if os.geteuid() != 0: print("must run as root"); return 2
    if sh("pinctrl", "lev", "24") != "0" or sh("pinctrl", "lev", "25") != "0":
        print("REFUSED: GPIO24/25 must be low (driver asleep, bridge off)"); return 2
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    pwm = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=PWM0)
    rio = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=RIO0)
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

if __name__ == "__main__":
    sys.exit(main())
