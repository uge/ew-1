"""Minimal TSL2591 reader (I2C 0x29, illumination mini board on J50; usually absent).

Command bit 0xA0 (normal transaction). ID 0x12 = 0x50. ENABLE 0x00 <- PON|AEN (0x03).
CONTROL 0x01 <- gain/integration. CH0 (full spectrum) 0x14-0x15, CH1 (IR) 0x16-0x17.
Lux uses the Adafruit/ams application-note formula with LUX_DF = 408.
"""
ADDR = 0x29
CMD = 0xA0
GAINS = {0x00: 1.0, 0x10: 25.0, 0x20: 428.0, 0x30: 9876.0}      # LOW / MED / HIGH / MAX
ATIME_MS = {0: 100, 1: 200, 2: 300, 3: 400, 4: 500, 5: 600}
LUX_DF = 408.0


def probe(bus, addr=ADDR):
    try:
        return bus.read_byte_data(addr, CMD | 0x12) == 0x50
    except OSError:
        return False


class TSL2591:
    def __init__(self, bus, addr=ADDR, gain=0x10, atime=0):
        self.bus, self.addr, self.gain, self.atime = bus, addr, gain, atime
        if not probe(bus, addr):
            raise RuntimeError("TSL2591 not found")
        bus.write_byte_data(addr, CMD | 0x01, gain | atime)
        bus.write_byte_data(addr, CMD | 0x00, 0x03)                 # PON | AEN

    def read(self):
        d = self.bus.read_i2c_block_data(self.addr, CMD | 0x14, 4)
        ch0 = d[0] | (d[1] << 8)
        ch1 = d[2] | (d[3] << 8)
        sat = ch0 >= 0xFFFF or ch1 >= 0xFFFF
        cpl = ATIME_MS[self.atime] * GAINS[self.gain] / LUX_DF
        lux = None
        if not sat and ch0 > 0:
            lux = max(0.0, (ch0 - ch1) * (1.0 - ch1 / ch0) / cpl)
        return {"ch0": ch0, "ch1": ch1, "lux": None if lux is None else round(lux, 2), "saturated": sat,
                "gain": GAINS[self.gain], "atime_ms": ATIME_MS[self.atime]}
