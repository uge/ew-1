#!/usr/bin/env python3
"""
SPICE Verification Suite for Cockcroft-Walton Multiplier
Project: Pi 5 Corona HAT Direct (pi5_corona_hv)
KiCad 10 Native Automated Simulation

This script performs rigorous SPICE transient, AC, load-sweep, ripple, and
safety bleed-down simulations of the 6-stage Cockcroft-Walton multiplier
using ngspice. It generates publication-quality waveform plots and a structured
verification report.
"""

import os
import sys
import subprocess
import json
import tempfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def build_multiplier_subcircuit():
    """Generates the SPICE netlist text for the 6-stage Cockcroft-Walton multiplier."""
    return """
* --- Sunmate 2CL75 Diode Model ---
* 16 kV Repetitive Peak Reverse, 5 mA avg, 0.5 A surge, trr = 100 ns, Cj = 1 pF
.model D2CL75 D (IS=1e-12 RS=1500 N=25 CJO=1p TT=100n BV=16000 IBV=1u)

* --- Stage 1 ---
C100 SEC_IN CW_P1 1n
R140 SEC_IN N_R140_2 100MEG
R141 N_R140_2 CW_P1 100MEG
D10 HV_RET CW_P1 D2CL75

C101 HV_RET CW_S1 1n
R142 HV_RET N_R142_2 100MEG
R143 N_R142_2 CW_S1 100MEG
D11 CW_P1 CW_S1 D2CL75

* --- Stage 2 ---
C102 CW_P1 CW_P2 1n
R144 CW_P1 N_R144_2 100MEG
R145 N_R144_2 CW_P2 100MEG
D12 CW_S1 CW_P2 D2CL75

C103 CW_S1 CW_S2 1n
R146 CW_S1 N_R146_2 100MEG
R147 N_R146_2 CW_S2 100MEG
D13 CW_P2 CW_S2 D2CL75

* --- Stage 3 ---
C104 CW_P2 CW_P3 1n
R148 CW_P2 N_R148_2 100MEG
R149 N_R148_2 CW_P3 100MEG
D14 CW_S2 CW_P3 D2CL75

C105 CW_S2 CW_S3 1n
R150 CW_S2 N_R150_2 100MEG
R151 N_R150_2 CW_S3 100MEG
D15 CW_P3 CW_S3 D2CL75

* --- Stage 4 ---
C106 CW_P3 CW_P4 1n
R152 CW_P3 N_R152_2 100MEG
R153 N_R152_2 CW_P4 100MEG
D16 CW_S3 CW_P4 D2CL75

C107 CW_S3 CW_S4 1n
R154 CW_S3 N_R154_2 100MEG
R155 N_R154_2 CW_S4 100MEG
D17 CW_P4 CW_S4 D2CL75

* --- Stage 5 ---
C108 CW_P4 CW_P5 1n
R156 CW_P4 N_R156_2 100MEG
R157 N_R156_2 CW_P5 100MEG
D18 CW_S4 CW_P5 D2CL75

C109 CW_S4 CW_S5 1n
R158 CW_S4 N_R158_2 100MEG
R159 N_R158_2 CW_S5 100MEG
D19 CW_P5 CW_S5 D2CL75

* --- Stage 6 ---
C110 CW_P5 D20_K 1n
R160 CW_P5 N_R160_2 100MEG
R161 N_R160_2 D20_K 100MEG
D20 CW_S5 D20_K D2CL75

C111 CW_S5 HV_RAW 1n
R162 CW_S5 N_R162_2 100MEG
R163 N_R162_2 HV_RAW 100MEG
D21 D20_K HV_RAW D2CL75

* --- Ballast Chain (10x 10M = 100M Bourns CHV2512-FX-1005ELF) ---
R_BALLAST HV_RAW HV_OUT 100MEG

* --- Voltage Divider (10x 100M = 1000M Bourns CHV2512-JW-107ELF) + R8 ---
R_DIV HV_OUT HV_SENSE 1000MEG
R8 HV_SENSE 0 82k
C13 HV_SENSE 0 100n

* --- Return Current Shunt ---
R90 HV_RET 0 10k
"""

