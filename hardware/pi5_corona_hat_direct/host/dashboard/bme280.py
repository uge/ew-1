"""Minimal BME280 reader (I2C 0x76), Bosch datasheet floating-point compensation.

Puts the sensor in normal mode (x1 oversampling on T/P/H, 1 s standby, filter off) if it
is not already, then reads the burst registers 0xF7..0xFE.
"""
import struct

ADDR = 0x76
CHIP_ID = 0x60
CTRL_HUM, CTRL_MEAS, CONFIG = 0xF2, 0xF4, 0xF5
WANT_HUM, WANT_MEAS, WANT_CONFIG = 0x01, 0x27, 0xA0


class BME280:
    def __init__(self, bus, addr=ADDR):
        self.bus, self.addr = bus, addr
        cid = bus.read_byte_data(addr, 0xD0)
        if cid != CHIP_ID:
            raise RuntimeError(f"BME280 chip id 0x{cid:02x} != 0x60")
        c = bytes(bus.read_i2c_block_data(addr, 0x88, 26))
        (self.T1, self.T2, self.T3, self.P1, self.P2, self.P3, self.P4, self.P5,
         self.P6, self.P7, self.P8, self.P9) = struct.unpack("<HhhHhhhhhhhh", c[:24])
        self.H1 = c[25]
        e = bus.read_i2c_block_data(addr, 0xE1, 7)
        self.H2 = struct.unpack("<h", bytes(e[0:2]))[0]
        self.H3 = e[2]
        h4 = (e[3] << 4) | (e[4] & 0x0F)
        h5 = (e[5] << 4) | (e[4] >> 4)
        self.H4 = h4 - 4096 if h4 & 0x800 else h4
        self.H5 = h5 - 4096 if h5 & 0x800 else h5
        self.H6 = e[6] - 256 if e[6] & 0x80 else e[6]
        self.configure()

    def configure(self):
        b, a = self.bus, self.addr
        if (b.read_byte_data(a, CTRL_HUM) & 0x07) != WANT_HUM or b.read_byte_data(a, CONFIG) != WANT_CONFIG \
                or b.read_byte_data(a, CTRL_MEAS) != WANT_MEAS:
            b.write_byte_data(a, CTRL_MEAS, 0x00)          # sleep before writing config
            b.write_byte_data(a, CTRL_HUM, WANT_HUM)       # takes effect on the next ctrl_meas write
            b.write_byte_data(a, CONFIG, WANT_CONFIG)
            b.write_byte_data(a, CTRL_MEAS, WANT_MEAS)
            return True
        return False

    def read(self):
        d = self.bus.read_i2c_block_data(self.addr, 0xF7, 8)
        adc_p = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
        adc_t = (d[3] << 12) | (d[4] << 4) | (d[5] >> 4)
        adc_h = (d[6] << 8) | d[7]
        if adc_t == 0x80000:
            return None                                    # no conversion yet (sleep / reset value)
        v1 = (adc_t / 16384.0 - self.T1 / 1024.0) * self.T2
        v2 = ((adc_t / 131072.0 - self.T1 / 8192.0) ** 2) * self.T3
        t_fine = v1 + v2
        t = t_fine / 5120.0
        v1 = t_fine / 2.0 - 64000.0
        v2 = v1 * v1 * self.P6 / 32768.0
        v2 = v2 + v1 * self.P5 * 2.0
        v2 = v2 / 4.0 + self.P4 * 65536.0
        v1 = (self.P3 * v1 * v1 / 524288.0 + self.P2 * v1) / 524288.0
        v1 = (1.0 + v1 / 32768.0) * self.P1
        if v1 == 0:
            p = None
        else:
            p = 1048576.0 - adc_p
            p = (p - v2 / 4096.0) * 6250.0 / v1
            v1 = self.P9 * p * p / 2147483648.0
            v2 = p * self.P8 / 32768.0
            p = p + (v1 + v2 + self.P7) / 16.0
        h = t_fine - 76800.0
        h = (adc_h - (self.H4 * 64.0 + self.H5 / 16384.0 * h)) * (
            self.H2 / 65536.0 * (1.0 + self.H6 / 67108864.0 * h * (1.0 + self.H3 / 67108864.0 * h)))
        h = h * (1.0 - self.H1 * h / 524288.0)
        h = max(0.0, min(100.0, h))
        return {"t_c": round(t, 2), "p_hpa": None if p is None else round(p / 100.0, 2), "rh_pct": round(h, 1)}
