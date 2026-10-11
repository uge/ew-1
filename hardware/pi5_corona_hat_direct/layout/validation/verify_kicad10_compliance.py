#!/usr/bin/env python3
"""
KiCad 10 Strict Compliance Verification & Auto-Upgrade Tool
Verifies all project files adhere strictly to native KiCad 10 format:
- PCBs: (version 20260206) (generator "pcbnew") (generator_version "10.0")
- Schematics: (version 20260306) (generator "eeschema") (generator_version "10.0")
- Symbols: (version 20251024) (generator "kicad_symbol_editor") (generator_version "10.0")
- Footprints: (version 20260206) (generator "pcbnew") (generator_version "10.0")
- Tables: (version 7)
- Zero references to legacy environment variables (${KICAD8_*}, ${KICAD7_*}, ${KICAD6_*}, ${KICAD_*})
"""

import os
import sys
import re
import argparse
import subprocess

EXPECTED = {
    ".kicad_pcb": {"version": "20260206", "gen_ver": '"10.0"'},
    ".kicad_sch": {"version": "20260306", "gen_ver": '"10.0"'},
    ".kicad_sym": {"version": "20251024", "gen_ver": '"10.0"'},
    ".kicad_mod": {"version": "20260206", "gen_ver": '"10.0"'},
    "fp-lib-table": {"version": "7"},
    "sym-lib-table": {"version": "7"},
}

LEGACY_VAR_PATTERN = re.compile(r"\$\{KICAD[0-9]*_[^}]+\}")
ALLOWED_VARS = {"${KICAD10_3DMODEL_DIR}", "${KICAD10_SYMBOL_DIR}", "${KICAD10_FOOTPRINT_DIR}"}


def check_file(path):
    issues = []
    base = os.path.basename(path)
    ext = os.path.splitext(path)[1]
    
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Check parenthesis balance for sexpr files
    if ext in [".kicad_pcb", ".kicad_sch", ".kicad_sym", ".kicad_mod"] or base in ["fp-lib-table", "sym-lib-table"]:
        opens = content.count("(")
        closes = content.count(")")
        if opens != closes:
            issues.append(f"Unbalanced parentheses: {opens} '(' vs {closes} ')'")
    
    # Check legacy environment variables
    vars_found = set(LEGACY_VAR_PATTERN.findall(content)) - ALLOWED_VARS
    if vars_found:
        issues.append(f"Legacy environment variables detected: {sorted(vars_found)}")
    
    # Check expected versions
    spec_key = ext if ext in EXPECTED else base
    if spec_key in EXPECTED:
        spec = EXPECTED[spec_key]
        if "version" in spec:
            v_match = re.search(r"\(version\s+([0-9]+)\)", content[:300])
            if not v_match:
                issues.append("Missing (version ...) tag in header")
            elif v_match.group(1) != spec["version"]:
                issues.append(f"Expected version {spec['version']}, found {v_match.group(1)}")
        
        if "gen_ver" in spec:
            gv_match = re.search(r"\(generator_version\s+([^\)]+)\)", content[:300])
            if not gv_match:
                issues.append("Missing (generator_version ...) tag in header")
            elif gv_match.group(1) != spec["gen_ver"]:
                issues.append(f"Expected generator_version {spec['gen_ver']}, found {gv_match.group(1)}")

    return issues


def fix_file(path):
    ext = os.path.splitext(path)[1]
    base = os.path.basename(path)
    if ext == ".kicad_sch":
        subprocess.run(["kicad-cli", "sch", "upgrade", "--force", path], check=False)
    elif ext == ".kicad_pcb":
        subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", path], check=False)
    elif ext == ".kicad_sym":
        subprocess.run(["kicad-cli", "sym", "upgrade", "--force", path], check=False)
    elif ext == ".kicad_mod":
        parent = os.path.dirname(path)
        subprocess.run(["kicad-cli", "fp", "upgrade", "--force", parent], check=False)


def main():
    parser = argparse.ArgumentParser(description="Verify KiCad 10 compliance for all project files.")
    parser.add_argument("--root", default=".", help="Root directory to check (default: current directory)")
    parser.add_argument("--fix", action="store_true", help="Automatically upgrade non-compliant files")
    args = parser.parse_args()

    root_dir = os.path.abspath(args.root)
    total_files = 0
    failed_files = 0

    print(f"Scanning for KiCad files under: {root_dir}")
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if ".git" in dirpath or ".history" in dirpath:
            continue
        for f in sorted(filenames):
            ext = os.path.splitext(f)[1]
            if ext in [".kicad_pcb", ".kicad_sch", ".kicad_sym", ".kicad_mod"] or f in ["fp-lib-table", "sym-lib-table"]:
                file_path = os.path.join(dirpath, f)
                total_files += 1
                rel_path = os.path.relpath(file_path, root_dir)
                
                issues = check_file(file_path)
                if issues:
                    failed_files += 1
                    print(f"FAIL: {rel_path}")
                    for issue in issues:
                        print(f"  - {issue}")
                    if args.fix:
                        print(f"  Attempting auto-upgrade on {rel_path}...")
                        fix_file(file_path)
                        # Recheck
                        new_issues = check_file(file_path)
                        if not new_issues:
                            print(f"  SUCCESS: {rel_path} upgraded to KiCad 10.")
                            failed_files -= 1
                        else:
                            print(f"  REMAINING ISSUES after upgrade on {rel_path}: {new_issues}")

    print("\n" + "="*60)
    print(f"KiCad 10 Compliance Verification: {total_files - failed_files}/{total_files} files compliant.")
    if failed_files == 0:
        print("PASS: ALL PROJECT FILES STRICTLY COMPLIANT WITH KICAD 10.")
        sys.exit(0)
    else:
        print(f"ERROR: {failed_files} file(s) failed KiCad 10 compliance.")
        sys.exit(1)


if __name__ == "__main__":
    main()
