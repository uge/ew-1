#!/bin/sh
# Copy the dashboard and its host-side dependencies to ew-1 (run from the repo, on the workstation).
# Does not start or restart anything.
set -eu
host=${1:-ew-1.local}
here=$(cd "$(dirname "$0")" && pwd)
ssh -o BatchMode=yes "$host" 'mkdir -p ~/dashboard/static ~/dashboard_runs'
scp -q "$here"/*.py "$here"/ew1-dashboard.service "$here"/install_service.sh "$here"/README.md \
      "$host":dashboard/
scp -q "$here"/static/index.html "$host":dashboard/static/
scp -q "$here"/../stage7_ramp.py "$here"/../husb238a.py "$here"/../rp1_pwm_sync.py "$host":
ssh -o BatchMode=yes "$host" 'md5sum ~/stage7_ramp.py ~/husb238a.py ~/rp1_pwm_sync.py ~/dashboard/*.py'
