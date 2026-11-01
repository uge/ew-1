#!/bin/sh
# Install (but do not enable or start) the ew-1 dashboard systemd unit. Run on ew-1:
#   sh ~/dashboard/install_service.sh
set -eu
here=$(cd "$(dirname "$0")" && pwd)
[ "$here" = "/home/uge/dashboard" ] || echo "note: unit file expects /home/uge/dashboard (this copy is $here)"
sudo install -m 644 "$here/ew1-dashboard.service" /etc/systemd/system/ew1-dashboard.service
sudo systemctl daemon-reload
echo "installed /etc/systemd/system/ew1-dashboard.service (not enabled, not started)"
echo "  start now:        sudo systemctl start ew1-dashboard"
echo "  start at boot:    sudo systemctl enable ew1-dashboard"
echo "  stop (safe-stop): sudo systemctl stop ew1-dashboard"
echo "  logs:             journalctl -u ew1-dashboard -f"
echo "  uninstall:        sudo systemctl disable --now ew1-dashboard; sudo rm /etc/systemd/system/ew1-dashboard.service; sudo systemctl daemon-reload"
