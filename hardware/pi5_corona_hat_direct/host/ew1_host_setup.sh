#!/usr/bin/env bash
# Runbook steps 2-5 for the ew-1 Pi 5 host. Idempotent; run as root with the
# HV board detached:  sudo bash ew1_host_setup.sh   (reboots at the end)
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }

echo "== step 2: packages"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get full-upgrade -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  i2c-tools gpiod python3-libgpiod python3-smbus2 python3-venv git
rpi-eeprom-update || true

echo "== step 3: /boot/firmware/config.txt"
CFG=/boot/firmware/config.txt
MARK="# --- ew-1 corona HV board host interface ---"
if grep -qF "$MARK" "$CFG"; then
  echo "block already present"
  # func values are legacy BCM2711 numbers: 2 = ALT5 = PWM0; 3 = ALT4 = SPI1 (wrong)
  sed -i 's/^dtoverlay=pwm-2chan,pin=18,func=3,pin2=19,func2=3$/dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2/' "$CFG"
else
  [ -e "$CFG.pre-ew1" ] || cp "$CFG" "$CFG.pre-ew1"
  cat >>"$CFG" <<EOF

[all]
$MARK
dtparam=i2c_arm=on
dtparam=i2c_arm_baudrate=100000
# PWM0 ch2/ch3 on GPIO18 (J2.12) / GPIO19 (J2.35) -> DRV8876 IN1/IN2
dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2
# Firmware drives the enables low before Linux starts
gpio=18,19,24,25=op,dl
gpio=23,26=ip,pd
gpio=5,6=ip,pu
EOF
fi

# /dev/i2c-1 needs the i2c-dev char-device module
echo i2c-dev >/etc/modules-load.d/ew1-i2c.conf

echo "== step 4: EEPROM POWER_OFF_ON_HALT=1, WAKE_ON_GPIO=0"
TMP=$(mktemp)
rpi-eeprom-config >"$TMP"
[ -e /root/eeprom-config.pre-ew1.txt ] || cp "$TMP" /root/eeprom-config.pre-ew1.txt
set_kv() { if grep -q "^$1=" "$TMP"; then sed -i "s/^$1=.*/$1=$2/" "$TMP"; else echo "$1=$2" >>"$TMP"; fi; }
set_kv POWER_OFF_ON_HALT 1
set_kv WAKE_ON_GPIO 0
if diff -q <(rpi-eeprom-config) "$TMP" >/dev/null; then
  echo "EEPROM already configured"
else
  rpi-eeprom-config --apply "$TMP"
fi

echo "== step 5: systemd hardware watchdog"
mkdir -p /etc/systemd/system.conf.d
cat >/etc/systemd/system.conf.d/ew1-watchdog.conf <<'EOF'
[Manager]
RuntimeWatchdogSec=15s
RebootWatchdogSec=2min
EOF

echo "== done; rebooting in 5 s"
sleep 5
systemctl reboot
