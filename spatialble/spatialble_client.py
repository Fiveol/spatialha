"""
spatialble_client - Tkinter GUI for monitoring BLE devices via MQTT.
"""

import json
import math
import os
import random
import time
import tkinter as tk
import tkinter.filedialog
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Tuple
import threading
import urllib.request
import urllib.error

import paho.mqtt.client as mqtt

_has_callback_api = hasattr(mqtt, 'CallbackAPIVersion')
if _has_callback_api:
    from paho.mqtt.client import CallbackAPIVersion

from spatialble_decoders import (
    decode_ibeacon,
    decode_eddystone,
    resolve_irk,
    SERVICE_NAMES,
    GRAPH_COLORS,
)

MQTT_RC_MESSAGES = {
    0: "Connection accepted",
    1: "Connection refused: unacceptable protocol version",
    2: "Connection refused: identifier rejected",
    3: "Connection refused: server unavailable",
    4: "Connection refused: bad user name or password",
    5: "Connection refused: not authorized",
}

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spatialble_config.json")
MQTT_TOPIC = "spatialble"
DEFAULT_CONFIG = {"broker": "localhost", "port": 1883, "username": "", "password": "", "irks": []}


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class ServerInfo:
    def __init__(self, server_id: str):
        self.server_id = server_id
        self.last_heartbeat: Optional[float] = None
        self.last_seen: Optional[float] = None
        self.device_count = 0
        self.ota_ip: Optional[str] = None
        self.ota_port: Optional[int] = None

    @property
    def has_ota(self) -> bool:
        return bool(self.ota_ip and self.ota_port)

    @property
    def is_alive(self) -> bool:
        now = time.time()
        hb_ok = self.last_heartbeat is not None and (now - self.last_heartbeat) < 30
        dev_ok = self.last_seen is not None and (now - self.last_seen) < 30
        return hb_ok or dev_ok

    @property
    def status_text(self) -> str:
        now = time.time()
        if self.is_alive:
            if self.last_heartbeat is not None:
                return f"Alive ({(now - self.last_heartbeat):.0f}s hb)"
            if self.last_seen is not None:
                return f"Alive ({(now - self.last_seen):.0f}s dev)"
            return "Alive"
        if self.last_heartbeat is not None:
            return f"Offline ({(now - self.last_heartbeat):.0f}s ago)"
        if self.last_seen is not None:
            return f"Offline ({(now - self.last_seen):.0f}s ago)"
        return "Waiting..."


class BLEDeviceInfo:
    def __init__(self, address: str):
        self.address = address
        self.name = ""
        self.rssi = -100
        self.manufacturer_data: Dict[str, str] = {}
        self.service_uuids: List[str] = []
        self.service_data: Dict[str, str] = {}
        self.tx_power: Optional[int] = None
        self.seen_by: Dict[str, float] = {}
        self.last_seen: Optional[float] = None
        self.first_seen: float = time.time()
        self.rssi_history: Dict[str, List[Tuple[float, int]]] = {}
        self._prev_timestamp: Optional[float] = None
        self._intervals: List[float] = []
        self.ibeacon: Optional[dict] = None
        self.eddystone: Optional[dict] = None

    def update(self, server_id: str, rssi: int, name: str,
               manufacturer_data: dict, service_uuids: list,
               service_data: dict, tx_power: Optional[int], timestamp: float):
        self.rssi = rssi
        if name:
            self.name = name
        self.manufacturer_data = manufacturer_data
        self.service_uuids = service_uuids
        self.service_data = service_data
        if tx_power is not None:
            self.tx_power = tx_power
        self.seen_by[server_id] = timestamp
        self.last_seen = timestamp

        if server_id not in self.rssi_history:
            self.rssi_history[server_id] = []
        self.rssi_history[server_id].append((timestamp, rssi))
        if len(self.rssi_history[server_id]) > 500:
            self.rssi_history[server_id] = self.rssi_history[server_id][-500:]

        if self._prev_timestamp is not None:
            delta = timestamp - self._prev_timestamp
            if 0.01 < delta < 600:
                self._intervals.append(delta)
                if len(self._intervals) > 100:
                    self._intervals = self._intervals[-100:]
        self._prev_timestamp = timestamp

        if not self.ibeacon:
            self.ibeacon = decode_ibeacon(manufacturer_data)
        if not self.eddystone:
            self.eddystone = decode_eddystone(service_data)

    @property
    def avg_rssi(self) -> Optional[float]:
        vals = [r for h in self.rssi_history.values() for _, r in h]
        if not vals:
            return None
        return sum(vals) / len(vals)

    @property
    def avg_broadcast_interval(self) -> Optional[float]:
        if not self._intervals:
            return None
        return sum(self._intervals) / len(self._intervals)

    @property
    def seen_by_str(self) -> str:
        return ", ".join(sorted(self.seen_by.keys()))

    @property
    def beacon_type(self) -> str:
        if self.ibeacon:
            return "iBeacon"
        if self.eddystone:
            return self.eddystone.get("type", "").replace("_", " ").title()
        return ""


