#!/usr/bin/env python3
"""
test_fanned_route.py
Routes all remaining nets from test_fanned_all.kicad_pcb using grid-step=0.05.
"""

from pathlib import Path
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path.home() / ".local/share/KiCadRoutingTools"
trial = ROOT / "layout/routing-trials"

source = ROOT / "pi5_corona_hv"
shutil.copy2(source.with_suffix(".kicad_pro"), trial / "test_fanned_all.kicad_pro")
shutil.copy2(source.with_suffix(".kicad_dru"), trial / "test_fanned_all.kicad_dru")
shutil.copy2(source.with_suffix(".kicad_pro"), trial / "test_fanned_routed.kicad_pro")
shutil.copy2(source.with_suffix(".kicad_dru"), trial / "test_fanned_routed.kicad_dru")

nets = [
    "/01_power_mcu/CC1",
    "/01_power_mcu/CC2",
    "/01_power_mcu/EFUSE_DVDT",
    "/01_power_mcu/EFUSE_ILM",
    "/01_power_mcu/EFUSE_OVLO",
    "/01_power_mcu/EN_DRV",
    "/01_power_mcu/GATE",
    "/01_power_mcu/IFB",
    "/01_power_mcu/ISENP",
    "/01_power_mcu/OTP_NTC",
    "/01_power_mcu/PD_VMON",
    "/01_power_mcu/SCL",
    "/01_power_mcu/SDA",
    "/01_power_mcu/USB_DN",
    "/01_power_mcu/USB_DP",
    "/01_power_mcu/V18",
    "/01_power_mcu/V5V",
    "/01_power_mcu/VBUS_IN",
    "/01_power_mcu/VBUS_RAW",
    "/01_power_mcu/VIN_PD",
    "/02_drive_transformer/DRV_A",
    "/02_drive_transformer/DRV_B",
    "/02_drive_transformer/DRV_CPH",
    "/02_drive_transformer/DRV_CPL",
    "/02_drive_transformer/DRV_IMODE",
    "/02_drive_transformer/DRV_IPROPI",
    "/02_drive_transformer/DRV_VCP",
    "/02_drive_transformer/HV_BRIDGE",
    "/02_drive_transformer/PRI_A",
    "/04_sense_safety/HV_SENSE_RAW",
    "/HV_CURR_ADC",
    "/HV_SENSE_ADC",
    "/INTERLOCK_OK",
    "/VIN_PROTECTED",
    "3V3",
    "Net-(C63-Pad1)",
    "Net-(R8-Pad2)",
    "Net-(U4-IN-)"
]

cmd = [
    "/usr/bin/python3", str(TOOLS / "py_router/route.py"),
    str(trial / "test_fanned_all.kicad_pcb"),
    str(trial / "test_fanned_routed.kicad_pcb"),
    "--nets", *nets,
    "--layers", "F.Cu", "B.Cu",
    "--track-width", "0.2",
    "--clearance", "0.2",
    "--grid-step", "0.05",
    "--net-clearances", str(trial / "net-clearances-ripup8.json"),
    "--via-size", "0.6",
    "--via-drill", "0.3",
    "--escalation", "off",
    "--no-fix-drc-settings",
    "--no-stub-layer-swap",
    "--same-net-pad-clearance", "0.15",
    "--write-fill",
    "--max-ripup", "8",
    "--max-iterations", "300000",
    "--json-out", str(trial / "test_fanned_result.json")
]

print("Launching py_router on fanned board with grid-step=0.05...")
with (trial / "test_fanned_router.log").open("w") as log:
    result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)

print("Route tool exit code:", result.returncode)

# Restore .kicad_pro
shutil.copy2(source.with_suffix(".kicad_pro"), trial / "test_fanned_routed.kicad_pro")

# Run DRC
drc_out = trial / "test_fanned_drc.json"
subprocess.run([
    "kicad-cli", "pcb", "drc",
    "--format", "json",
    "-o", str(drc_out),
    str(trial / "test_fanned_routed.kicad_pcb")
], capture_output=True, text=True)

if drc_out.exists():
    d = json.load(drc_out.open())
    clearance_v = [v for v in d.get("violations", []) if v["type"] == "clearance"]
    other_v = [v for v in d.get("violations", []) if v["type"] not in ["clearance", "lib_footprint_issues"]]
    unc = d.get("unconnected_items", [])
    print(f"DRC Clearance Violations: {len(clearance_v)}")
    print(f"DRC Other Violations:     {len(other_v)}")
    print(f"Unconnected Items:        {len(unc)}")
    for v in clearance_v[:5]:
        print("  Clearance:", v.get("description"))
    for v in other_v[:5]:
        print("  Other:", v.get("type"), v.get("description"))
