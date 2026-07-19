"""
spatialble_client - Tkinter GUI for monitoring BLE devices via MQTT.
"""

import json
import os
import time
import tkinter as tk
import tkinter.filedialog
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Tuple
import threading
import urllib.request
import urllib.error
from collections import OrderedDict

import paho.mqtt.client as mqtt

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

CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "spatialble_config.json"
)
MQTT_TOPIC = "spatialble"
DEFAULT_CONFIG = {
    "broker": "localhost",
    "port": 1883,
    "username": "",
    "password": "",
    "irks": [],
}


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


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
        if self.last_heartbeat is None:
            return False
        return (time.time() - self.last_heartbeat) < 30

    @property
    def status_text(self) -> str:
        if self.last_heartbeat is None:
            return "Waiting..."
        if self.is_alive:
            return f"Alive ({(time.time() - self.last_heartbeat):.0f}s ago)"
        return f"Offline ({(time.time() - self.last_heartbeat):.0f}s ago)"


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
        self._last_device_data: Optional[dict] = None

    def update(self, server_id: str, rssi: int, name: str,
               manufacturer_data: dict, service_uuids: list,
               service_data: dict, tx_power: Optional[int],
               timestamp: float):
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
        # Keep last 500 readings per server
        if len(self.rssi_history[server_id]) > 500:
            self.rssi_history[server_id] = self.rssi_history[server_id][-500:]

        if self._prev_timestamp is not None:
            delta = timestamp - self._prev_timestamp
            if 0.01 < delta < 600:
                self._intervals.append(delta)
                if len(self._intervals) > 100:
                    self._intervals = self._intervals[-100:]
        self._prev_timestamp = timestamp

        # Decode beacons on first useful data
        if not self.ibeacon:
            self.ibeacon = decode_ibeacon(manufacturer_data)
        if not self.eddystone:
            self.eddystone = decode_eddystone(service_data)

    @property
    def avg_rssi(self) -> Optional[float]:
        vals = []
        for h in self.rssi_history.values():
            vals.extend(r for _, r in h)
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
            t = self.eddystone.get("type", "")
            return t.replace("_", " ").title()
        return ""


