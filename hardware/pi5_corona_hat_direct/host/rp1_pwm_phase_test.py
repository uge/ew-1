# Phase repeatability via simultaneous RIO read (sudo). Driver asleep, bridge off.
import mmap, os, random, struct, subprocess, time
def sh(*a): return subprocess.run(a, capture_output=True, text=True).stdout.strip()
assert sh("pinctrl","lev","24") == "0" and sh("pinctrl","lev","25") == "0"
P = "/sys/class/pwm/pwmchip0"
def pw(p, v): open(p, "w").write(str(v))
fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
rio = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=0x1f000e0000)
r = lambda o: struct.unpack_from("<I", rio, o)[0]
def states(n=20000):
    c = [0, 0, 0, 0]
    for _ in range(n):
        v = r(8); c[((v >> 18) & 1) | (((v >> 19) & 1) << 1)] += 1
    return [x / n * 100 for x in c]
for freq in (32000, 26000):
    T = round(1e9 / freq)
    for ch in (2, 3):
        pw(f"{P}/pwm{ch}/enable", 0); pw(f"{P}/pwm{ch}/polarity", "normal"); pw(f"{P}/pwm{ch}/duty_cycle", 0); pw(f"{P}/pwm{ch}/period", T)
    for trial in range(8):
        for ch in (2, 3): pw(f"{P}/pwm{ch}/enable", 0)
        pw(f"{P}/pwm3/polarity", "normal"); pw(f"{P}/pwm2/duty_cycle", T // 2); pw(f"{P}/pwm3/duty_cycle", T // 2)
        pw(f"{P}/pwm3/polarity", "inversed")
        first = random.choice((2, 3)); second = 5 - first
        pw(f"{P}/pwm{first}/enable", 1); time.sleep(random.uniform(0, 0.02)); pw(f"{P}/pwm{second}/enable", 1)
        time.sleep(0.005)
        s = states()
        # duty change test while running (ramp relies on it)
        pw(f"{P}/pwm2/duty_cycle", round(0.1 * T)); pw(f"{P}/pwm3/duty_cycle", round(0.9 * T)); time.sleep(0.005)
        s2 = states()
        print(f"{freq/1e3:.0f} kHz trial {trial} (ch{first} first): D=0.5 00 {s[0]:4.1f} 10 {s[1]:4.1f} 01 {s[2]:4.1f} 11 {s[3]:4.1f} | "
              f"D=0.1 00 {s2[0]:4.1f} 10 {s2[1]:4.1f} 01 {s2[2]:4.1f} 11 {s2[3]:4.1f}")
for ch in (2, 3): pw(f"{P}/pwm{ch}/enable", 0); pw(f"{P}/pwm{ch}/polarity", "normal")
print("final pins", sh("pinctrl", "lev", "18,19"))