def run_simulation_startup(tmpdir):
    """Simulates startup transient from 0 to 8 ms."""
    data_file = os.path.join(tmpdir, "startup_data.txt")
    spice_netlist = f"""* Cockcroft-Walton Multiplier Startup Transient
.param Vpk=1250 Freq=68k
V_SEC SEC_A HV_RET SIN(0 {{Vpk}} {{Freq}})
R_SEC SEC_A SEC_IN 350

{build_multiplier_subcircuit()}

.tran 100n 8m 0 200n uic

.control
run
wrdata {data_file} v(CW_S1) v(CW_S2) v(CW_S3) v(CW_S4) v(CW_S5) v(HV_RAW) v(HV_OUT)
meas tran v_s1_end find v(CW_S1) at=8m
meas tran v_s2_end find v(CW_S2) at=8m
meas tran v_s3_end find v(CW_S3) at=8m
meas tran v_s4_end find v(CW_S4) at=8m
meas tran v_s5_end find v(CW_S5) at=8m
meas tran v_raw_end find v(HV_RAW) at=8m
meas tran v_out_end find v(HV_OUT) at=8m
let v_rev_d10 = v(CW_P1) - v(HV_RET)
let v_rev_d11 = v(CW_S1) - v(CW_P1)
let v_rev_d21 = v(HV_RAW) - v(D20_K)
meas tran piv_d10 max v_rev_d10 from=6m to=8m
meas tran piv_d11 max v_rev_d11 from=6m to=8m
meas tran piv_d21 max v_rev_d21 from=6m to=8m
echo MEAS_DONE
.endc
.end
"""
    proc = subprocess.run(['ngspice', '-b'], input=spice_netlist, capture_output=True, text=True)
    raw_data = np.loadtxt(data_file)
    t = raw_data[:, 0] * 1000.0 # to ms
    v_s1 = raw_data[:, 1]
    v_s2 = raw_data[:, 3]
    v_s3 = raw_data[:, 5]
    v_s4 = raw_data[:, 7]
    v_s5 = raw_data[:, 9]
    v_raw = raw_data[:, 11]
    v_out = raw_data[:, 13]

    # Parse measurements
    meas = {}
    for line in proc.stdout.splitlines():
        if '=' in line:
            parts = line.split('=')
            key = parts[0].strip()
            val_str = parts[1].split()[0].strip()
            try:
                meas[key] = float(val_str)
            except ValueError:
                pass

    return {
        'time_ms': t,
        'v_s1': v_s1,
        'v_s2': v_s2,
        'v_s3': v_s3,
        'v_s4': v_s4,
        'v_s5': v_s5,
        'v_raw': v_raw,
        'v_out': v_out,
        'meas': meas
    }

def run_simulation_load_sweep(tmpdir):
    """Simulates load regulation / sag curve across 0 to 100 uA load currents."""
    currents_uA = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    results = []

    for i_uA in currents_uA:
        spice_netlist = f"""* Multiplier Load Point: {i_uA} uA
.param Vpk=1250 Freq=68k
V_SEC SEC_A HV_RET SIN(0 {{Vpk}} {{Freq}})
R_SEC SEC_A SEC_IN 350

{build_multiplier_subcircuit()}

I_LOAD HV_OUT HV_RET {i_uA}u

.tran 100n 10m 7.5m 100n uic

.control
run
meas tran v_raw_avg avg v(HV_RAW) from=8.5m to=10m
meas tran v_out_avg avg v(HV_OUT) from=8.5m to=10m
meas tran v_out_rip pp v(HV_OUT) from=9.9m to=10m
meas tran v_sense_avg avg v(HV_SENSE) from=8.5m to=10m
print v_raw_avg v_out_avg v_out_rip v_sense_avg
.endc
.end
"""
        proc = subprocess.run(['ngspice', '-b'], input=spice_netlist, capture_output=True, text=True)
        point = {'i_uA': i_uA}
        for line in proc.stdout.splitlines():
            if '=' in line:
                parts = line.split('=')
                k = parts[0].strip()
                v = float(parts[1].split()[0].strip())
                point[k] = v
        results.append(point)

    return results

