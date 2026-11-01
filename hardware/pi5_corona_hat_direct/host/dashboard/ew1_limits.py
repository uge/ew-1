"""Hard limits and precondition checks for the ew-1 dashboard (no hardware imports).

These are the server-side gates. The browser shows the same numbers, but only this
module decides. Keep it free of smbus2/gpiod so it can be unit-tested anywhere.
"""
import math

# Hard limits the UI cannot exceed (user-specified 2026-11-01).
LIMITS = {
    "vbus": (5, 9),                 # allowed PD contracts, V (fixed PDOs only)
    "freq_hz": (20_000, 100_000),   # DRV8876 fPWM max 100 kHz
    "target_kv": (0.1, 10.0),      # user: allow up to 10 kV (2026-11-01)
    "abort_kv": (0.2, 11.0),
    "max_duty": (0.01, 0.25),       # raised from 0.17 (2026-11-01) so a corona-loaded gap can reach 10 kV;
                                    # HV vs duty is non-monotonic (unloaded peak ~0.16): past it more duty gives LESS HV
    "ain1_max_v": (0.01, 0.5),      # 100 uA/V -> 50 uA
    "hold_s": (0.0, 30.0),
}
DEFAULTS = {"vbus": 5, "freq_hz": 32000, "target_kv": 3.0, "abort_kv": 4.0,
            "max_duty": 0.17, "ain1_max_v": 0.10, "hold_s": 2.0}
CONFIRM_WORD = "HV ON"

# Precondition thresholds (the ramp itself also insists on AIN0 < 0.01 V, AIN1 < 0.1 V, bridge < 0.2 V).
PRE_AIN0_MAX_V = 0.05
PRE_AIN1_MAX_V = 0.10
PRE_BRIDGE_MAX_V = 0.2
PRE_VBUS_BAND = (4.6, 5.6)
DO_NOT_TOUCH_S = 300


def _num(d, key, errors, integer=False, required=True):
    if key not in d:
        if required:
            errors.append(f"{key}: missing"); return None
        return DEFAULTS[key]
    v = d[key]
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        errors.append(f"{key}: not a number"); return None
    try:
        v = float(v)
    except ValueError:
        errors.append(f"{key}: not a number"); return None
    if not math.isfinite(v):
        errors.append(f"{key}: not finite"); return None
    if integer:
        if v != int(v):
            errors.append(f"{key}: must be an integer"); return None
        v = int(v)
    return v


def validate_run_params(d):
    """Validate a ramp request. Returns (params, errors); params is None when errors is non-empty."""
    errors = []
    if not isinstance(d, dict):
        return None, ["body must be a JSON object"]
    p = {}
    vbus = _num(d, "vbus", errors, integer=True)
    if vbus is not None and vbus not in LIMITS["vbus"]:
        errors.append(f"vbus: {vbus} not allowed (5 or 9 only)")
    p["vbus"] = vbus
    for key, integer in (("freq_hz", True), ("target_kv", False), ("abort_kv", False),
                         ("max_duty", False), ("ain1_max_v", False), ("hold_s", False)):
        v = _num(d, key, errors, integer=integer)
        if v is not None:
            lo, hi = LIMITS[key]
            if not lo <= v <= hi:
                errors.append(f"{key}: {v} outside {lo}..{hi}")
        p[key] = v
    if not errors and p["target_kv"] >= p["abort_kv"]:
        errors.append(f"target_kv {p['target_kv']} must be below abort_kv {p['abort_kv']}")
    if d.get("confirm") != CONFIRM_WORD:
        errors.append(f'confirm: must be the string "{CONFIRM_WORD}"')
    return (None, errors) if errors else (p, [])


def validate_align_params(d):
    errors = []
    if not isinstance(d, dict):
        return None, ["body must be a JSON object"]
    f = _num(d, "freq_hz", errors, integer=True, required=False)
    if f is not None and not LIMITS["freq_hz"][0] <= f <= LIMITS["freq_hz"][1]:
        errors.append(f"freq_hz: {f} outside {LIMITS['freq_hz'][0]}..{LIMITS['freq_hz'][1]}")
    return (None, errors) if errors else ({"freq_hz": f}, [])


def check_preconditions(s, mode="ramp"):
    """s: a fresh hardware snapshot dict with keys
         ain0_v, ain1_v, vbus_v, bridge_v (floats or None),
         gpio: {"nFAULT","EFUSE_FLT","INTLK","OVTRIP"} -> 0/1/None,
         out: {18,19,24,25} -> 0/1/None (output pin levels),
         pwm: {2: {"enable": 0/1}, 3: {...}} (optional),
         pd_contract: str or None, run_active: bool, lock_holders: list of pids (others).
       Returns a list of human-readable failures; empty means OK to start."""
    f = []
    g = s.get("gpio") or {}
    out = s.get("out") or {}
    if s.get("run_active"):
        f.append("a run is already active")
    if s.get("lock_holders"):
        f.append(f"HV lock held by another process (pid {', '.join(map(str, s['lock_holders']))})")
    if mode == "ramp" and g.get("INTLK") != 1:
        f.append("interlock open (GPIO23 != 1)")
    if g.get("nFAULT") != 1:
        f.append("DRV_nFAULT not OK (GPIO5 != 1)")
    if g.get("EFUSE_FLT") != 1:
        f.append("EFUSE_FLT not OK (GPIO6 != 1)")
    if g.get("OVTRIP") != 0:
        f.append("HV OV trip latched or unknown (GPIO26 != 0)")
    a0 = s.get("ain0_v")
    if a0 is None or not a0 < PRE_AIN0_MAX_V:
        f.append(f"AIN0 {a0} V not below {PRE_AIN0_MAX_V} V (HV still present?)")
    a1 = s.get("ain1_v")
    if a1 is None or not a1 < PRE_AIN1_MAX_V:
        f.append(f"AIN1 {a1} V not below {PRE_AIN1_MAX_V} V")
    br = s.get("bridge_v")
    if br is None or not br < PRE_BRIDGE_MAX_V:
        f.append(f"bridge {br} V not below {PRE_BRIDGE_MAX_V} V (GPIO25 path on?)")
    vb = s.get("vbus_v")
    if vb is None or not PRE_VBUS_BAND[0] < vb < PRE_VBUS_BAND[1]:
        f.append(f"VBUS {vb} V not in {PRE_VBUS_BAND} (5 V contract required at start)")
    if s.get("pd_contract") != "5V":
        f.append(f"PD contract {s.get('pd_contract')!r} is not 5V")
    for pin in (18, 19, 24, 25):
        if out.get(pin) != 0:
            f.append(f"GPIO{pin} not low ({out.get(pin)})")
    for ch, st in (s.get("pwm") or {}).items():
        if st and st.get("enable") not in (0, None):
            f.append(f"pwm{ch} enabled")
    return f
