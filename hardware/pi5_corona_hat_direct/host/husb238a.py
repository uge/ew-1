#!/usr/bin/env python3
"""HUSB238A (U7) USB-PD sink driver for the ew-1 HV board.

Register map: UNOFFICIAL, reverse-engineered community map. See HUSB238A.md for
sources, confidence and the on-board observations. Hynetek's public datasheet
(procurement/HUSB238A_datasheet.pdf, Rev 1.2) has no register tables.

Safety policy for this board (see HUSB238A.md "Board hazards"):
  * Read-only by default. Every write needs HUSB238A(..., allow_write=True).
  * Fixed SPR PDOs only (5/9/12/15/20 V). EPR (28/36/48 V), AVS and PPS are
    refused: U9 TPS25947 is 23 V operating / 28 V abs max and F1 is 24 V.
  * Requests above `max_volts` (default 5 V) are refused; the ceiling can be
    raised per call site, never above BOARD_MAX_VOLTS.

CLI:
  husb238a.py status          decoded status (read only)
  husb238a.py dump            raw 0x00-0x91 hex dump (read only)
  husb238a.py srccap --arm    enable + Get_Source_Cap, re-hold 5 V, then status
  husb238a.py request V --arm [--max V]   request fixed PDO V volts
"""
import argparse
import sys
import time

from smbus2 import SMBus

I2C_ADDR_GND = 0x42  # ADDR/ORIENT to GND via ~1 MOhm (R15 on this board)
I2C_ADDR_VDD = 0x62

BOARD_MAX_VOLTS = 20  # hard ceiling: U9 23 V operating, F1 24 V, D51 SMBJ22A

# ---- register addresses (unofficial map) ----
PORTROLE = 0x00
CONTROL = 0x01
CONTROL1 = 0x02
MANUAL = 0x03
RESET = 0x04
INTERRUPT = 0x09
INTERRUPT1 = 0x0A
INTERRUPT2 = 0x0B
USER_CFG0, USER_CFG1, USER_CFG2, USER_CFG3 = 0x0C, 0x0D, 0x0E, 0x0F
GO_COMMAND = 0x18
SRC_PDO = 0x19
STATUS = 0x63
STATUS1 = 0x64
TYPE = 0x65
DPDM_STATUS = 0x66
CONTRACT_STATUS0 = 0x67
CONTRACT_STATUS1 = 0x68
SOURCECAP_INFO = 0x69
SRC_PDO_FIXED = {5: 0x6A, 9: 0x6B, 12: 0x6C, 15: 0x6D, 20: 0x6E,
                 28: 0x6F, 36: 0x70, 48: 0x71}
SRC_PDO_PPS = {1: 0x72, 2: 0x73, 3: 0x74}
SRC_PDO_AVS = 0x76
SRC_EPR_AVS = 0x79
VBUS_MEASUREMENT = 0x87
SNK_FSM_STATE = 0x90
SRC_FSM_STATE = 0x91

# ---- field encodings ----
CONTROL1_ENABLE = 1 << 3          # gates every GO_COMMAND action
GO_SELECT_PDO = 0x01
GO_GET_SRC_CAP = 0x04
GO_SOFT_RESET = 0x1D
GO_HARD_RESET = 0x1E
PDO_SELECT_FIXED = {5: 0x01, 9: 0x02, 12: 0x03, 15: 0x04, 20: 0x05}  # SRC_PDO[7:3]

PD_CONTRACT = {0x0: "Type-C 5V (no PD)", 0x1: "5V", 0x2: "9V", 0x3: "12V",
               0x4: "15V", 0x5: "20V", 0x6: "PPS1", 0x7: "PPS2", 0x8: "PPS3",
               0x9: "SPR AVS", 0xA: "EPR 28V", 0xB: "EPR 36V", 0xC: "EPR 48V",
               0xD: "EPR AVS"}
DPM_CONTRACT = {0: "default 5V", 1: "divider3", 2: "SDP", 3: "CDP", 4: "DCP",
                5: "HVDCP", 6: "QC2 9V", 7: "QC2 12V"}
BC_LVL = {0: "none/Ra", 1: "default USB", 2: "1.5 A", 3: "3.0 A"}


class WriteRefused(RuntimeError):
    pass


def _bit(v, n):
    return bool(v >> n & 1)