class DeviceGroup:
    """Group of MACs sharing the same device name (rotating MAC)."""

    def __init__(self, name: str, first_mac: str, device: BLEDeviceInfo):
        self.name = name
        self.macs: List[str] = [first_mac]
        self.devices: Dict[str, BLEDeviceInfo] = {first_mac: device}
        self.first_seen: float = device.first_seen
        self.last_seen: float = device.last_seen

    def add_mac(self, mac: str, device: BLEDeviceInfo):
        if mac not in self.macs:
            self.macs.append(mac)
        self.devices[mac] = device
        if device.last_seen and device.last_seen > self.last_seen:
            self.last_seen = device.last_seen

    @property
    def all_macs_str(self) -> str:
        if len(self.macs) == 1:
            return self.macs[0]
        return f"{self.macs[0]} (+{len(self.macs) - 1} more)"

    @property
    def latest_rssi(self) -> int:
        best = -100
        for d in self.devices.values():
            if d.rssi > best:
                best = d.rssi
        return best

    @property
    def avg_rssi(self) -> Optional[float]:
        vals = []
        for d in self.devices.values():
            for h in d.rssi_history.values():
                vals.extend(r for _, r in h)
        if not vals:
            return None
        return sum(vals) / len(vals)

    @property
    def seen_by(self) -> Dict[str, float]:
        combined = {}
        for d in self.devices.values():
            for sid, ts in d.seen_by.items():
                if sid not in combined or ts > combined[sid]:
                    combined[sid] = ts
        return combined

    @property
    def seen_by_str(self) -> str:
        return ", ".join(sorted(self.seen_by.keys()))

    @property
    def beacon_type(self) -> str:
        for d in self.devices.values():
            if d.ibeacon:
                return "iBeacon"
            if d.eddystone:
                return d.eddystone.get("type", "").replace("_", " ").title()
        return ""

    @property
    def rssi_to_server(self) -> Dict[str, int]:
        """Latest RSSI per server across all MACs."""
        result = {}
        for d in self.devices.values():
            for sid, hist in d.rssi_history.items():
                if hist:
                    rssi = hist[-1][1]
                    if sid not in result or rssi > result[sid]:
                        result[sid] = rssi
        return result

    def latest_device(self) -> Optional[BLEDeviceInfo]:
        best = None
        best_ts = 0
        for d in self.devices.values():
            ts = d.last_seen or 0
            if ts > best_ts:
                best_ts = ts
                best = d
        return best


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class SpatialBLEClient:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SpatialBLE Client")
        self.root.geometry("1100x800")

        self.config = load_config()
        self.servers: Dict[str, ServerInfo] = {}
        self.devices: Dict[str, BLEDeviceInfo] = {}
        self.device_groups: Dict[str, DeviceGroup] = {}  # name.lower() -> group
        self.mqtt_client: Optional[mqtt.Client] = None
        self.mqtt_thread: Optional[threading.Thread] = None
        self._connected = False
        self._selected_group: Optional[str] = None
        self._map_angle = 0.0

        self._setup_ui()
        self._connect_mqtt()
        self._start_periodic_update()

    # --- MQTT ---

    def _connect_mqtt(self):
        self._disconnect_mqtt()
        kwargs = dict()
        if _has_callback_api:
            kwargs['callback_api_version'] = CallbackAPIVersion.VERSION1
        client = mqtt.Client(**kwargs)
        client.on_message = self._on_message
        client.on_connect = self._on_mqtt_connect
        client.on_disconnect = self._on_mqtt_disconnect
        client.reconnect_delay_set(max_delay=30)
        u = self.config.get("username", "")
        p = self.config.get("password", "")
        if u:
            client.username_pw_set(u, p)
        try:
            client.connect(self.config["broker"], int(self.config["port"]), keepalive=60)
        except Exception as e:
            self._log(f"Connection failed: {e}")
            self._update_connection_status(False)
            return
        client.subscribe(f"{MQTT_TOPIC}/+")
        t = threading.Thread(target=client.loop_forever, daemon=True)
        t.start()
        self.mqtt_client = client
        self.mqtt_thread = t

    def _disconnect_mqtt(self):
        if self.mqtt_client:
            try:
                self.mqtt_client.disconnect()
                self.mqtt_client.loop_stop()
            except Exception:
                pass
            self.mqtt_client = None
            self.mqtt_thread = None
        self._connected = False
        self._update_connection_status(False)

    def _restart_mqtt(self):
        save_config(self.config)
        self.servers.clear()
        self.devices.clear()
        self.device_groups.clear()
        self._connect_mqtt()

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        ok = rc == 0
        self._connected = ok
        self.root.after(0, self._update_connection_status, ok)
        msg = MQTT_RC_MESSAGES.get(rc, f"Unknown code {rc}")
        if ok:
            self._log(f"Connected to {self.config['broker']}:{self.config['port']}")
        else:
            self._log(msg)

    def _on_mqtt_disconnect(self, client, userdata, rc):
        self._connected = False
        self.root.after(0, self._update_connection_status, False)

    def _update_connection_status(self, connected: bool):
        if hasattr(self, "conn_status_label"):
            c = "#2e7d32" if connected else "#c62828"
            t = "Connected" if connected else "Disconnected"
            self.conn_status_label.config(text=t, foreground=c)

    def _on_message(self, client, userdata, msg):
        try:
            p = json.loads(msg.payload)
        except json.JSONDecodeError:
            return
        if p.get("type") == "heartbeat":
            self._handle_heartbeat(p)
        elif p.get("type") == "advertisement":
            self._handle_advertisement(p)

    def _resolve_address(self, address: str) -> str:
        for irk in self.config.get("irks", []):
            r = resolve_irk(address, irk)
            if r:
                return r
        return address

    def _handle_heartbeat(self, payload: dict):
        sid = payload["server_id"]
        ts = payload.get("timestamp", time.time())
        if sid not in self.servers:
            self.servers[sid] = ServerInfo(sid)
        info = self.servers[sid]
        info.last_heartbeat = ts
        info.last_seen = time.time()
        info.ota_ip = payload.get("ota_ip")
        info.ota_port = payload.get("ota_port")

    def _handle_advertisement(self, payload: dict):
        sid = payload["server_id"]
        dd = payload["device"]
        addr = self._resolve_address(dd["address"])
        ts = payload.get("timestamp", time.time())
        name = dd.get("name", "")
        if sid not in self.servers:
            self.servers[sid] = ServerInfo(sid)

        # Create/update device
        if addr not in self.devices:
            self.devices[addr] = BLEDeviceInfo(addr)
        dev = self.devices[addr]
        dev.update(sid, dd["rssi"], name, dd.get("manufacturer_data", {}),
                   dd.get("service_uuids", []), dd.get("service_data", {}),
                   dd.get("tx_power"), ts)

        # Group by name for rotating MACs
        if name:
            key = name.lower()
            if key not in self.device_groups:
                self.device_groups[key] = DeviceGroup(name, addr, dev)
            else:
                self.device_groups[key].add_mac(addr, dev)
        else:
            # unnamed device — identify by first seen address
            key = f"__unnamed__{addr}"
            self.device_groups[key] = DeviceGroup("", addr, dev)

        # Update server device count
        seen = set()
        for d in self.devices.values():
            if sid in d.seen_by:
                seen.add(d.address)
        self.servers[sid].device_count = len(seen)

    # --- UI Setup ---

    def _setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.servers_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.servers_frame, text="Servers")
        self._setup_servers_tab()

        self.devices_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.devices_frame, text="BLE Devices")
        self._setup_devices_tab()

        self.map_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.map_frame, text="Network Map")
        self._setup_map_tab()

        self.ota_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ota_frame, text="OTA")
        self._setup_ota_tab()

        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Configuration")
        self._setup_config_tab()

    # --- Servers Tab ---

    def _setup_servers_tab(self):
        cols = ("Server ID", "Status", "Devices Seen", "Last Seen")
        self.servers_tree = ttk.Treeview(self.servers_frame, columns=cols, show="headings")
        for c in cols:
            self.servers_tree.heading(c, text=c)
            self.servers_tree.column(c, width=200)
        self.servers_tree.pack(fill=tk.BOTH, expand=True)

    # --- BLE Devices Tab ---

    def _setup_devices_tab(self):
        paned = ttk.PanedWindow(self.devices_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(paned)
        paned.add(top, weight=3)

        cols = ("Name / Address", "Avg RSSI", "RSSI", "Beacon Type",
                "Broadcast Int.", "Seen By")
        self.devices_tree = ttk.Treeview(top, columns=cols, show="headings")
        cw = [250, 75, 60, 100, 90, 200]
        for c, w in zip(cols, cw):
            self.devices_tree.heading(c, text=c)
            self.devices_tree.column(c, width=w, minwidth=50)
        self.devices_tree.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        self.devices_tree.bind("<<TreeviewSelect>>", self._on_device_select)

        sf = ttk.Frame(top)
        sf.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(sf, text="Filter:").pack(side=tk.LEFT, padx=(0, 4))
        self.device_filter = tk.StringVar()
        self.device_filter.trace("w", lambda *a: self._update_ui())
        ttk.Entry(sf, textvariable=self.device_filter).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.detail_frame = ttk.LabelFrame(paned, text="Device Detail", padding=5)
        paned.add(self.detail_frame, weight=2)
        self._setup_detail_pane()

    def _setup_detail_pane(self):
        cols = ttk.Frame(self.detail_frame)
        cols.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(cols)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.info_frame = ttk.LabelFrame(left, text="Info", padding=5)
        self.info_frame.pack(fill=tk.X, pady=(0, 4))
        self.info_labels = {}
        for i, k in enumerate(["Name", "Addresses", "First Seen", "Last Seen",
                                "TX Power", "Avg RSSI", "Broadcast Int.", "Beacon Type"]):
            lbl = ttk.Label(self.info_frame, text=f"{k}: —", anchor=tk.W)
            lbl.grid(row=i, column=0, sticky=tk.W, padx=2)
            self.info_labels[k] = lbl

        srvf = ttk.LabelFrame(left, text="Per Server", padding=2)
        srvf.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        sc = ("Server", "RSSI", "Last Seen", "Samples")
        self.server_detail_tree = ttk.Treeview(srvf, columns=sc, show="headings", height=4)
        for c, w in zip(sc, [150, 60, 140, 70]):
            self.server_detail_tree.heading(c, text=c)
            self.server_detail_tree.column(c, width=w)

        svcf = ttk.LabelFrame(left, text="Service UUIDs", padding=2)
        svcf.pack(fill=tk.X)
        self.svc_listbox = tk.Listbox(svcf, height=3, state=tk.DISABLED)
        ss = ttk.Scrollbar(svcf, orient=tk.VERTICAL, command=self.svc_listbox.yview)
        self.svc_listbox.configure(yscrollcommand=ss.set)
        self.svc_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ss.pack(side=tk.RIGHT, fill=tk.Y)

        right = ttk.Frame(cols)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.beacon_frame = ttk.LabelFrame(right, text="Beacon", padding=5)
        self.beacon_frame.pack(fill=tk.X, pady=(0, 4))
        self.beacon_labels = {}
        for i, k in enumerate(["Type", "UUID", "Major", "Minor", "Namespace",
                                "Instance", "URL", "TX Power (1m)", "Battery", "Temp"]):
            lbl = ttk.Label(self.beacon_frame, text=f"{k}: —", anchor=tk.W)
            lbl.grid(row=i, column=0, sticky=tk.W, padx=2)
            self.beacon_labels[k] = lbl

        mfrf = ttk.LabelFrame(right, text="Manufacturer Data", padding=2)
        mfrf.pack(fill=tk.X, pady=(0, 4))
        self.mfr_text = tk.Text(mfrf, height=3, state=tk.DISABLED)
        self.mfr_text.pack(fill=tk.X)

        gfx = ttk.LabelFrame(right, text="RSSI Graph (last 5 min)", padding=2)
        gfx.pack(fill=tk.BOTH, expand=True)
        self.graph_canvas = tk.Canvas(gfx, bg="#1e1e1e", height=150)
        self.graph_canvas.pack(fill=tk.BOTH, expand=True)

    def _on_device_select(self, event=None):
        sel = self.devices_tree.selection()
        if not sel:
            return
        self._selected_group = self.devices_tree.item(sel[0])["values"][0]
        self._update_detail_pane()

    def _update_detail_pane(self):
        if not self._selected_group or self._selected_group not in self.device_groups:
            for k in self.info_labels:
                self.info_labels[k].config(text=f"{k}: —")
            for k in self.beacon_labels:
                self.beacon_labels[k].config(text=f"{k}: —")
            self.mfr_text.config(state=tk.NORMAL)
            self.mfr_text.delete("1.0", tk.END)
            self.mfr_text.config(state=tk.DISABLED)
            self.svc_listbox.config(state=tk.NORMAL)
            self.svc_listbox.delete(0, tk.END)
            self.svc_listbox.config(state=tk.DISABLED)
            for c in self.server_detail_tree.get_children():
                self.server_detail_tree.delete(c)
            self.graph_canvas.delete("all")
            return

        grp = self.device_groups[self._selected_group]
        dev = grp.latest_device()
        if not dev:
            return

        def _ts(ts):
            return time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "—"

        self.info_labels["Name"].config(text=f"Name: {grp.name or '—'}")
        self.info_labels["Addresses"].config(text=f"Addresses: {grp.all_macs_str}")
        self.info_labels["First Seen"].config(text=f"First Seen: {_ts(grp.first_seen)}")
        self.info_labels["Last Seen"].config(text=f"Last Seen: {_ts(grp.last_seen)}")
        tp = dev.tx_power
        self.info_labels["TX Power"].config(text=f"TX Power: {tp} dBm" if tp is not None else "TX Power: —")
        avg = grp.avg_rssi
        self.info_labels["Avg RSSI"].config(text=f"Avg RSSI: {avg:.1f} dBm" if avg is not None else "Avg RSSI: —")
        bi = dev.avg_broadcast_interval
        self.info_labels["Broadcast Int."].config(text=f"Broadcast Int.: {bi:.2f}s" if bi else "Broadcast Int.: —")
        self.info_labels["Beacon Type"].config(text=f"Beacon Type: {grp.beacon_type or '—'}")

        for c in self.server_detail_tree.get_children():
            self.server_detail_tree.delete(c)
        rssi_map = grp.rssi_to_server
        for sid in sorted(self.servers.keys()):
            r = rssi_map.get(sid, "—")
            ts = grp.seen_by.get(sid)
            samples = len(dev.rssi_history.get(sid, [])) if sid in dev.rssi_history else 0
            self.server_detail_tree.insert("", tk.END, values=(sid, r, _ts(ts) if ts else "—", samples))

        self.svc_listbox.config(state=tk.NORMAL)
        self.svc_listbox.delete(0, tk.END)
        for u in dev.service_uuids:
            n = SERVICE_NAMES.get(u.lower(), "")
            self.svc_listbox.insert(tk.END, f"{u}  ({n})" if n else u)
        if not dev.service_uuids:
            self.svc_listbox.insert(tk.END, "(none)")
        self.svc_listbox.config(state=tk.DISABLED)

        for k in self.beacon_labels:
            self.beacon_labels[k].config(text=f"{k}: —")
        if dev.ibeacon:
            ib = dev.ibeacon
            self.beacon_labels["Type"].config(text="Type: iBeacon")
            self.beacon_labels["UUID"].config(text=f"UUID: {ib.get('uuid', '—')}")
            self.beacon_labels["Major"].config(text=f"Major: {ib.get('major', '—')}")
            self.beacon_labels["Minor"].config(text=f"Minor: {ib.get('minor', '—')}")
            self.beacon_labels["TX Power (1m)"].config(text=f"TX Power (1m): {ib.get('tx_power', '—')} dBm")
        elif dev.eddystone:
            ed = dev.eddystone
            t = ed.get("type", "")
            self.beacon_labels["Type"].config(text=f"Type: {t}")
            if t == "eddystone_uid":
                self.beacon_labels["Namespace"].config(text=f"Namespace: {ed.get('namespace', '—')}")
                self.beacon_labels["Instance"].config(text=f"Instance: {ed.get('instance', '—')}")
            elif t == "eddystone_url":
                self.beacon_labels["URL"].config(text=f"URL: {ed.get('url', '—')}")
            elif t == "eddystone_tlm":
                self.beacon_labels["Battery"].config(text=f"Battery: {ed.get('battery_mv', '—')} mV")
                self.beacon_labels["Temp"].config(text=f"Temp: {ed.get('temp_c', '—')} °C")

        self.mfr_text.config(state=tk.NORMAL)
        self.mfr_text.delete("1.0", tk.END)
        if dev.manufacturer_data:
            for mid, data in sorted(dev.manufacturer_data.items()):
                self.mfr_text.insert(tk.END, f"0x{mid}: {data}\n")
        else:
            self.mfr_text.insert(tk.END, "(none)")
        self.mfr_text.config(state=tk.DISABLED)
        self._draw_rssi_graph(dev)

    def _draw_rssi_graph(self, dev: BLEDeviceInfo):
        c = self.graph_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 50 or h < 50:
            c.create_text(80, 20, text="(waiting for graph area)", fill="#888", anchor=tk.NW, font=("", 8))
            return
        ml, mr, mt, mb = 40, 10, 15, 25
        gw, gh = w - ml - mr, h - mt - mb
        if gw < 20 or gh < 20:
            return

        now = time.time()
        cutoff = now - 300
        all_pts = []
        sdata = []
        for sid in sorted(dev.rssi_history.keys()):
            pts = [(t, r) for t, r in dev.rssi_history[sid] if t >= cutoff]
            if pts:
                sdata.append((sid, pts, GRAPH_COLORS[len(sdata) % len(GRAPH_COLORS)]))
                all_pts.extend(pts)

        if not all_pts:
            c.create_text(ml + gw // 2, mt + gh // 2, text="No recent RSSI data", fill="#888", font=("", 9))
            return

        min_t = min(t for t, _ in all_pts)
        max_t = max(t for t, _ in all_pts)
        if max_t - min_t < 1:
            max_t = min_t + 60
        min_r = min(r for _, r in all_pts) - 5
        max_r = max(0, max(r for _, r in all_pts) + 5)
        if max_r - min_r < 20:
            max_r = min_r + 20

        def tx(t): return ml + (t - min_t) / (max_t - min_t) * gw
        def ty(r): return mt + (max_r - r) / (max_r - min_r) * gh

        for r in range(int(min_r / 10) * 10, int(max_r / 10) * 10 + 1, 10):
            if r < min_r or r > max_r:
                continue
            y = ty(r)
            c.create_line(ml, y, ml + gw, y, fill="#333", width=1)
            c.create_text(ml - 4, y, text=str(r), fill="#aaa", anchor=tk.E, font=("", 7))

        for offset in range(0, 300, 60):
            t = min_t + offset
            if t > max_t:
                break
            x = tx(t)
            c.create_line(x, mt, x, mt + gh, fill="#333", width=1)
            label = f"-{int(max_t - t)}s" if max_t - t > 0 else "now"
            c.create_text(x, mt + gh + 12, text=label, fill="#aaa", font=("", 7))

        for sid, pts, color in sdata:
            pts.sort()
            coords = []
            for t, r in pts:
                coords.append(tx(t))
                coords.append(ty(r))
            if len(coords) >= 4:
                c.create_line(*coords, fill=color, width=2, smooth=True)
            lp = pts[-1]
            cx, cy = tx(lp[0]), ty(lp[1])
            c.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=color, outline="")
            xl = cx + 5
            yl = cy - 6
            if xl + 50 > w:
                xl = cx - 55
            c.create_text(xl, yl, text=sid, fill=color, anchor=tk.W, font=("", 7))

    # --- Network Map Tab (3D Orbital) ---

    def _setup_map_tab(self):
        self._map_azimuth = 0.0
        self._map_elevation = math.radians(55)
        self._map_orbit_dist = 420.0
        self._map_dragging = False
        self._map_drag_start = None
        self._map_tooltip = None
        self._map_last_dev_pos = {}
        self._map_dev_alpha = {}
        self._map_prev_devs = set()
        self._map_search_text = ""
        self._map_show_unnamed = True

        # Toolbar
        self.map_toolbar = ttk.Frame(self.map_frame)
        self.map_toolbar.pack(fill=tk.X, padx=4, pady=2)

        ttk.Label(self.map_toolbar, text="Search:").pack(side=tk.LEFT, padx=(0, 4))
        self.map_search_var = tk.StringVar()
        self.map_search_var.trace_add("write", lambda *_: self._on_map_filter())
        self.map_search_entry = ttk.Entry(self.map_toolbar, textvariable=self.map_search_var, width=20)
        self.map_search_entry.pack(side=tk.LEFT, padx=(0, 10))

        self._map_show_unnamed_var = tk.BooleanVar(value=True)
        cb = ttk.Checkbutton(self.map_toolbar, text="Show unnamed",
                             variable=self._map_show_unnamed_var,
                             command=self._on_map_filter)
        cb.pack(side=tk.LEFT, padx=4)

        ttk.Separator(self.map_toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=6, fill=tk.Y)
        self._map_frozen = False
        self.map_freeze_btn = ttk.Button(self.map_toolbar, text="❄ Freeze",
                                         command=self._toggle_map_freeze, width=8)
        self.map_freeze_btn.pack(side=tk.LEFT, padx=4)

        # Canvas
        self.map_canvas = tk.Canvas(self.map_frame, bg="#0f0f23", highlightthickness=0)
        self.map_canvas.pack(fill=tk.BOTH, expand=True)

        self.map_canvas.bind("<MouseWheel>", self._on_map_zoom)
        self.map_canvas.bind("<Button-4>", self._on_map_zoom)
        self.map_canvas.bind("<Button-5>", self._on_map_zoom)
        self.map_canvas.bind("<ButtonPress-1>", self._on_map_mouse_down)
        self.map_canvas.bind("<B1-Motion>", self._on_map_mouse_move)
        self.map_canvas.bind("<ButtonRelease-1>", self._on_map_mouse_up)
        self.map_canvas.bind("<Motion>", self._on_map_motion)

        self._map_angle = 0
        self._animate_map()

    def _on_map_filter(self):
        self._map_search_text = self.map_search_var.get().strip().lower()
        self._map_show_unnamed = self._map_show_unnamed_var.get()

    def _toggle_map_freeze(self):
        self._map_frozen = not self._map_frozen
        self.map_freeze_btn.config(text="▶ Live" if self._map_frozen else "❄ Freeze")

    def _on_map_zoom(self, event):
        if event.num == 5 or event.delta < 0:
            self._map_orbit_dist = min(2000, self._map_orbit_dist * 1.15)
        else:
            self._map_orbit_dist = max(80, self._map_orbit_dist / 1.15)

    def _on_map_mouse_down(self, event):
        self._map_dragging = True
        self._map_drag_start = (event.x, event.y)

    def _on_map_mouse_move(self, event):
        if not self._map_dragging or self._map_drag_start is None:
            return
        dx = event.x - self._map_drag_start[0]
        dy = event.y - self._map_drag_start[1]
        self._map_azimuth -= dx * 0.008
        self._map_elevation -= dy * 0.008
        self._map_elevation = max(math.radians(5), min(math.radians(85), self._map_elevation))
        self._map_drag_start = (event.x, event.y)

    def _on_map_mouse_up(self, event):
        self._map_dragging = False
        self._map_drag_start = None

    def _animate_map(self):
        if hasattr(self, "map_canvas") and self.map_canvas.winfo_exists():
            self._draw_3d_map()
        self.root.after(16, self._animate_map)

    # ------------------------------------------------------------------
    # 3D projection
    # ------------------------------------------------------------------
    def _project(self, wx, wy, wz, w, h):
        """Project 3D world point to 2D. Returns (sx, sy, depth) or None."""
        az, el, dist = self._map_azimuth, self._map_elevation, self._map_orbit_dist

        cx = dist * math.sin(el) * math.sin(az)
        cy = dist * math.cos(el)
        cz = dist * math.sin(el) * math.cos(az)

        vx, vy, vz = wx - cx, wy - cy, wz - cz

        fl = math.hypot(cx, cy, cz)
        if fl < 0.001:
            return None
        fx, fy, fz = -cx / fl, -cy / fl, -cz / fl

        world_up = (0, 1, 0)
        rx = fy * world_up[2] - fz * world_up[1]
        ry = fz * world_up[0] - fx * world_up[2]
        rz = fx * world_up[1] - fy * world_up[0]
        rl = math.hypot(rx, ry, rz)
        if rl < 0.001:
            world_up = (0, 0, -1)
            rx = fy * world_up[2] - fz * world_up[1]
            ry = fz * world_up[0] - fx * world_up[2]
            rz = fx * world_up[1] - fy * world_up[0]
            rl = math.hypot(rx, ry, rz)
        rx, ry, rz = rx / rl, ry / rl, rz / rl

        ux = ry * fz - rz * fy
        uy = rz * fx - rx * fz
        uz = rx * fy - ry * fx

        screen_x = vx * rx + vy * ry + vz * rz
        screen_y = vx * ux + vy * uy + vz * uz
        depth = vx * fx + vy * fy + vz * fz

        if depth < 5:
            return None

        focal = max(w, h) * 0.55
        scale = focal / depth
        sx = w // 2 + screen_x * scale
        sy = h // 2 - screen_y * scale
        return sx, sy, depth

    @staticmethod
    def _darken(hex_color, amount):
        c = hex_color.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return f"#{int(r*(1-amount)):02x}{int(g*(1-amount)):02x}{int(b*(1-amount)):02x}"

    # ------------------------------------------------------------------
    # 3D map drawing
    # ------------------------------------------------------------------
    def _draw_3d_map(self):
        frozen = getattr(self, '_map_frozen', False)
        c = self.map_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 100 or h < 100:
            return

        objects = []
        self._map_last_dev_pos.clear()

        def emit(depth, priority, func):
            objects.append((depth, priority, func))

        if not frozen:
            # ---- COMPUTE: server positions ----
            alive = {sid: info for sid, info in self.servers.items() if info.is_alive and info.device_count > 0}
            if not alive:
                c.create_text(w // 2, h // 2, text="No servers online", fill="#555", font=("", 14))
                return
            sorted_sv = sorted(alive.keys())
            poly_radius = 80
            n = len(alive)
            sv_3d = {}
            for i, sid in enumerate(sorted_sv):
                a = 2 * math.pi * i / n - math.pi / 2 + self._map_angle
                sv_3d[sid] = (poly_radius * math.cos(a), 0, poly_radius * math.sin(a))

            # ---- COMPUTE: filtered device groups ----
            search = getattr(self, '_map_search_text', '')
            show_unnamed = getattr(self, '_map_show_unnamed', True)
            map_groups = {}
            for gkey, grp in self.device_groups.items():
                if not any(s in grp.rssi_to_server for s in alive):
                    continue
                if not show_unnamed and not grp.name:
                    continue
                if search and search not in (grp.name or gkey).lower():
                    continue
                map_groups[gkey] = grp
            if not map_groups and not any(k in self._map_dev_alpha for k in self.device_groups):
                return

            # ---- COMPUTE: fade animation ----
            current_devs = set(map_groups.keys())
            for gkey, alpha in list(self._map_dev_alpha.items()):
                if gkey in current_devs:
                    self._map_dev_alpha[gkey] = min(1.0, alpha + 0.06)
                elif gkey in self.device_groups:
                    map_groups[gkey] = self.device_groups[gkey]
                    self._map_dev_alpha[gkey] = alpha - 0.04
                    if self._map_dev_alpha[gkey] <= 0.02:
                        del self._map_dev_alpha[gkey]
                        map_groups.pop(gkey, None)
                else:
                    self._map_dev_alpha[gkey] = alpha - 0.04
                    if self._map_dev_alpha[gkey] <= 0.02:
                        del self._map_dev_alpha[gkey]
            for gkey in current_devs - set(self._map_dev_alpha.keys()):
                self._map_dev_alpha[gkey] = 0.0

            # ---- COMPUTE: device positions by connectivity ----
            # 1 server  → outside polygon, radial from server
            # 2 servers → RSSI-weighted line between them, pushed outward
            # 3+ servers → weighted centroid inside polygon
            dev_3d = {}
            conn_groups = {}
            for gkey, grp in map_groups.items():
                seen_by = [(sid, grp.rssi_to_server[sid]) for sid in sorted_sv if sid in grp.rssi_to_server]
                n = len(seen_by)
                if n == 1:
                    ck = ('1', seen_by[0][0])
                elif n == 2:
                    seen_by.sort(key=lambda x: x[0])
                    ck = ('2', seen_by[0][0], seen_by[1][0])
                else:
                    ck = ('3+',)
                conn_groups.setdefault(ck, []).append((gkey, grp, seen_by))

            for ck, items in conn_groups.items():
                tier = ck[0]
                for idx, (gkey, grp, seen_by) in enumerate(items):
                    n_conn = len(seen_by)
                    avg_rssi = grp.avg_rssi or -95
                    rssi_r = max(20, min(140, (127 - abs(avg_rssi)) * 5))
                    rssi_y = max(2, min(22, (95 - abs(avg_rssi)) * 0.25))
                    if n_conn == 1:
                        sid, _ = seen_by[0]
                        sx, _, sz = sv_3d[sid]
                        base_angle = math.atan2(sz, sx)
                        n_in = len(items)
                        if n_in > 1:
                            spread = math.radians(60)
                            angle = base_angle + spread * (idx / (n_in - 1) - 0.5)
                        else:
                            angle = base_angle
                        dist = poly_radius + rssi_r
                        dx = math.cos(angle) * dist
                        dz = math.sin(angle) * dist
                        dy = rssi_y
                    elif n_conn == 2:
                        (s0, r0), (s1, r1) = seen_by
                        ax, _, az = sv_3d[s0]
                        bx, _, bz = sv_3d[s1]
                        w0 = abs(r0) + 10
                        w1 = abs(r1) + 10
                        t = w1 / (w0 + w1)
                        lx = ax + (bx - ax) * t
                        lz = az + (bz - az) * t
                        dl = math.hypot(lx, lz)
                        if dl < 1:
                            lx, lz = 0, -1
                            dl = 1
                        dx = lx + (lx / dl) * rssi_r * 0.6
                        dz = lz + (lz / dl) * rssi_r * 0.6
                        dy = rssi_y
                    else:  # n_conn >= 3
                        tw, xa, za = 0.0, 0.0, 0.0
                        for sid, rssi in seen_by:
                            sx2, _, sz2 = sv_3d[sid]
                            wgt = max(1.0, abs(rssi) + 10)
                            tw += wgt
                            xa += sx2 * wgt
                            za += sz2 * wgt
                        dx = xa / tw if tw > 0 else 0
                        dz = za / tw if tw > 0 else 0
                        dy = rssi_y
                    dev_3d[gkey] = (dx, dy, dz)
            keys = sorted(dev_3d.keys())

            # ---- COMPUTE: smooth position interpolation ----
            if not hasattr(self, '_map_dev_smooth'):
                self._map_dev_smooth = {}
            smooth = self._map_dev_smooth
            for gkey in keys:
                target = dev_3d[gkey]
                if gkey not in smooth:
                    smooth[gkey] = target
                else:
                    cur = smooth[gkey]
                    smooth[gkey] = (cur[0] + (target[0] - cur[0]) * 0.12,
                                    cur[1] + (target[1] - cur[1]) * 0.12,
                                    cur[2] + (target[2] - cur[2]) * 0.12)
            for gkey in keys:
                dev_3d[gkey] = smooth[gkey]
            for gkey in list(smooth.keys()):
                if gkey not in keys and gkey not in self._map_dev_alpha:
                    del smooth[gkey]

            # ---- Cache for frozen mode ----
            self._map_cache = {
                'alive': alive, 'sorted_sv': sorted_sv, 'poly_radius': poly_radius,
                'sv_3d': dict(sv_3d), 'map_groups_items': list(map_groups.items()),
                'dev_3d': dict(dev_3d), 'keys': list(keys),
                'map_dev_alpha': dict(self._map_dev_alpha),
                'map_last_dev_pos': dict(self._map_last_dev_pos),
            }
        else:
            # ---- FROZEN: restore from cache ----
            if not hasattr(self, '_map_cache'):
                return
            cache = self._map_cache
            alive = cache['alive']
            sorted_sv = cache['sorted_sv']
            poly_radius = cache['poly_radius']
            sv_3d = cache['sv_3d']
            map_groups = dict(cache['map_groups_items'])
            dev_3d = cache['dev_3d']
            keys = cache['keys']
            self._map_dev_alpha = dict(cache['map_dev_alpha'])

            if not alive:
                return

        # ---- RENDER (always runs, uses current camera) ----
        # Ground grid
        def _grid_seg(x1, z1, x2, z2, col="#1a1a3a"):
            p1 = self._project(x1, 0, z1, w, h)
            p2 = self._project(x2, 0, z2, w, h)
            if p1 and p2:
                emit((p1[2] + p2[2]) / 2, 0,
                     lambda c=c, p1=p1, p2=p2, col=col: c.create_line(p1[0], p1[1], p2[0], p2[1], fill=col, width=1))
        segs = 24
        for radius in (40, 80, 120, 160):
            pts = [(radius * math.cos(2 * math.pi * i / segs), radius * math.sin(2 * math.pi * i / segs)) for i in range(segs + 1)]
            for i in range(segs):
                _grid_seg(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
        for i in range(8):
            a = 2 * math.pi * i / 8
            _grid_seg(0, 0, 160 * math.cos(a), 160 * math.sin(a))

        # Center label
        pc = self._project(0, 10, 0, w, h)
        if pc:
            emit(pc[2], 1, lambda c=c, pc=pc: c.create_text(pc[0], pc[1], text="SpatialHA", fill="#fff", font=("", 14, "bold")))

        # Server-to-center lines
        for sid, (sx, _, sz) in sv_3d.items():
            color = GRAPH_COLORS[sorted_sv.index(sid) % len(GRAPH_COLORS)]
            ps = self._project(sx, 0, sz, w, h)
            p_c = self._project(0, 0, 0, w, h)
            if ps and p_c:
                d = (ps[2] + p_c[2]) / 2
                emit(d, 5, lambda c=c, ps=ps, pc=p_c, col=color: (
                    c.create_line(ps[0], ps[1], pc[0], pc[1], fill=self._darken(col, 0.3), width=2)
                ))

        # Device-to-server connection lines
        for gkey, (dx, dy, dz) in dev_3d.items():
            alpha = self._map_dev_alpha.get(gkey, 1.0)
            if alpha < 0.02:
                continue
            grp = map_groups.get(gkey)
            if grp is None:
                continue
            for sid, (sx, _, sz) in sv_3d.items():
                rssi = grp.rssi_to_server.get(sid)
                if rssi is None:
                    continue
                color = GRAPH_COLORS[sorted_sv.index(sid) % len(GRAPH_COLORS)]
                ps = self._project(sx, dy, sz, w, h)
                pd = self._project(dx, dy, dz, w, h)
                if ps and pd:
                    d = (ps[2] + pd[2]) / 2
                    emit(d, 10, lambda c=c, ps=ps, pd=pd, col=color: (
                        c.create_line(ps[0], ps[1], pd[0], pd[1], fill=self._darken(col, 0.4), width=4),
                        c.create_line(ps[0], ps[1], pd[0], pd[1], fill=col, width=2)
                    ))
                    mx, my = (ps[0] + pd[0]) / 2, (ps[1] + pd[1]) / 2
                    dxs = pd[0] - ps[0]
                    dys = pd[1] - ps[1]
                    dl_s = math.hypot(dxs, dys)
                    if dl_s > 0:
                        mx += (dxs / dl_s) * 20
                        my += (dys / dl_s) * 20
                    emit(d, 11, lambda c=c, mx=mx, my=my, col=color, rssi=rssi: (
                        c.create_rectangle(mx - 12, my - 7, mx + 12, my + 7, fill="#0f0f23", outline=col, width=1),
                        c.create_text(mx, my, text=str(rssi), fill=col, font=("", 7, "bold"))
                    ))

        # Server pillars
        for sid, (sx, _, sz) in sv_3d.items():
            color = GRAPH_COLORS[sorted_sv.index(sid) % len(GRAPH_COLORS)]
            pb = self._project(sx, 0, sz, w, h)
            pt = self._project(sx, 22, sz, w, h)
            if not pb or not pt:
                continue
            depth = min(pb[2], pt[2])
            emit(depth, 30, lambda c=c, pb=pb, pt=pt, col=color: (
                c.create_line(pb[0], pb[1], pt[0], pt[1], fill=col, width=3)
            ))
            r = 20 * (300 / pt[2])
            emit(depth, 40, lambda c=c, pt=pt, r=r, col=color, lbl=sid[:10], dp=pt[2]: (
                c.create_oval(pt[0] - r - 4, pt[1] - r - 4, pt[0] + r + 4, pt[1] + r + 4, outline=col, width=1, stipple="gray25"),
                c.create_oval(pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r, fill=col, outline="#fff", width=2),
                c.create_text(pt[0], pt[1], text=lbl, fill="#fff", font=("", max(7, int(8 * 300 / dp)), "bold"))
            ))

        # Device nodes
        for gkey, (dx, dy, dz) in dev_3d.items():
            alpha = self._map_dev_alpha.get(gkey, 1.0)
            if alpha < 0.02:
                continue
            grp = map_groups.get(gkey)
            if grp is None:
                continue
            dev = grp.latest_device()
            lbl = grp.name or (dev.address if dev else gkey)
            avg = grp.avg_rssi
            if avg is not None:
                i_val = max(0, min(255, int((avg + 95) / 95 * 200)))
                base_c = f"#{i_val:02x}{int(i_val*0.3):02x}{int(255-i_val*0.5):02x}"
            else:
                base_c = "#445"
            pn = self._project(dx, dy, dz, w, h)
            if not pn:
                continue
            depth = pn[2]
            r = 11 * (240 / depth)
            r_fade = r * alpha
            emit(depth, 60, lambda c=c, pn=pn, r=r_fade, bc=base_c, lbl=lbl[:18], dp=depth: (
                c.create_oval(pn[0] - r, pn[1] - r, pn[0] + r, pn[1] + r, fill=bc, outline="#fff", width=1),
                c.create_text(pn[0], pn[1] + r + 8, text=lbl, fill="#ccc", font=("", max(6, int(7 * 240 / dp))), anchor=tk.N)
            ))
            self._map_last_dev_pos[gkey] = (pn[0], pn[1], r + 4)

        # Sort and draw
        objects.sort(key=lambda o: o[0])
        for _, _, fn in objects:
            fn()

        # HUD
        el_deg = math.degrees(self._map_elevation)
        c.create_text(w - 10, 10, text=f"⌀{self._map_orbit_dist:.0f}  {el_deg:.0f}°", fill="#666", anchor=tk.NE, font=("", 8))

    # ------------------------------------------------------------------
    # Hover tooltip
    # ------------------------------------------------------------------
    def _on_map_motion(self, event):
        c = self.map_canvas
        best = (None, 99)
        for gkey, (cx2, cy2, hr) in self._map_last_dev_pos.items():
            d = math.hypot(event.x - cx2, event.y - cy2)
            if d < hr and d < best[1]:
                best = (gkey, d)
        if best[0] is not None:
            grp = self.device_groups.get(best[0])
            if grp:
                rssi_map = grp.rssi_to_server
                lines = [f"Device: {grp.name or '(unnamed)'}"]
                lines.append(f"MACs: {grp.all_macs_str}")
                if grp.avg_rssi is not None:
                    lines.append(f"Avg RSSI: {grp.avg_rssi:.1f}")
                for sid, rssi in sorted(rssi_map.items()):
                    lines.append(f"  {sid}: {rssi} dBm")
                self._show_map_tooltip(c, event.x_root + 12, event.y_root + 12, "\n".join(lines))
        else:
            self._hide_map_tooltip(c)

    def _show_map_tooltip(self, canvas, x, y, text):
        self._hide_map_tooltip(canvas)
        self._map_tooltip = tk.Toplevel(canvas)
        self._map_tooltip.wm_overrideredirect(True)
        self._map_tooltip.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(self._map_tooltip, text=text, bg="#ffffcc", fg="#000",
                       font=("", 8), padx=4, pady=2, justify=tk.LEFT)
        lbl.pack()

    def _hide_map_tooltip(self, canvas):
        if self._map_tooltip:
            self._map_tooltip.destroy()
            self._map_tooltip = None

    # --- OTA Tab ---

    def _setup_ota_tab(self):
        frame = ttk.Frame(self.ota_frame, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        lf = ttk.LabelFrame(frame, text="OTA Servers", padding=5)
        lf.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        cols = ("Server ID", "OTA IP", "OTA Port", "Status")
        self.ota_tree = ttk.Treeview(lf, columns=cols, show="headings", height=6)
        for c, w in zip(cols, [200, 150, 80, 80]):
            self.ota_tree.heading(c, text=c)
            self.ota_tree.column(c, width=w)
        self.ota_tree.pack(fill=tk.BOTH, expand=True)
        uf = ttk.LabelFrame(frame, text="Upload", padding=10)
        uf.pack(fill=tk.X)
        fr = ttk.Frame(uf)
        fr.pack(fill=tk.X, pady=5)
        self._file_path = tk.StringVar()
        ttk.Entry(fr, textvariable=self._file_path, width=60).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(fr, text="Browse...", command=self._browse_file).pack(side=tk.LEFT)
        self.ota_status_label = ttk.Label(uf, text="")
        self.ota_status_label.pack(pady=5)
        br = ttk.Frame(uf)
        br.pack(pady=5)
        ttk.Button(br, text="Push Update", command=self._push_ota).pack()

    def _browse_file(self):
        p = tkinter.filedialog.askopenfilename(
            title="Select spatialble_server.py", filetypes=[("Python files", "*.py"), ("All files", "*.*")])
        if p:
            self._file_path.set(p)

    def _push_ota(self):
        sel = self.ota_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select an OTA server first")
            return
        fp = self._file_path.get().strip()
        if not fp:
            messagebox.showwarning("No File", "Browse for a file to upload first")
            return
        item = self.ota_tree.item(sel[0])
        ip, port = item["values"][1], item["values"][2]
        url = f"http://{ip}:{port}/upload"
        self.ota_status_label.config(text="Uploading...", foreground="")

        def _up():
            try:
                with open(fp, "rb") as f:
                    data = f.read()
                req = urllib.request.Request(url, data=data, method="POST")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read())
                msg = result.get("message", "Unknown")
                if result.get("success"):
                    self.root.after(0, lambda: self.ota_status_label.config(text=f"OK: {msg}", foreground="#2e7d32"))
                else:
                    self.root.after(0, lambda: self.ota_status_label.config(text=f"Failed: {msg}", foreground="#c62828"))
            except urllib.error.URLError as e:
                self.root.after(0, lambda: self.ota_status_label.config(text=f"Connection failed: {e.reason}", foreground="#c62828"))
            except Exception as e:
                self.root.after(0, lambda: self.ota_status_label.config(text=f"Error: {e}", foreground="#c62828"))

        threading.Thread(target=_up, daemon=True).start()

    # --- Config Tab ---

    def _setup_config_tab(self):
        frame = ttk.Frame(self.config_frame, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        row = 0
        ttk.Label(frame, text="Broker").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.broker_entry = ttk.Entry(frame, width=40)
        self.broker_entry.insert(0, self.config.get("broker", ""))
        self.broker_entry.grid(row=row, column=1, pady=5, sticky=tk.EW)
        row += 1
        ttk.Label(frame, text="Port").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.port_entry = ttk.Entry(frame, width=40)
        self.port_entry.insert(0, str(self.config.get("port", 1883)))
        self.port_entry.grid(row=row, column=1, pady=5, sticky=tk.EW)
        row += 1
        ttk.Label(frame, text="Username").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.username_entry = ttk.Entry(frame, width=40)
        self.username_entry.insert(0, self.config.get("username", ""))
        self.username_entry.grid(row=row, column=1, pady=5, sticky=tk.EW)
        row += 1
        ttk.Label(frame, text="Password").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.password_entry = ttk.Entry(frame, width=40, show="*")
        self.password_entry.insert(0, self.config.get("password", ""))
        self.password_entry.grid(row=row, column=1, pady=5, sticky=tk.EW)
        row += 1
        sf = ttk.Frame(frame)
        sf.grid(row=row, column=0, columnspan=2, pady=(15, 5), sticky=tk.W)
        ttk.Label(sf, text="Status:").pack(side=tk.LEFT)
        self.conn_status_label = ttk.Label(sf, text="Disconnected", foreground="#c62828")
        self.conn_status_label.pack(side=tk.LEFT, padx=(5, 0))
        row += 1
        bf = ttk.Frame(frame)
        bf.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Button(bf, text="Connect", command=self._apply_and_connect).pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text="Disconnect", command=self._disconnect_mqtt).pack(side=tk.LEFT, padx=5)
        row += 1

        irkf = ttk.LabelFrame(frame, text="BLE Identity Resolving Keys (IRK)", padding=5)
        irkf.grid(row=row, column=0, columnspan=2, pady=(10, 0), sticky=tk.NSEW)
        row += 1
        irki = ttk.Frame(irkf)
        irki.pack(fill=tk.X, pady=2)
        ttk.Label(irki, text="New IRK (hex, 32 chars):").pack(side=tk.LEFT)
        self.irk_entry = ttk.Entry(irki, width=35)
        self.irk_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(irki, text="Add", command=self._add_irk).pack(side=tk.LEFT)
        self.irk_listbox = tk.Listbox(irkf, height=4)
        self.irk_listbox.pack(fill=tk.X, pady=5)
        self._populate_irk_listbox()
        irkb = ttk.Frame(irkf)
        irkb.pack()
        ttk.Button(irkb, text="Remove Selected", command=self._remove_irk).pack(side=tk.LEFT, padx=5)

        lf = ttk.LabelFrame(frame, text="Log", padding=5)
        lf.grid(row=row, column=0, columnspan=2, pady=(15, 0), sticky=tk.NSEW)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(row, weight=1)
        self.log_text = tk.Text(lf, wrap=tk.WORD, state=tk.DISABLED, height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self._log("Configuration loaded")

    def _populate_irk_listbox(self):
        self.irk_listbox.delete(0, tk.END)
        for irk in self.config.get("irks", []):
            self.irk_listbox.insert(tk.END, irk)

    def _add_irk(self):
        irk = self.irk_entry.get().strip().replace(" ", "").lower()
        if len(irk) != 32:
            messagebox.showerror("Invalid IRK", "IRK must be exactly 32 hex characters (16 bytes)")
            return
        try:
            bytes.fromhex(irk)
        except ValueError:
            messagebox.showerror("Invalid IRK", "IRK contains non-hex characters")
            return
        self.config.setdefault("irks", []).append(irk)
        save_config(self.config)
        self.irk_entry.delete(0, tk.END)
        self._populate_irk_listbox()
        self._log(f"Added IRK: {irk[:8]}...")

    def _remove_irk(self):
        sel = self.irk_listbox.curselection()
        if not sel:
            return
        removed = self.config["irks"].pop(sel[0])
        save_config(self.config)
        self._populate_irk_listbox()
        self._log(f"Removed IRK: {removed[:8]}...")

    def _apply_and_connect(self):
        self.config["broker"] = self.broker_entry.get().strip()
        try:
            self.config["port"] = int(self.port_entry.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Port", "Port must be a number")
            return
        self.config["username"] = self.username_entry.get().strip()
        self.config["password"] = self.password_entry.get().strip()
        self._restart_mqtt()

    def _log(self, message: str):
        if not hasattr(self, "log_text"):
            return
        self.log_text.config(state=tk.NORMAL)
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    # --- Periodic UI update ---

    def _start_periodic_update(self):
        self._update_ui()
        self.root.after(2000, self._start_periodic_update)

    def _update_ui(self):
        # Servers tab
        for i in self.servers_tree.get_children():
            self.servers_tree.delete(i)
        for sid, info in sorted(self.servers.items()):
            self.servers_tree.insert("", tk.END, values=(
                sid, info.status_text, info.device_count,
                time.strftime("%H:%M:%S", time.localtime(info.last_seen)) if info.last_seen else "Never"))

        # Devices tab — show groups
        search = self.device_filter.get().strip().lower()
        for i in self.devices_tree.get_children():
            self.devices_tree.delete(i)

        for gkey, grp in sorted(self.device_groups.items()):
            display_name = grp.name or (grp.macs[0] if grp.macs else gkey)
            if search and search not in display_name.lower():
                continue
            avg = grp.avg_rssi
            avg_str = f"{avg:.1f}" if avg is not None else "—"
            bi = grp.latest_device()
            bi_str = f"{bi.avg_broadcast_interval:.2f}s" if bi and bi.avg_broadcast_interval else "—"
            vals = (display_name, avg_str, grp.latest_rssi,
                    grp.beacon_type or "—", bi_str, grp.seen_by_str)
            item = self.devices_tree.insert("", tk.END, values=vals)
            if gkey == self._selected_group:
                self.devices_tree.selection_set(item)

        if self._selected_group not in self.device_groups:
            self._selected_group = None
            self._update_detail_pane()
        if self._selected_group:
            self._update_detail_pane()

        # OTA tab
        for i in self.ota_tree.get_children():
            self.ota_tree.delete(i)
        for sid, info in sorted(self.servers.items()):
            if info.has_ota:
                self.ota_tree.insert("", tk.END, values=(
                    sid, info.ota_ip, info.ota_port, "Alive" if info.is_alive else "Offline"))

        # Network map is animated separately at ~60 fps in _animate_map


def main():
    root = tk.Tk()
    app = SpatialBLEClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()
