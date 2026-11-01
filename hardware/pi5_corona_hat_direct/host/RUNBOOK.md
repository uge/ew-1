# Pi 5 host runbook — `ew-1.local`

Prepares a Raspberry Pi 5 to host the N-layout-17 corona HV board. Every step
here is done with the **HV board detached**. Nothing in this runbook energizes
the transformer driver or requests a USB-PD contract. Bringing up high voltage
is a separate, supervised bench procedure gated by [AUDIT.md](../AUDIT.md).

Current bench state and stage-by-stage bring-up: [BRINGUP.md](BRINGUP.md).

## 0. Baseline (observed 2026-10-31)

| Item | State on ew-1 |
|---|---|
| Hardware | Raspberry Pi 5 Model B Rev 1.1, 16 GB |
| OS / kernel | Raspberry Pi OS (Debian 13 trixie), `6.18.50+rpt-rpi-2712` |
| Bootloader | 2026-09-25 |
| User `uge` groups | already in `gpio`, `i2c`, `spi`, `dialout` |
| I²C | **disabled**: no `/dev/i2c-*` |
| PWM | **no overlay**: `/sys/class/pwm` empty |
| GPIO | RP1 is `gpiochip0` (54 lines). 5/6 pull up and 18/19/23–26 pull down, all unclaimed |
| Already installed | `gpiod`, `python3-libgpiod` 2.2.1, `python3-smbus2`, `python3-lgpio`, `python3-venv` |
| Missing | `i2c-tools` |

## 1. Host interface (from `layout/schematic-connectivity.json`)

The board takes only **3V3 (J2.1)** and GND from the Pi. J2.2/J2.4 (5 V) are
not connected, and neither are the HAT ID EEPROM pins J2.27/28. HV power comes
in separately on USB-C J3.

| BCM | J2 pin | Net | Dir | Safe state | Notes |
|---|---|---|---|---|---|
| GPIO2 | 3 | SDA | I²C | — | I2C1. Uses the Pi's on-board pull-ups only; the board adds none |
| GPIO3 | 5 | SCL | I²C | — | |
| GPIO18 | 12 | DRV_IN1 | out | **low** | DRV8876 IN1, PWM0 ch2 |
| GPIO19 | 35 | DRV_IN2 | out | **low** | DRV8876 IN2, PWM0 ch3 |
| GPIO24 | 18 | DRV_SLEEP_CMD | out | **low** | Gated by K1 into DRV_nSLEEP. Low also clears the OV latch |
| GPIO25 | 22 | BULK_CMD | out | **low** | Gated by K1 into the U9 eFuse enable. Assert only after the PD contract |
| GPIO23 | 16 | INTERLOCK_OK | in | — | Senses the switched K1 coil feed (lid chain S3–S6) |
| GPIO5 | 29 | DRV_nFAULT | in | high | Open-drain, R63 pull-up |
| GPIO6 | 31 | EFUSE_FLT | in | high | Open-drain, R107 pull-up |
| GPIO26 | 37 | HV_OV_TRIP_GPIO | in | low | High means the hardware 16.96 kV trip has latched |

I²C1 devices: TSL2591 **0x29** (only with the illumination mini board on J50),
HUSB238A **0x42**, ADS1115 **0x48**, BME280 **0x76**. ADS1115 channels:
AIN0 HV_SENSE (≈6.10 kV/V nominal), AIN1 HV return current (100 µA/V),
AIN2 VBUS (×6.556), AIN3 bridge supply (×11). The ADS1115 ALERT, HUSB238A INT_N
and TSL2591 INT pins are not connected, so firmware must poll.

## 2. Update and install packages

```bash
ssh ew-1.local
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y i2c-tools gpiod python3-libgpiod python3-smbus2 python3-venv git
sudo rpi-eeprom-update            # report only. Use -a to apply if one is pending
```

## 3. Boot configuration

Back up the config, then append this block **after the final `[all]`** in
`/boot/firmware/config.txt`:

```bash
sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.pre-ew1
sudo tee -a /boot/firmware/config.txt >/dev/null <<'EOF'

# --- ew-1 corona HV board host interface ---
dtparam=i2c_arm=on
dtparam=i2c_arm_baudrate=100000
# PWM0 ch2/ch3 on GPIO18 (J2.12) / GPIO19 (J2.35) -> DRV8876 IN1/IN2
dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2
# Firmware drives the enables low before Linux starts
gpio=18,19,24,25=op,dl
gpio=23,26=ip,pd
gpio=5,6=ip,pu
EOF
```

`func` uses the legacy BCM2711 numbering, which the Pi 5 pin driver translates
pin by pin. `func=2` (ALT5) maps to RP1 a3, which is PWM0_CHAN2/3. **Do not use
`func=3`**: that is ALT4, which maps to SPI1. On ew-1 it booted GPIO18 as
SPI1_CE0 and drove DRV_IN1 high (found 2026-10-31).

`/dev/i2c-1` also needs the `i2c-dev` module:

```bash
echo i2c-dev | sudo tee /etc/modules-load.d/ew1-i2c.conf
```

The `gpio=` lines fix the pin states from early firmware until a driver or the
control daemon claims each pin. 100 kHz I²C leaves margin for the cable and neck
to the illumination mini board.

## 4. Power-off behaviour

