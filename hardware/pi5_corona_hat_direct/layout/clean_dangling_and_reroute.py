#!/usr/bin/env python3
"""
clean_dangling_and_reroute.py
Removes dangling vias/tracks from lv-trial2-routed and runs py_router on remaining nets.
"""

from pathlib import Path
import json
import shutil
import subprocess
import pcbnew as p

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path.home() / ".local/share/KiCadRoutingTools"
trial = ROOT / "layout/routing-trials"

drc_file = trial / "lv-trial2-drc.json"
d = json.load(open(drc_file))
dangling_ids = {v["items"][0]["uuid"] for v in d.get("violations", []) if v["type"] in ["track_dangling", "via_dangling"]}

print(f"Removing {len(dangling_ids)} dangling elements...")

b = p.LoadBoard(str(trial / "lv-trial2-routed.kicad_pcb"))
for t in list(b.GetTracks()):
    if t.m_Uuid.AsString() in dangling_ids:
        b.Remove(t)
        t.thisown = False

# Ensure local clearance on zones is 0.3mm to fix NPTH hole clearance
for z in b.Zones():
    if not z.GetIsRuleArea():
        z.SetLocalClearance(p.FromMM(0.3))

filler = p.ZONE_FILLER(b)
filler.Fill(b.Zones())
b.BuildConnectivity()

input_pcb = trial / "lv-trial3-input.kicad_pcb"
p.SaveBoard(str(input_pcb), b)

source = ROOT / "pi5_corona_hv"
shutil.copy2(source.with_suffix(".kicad_pro"), trial / "lv-trial3-input.kicad_pro")
shutil.copy2(source.with_suffix(".kicad_dru"), trial / "lv-trial3-input.kicad_dru")

# Remaining nets
remaining_nets = [
    "/HV_CURR_ADC",
    "/01_power_mcu/VIN_PD",
    "/02_drive_transformer/HV_BRIDGE",
    "3V3",
    "/HV_SENSE_ADC",
    "/01_power_mcu/PD_VMON",
    "/01_power_mcu/SDA",
    "/01_power_mcu/SCL",
    "/02_drive_transformer/DRV_B",
    "/02_drive_transformer/PRI_A",
    "/01_power_mcu/CC1",
    "/01_power_mcu/CC2",
    "Net-(R8-Pad2)",
    "/01_power_mcu/V18",
    "/01_power_mcu/V5V",
    "/01_power_mcu/OTP_NTC",
    "/01_power_mcu/EFUSE_OVLO",
    "/01_power_mcu/EFUSE_ILM"
]

shutil.copy2(source.with_suffix(".kicad_pro"), trial / "lv-trial3-routed.kicad_pro")
shutil.copy2(source.with_suffix(".kicad_dru"), trial / "lv-trial3-routed.kicad_dru")

cmd = [
    "/usr/bin/python3", str(TOOLS / "py_router/route.py"),
    str(trial / "lv-trial3-input.kicad_pcb"),
    str(trial / "lv-trial3-routed.kicad_pcb"),
    "--nets", *remaining_nets,
    "--layers", "F.Cu", "B.Cu",
    "--track-width", "0.2",
    "--clearance", "0.15",
    "--net-clearances", str(trial / "net-clearances2.json"),
    "--via-size", "0.6",
    "--via-drill", "0.3",
    "--escalation", "board",
    "--no-fix-drc-settings",
    "--no-stub-layer-swap",
    "--same-net-pad-clearance", "0.15",
    "--write-fill",
    "--max-ripup", "4",
    "--max-iterations", "100000",
    "--json-out", str(trial / "lv-trial3-result.json")
]

print("Launching py_router for remaining nets...")
with (trial / "lv-trial3-router.log").open("w") as log:
    result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)

print("Route tool exit code:", result.returncode)

# Restore .kicad_pro
shutil.copy2(source.with_suffix(".kicad_pro"), trial / "lv-trial3-routed.kicad_pro")

# Run DRC
drc_out = trial / "lv-trial3-drc.json"
subprocess.run([
    "kicad-cli", "pcb", "drc",
    "--format", "json",
    "-o", str(drc_out),
    str(trial / "lv-trial3-routed.kicad_pcb")
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