class HUSB238A:
    def __init__(self, bus=1, addr=I2C_ADDR_GND, allow_write=False):
        self.bus_no = bus
        self.addr = addr
        self.allow_write = allow_write

    # -- raw access --
    def read(self, reg):
        with SMBus(self.bus_no) as b:
            return b.read_byte_data(self.addr, reg)

    def read_block(self, start, n):
        with SMBus(self.bus_no) as b:
            return [b.read_byte_data(self.addr, start + i) for i in range(n)]

    def _write(self, reg, val):
        if not self.allow_write:
            raise WriteRefused(f"write 0x{val:02x} -> reg 0x{reg:02x} refused "
                               "(construct with allow_write=True)")
        with SMBus(self.bus_no) as b:
            b.write_byte_data(self.addr, reg, val)

    # -- decoded reads --
    def status(self):
        c1 = self.read(CONTROL1)
        st, st1, typ, dpdm, cs0, cs1, sci = self.read_block(STATUS, 7)
        fixed = {}
        for v, reg in SRC_PDO_FIXED.items():
            raw = self.read(reg)
            fixed[v] = {"detect": _bit(raw, 7), "max_ma": (raw & 0x7F) * 100,
                        "raw": raw}
        pd_code = cs0 >> 4
        pd_is_fixed = pd_code in (0x1, 0x2, 0x3, 0x4, 0x5, 0xA, 0xB, 0xC)
        if pd_is_fixed:
            step = 20 if cs1 <= 0x7D else 40
            contract_ma = 500 + cs1 * step
        else:
            contract_ma = cs1 * 50
        return {
            "control1": {"raw": c1, "enable": bool(c1 & CONTROL1_ENABLE),
                         "tccdeb_ms": 120 + 10 * (c1 & 0x07)},
            "attached": _bit(st, 0),
            "ams_in_progress": _bit(st, 7),
            "epr_sink": _bit(st, 6),
            "thermal_shutdown": _bit(st, 3),
            "cc_advertised": BC_LVL[(st >> 1) & 0x3],
            "pd_hv": _bit(st1, 5),
            "pd_comm": _bit(st1, 4),
            "ams_success": _bit(st1, 2),
            "fault": _bit(st1, 1),
            "flgin": _bit(st1, 7),
            "pd_contract": PD_CONTRACT.get(pd_code, f"0x{pd_code:x}?"),
            "dpm_contract": DPM_CONTRACT.get(cs0 & 0xF, f"0x{cs0 & 0xF:x}?"),
            "contract_ma": contract_ma if pd_code else None,
            "source_epr_capable": _bit(sci, 0),
            "src_fixed_pdos": fixed,
            "vbus_mv": self.read(VBUS_MEASUREMENT) * 125,
            "snk_fsm": self.read(SNK_FSM_STATE),
            "raw_status_block": [st, st1, typ, dpdm, cs0, cs1, sci],
        }

    def wait_ams(self, timeout=1.0):
        """Wait for a PD message exchange to finish; return AMS_SUCC."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if not _bit(self.read(STATUS), 7):
                return _bit(self.read(STATUS1), 2)
            time.sleep(0.02)
        return False

    # -- guarded writes --
    # Bench-confirmed 2026-10-31: on HUSB238A-BB001 every Source_Capabilities
    # (ENABLE 0->1 attach, or GET_SRC_CAP) triggers an automatic request for the
    # highest PDO up to 28 V. Every path below that can cause one immediately
    # re-selects 5 V through _check_fixed() so the excursion is bounded.

    def _check_fixed(self, volts, max_volts):
        """Validate a fixed-PDO selection; raise WriteRefused if not allowed."""
        ceiling = min(max_volts, BOARD_MAX_VOLTS)
        if volts not in PDO_SELECT_FIXED:
            raise WriteRefused(f"{volts} V is not a fixed SPR PDO this board allows")
        if volts > ceiling:
            raise WriteRefused(f"{volts} V exceeds ceiling {ceiling} V")
        if volts != 5 and not _bit(self.read(SRC_PDO_FIXED[volts]), 7):
            raise WriteRefused(f"source does not advertise {volts} V "
                               "(run get_source_caps first)")

    def _select_fixed(self, volts):
        """Write SRC_PDO + SELECT_PDO. Callers must run _check_fixed first."""
        self._write(SRC_PDO, PDO_SELECT_FIXED[volts] << 3)
        time.sleep(0.005)
        self._write(GO_COMMAND, GO_SELECT_PDO)
        return self.wait_ams()

    def enable(self):
        """Set CONTROL1.ENABLE. On a 0->1 transition, wait for attach + the
        automatic request, then immediately hold 5 V."""
        c1 = self.read(CONTROL1)
        if not c1 & CONTROL1_ENABLE:
            tccdeb_s = (120 + 10 * (c1 & 0x07)) / 1000.0
            self._write(CONTROL1, c1 | CONTROL1_ENABLE)
            time.sleep(tccdeb_s + 0.05)
            self.wait_ams(timeout=1.0)
            if _bit(self.read(STATUS), 0):
                self._select_fixed(5)

    def get_source_caps(self, hold_volts=5, max_volts=5):
        """Query Source_Capabilities, then re-select hold_volts (default 5 V).
        hold_volts goes through the same checks as request_fixed; None is not
        allowed, because the automatic request would otherwise stand."""
        if hold_volts is None:
            raise WriteRefused("hold_volts=None would leave the automatic request in place")
        # Value and ceiling checks before any write; the "advertised" check
        # can only run after the query has filled SRC_PDO_xV.
        if hold_volts not in PDO_SELECT_FIXED:
            raise WriteRefused(f"{hold_volts} V is not a fixed SPR PDO this board allows")
        if hold_volts > min(max_volts, BOARD_MAX_VOLTS):
            raise WriteRefused(f"{hold_volts} V exceeds ceiling {min(max_volts, BOARD_MAX_VOLTS)} V")
        self.enable()
        self._write(GO_COMMAND, GO_GET_SRC_CAP)
        ok = self.wait_ams()
        try:
            self._check_fixed(hold_volts, max_volts)
        except WriteRefused:
            self._select_fixed(5)  # never leave the automatic request standing
            raise
        self._select_fixed(hold_volts)
        return ok

    def request_fixed(self, volts, max_volts=5):
        """Request a fixed SPR PDO. Refuses EPR/AVS/PPS and anything above
        min(max_volts, BOARD_MAX_VOLTS) or not advertised by the source."""
        self._check_fixed(volts, max_volts)
        self.enable()
        return self._select_fixed(volts)


def _print_status(s):
    c1 = s["control1"]
    print(f"CONTROL1 0x{c1['raw']:02x}  ENABLE={int(c1['enable'])}  tCCdeb={c1['tccdeb_ms']} ms")
    print(f"attached={int(s['attached'])}  cc={s['cc_advertised']}  pd_comm={int(s['pd_comm'])}"
          f"  pd_hv={int(s['pd_hv'])}  epr_sink={int(s['epr_sink'])}")
    print(f"ams_in_progress={int(s['ams_in_progress'])}  ams_success={int(s['ams_success'])}"
          f"  fault={int(s['fault'])}  tsd={int(s['thermal_shutdown'])}  flgin={int(s['flgin'])}")
    ma = s["contract_ma"]
    print(f"contract: PD={s['pd_contract']}  DPM={s['dpm_contract']}"
          f"  current={'-' if ma is None else f'{ma} mA'}")
    print(f"VBUS (chip ADC) = {s['vbus_mv'] / 1000:.3f} V   source EPR capable={int(s['source_epr_capable'])}")
    pdos = ", ".join(f"{v}V {p['max_ma']}mA" for v, p in s["src_fixed_pdos"].items() if p["detect"])
    print(f"source fixed PDOs: {pdos or 'none reported'}")
    print(f"SNK_FSM_STATE=0x{s['snk_fsm']:02x}  raw 0x63-0x69: "
          + " ".join(f"{x:02x}" for x in s["raw_status_block"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bus", type=int, default=1)
    ap.add_argument("--addr", type=lambda x: int(x, 0), default=I2C_ADDR_GND)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    sub.add_parser("dump")
    sc = sub.add_parser("srccap")
    sc.add_argument("--arm", action="store_true")
    rq = sub.add_parser("request")
    rq.add_argument("volts", type=int)
    rq.add_argument("--max", type=int, default=5, dest="max_volts")
    rq.add_argument("--arm", action="store_true")
    a = ap.parse_args()
    cmd = a.cmd or "status"

    armed = getattr(a, "arm", False)
    dev = HUSB238A(a.bus, a.addr, allow_write=armed)
    try:
        if cmd == "dump":
            r = dev.read_block(0x00, 0x92)
            for base in range(0, 0x92, 16):
                print(f"{base:02x}: " + " ".join(f"{x:02x}" for x in r[base:base + 16]))
        elif cmd == "srccap":
            print("Get_Source_Cap AMS success:", dev.get_source_caps())
            _print_status(dev.status())
        elif cmd == "request":
            print(f"request {a.volts} V AMS success:", dev.request_fixed(a.volts, a.max_volts))
            time.sleep(0.2)
            _print_status(dev.status())
        else:
            _print_status(dev.status())
    except WriteRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