class SpatialBLEClient:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SpatialBLE Client")
        self.root.geometry("1000x750")

        self.config = load_config()
        self.servers: Dict[str, ServerInfo] = {}
        self.devices: Dict[str, BLEDeviceInfo] = {}
        self.mqtt_client: Optional[mqtt.Client] = None
        self.mqtt_thread: Optional[threading.Thread] = None
        self._connected = False
        self._selected_device: Optional[str] = None

        self._setup_ui()
        self._connect_mqtt()
        self._start_periodic_update()

    # --- MQTT ---

    def _connect_mqtt(self):
        self._disconnect_mqtt()
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
        client.on_message = self._on_message
        client.on_connect = self._on_mqtt_connect
        client.on_disconnect = self._on_mqtt_disconnect
        client.reconnect_delay_set(max_delay=30)
        username = self.config.get("username", "")
        password = self.config.get("password", "")
        if username:
            client.username_pw_set(username, password)
        try:
            client.connect(self.config["broker"], int(self.config["port"]), keepalive=60)
        except Exception as e:
            self._log(f"Connection failed: {e}")
            self._update_connection_status(False)
            return
        client.subscribe(f"{MQTT_TOPIC}/+")
        thread = threading.Thread(target=client.loop_forever, daemon=True)
        thread.start()
        self.mqtt_client = client
        self.mqtt_thread = thread

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
        self._connect_mqtt()

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        self._connected = rc == 0
        self.root.after(0, self._update_connection_status, self._connected)
        msg = MQTT_RC_MESSAGES.get(rc, f"Unknown code {rc}")
        if self._connected:
            self._log(f"Connected to {self.config['broker']}:{self.config['port']}")
        else:
            self._log(msg)

    def _on_mqtt_disconnect(self, client, userdata, rc):
        self._connected = False
        self.root.after(0, self._update_connection_status, False)

    def _update_connection_status(self, connected: bool):
        color = "#2e7d32" if connected else "#c62828"
        text = "Connected" if connected else "Disconnected"
        if hasattr(self, "conn_status_label"):
            self.conn_status_label.config(text=text, foreground=color)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
        except json.JSONDecodeError:
            return
        msg_type = payload.get("type")
        if msg_type == "heartbeat":
            self._handle_heartbeat(payload)
        elif msg_type == "advertisement":
            self._handle_advertisement(payload)

    def _resolve_address(self, address: str) -> str:
        for irk in self.config.get("irks", []):
            resolved = resolve_irk(address, irk)
            if resolved:
                return resolved
        return address

    def _handle_heartbeat(self, payload: dict):
        server_id = payload["server_id"]
        timestamp = payload.get("timestamp", time.time())
        if server_id not in self.servers:
            self.servers[server_id] = ServerInfo(server_id)
        info = self.servers[server_id]
        info.last_heartbeat = timestamp
        info.last_seen = time.time()
        info.ota_ip = payload.get("ota_ip")
        info.ota_port = payload.get("ota_port")

    def _handle_advertisement(self, payload: dict):
        server_id = payload["server_id"]
        device_data = payload["device"]
        address = self._resolve_address(device_data["address"])
        timestamp = payload.get("timestamp", time.time())
        if server_id not in self.servers:
            self.servers[server_id] = ServerInfo(server_id)
        if address not in self.devices:
            self.devices[address] = BLEDeviceInfo(address)
        self.devices[address].update(
            server_id=server_id,
            rssi=device_data["rssi"],
            name=device_data.get("name", ""),
            manufacturer_data=device_data.get("manufacturer_data", {}),
            service_uuids=device_data.get("service_uuids", []),
            service_data=device_data.get("service_data", {}),
            tx_power=device_data.get("tx_power"),
            timestamp=timestamp,
        )
        self.servers[server_id].last_seen = time.time()
        seen = set()
        for dev_addr, dev_info in self.devices.items():
            if server_id in dev_info.seen_by:
                seen.add(dev_addr)
        self.servers[server_id].device_count = len(seen)

    # --- UI ---

    def _setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.servers_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.servers_frame, text="Servers")
        self._setup_servers_tab()

        self.devices_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.devices_frame, text="BLE Devices")
        self._setup_devices_tab()

        self.ota_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ota_frame, text="OTA")
        self._setup_ota_tab()

        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Configuration")
        self._setup_config_tab()

    # --- Servers Tab ---

    def _setup_servers_tab(self):
        columns = ("Server ID", "Status", "Devices Seen", "Last Seen")
        self.servers_tree = ttk.Treeview(self.servers_frame, columns=columns, show="headings")
        for col in columns:
            self.servers_tree.heading(col, text=col)
            self.servers_tree.column(col, width=200)
        self.servers_tree.pack(fill=tk.BOTH, expand=True)

    # --- BLE Devices Tab ---

    def _setup_devices_tab(self):
        paned = ttk.PanedWindow(self.devices_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(paned)
        paned.add(top, weight=3)

        columns = ("Address", "Name", "Avg RSSI", "RSSI", "Beacon Type",
                    "Broadcast Int.", "Seen By")
        self.devices_tree = ttk.Treeview(top, columns=columns, show="headings")
        col_widths = [180, 140, 75, 60, 100, 90, 200]
        for col, w in zip(columns, col_widths):
            self.devices_tree.heading(col, text=col)
            self.devices_tree.column(col, width=w, minwidth=50)
        self.devices_tree.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        self.devices_tree.bind("<<TreeviewSelect>>", self._on_device_select)

        # Search bar
        search_frame = ttk.Frame(top)
        search_frame.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(search_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 4))
        self.device_filter = tk.StringVar()
        self.device_filter.trace("w", lambda *a: self._update_ui())
        ttk.Entry(search_frame, textvariable=self.device_filter).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Detail pane at bottom
        self.detail_frame = ttk.LabelFrame(paned, text="Device Detail", padding=5)
        paned.add(self.detail_frame, weight=2)
        self._setup_detail_pane()

    def _setup_detail_pane(self):
        cols = ttk.Frame(self.detail_frame)
        cols.pack(fill=tk.BOTH, expand=True)

        # Left: info + servers
        left = ttk.Frame(cols)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Info section
        self.info_frame = ttk.LabelFrame(left, text="Info", padding=5)
        self.info_frame.pack(fill=tk.X, pady=(0, 4))
        self.info_labels = {}
        for i, key in enumerate(["Address", "Name", "First Seen", "Last Seen",
                                  "TX Power", "Avg RSSI", "Broadcast Int.",
                                  "Beacon Type"]):
            lbl = ttk.Label(self.info_frame, text=f"{key}: —", anchor=tk.W)
            lbl.grid(row=i, column=0, sticky=tk.W, padx=2)
            self.info_labels[key] = lbl

        # Per-server table
        srv_frame = ttk.LabelFrame(left, text="Per Server", padding=2)
        srv_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        srv_cols = ("Server", "RSSI", "Last Seen", "Samples")
        self.server_detail_tree = ttk.Treeview(srv_frame, columns=srv_cols,
                                                show="headings", height=4)
        for c, w in zip(srv_cols, [150, 60, 140, 70]):
            self.server_detail_tree.heading(c, text=c)
            self.server_detail_tree.column(c, width=w)

        # Service UUIDs
        svc_frame = ttk.LabelFrame(left, text="Service UUIDs", padding=2)
        svc_frame.pack(fill=tk.X)
        self.svc_listbox = tk.Listbox(svc_frame, height=3, state=tk.DISABLED)
        svc_scroll = ttk.Scrollbar(svc_frame, orient=tk.VERTICAL, command=self.svc_listbox.yview)
        self.svc_listbox.configure(yscrollcommand=svc_scroll.set)
        self.svc_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        svc_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Right: beacon + graph
        right = ttk.Frame(cols)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Beacon info
        self.beacon_frame = ttk.LabelFrame(right, text="Beacon", padding=5)
        self.beacon_frame.pack(fill=tk.X, pady=(0, 4))
        self.beacon_labels = {}
        for i, key in enumerate(["Type", "UUID", "Major", "Minor",
                                  "Namespace", "Instance", "URL",
                                  "TX Power (1m)", "Battery", "Temp"]):
            lbl = ttk.Label(self.beacon_frame, text=f"{key}: —", anchor=tk.W)
            lbl.grid(row=i, column=0, sticky=tk.W, padx=2)
            self.beacon_labels[key] = lbl

        # Manufacturer data
        mfr_frame = ttk.LabelFrame(right, text="Manufacturer Data", padding=2)
        mfr_frame.pack(fill=tk.X, pady=(0, 4))
        self.mfr_text = tk.Text(mfr_frame, height=3, state=tk.DISABLED)
        self.mfr_text.pack(fill=tk.X)

        # RSSI graph
        graph_frame = ttk.LabelFrame(right, text="RSSI Graph (last 5 min)", padding=2)
        graph_frame.pack(fill=tk.BOTH, expand=True)
        self.graph_canvas = tk.Canvas(graph_frame, bg="#1e1e1e", height=150)
        self.graph_canvas.pack(fill=tk.BOTH, expand=True)

    def _on_device_select(self, event=None):
        sel = self.devices_tree.selection()
        if not sel:
            return
        item = self.devices_tree.item(sel[0])
        self._selected_device = item["values"][0]
        self._update_detail_pane()

    def _update_detail_pane(self):
        dev = self.devices.get(self._selected_device)
        if not dev:
            # Clear detail
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
            for child in self.server_detail_tree.get_children():
                self.server_detail_tree.delete(child)
            self.graph_canvas.delete("all")
            return

        # Info
        def _ts(ts):
            return time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "—"
        self.info_labels["Address"].config(text=f"Address: {dev.address}")
        self.info_labels["Name"].config(text=f"Name: {dev.name or '—'}")
        self.info_labels["First Seen"].config(text=f"First Seen: {_ts(dev.first_seen)}")
        self.info_labels["Last Seen"].config(text=f"Last Seen: {_ts(dev.last_seen)}")
        self.info_labels["TX Power"].config(
            text=f"TX Power: {dev.tx_power} dBm" if dev.tx_power is not None else "TX Power: —")
        avg = dev.avg_rssi
        self.info_labels["Avg RSSI"].config(
            text=f"Avg RSSI: {avg:.1f} dBm" if avg is not None else "Avg RSSI: —")
        bi = dev.avg_broadcast_interval
        self.info_labels["Broadcast Int."].config(
            text=f"Broadcast Int.: {bi:.2f}s" if bi is not None else "Broadcast Int.: —")
        self.info_labels["Beacon Type"].config(text=f"Beacon Type: {dev.beacon_type or '—'}")

        # Per-server
        for child in self.server_detail_tree.get_children():
            self.server_detail_tree.delete(child)
        for sid, last_seen in sorted(dev.seen_by.items()):
            hist = dev.rssi_history.get(sid, [])
            rssi = hist[-1][1] if hist else "—"
            samples = len(hist)
            self.server_detail_tree.insert("", tk.END, values=(
                sid, rssi, _ts(last_seen), samples))

        # Service UUIDs
        self.svc_listbox.config(state=tk.NORMAL)
        self.svc_listbox.delete(0, tk.END)
        for uuid in dev.service_uuids:
            name = SERVICE_NAMES.get(uuid.lower(), "")
            label = f"{uuid}  ({name})" if name else uuid
            self.svc_listbox.insert(tk.END, label)
        if not dev.service_uuids:
            self.svc_listbox.insert(tk.END, "(none)")
        self.svc_listbox.config(state=tk.DISABLED)

        # Beacon
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
                self.beacon_labels["TX Power (1m)"].config(text=f"PKT Count: {ed.get('pkt_count', '—')}")

        # Manufacturer data
        self.mfr_text.config(state=tk.NORMAL)
        self.mfr_text.delete("1.0", tk.END)
        if dev.manufacturer_data:
            for mid, data in sorted(dev.manufacturer_data.items()):
                self.mfr_text.insert(tk.END, f"0x{mid}: {data}\n")
        else:
            self.mfr_text.insert(tk.END, "(none)")
        self.mfr_text.config(state=tk.DISABLED)

        # RSSI graph
        self._draw_rssi_graph(dev)

    def _draw_rssi_graph(self, dev: BLEDeviceInfo):
        c = self.graph_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 50 or h < 50:
            c.create_text(80, 20, text="(waiting for graph area)", fill="#888",
                          anchor=tk.NW, font=("", 8))
            return

        margin_l, margin_r, margin_t, margin_b = 40, 10, 15, 25
        gw = w - margin_l - margin_r
        gh = h - margin_t - margin_b

        if gw < 20 or gh < 20:
            return

        # Gather all server histories within last 5 min
        now = time.time()
        cutoff = now - 300
        all_pts: List[Tuple[float, int]] = []
        server_data: List[Tuple[str, List[Tuple[float, int]], str]] = []

        for sid in sorted(dev.rssi_history.keys()):
            pts = [(t, r) for t, r in dev.rssi_history[sid] if t >= cutoff]
            if pts:
                server_data.append((sid, pts, GRAPH_COLORS[len(server_data) % len(GRAPH_COLORS)]))
                all_pts.extend(pts)

        if not all_pts:
            c.create_text(margin_l + gw // 2, margin_t + gh // 2,
                          text="No recent RSSI data", fill="#888", font=("", 9))
            return

        min_time = min(t for t, _ in all_pts)
        max_time = max(t for t, _ in all_pts)
        if max_time - min_time < 1:
            max_time = min_time + 60
        min_rssi = min(r for _, r in all_pts) - 5
        max_rssi = max(0, max(r for _, r in all_pts) + 5)
        if max_rssi - min_rssi < 20:
            max_rssi = min_rssi + 20

        def tx(t): return margin_l + (t - min_time) / (max_time - min_time) * gw
        def ty(r): return margin_t + (max_rssi - r) / (max_rssi - min_rssi) * gh

        # Grid lines
        for r in range(int(min_rssi / 10) * 10, int(max_rssi / 10) * 10 + 1, 10):
            if r < min_rssi or r > max_rssi:
                continue
            y = ty(r)
            c.create_line(margin_l, y, margin_l + gw, y, fill="#333", width=1)
            c.create_text(margin_l - 4, y, text=str(r), fill="#aaa",
                          anchor=tk.E, font=("", 7))

        # X axis labels
        for offset in range(0, 300, 60):
            t = min_time + offset
            if t > max_time:
                break
            x = tx(t)
            c.create_line(x, margin_t, x, margin_t + gh, fill="#333", width=1)
            label = f"-{int(max_time - t)}s" if max_time - t > 0 else "now"
            c.create_text(x, margin_t + gh + 12, text=label, fill="#aaa",
                          font=("", 7))

        # Plot each server
        for sid, pts, color in server_data:
            pts.sort()
            coords = []
            for t, r in pts:
                coords.append(tx(t))
                coords.append(ty(r))
            if len(coords) >= 4:
                c.create_line(*coords, fill=color, width=2, smooth=True)

            # Legend dot
            last_pt = pts[-1]
            cx = tx(last_pt[0])
            cy = ty(last_pt[1])
            c.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=color, outline="")
            # Server name label near last point
            x_lbl = cx + 5
            y_lbl = cy - 6
            # Adjust to stay in bounds
            if x_lbl + 50 > w:
                x_lbl = cx - 55
            c.create_text(x_lbl, y_lbl, text=sid, fill=color,
                          anchor=tk.W, font=("", 7))

    # --- OTA Tab ---

    def _setup_ota_tab(self):
        frame = ttk.Frame(self.ota_frame, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        list_frame = ttk.LabelFrame(frame, text="OTA Servers", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        columns = ("Server ID", "OTA IP", "OTA Port", "Status")
        self.ota_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=6)
        for col, w in zip(columns, [200, 150, 80, 80]):
            self.ota_tree.heading(col, text=col)
            self.ota_tree.column(col, width=w)
        self.ota_tree.pack(fill=tk.BOTH, expand=True)
        upload_frame = ttk.LabelFrame(frame, text="Upload", padding=10)
        upload_frame.pack(fill=tk.X)
        file_row = ttk.Frame(upload_frame)
        file_row.pack(fill=tk.X, pady=5)
        self._file_path = tk.StringVar()
        ttk.Entry(file_row, textvariable=self._file_path, width=60).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(file_row, text="Browse...", command=self._browse_file).pack(side=tk.LEFT)
        self.ota_status_label = ttk.Label(upload_frame, text="")
        self.ota_status_label.pack(pady=5)
        btn_row = ttk.Frame(upload_frame)
        btn_row.pack(pady=5)
        ttk.Button(btn_row, text="Push Update", command=self._push_ota).pack()

    def _browse_file(self):
        path = tkinter.filedialog.askopenfilename(
            title="Select spatialble_server.py",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")],
        )
        if path:
            self._file_path.set(path)

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
        ip = item["values"][1]
        port = item["values"][2]
        url = f"http://{ip}:{port}/upload"
        self.ota_status_label.config(text="Uploading...", foreground="")
        def _upload():
            try:
                with open(fp, "rb") as f:
                    data = f.read()
                req = urllib.request.Request(url, data=data, method="POST")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read())
                msg = result.get("message", "Unknown")
                if result.get("success"):
                    self.root.after(0, lambda: self.ota_status_label.config(
                        text=f"OK: {msg}", foreground="#2e7d32"))
                else:
                    self.root.after(0, lambda: self.ota_status_label.config(
                        text=f"Failed: {msg}", foreground="#c62828"))
            except urllib.error.URLError as e:
                self.root.after(0, lambda: self.ota_status_label.config(
                    text=f"Connection failed: {e.reason}", foreground="#c62828"))
            except Exception as e:
                self.root.after(0, lambda: self.ota_status_label.config(
                    text=f"Error: {e}", foreground="#c62828"))
        threading.Thread(target=_upload, daemon=True).start()

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

        # Connection status
        status_frame = ttk.Frame(frame)
        status_frame.grid(row=row, column=0, columnspan=2, pady=(15, 5), sticky=tk.W)
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        self.conn_status_label = ttk.Label(status_frame, text="Disconnected", foreground="#c62828")
        self.conn_status_label.pack(side=tk.LEFT, padx=(5, 0))
        row += 1

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Connect", command=self._apply_and_connect).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Disconnect", command=self._disconnect_mqtt).pack(side=tk.LEFT, padx=5)
        row += 1

        # IRK Keys
        irk_frame = ttk.LabelFrame(frame, text="BLE Identity Resolving Keys (IRK)", padding=5)
        irk_frame.grid(row=row, column=0, columnspan=2, pady=(10, 0), sticky=tk.NSEW)
        row += 1

        irk_inner = ttk.Frame(irk_frame)
        irk_inner.pack(fill=tk.X, pady=2)
        ttk.Label(irk_inner, text="New IRK (hex, 32 chars):").pack(side=tk.LEFT)
        self.irk_entry = ttk.Entry(irk_inner, width=35)
        self.irk_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(irk_inner, text="Add", command=self._add_irk).pack(side=tk.LEFT)

        self.irk_listbox = tk.Listbox(irk_frame, height=4)
        self.irk_listbox.pack(fill=tk.X, pady=5)
        self._populate_irk_listbox()

        irk_btn_frame = ttk.Frame(irk_frame)
        irk_btn_frame.pack()
        ttk.Button(irk_btn_frame, text="Remove Selected", command=self._remove_irk).pack(side=tk.LEFT, padx=5)

        # Log area
        log_frame = ttk.LabelFrame(frame, text="Log", padding=5)
        log_frame.grid(row=row, column=0, columnspan=2, pady=(15, 0), sticky=tk.NSEW)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(row, weight=1)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, state=tk.DISABLED, height=8)
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
        if "irks" not in self.config:
            self.config["irks"] = []
        self.config["irks"].append(irk)
        save_config(self.config)
        self.irk_entry.delete(0, tk.END)
        self._populate_irk_listbox()
        self._log(f"Added IRK: {irk[:8]}...")

    def _remove_irk(self):
        sel = self.irk_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        removed = self.config["irks"].pop(idx)
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
        for item in self.servers_tree.get_children():
            self.servers_tree.delete(item)
        for server_id, info in sorted(self.servers.items()):
            self.servers_tree.insert("", tk.END, values=(
                server_id, info.status_text, info.device_count,
                time.strftime("%H:%M:%S", time.localtime(info.last_seen))
                if info.last_seen else "Never"))

        # Devices tab
        search = self.device_filter.get().strip().lower()
        selected_addr = None
        sel = self.devices_tree.selection()
        if sel:
            selected_addr = self.devices_tree.item(sel[0])["values"][0]

        for item in self.devices_tree.get_children():
            self.devices_tree.delete(item)

        for address, dev in sorted(self.devices.items()):
            if search and search not in address.lower() and search not in dev.name.lower():
                continue
            avg = dev.avg_rssi
            avg_str = f"{avg:.1f}" if avg is not None else "—"
            bi = dev.avg_broadcast_interval
            bi_str = f"{bi:.2f}s" if bi is not None else "—"
            bt = dev.beacon_type or "—"
            vals = (address, dev.name or "—", avg_str, dev.rssi,
                    bt, bi_str, dev.seen_by_str)
            item = self.devices_tree.insert("", tk.END, values=vals)
            if address == self._selected_device:
                self.devices_tree.selection_set(item)

        # Update detail pane if device still selected
        if self._selected_device not in self.devices:
            self._selected_device = None
            self._update_detail_pane()
        elif selected_addr != self._selected_device:
            pass  # selection changed by user, will be caught by bind
        # Always redraw detail for the selected device to refresh graph
        if self._selected_device:
            self._update_detail_pane()

        # OTA tab
        for item in self.ota_tree.get_children():
            self.ota_tree.delete(item)
        for server_id, info in sorted(self.servers.items()):
            if info.has_ota:
                status = "Alive" if info.is_alive else "Offline"
                self.ota_tree.insert("", tk.END,
                                     values=(server_id, info.ota_ip, info.ota_port, status))


def main():
    root = tk.Tk()
    app = SpatialBLEClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()
