# Pi Zero 2W mixed AP + client setup — `ew-1-zero-2w.local`

Configures a Raspberry Pi Zero 2W (`ew-1-zero-2w.local`) running Raspberry Pi OS (Debian 13 `trixie`) to operate concurrently as:

1. **Wi-Fi station (`wlan0`)**: Client connected to `SophieNet24GHz` (managed by NetworkManager / Netplan).
2. **Open Wi-Fi Access Point (`uap0`)**: Broadcasting SSID `ew-1-zero-2w` on `10.42.0.1/24` with DHCP, DNS, and NAT forwarding to `wlan0`.

---

## 1. Hardware & driver constraints (`brcmfmac` / BCM43430)

The Raspberry Pi Zero 2W uses the Cypress/Broadcom BCM43430 SDIO radio (`brcmfmac43430-sdio`), which advertises the following `nl80211` interface combination limits (`/usr/sbin/iw list`):

```text
valid interface combinations:
  * #{ managed } <= 1, #{ AP } <= 1, #{ P2P-client } <= 1, #{ P2P-device } <= 1,
    total <= 4, #channels <= 1
```

Key operational requirements imposed by the hardware and firmware:

1. **Single station interface (`#{ managed } <= 1`)**: `uap0` must be created with `type __ap` and explicitly marked **unmanaged** in NetworkManager. If NetworkManager attempts to manage `uap0`, `wpa_supplicant` initializes it in `managed` (station) mode, which violates `#{ managed } <= 1` and disrupts `wlan0`.
2. **Single radio channel (`#channels <= 1`)**: Both `wlan0` and `uap0` must operate on the same 2.4 GHz channel. When `wlan0` is associated with `SophieNet24GHz`, `hostapd` on `uap0` must use `wlan0`'s active channel.
3. **Scan before AP beacon startup**: While `uap0` is actively broadcasting beacons on a fixed channel, `brcmfmac` cannot switch channels for `wlan0` to scan and associate. At boot, the setup script waits up to 20 seconds for `wlan0` to associate before creating `uap0` (falling back to channel `11` if `SophieNet24GHz` is out of range so standalone field operation still works).
4. **Non-overlapping subnet**: `SophieNet24GHz` uses `192.168.0.0/21` (`192.168.0.0` – `192.168.7.255`), which overlaps the common `192.168.4.0/24` AP range. `uap0` uses **`10.42.0.1/24`** instead.
5. **Power-save off**: Disabling 802.11 power management on `wlan0` and `uap0` prevents beacon stalls and packet drops in concurrent mode.

---

## 2. Install required packages

`dnsmasq-base` and `nftables` are pre-installed on Raspberry Pi OS `trixie`. Install `hostapd`:

```bash
sudo DEBIAN_FRONTEND=noninteractive apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y hostapd
```

*(Note: Debian masks the stock `/etc/systemd/system/hostapd.service` when no `/etc/hostapd/hostapd.conf` exists; keep it masked so `ew1-ap.service` manages `hostapd` exclusively on `uap0`.)*

---

## 3. Mark `uap0` unmanaged in NetworkManager

Prevent NetworkManager from claiming `uap0` when the virtual interface is created:

```bash
sudo tee /etc/NetworkManager/conf.d/99-unmanaged-uap0.conf >/dev/null <<'EOF'
[keyfile]
unmanaged-devices=interface-name:uap0
EOF

sudo nmcli general reload
```

---

## 4. Create the AP management script

Create `/usr/local/sbin/ew1-ap-setup.sh`:

```bash
sudo tee /usr/local/sbin/ew1-ap-setup.sh >/dev/null <<'EOF'
#!/bin/bash
set -euo pipefail

RUN_DIR=/run/ew1-ap
AP_IF=uap0
STA_IF=wlan0
AP_SSID=ew-1-zero-2w
AP_IP=10.42.0.1
AP_CIDR=10.42.0.1/24
AP_SUBNET=10.42.0.0/24
DEFAULT_CHANNEL=11

get_sta_channel() {
    /usr/sbin/iw dev "${STA_IF}" info 2>/dev/null | awk '/channel / {print $2; exit}' || true
}

stop_ap() {
    if [ -f "${RUN_DIR}/dnsmasq.pid" ]; then
        kill "$(cat "${RUN_DIR}/dnsmasq.pid")" 2>/dev/null || true
        rm -f "${RUN_DIR}/dnsmasq.pid"
    fi
    if [ -f "${RUN_DIR}/hostapd.pid" ]; then
        kill "$(cat "${RUN_DIR}/hostapd.pid")" 2>/dev/null || true
        rm -f "${RUN_DIR}/hostapd.pid"
        sleep 0.3
    fi
    /usr/sbin/nft delete table ip ew1_ap_nat 2>/dev/null || true
    if /usr/sbin/iw dev "${AP_IF}" info >/dev/null 2>&1; then
        ip link set "${AP_IF}" down 2>/dev/null || true
        /usr/sbin/iw dev "${AP_IF}" del 2>/dev/null || true
    fi
}

start_ap() {
    mkdir -p "${RUN_DIR}" /var/lib/misc

    # Wait up to 20s for wlan0 to associate so brcmfmac can scan freely before AP starts
    for _ in $(seq 1 20); do
        CH=$(get_sta_channel)
        if [ -n "${CH}" ]; then
            break
        fi
        sleep 1
    done

    CH=$(get_sta_channel)
    if [ -z "${CH}" ]; then
        CH="${DEFAULT_CHANNEL}"
    fi

    stop_ap

    /usr/sbin/iw dev "${STA_IF}" set power_save off 2>/dev/null || true
    # Keep promisc on wlan0 so brcmfmac ARP offload on uap0 does not drop wlan0 ARP requests
    ip link set "${STA_IF}" promisc on 2>/dev/null || true
    /usr/sbin/iw dev "${STA_IF}" interface add "${AP_IF}" type __ap
    /usr/sbin/iw dev "${AP_IF}" set power_save off 2>/dev/null || true

    ip addr replace "${AP_CIDR}" dev "${AP_IF}"
    ip link set "${AP_IF}" up

    cat > "${RUN_DIR}/hostapd.conf" <<HOSTAPD_EOF
interface=${AP_IF}
driver=nl80211
ssid=${AP_SSID}
hw_mode=g
channel=${CH}
ieee80211n=1
wmm_enabled=1
auth_algs=1
wpa=0
ignore_broadcast_ssid=0
ctrl_interface=${RUN_DIR}/hostapd
HOSTAPD_EOF

    /usr/sbin/hostapd -B -P "${RUN_DIR}/hostapd.pid" "${RUN_DIR}/hostapd.conf"

    /usr/sbin/dnsmasq \
        --conf-file=/dev/null \
        --pid-file="${RUN_DIR}/dnsmasq.pid" \
        --bind-interfaces \
        --interface="${AP_IF}" \
        --except-interface=lo \
        --listen-address="${AP_IP}" \
        --dhcp-range=10.42.0.10,10.42.0.250,255.255.255.0,12h \
        --dhcp-option=option:router,"${AP_IP}" \
        --dhcp-option=option:dns-server,"${AP_IP}" \
        --dhcp-leasefile=/var/lib/misc/ew1-ap-dnsmasq.leases

    sysctl -w net.ipv4.ip_forward=1 >/dev/null
    /usr/sbin/nft -f - <<NFT_EOF
table ip ew1_ap_nat {
    chain postrouting {
        type nat hook postrouting priority srcnat; policy accept;
        ip saddr ${AP_SUBNET} oifname "${STA_IF}" masquerade
    }
    chain forward {
        type filter hook forward priority filter; policy accept;
        iifname "${AP_IF}" oifname "${STA_IF}" accept
        iifname "${STA_IF}" oifname "${AP_IF}" ct state established,related accept
    }
}
NFT_EOF
}

sync_channel() {
    STA_CH=$(get_sta_channel)
    if [ -z "${STA_CH}" ]; then
        exit 0
    fi
    AP_CH=$(/usr/sbin/iw dev "${AP_IF}" info 2>/dev/null | awk '/channel / {print $2; exit}' || true)
    if [ "${STA_CH}" != "${AP_CH}" ] || [ ! -f "${RUN_DIR}/hostapd.pid" ]; then
        systemctl restart ew1-ap.service
    fi
}

case "${1:-}" in
    start)
        start_ap
        ;;
    stop)
        stop_ap
        ;;
    restart)
        start_ap
        ;;
    sync-channel)
        sync_channel
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|sync-channel}" >&2
        exit 1
        ;;
esac
EOF

sudo chmod 755 /usr/local/sbin/ew1-ap-setup.sh
```