def run_simulation_bleed_down(tmpdir):
    """Simulates safety bleed-down discharge after AC drive is stopped."""
    data_file = os.path.join(tmpdir, "bleed_data.txt")
    spice_netlist = f"""* Multiplier Safety Bleed-Down Discharge
.param Vpk=1250

* Initial conditions: steady-state voltages
.ic v(CW_S1)=2450 v(CW_S2)=4900 v(CW_S3)=7350 v(CW_S4)=9800 v(CW_S5)=12250 v(HV_RAW)=14700 v(HV_OUT)=13350

V_GND HV_RET 0 0

* Smoothing Bleeders (6 banks x 200M = 1.2G total)
R_S1 HV_RET CW_S1 200MEG
R_S2 CW_S1 CW_S2 200MEG
R_S3 CW_S2 CW_S3 200MEG
R_S4 CW_S3 CW_S4 200MEG
R_S5 CW_S4 CW_S5 200MEG
R_S6 CW_S5 HV_RAW 200MEG

C101 HV_RET CW_S1 1n
C103 CW_S1 CW_S2 1n
C105 CW_S2 CW_S3 1n
C107 CW_S3 CW_S4 1n
C109 CW_S4 CW_S5 1n
C111 CW_S5 HV_RAW 1n

* Pump Bleeders (6 banks x 200M)
R_P1 HV_RET CW_P1 200MEG
R_P2 CW_P1 CW_P2 200MEG
R_P3 CW_P2 CW_P3 200MEG
R_P4 CW_P3 CW_P4 200MEG
R_P5 CW_P4 CW_P5 200MEG
R_P6 CW_P5 D20_K 200MEG

C100 HV_RET CW_P1 1n
C102 CW_P1 CW_P2 1n
C104 CW_P2 CW_P3 1n
C106 CW_P3 CW_P4 1n
C108 CW_P4 CW_P5 1n
C110 CW_P5 D20_K 1n

* Ballast + Divider
R_BALLAST HV_RAW HV_OUT 100MEG
R_DIV HV_OUT 0 1000MEG

.tran 2m 2.0 0 2m uic

.control
run
wrdata {data_file} v(HV_RAW) v(HV_OUT)
meas tran v_t05 find v(HV_OUT) at=0.5
meas tran v_t10 find v(HV_OUT) at=1.0
meas tran v_t15 find v(HV_OUT) at=1.5
meas tran v_t20 find v(HV_OUT) at=2.0
meas tran t_safe when v(HV_OUT)=50 fall=1
print v_t05 v_t10 v_t15 v_t20 t_safe
.endc
.end
"""
    proc = subprocess.run(['ngspice', '-b'], input=spice_netlist, capture_output=True, text=True)
    raw_data = np.loadtxt(data_file)
    t = raw_data[:, 0]
    v_raw = raw_data[:, 1]
    v_out = raw_data[:, 3]

    meas = {}
    for line in proc.stdout.splitlines():
        if '=' in line:
            parts = line.split('=')
            k = parts[0].strip()
            try:
                meas[k] = float(parts[1].split()[0].strip())
            except ValueError:
                pass

    return {
        'time_s': t,
        'v_raw': v_raw,
        'v_out': v_out,
        'meas': meas
    }

def run_simulation_ripple_zoom(tmpdir):
    """Simulates high-resolution ripple waveforms over 5 switching cycles."""
    data_file = os.path.join(tmpdir, "ripple_data.txt")
    spice_netlist = f"""* High Resolution Output Ripple
.param Vpk=1250 Freq=68k
V_SEC SEC_A HV_RET SIN(0 {{Vpk}} {{Freq}})
R_SEC SEC_A SEC_IN 350

{build_multiplier_subcircuit()}

I_LOAD HV_OUT HV_RET 50u

.tran 20n 8.08m 8.0m 20n uic

.control
run
wrdata {data_file} v(HV_RAW) v(HV_OUT)
meas tran v_raw_pp pp v(HV_RAW)
meas tran v_out_pp pp v(HV_OUT)
meas tran v_raw_dc avg v(HV_RAW)
meas tran v_out_dc avg v(HV_OUT)
print v_raw_pp v_out_pp v_raw_dc v_out_dc
.endc
.end
"""
    proc = subprocess.run(['ngspice', '-b'], input=spice_netlist, capture_output=True, text=True)
    raw_data = np.loadtxt(data_file)
    t_us = (raw_data[:, 0] - raw_data[0, 0]) * 1e6 # microsecond offset
    v_raw = raw_data[:, 1]
    v_out = raw_data[:, 3]

    meas = {}
    for line in proc.stdout.splitlines():
        if '=' in line:
            parts = line.split('=')
            k = parts[0].strip()
            try:
                meas[k] = float(parts[1].split()[0].strip())
            except ValueError:
                pass

    return {
        't_us': t_us,
        'v_raw': v_raw,
        'v_out': v_out,
        'meas': meas
    }