Set the EEPROM so a halt removes the 3V3 rail. With 3V3 gone, K1 drops out and
opens both BULK_EN and DRV_nSLEEP, so a shut-down Pi cannot leave the driver
enabled through a floating GPIO.

```bash
sudo rpi-eeprom-config --edit
#   POWER_OFF_ON_HALT=1
#   WAKE_ON_GPIO=0
```

## 5. Hardware watchdog

If the kernel hangs, the watchdog reboots the Pi, and the pins return to the
§3 defaults.

```bash
sudo mkdir -p /etc/systemd/system.conf.d
sudo tee /etc/systemd/system.conf.d/ew1-watchdog.conf >/dev/null <<'EOF'
[Manager]
RuntimeWatchdogSec=15s
RebootWatchdogSec=2min
EOF
sudo reboot
```

## 6. Verify (board still detached)

```bash
ssh ew-1.local
export PATH=$PATH:/usr/sbin            # i2cdetect lives in /usr/sbin
ls /dev/i2c-1                        # exists
i2cdetect -y 1                       # all "--" with nothing attached
pinctrl get 5,6,18,19,23,24,25,26    # 18/19 = a3 PWM0_CHAN2/3 lo, 24/25 = op dl lo
ls /sys/class/pwm/                   # a pwmchipN with npwm = 4 (RP1 PWM0)
cat /sys/class/pwm/pwmchip*/npwm
wdctl | head -3                      # bcm2835-wdt, timeout 15 s
sudo rpi-eeprom-config | grep -E 'POWER_OFF_ON_HALT|WAKE_ON_GPIO'
```

The `pwmchipN` index changes between kernels. Always find the chip by its
`device` symlink (`…1f00098000.pwm`) and never hard-code the number.

**PWM smoke test.** Do this with the board detached. The `gpio` group can write
the PWM sysfs files, so no sudo is needed. At 1 Hz you can watch the levels with
`pinctrl lev`; use a faster period with a scope on J2.12/J2.35.

```bash
P=$(for c in /sys/class/pwm/pwmchip*; do readlink -f $c/device | grep -q 1f00098000 && echo $c; done)
for c in 2 3; do echo $c > $P/export; done; sleep 0.5
for c in 2 3; do echo 1000000000 > $P/pwm$c/period; echo 500000000 > $P/pwm$c/duty_cycle; done
echo inversed > $P/pwm3/polarity          # only while disabled
echo 1 > $P/pwm2/enable; echo 1 > $P/pwm3/enable
for i in 1 2 3 4 5 6; do echo "$(pinctrl lev 18) $(pinctrl lev 19)"; sleep 0.3; done   # 1 0 / 0 1 alternating
# stop: disable, then restore polarity (an inverted channel idles HIGH while disabled)
echo 0 > $P/pwm2/enable; echo 0 > $P/pwm3/enable; echo normal > $P/pwm3/polarity
for c in 2 3; do echo $c > $P/unexport; done
pinctrl get 18,19                         # both lo
```

Measured on ew-1 (2026-10-31): the outputs are complementary, as expected.
**After `enable=0`, an `inversed` channel holds its pin high** until polarity
returns to `normal`. The control daemon's stop path must do both, and must drop
DRV_SLEEP_CMD (GPIO24) first.

**Output toggle check.** With the board still detached, confirm each enable
moves, then put it back:

```bash
for p in 24 25; do pinctrl set $p op dh; pinctrl get $p; pinctrl set $p op dl; done
```

## 7. Install the self-test

From the repo checkout on your workstation:

```bash
scp hardware/pi5_corona_hat_direct/host/ew1_selftest.py ew-1.local:~/
ssh ew-1.local python3 ~/ew1_selftest.py
```

With the board detached, all four addresses report `absent` and the inputs show
their pull defaults. The script never drives an output.

## 8. First attach of the HV board (logic only, no HV)

1. Shut the Pi down (`sudo poweroff`) and remove its USB-C power.
2. Make sure **J3 (HV USB-C input) is not connected** and the HV output and
   return (J60/J61) are open or terminated to a safe load per the bench plan.
3. Fit the board on the 40-pin header and standoffs, then power the Pi.
4. Run `i2cdetect -y 1`. Expect 0x42, 0x48 and 0x76, plus 0x29 if the
   illumination board is attached. If none appear, check SDA/SCL and 3V3 at J2.1.
5. Run `python3 ~/ew1_selftest.py`. Expected with J3 unplugged:
   - BME280 id 0x60.
   - AIN0–AIN3 ≈ 0 V.
   - GPIO5 and GPIO6 = 1.
   - GPIO26 = 0.
   - GPIO23 = 0 unless all four lid switches S3–S6 are closed.
6. Close the lid chain and confirm that GPIO23 goes to 1. Open any single switch
   and confirm it returns to 0.
7. Stop here. PD negotiation (HUSB238A at 0x42), BULK_CMD, DRV_SLEEP_CMD and PWM
   with VM present belong to the supervised HV bring-up. That procedure requires
   the hardware OV trip characterization and the qualification items still open
   in [AUDIT.md](../AUDIT.md).

## Rollback

```bash
sudo cp /boot/firmware/config.txt.pre-ew1 /boot/firmware/config.txt
sudo rm /etc/systemd/system.conf.d/ew1-watchdog.conf
sudo reboot
```
