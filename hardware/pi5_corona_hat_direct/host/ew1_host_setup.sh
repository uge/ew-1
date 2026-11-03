#!/usr/bin/env bash
# Runbook steps 2-5 for the ew-1 Pi 5 / Pi Zero 2W host. Idempotent; run as root:
#   sudo bash ew1_host_setup.sh   (reboots at the end)
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }

echo "== step 1b: passwordless sudo for uge (needed by stage7_ramp / dashboard phase sync)"
if [ ! -f /etc/sudoers.d/010_uge-nopasswd ]; then
  echo "uge ALL=(ALL) NOPASSWD: ALL" >/etc/sudoers.d/010_uge-nopasswd
  chmod 0440 /etc/sudoers.d/010_uge-nopasswd
fi

echo "== step 2: packages"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get full-upgrade -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  i2c-tools gpiod python3-libgpiod python3-smbus2 python3-venv git ffmpeg
if command -v rpi-eeprom-update >/dev/null 2>&1; then
  rpi-eeprom-update || true
fi

echo "== step 3: /boot/firmware/config.txt"
CFG=/boot/firmware/config.txt
MARK="# --- ew-1 corona HV board host interface ---"
# Disable onboard PWM audio so snd_bcm2835 cannot conflict with pwm-2chan on Pi Zero 2W
sed -i 's/^dtparam=audio=on$/#dtparam=audio=on/' "$CFG"
if grep -qF "$MARK" "$CFG"; then
  echo "block already present"
  # func values are legacy BCM2711 numbers: 2 = ALT5 = PWM; 3 = ALT4 = SPI1 (wrong)
  sed -i 's/^dtoverlay=pwm-2chan,pin=18,func=3,pin2=19,func2=3$/dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2/' "$CFG"
else
  [ -e "$CFG.pre-ew1" ] || cp "$CFG" "$CFG.pre-ew1"
  cat >>"$CFG" <<EOF

[all]
$MARK
dtparam=audio=off
dtparam=i2c_arm=on
dtparam=i2c_arm_baudrate=100000
# PWM on GPIO18 (J2.12) / GPIO19 (J2.35) -> DRV8876 IN1/IN2 (RP1 ch2/3 on Pi 5; BCM2835 ch0/1 on Zero 2W)
dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2
# Firmware drives the enables low before Linux starts
gpio=18,19,24,25=op,dl
gpio=23,26=ip,pd
gpio=5,6=ip,pu
EOF
fi

# /dev/i2c-1 needs the i2c-dev char-device module
echo i2c-dev >/etc/modules-load.d/ew1-i2c.conf

echo "== step 4: EEPROM POWER_OFF_ON_HALT=1, WAKE_ON_GPIO=0 (Pi 4/5 only)"
if grep -qE "Raspberry Pi [45]" /proc/device-tree/model 2>/dev/null && command -v rpi-eeprom-config >/dev/null 2>&1; then
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
  rm -f "$TMP"
else
  echo "No SPI bootloader EEPROM on this model (e.g. Pi Zero 2W); skipping EEPROM step"
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