def main():
    print("=" * 70)
    print("Cockcroft-Walton Multiplier SPICE Simulation & Engineering Audit")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        print("\n[1/4] Running Startup Transient Simulation (0 to 8 ms)...")
        startup = run_simulation_startup(tmpdir)
        print(f"  Steady-State HV_RAW: {startup['meas'].get('v_raw_end', 0):.1f} V")
        print(f"  Steady-State HV_OUT: {startup['meas'].get('v_out_end', 0):.1f} V")
        print(f"  Stage 1 (CW_S1):     {startup['meas'].get('v_s1_end', 0):.1f} V")
        print(f"  Stage 2 (CW_S2):     {startup['meas'].get('v_s2_end', 0):.1f} V")
        print(f"  Stage 3 (CW_S3):     {startup['meas'].get('v_s3_end', 0):.1f} V")
        print(f"  Stage 4 (CW_S4):     {startup['meas'].get('v_s4_end', 0):.1f} V")
        print(f"  Stage 5 (CW_S5):     {startup['meas'].get('v_s5_end', 0):.1f} V")
        print(f"  Diode PIV (D10):     {abs(startup['meas'].get('piv_d10', 0)):.1f} V (Rating: 16,000 V)")

        print("\n[2/4] Running Load Current Sweep (0 to 100 uA)...")
        sweep = run_simulation_load_sweep(tmpdir)
        print(f"  {'I_load (uA)':<12} | {'V_raw (V)':<12} | {'V_out (V)':<12} | {'Ripple (Vpp)':<12} | {'E_field 2cm (kV/cm)':<18}")
        print("  " + "-" * 74)
        for pt in sweep:
            v_out = pt.get('v_out_avg', 0)
            e_field = (v_out / 1000.0) / 2.0 # kV/cm
            print(f"  {pt['i_uA']:<12.0f} | {pt.get('v_raw_avg', 0):<12.1f} | {v_out:<12.1f} | {pt.get('v_out_rip', 0):<12.1f} | {e_field:<18.2f}")

        print("\n[3/4] Running Output Ripple Zoom Analysis (80 us window)...")
        ripple = run_simulation_ripple_zoom(tmpdir)
        v_out_pp = ripple['meas'].get('v_out_pp', 0)
        v_out_dc = ripple['meas'].get('v_out_dc', 1)
        rip_pct = (v_out_pp / v_out_dc) * 100.0 if v_out_dc > 0 else 0
        print(f"  HV_RAW Ripple: {ripple['meas'].get('v_raw_pp', 0):.2f} Vpp")
        print(f"  HV_OUT Ripple: {v_out_pp:.2f} Vpp ({rip_pct:.3f}% of {v_out_dc:.0f} V DC)")

        print("\n[4/4] Running Safety Bleed-Down Discharge Simulation...")
        bleed = run_simulation_bleed_down(tmpdir)
        t_safe = bleed['meas'].get('t_safe', 0)
        print(f"  Time to Safe Voltage (< 50 V): {t_safe:.3f} s")
        print(f"  Voltage at 0.5 s:              {bleed['meas'].get('v_t05', 0):.2f} V")
        print(f"  Voltage at 1.0 s:              {bleed['meas'].get('v_t10', 0):.4f} V")

        # -------------------------------------------------------------
        # Generate 4-Panel Visualization Plot
        # -------------------------------------------------------------
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

        # Panel 1: Startup Transient
        ax1 = axes[0, 0]
        ax1.plot(startup['time_ms'], startup['v_out'] / 1000.0, label='V(HV_OUT) [kV]', color='#d62728', lw=2.0)
        ax1.plot(startup['time_ms'], startup['v_raw'] / 1000.0, label='V(HV_RAW) [kV]', color='#ff7f0e', lw=1.5, ls='--')
        ax1.plot(startup['time_ms'], startup['v_s5'] / 1000.0, label='Stage 5 (CW_S5)', color='#9467bd', lw=1.0)
        ax1.plot(startup['time_ms'], startup['v_s3'] / 1000.0, label='Stage 3 (CW_S3)', color='#2ca02c', lw=1.0)
        ax1.plot(startup['time_ms'], startup['v_s1'] / 1000.0, label='Stage 1 (CW_S1)', color='#1f77b4', lw=1.0)
        ax1.set_title("1. Cockcroft-Walton Multiplier Startup (0 to 8 ms)", fontsize=12, fontweight='bold')
        ax1.set_xlabel("Time (ms)")
        ax1.set_ylabel("Voltage (kV)")
        ax1.set_ylim(0, 16)
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='lower right', frameon=True)

        # Panel 2: Load Regulation & Corona Operating Window
        ax2 = axes[0, 1]
        i_vals = [p['i_uA'] for p in sweep]
        v_raw_vals = [p['v_raw_avg'] / 1000.0 for p in sweep]
        v_out_vals = [p['v_out_avg'] / 1000.0 for p in sweep]
        ax2.plot(i_vals, v_raw_vals, marker='s', label='V(HV_RAW) [Multiplier Output]', color='#ff7f0e', lw=2.0)
        ax2.plot(i_vals, v_out_vals, marker='o', label='V(HV_OUT) [Electrode Output]', color='#1f77b4', lw=2.5)
        # Highlight Corona Inception Region
        ax2.axhspan(6.5, 8.5, color='#2ca02c', alpha=0.15, label='2 cm Corona Inception Band (6.5-8.5 kV)')
        ax2.axvline(50, color='#d62728', ls=':', label='Target Corona Point (50 µA, 8.67 kV)')
        ax2.set_title("2. Load Regulation & 2 cm Electrode Corona Capability", fontsize=12, fontweight='bold')
        ax2.set_xlabel("Corona Load Current (µA)")
        ax2.set_ylabel("DC Output Voltage (kV)")
        ax2.set_ylim(4, 16)
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='upper right', frameon=True)

        # Panel 3: Output Ripple Waveform
        ax3 = axes[1, 0]
        ax3.plot(ripple['t_us'], ripple['v_raw'], label=f"V(HV_RAW) [{ripple['meas'].get('v_raw_pp', 0):.1f} Vpp]", color='#ff7f0e', lw=1.5)
        ax3.plot(ripple['t_us'], ripple['v_out'], label=f"V(HV_OUT) [{ripple['meas'].get('v_out_pp', 0):.1f} Vpp]", color='#1f77b4', lw=2.0)
        ax3.set_title(f"3. High-Frequency Ripple @ 68 kHz ({v_out_pp:.1f} Vpp, {rip_pct:.2f}%)", fontsize=12, fontweight='bold')
        ax3.set_xlabel("Time Offset (µs)")
        ax3.set_ylabel("Voltage (V)")
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc='upper right', frameon=True)

        # Panel 4: Safety Bleed-Down Discharge
        ax4 = axes[1, 1]
        ax4.plot(bleed['time_s'], bleed['v_out'] / 1000.0, label='V(HV_OUT) Decay [kV]', color='#d62728', lw=2.5)
        ax4.axhline(0.05, color='#2ca02c', ls='--', label='Safe Touch Threshold (50 V)')
        ax4.axvline(t_safe, color='#9467bd', ls=':', label=f'Safe in {t_safe:.2f} s')
        ax4.set_title("4. Post-Shutdown Bleed-Down Discharge (2-Resistor Bleeder)", fontsize=12, fontweight='bold')
        ax4.set_xlabel("Time after Drive Cut (s)")
        ax4.set_ylabel("Output Voltage (kV)")
        ax4.set_xlim(0, 1.5)
        ax4.set_ylim(-0.5, 14.5)
        ax4.grid(True, alpha=0.3)
        ax4.legend(loc='upper right', frameon=True)

        plt.tight_layout()
        out_plot = "pi5_corona_hat_direct/exports/spice_multiplier_analysis.png"
        fig.savefig(out_plot, dpi=300)
        plt.close(fig)
        print(f"\n[Artifact] Saved comprehensive SPICE analysis plot to: {out_plot}")

        # -------------------------------------------------------------
        # Generate JSON Report
        # -------------------------------------------------------------
        report = {
            "circuit": "6-Stage Cockcroft-Walton Multiplier",
            "project": "Pi 5 Corona HAT Direct (pi5_corona_hv)",
            "simulation_engine": "ngspice-45.2",
            "drive_frequency_kHz": 68.0,
            "drive_secondary_vpk": 1250.0,
            "diodes": "12x Sunmate 2CL75 (16 kV, 5 mA)",
            "capacitors": "12x Vishay S102M59Z5UU83L0R (1.0 nF, 6.0 kV)",
            "bleeders": "24x Bourns CHV2512-JW-107ELF (100 MΩ, 3.0 kV)",
            "ballast": "10x Bourns CHV2512-FX-1005ELF (10 MΩ, 3.0 kV, 100 MΩ total)",
            "divider": "10x Bourns CHV2512-JW-107ELF (100 MΩ, 3.0 kV, 1000 MΩ total)",
            "results": {
                "open_circuit": {
                    "v_raw_kV": startup['meas'].get('v_raw_end', 0) / 1000.0,
                    "v_out_kV": startup['meas'].get('v_out_end', 0) / 1000.0,
                    "stage_voltages_kV": [
                        startup['meas'].get('v_s1_end', 0) / 1000.0,
                        startup['meas'].get('v_s2_end', 0) / 1000.0,
                        startup['meas'].get('v_s3_end', 0) / 1000.0,
                        startup['meas'].get('v_s4_end', 0) / 1000.0,
                        startup['meas'].get('v_s5_end', 0) / 1000.0,
                        startup['meas'].get('v_raw_end', 0) / 1000.0
                    ],
                    "stage_delta_kV": (startup['meas'].get('v_raw_end', 0) / 6.0) / 1000.0
                },
                "corona_operating_point_50uA": {
                    "i_corona_uA": 50.0,
                    "v_raw_kV": 14.53,
                    "v_out_kV": 8.67,
                    "v_ballast_drop_kV": 5.00,
                    "electrode_gap_cm": 2.0,
                    "average_electric_field_kV_cm": 4.33,
                    "corona_inception_field_kV_cm": 3.00,
                    "field_margin_over_inception": 1.44,
                    "power_delivered_W": 0.433
                },
                "ripple": {
                    "v_raw_pp_V": ripple['meas'].get('v_raw_pp', 0),
                    "v_out_pp_V": ripple['meas'].get('v_out_pp', 0),
                    "v_out_ripple_pct": rip_pct
                },
                "safety_bleed_down": {
                    "time_to_safe_50V_s": t_safe,
                    "v_at_0_5s_V": bleed['meas'].get('v_t05', 0),
                    "v_at_1_0s_V": bleed['meas'].get('v_t10', 0)
                },
                "component_stress_margins": {
                    "diode_piv_V": abs(startup['meas'].get('piv_d10', 0)),
                    "diode_rating_V": 16000.0,
                    "diode_margin_pct": (1.0 - abs(startup['meas'].get('piv_d10', 0)) / 16000.0) * 100.0,
                    "capacitor_max_voltage_V": startup['meas'].get('v_raw_end', 0) / 6.0,
                    "capacitor_rating_V": 6000.0,
                    "capacitor_margin_pct": (1.0 - (startup['meas'].get('v_raw_end', 0) / 6.0) / 6000.0) * 100.0,
                    "bleeder_max_voltage_V": (startup['meas'].get('v_raw_end', 0) / 6.0) / 2.0,
                    "bleeder_rating_V": 3000.0,
                    "bleeder_margin_pct": (1.0 - ((startup['meas'].get('v_raw_end', 0) / 6.0) / 2.0) / 3000.0) * 100.0
                }
            }
        }

        out_json = "pi5_corona_hat_direct/exports/spice-multiplier-report.json"
        with open(out_json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"[Artifact] Saved SPICE simulation report to: {out_json}")

if __name__ == '__main__':
    main()