---

## 5. Create systemd service & NetworkManager dispatcher hook

Create `/etc/systemd/system/ew1-ap.service` so the AP starts automatically on boot:

```bash
sudo tee /etc/systemd/system/ew1-ap.service >/dev/null <<'EOF'
[Unit]
Description=ew-1-zero-2w Concurrent Wi-Fi Access Point (uap0)
After=NetworkManager.service wpa_supplicant.service network.target
Wants=NetworkManager.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/ew1-ap-setup.sh start
ExecStop=/usr/local/sbin/ew1-ap-setup.sh stop
ExecReload=/usr/local/sbin/ew1-ap-setup.sh restart

[Install]
WantedBy=multi-user.target
EOF
```

Create `/etc/NetworkManager/dispatcher.d/99-ew1-ap` so `uap0` automatically follows `wlan0` if `SophieNet24GHz` changes channels:

```bash
sudo tee /etc/NetworkManager/dispatcher.d/99-ew1-ap >/dev/null <<'EOF'
#!/bin/bash
IFACE="${1:-}"
ACTION="${2:-}"

if [ "${IFACE}" = "wlan0" ] && [ "${ACTION}" = "up" ]; then
    /usr/local/sbin/ew1-ap-setup.sh sync-channel >/dev/null 2>&1 || true
fi
EOF

sudo chmod 755 /etc/NetworkManager/dispatcher.d/99-ew1-ap
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ew1-ap.service
```

---

## 6. Verification

Verify that both interfaces are up on the same channel, `dnsmasq` is serving DHCP/DNS on `10.42.0.1`, and NAT rules are loaded:

```bash
systemctl status ew1-ap.service --no-pager
/usr/sbin/iw dev
ip addr show uap0
sudo ss -tulnp | grep dnsmasq
sudo nft list table ip ew1_ap_nat
```

Expected `/usr/sbin/iw dev` output:

```text
phy#0
	Interface uap0
		ifindex 4
		wdev 0x4
		addr 8a:a2:9e:eb:50:f7
		ssid ew-1-zero-2w
		type AP
		channel 11 (2462 MHz), width: 20 MHz, center1: 2462 MHz
		txpower 31.00 dBm
	Interface wlan0
		ifindex 2
		wdev 0x1
		addr 88:a2:9e:2b:50:f7
		ssid SophieNet24GHz
		type managed
		channel 11 (2462 MHz), width: 20 MHz, center1: 2462 MHz
		txpower 31.00 dBm
```

Clients connecting to the open **`ew-1-zero-2w`** Wi-Fi network receive an IP in `10.42.0.10` – `10.42.0.250` and can reach the Pi via **`10.42.0.1`** or **`ew-1-zero-2w.local`**.

---

## 7. Rollback / disable AP mode

To stop and disable the `ew-1-zero-2w` AP while leaving `wlan0` client connectivity intact:

```bash
sudo systemctl disable --now ew1-ap.service
sudo rm -f /etc/NetworkManager/dispatcher.d/99-ew1-ap \
           /etc/systemd/system/ew1-ap.service \
           /usr/local/sbin/ew1-ap-setup.sh \
           /etc/NetworkManager/conf.d/99-unmanaged-uap0.conf
sudo systemctl daemon-reload
sudo nmcli general reload
```
