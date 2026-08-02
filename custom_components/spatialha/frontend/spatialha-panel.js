const TPL = document.createElement("template");
TPL.innerHTML = `
<style>
  :host {
    --sidebar-width: 220px;
    --sidebar-bg: var(--sidebar-background-color, #f5f5f5);
    --primary: var(--primary-color, #03a9f4);
    --text: var(--primary-text-color, #212121);
    --text-secondary: var(--secondary-text-color, #727272);
    --divider: var(--divider-color, #e0e0e0);
    --card-bg: var(--card-background-color, #fff);
    font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
    color: var(--primary-text-color, #212121);
    font-size: 14px;
  }
  * { box-sizing: border-box; }
  .layout { display: flex; height: calc(100vh - 52px); overflow: hidden; }
  .sidebar {
    width: var(--sidebar-width); min-width: var(--sidebar-width);
    background: var(--sidebar-bg);
    border-right: 1px solid var(--divider);
    display: flex; flex-direction: column;
    transition: width 0.25s, min-width 0.25s;
    overflow: hidden;
  }
  .sidebar.collapsed { width: 0; min-width: 0; }
  .sidebar-header {
    padding: 12px 16px; font-size: 13px; font-weight: 500;
    color: var(--text-secondary); text-transform: uppercase;
    letter-spacing: 0.5px; white-space: nowrap;
  }
  .nav-items { flex: 1; display: flex; flex-direction: column; gap: 2px; padding: 4px 8px; }
  .nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 12px; border-radius: 8px; cursor: pointer;
    color: var(--text); white-space: nowrap; font-size: 14px;
    transition: background 0.15s;
  }
  .nav-item:hover { background: rgba(0,0,0,0.05); }
  .nav-item.active { background: var(--primary); color: #fff; }
  .nav-item svg { width: 20px; height: 20px; fill: currentColor; flex-shrink: 0; }
  .sidebar-footer {
    padding: 12px 16px; border-top: 1px solid var(--divider);
    font-size: 12px; color: var(--text-secondary); white-space: nowrap;
  }
  .main { flex: 1; overflow-y: auto; padding: 16px; background: var(--card-bg); }
  .toolbar {
    display: flex; align-items: center; height: 48px; padding: 0 8px;
    border-bottom: 1px solid var(--divider); background: var(--sidebar-bg);
  }
  .toolbar-btn {
    background: none; border: none; cursor: pointer; padding: 8px; border-radius: 4px;
    display: flex; align-items: center; justify-content: center; color: var(--text);
  }
  .toolbar-btn:hover { background: rgba(0,0,0,0.05); }
  .toolbar-btn svg { width: 24px; height: 24px; fill: currentColor; }
  .toolbar-title { font-size: 16px; font-weight: 500; margin-left: 12px; color: var(--text); flex: 1; }
  .status-chip {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 500;
    background: var(--divider); color: var(--text-secondary);
    margin-right: 8px; white-space: nowrap;
  }
  .status-chip .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
  .status-chip.ok { background: #e8f5e9; color: #2e7d32; }
  .status-chip.bad { background: #fbe9e7; color: #c62828; }
  .tab-content { display: none; }
  .tab-content.active { display: block; }
  .card {
    background: var(--card-bg); border: 1px solid var(--divider);
    border-radius: 10px; padding: 16px; margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }
  .card h2 { margin: 0 0 12px; font-size: 18px; font-weight: 500; }
  .card p { margin: 4px 0; color: var(--text); line-height: 1.5; }
  .label { color: var(--text-secondary); font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
  .value { font-size: 14px; font-weight: 500; margin-bottom: 10px; }
  .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }
  .stat-card {
    background: var(--card-bg); border: 1px solid var(--divider);
    border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }
  .stat-card .stat-value { font-size: 26px; font-weight: 600; margin: 4px 0; }
  .stat-card .stat-label { font-size: 12px; color: var(--text-secondary); }
  .device-row {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 0; border-bottom: 1px solid var(--divider);
    cursor: pointer;
  }
  .device-row:last-child { border-bottom: none; }
  .device-row.expanded { border-bottom: 1px solid var(--divider); }
  .device-info { flex: 1; }
  .device-name { font-weight: 500; font-size: 14px; }
  .device-addr { font-size: 12px; color: var(--text-secondary); font-family: monospace; }
  .device-rssi { font-size: 13px; font-weight: 500; white-space: nowrap; }
  .rssi-weak { color: #f44336; }
  .rssi-ok { color: #ff9800; }
  .rssi-good { color: #4caf50; }
  .device-details {
    display: none; padding: 10px 0 14px; border-bottom: 1px solid var(--divider);
    font-size: 12px; color: var(--text-secondary); line-height: 1.6;
  }
  .device-row.expanded + .device-details { display: block; }
  .device-details .detail-label { color: var(--text); font-weight: 500; margin-top: 6px; }
  .device-details code { font-family: monospace; font-size: 11px; word-break: break-all; }
  .field { margin-bottom: 12px; }
  .field label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
  .field input, .field select {
    width: 100%; padding: 8px 10px; border: 1px solid var(--divider);
    border-radius: 6px; font-size: 14px; background: var(--card-bg);
    color: var(--text); outline: none;
  }
  .field input:focus, .field select:focus { border-color: var(--primary); }
  .btn {
    background: var(--primary); color: #fff; border: none;
    padding: 8px 16px; border-radius: 6px; font-size: 13px; cursor: pointer;
  }
  .btn:hover { opacity: 0.9; }
  .btn-secondary { background: var(--divider); color: var(--text); }
  .status-badge {
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 11px; font-weight: 500;
  }
  .status-online { background: #e8f5e9; color: #2e7d32; }
  .status-offline { background: #fbe9e7; color: #c62828; }
  .status-idle { background: #eceff1; color: #607d8b; }
  .empty { color: var(--text-secondary); text-align: center; padding: 40px 0; font-style: italic; }
  .section-title { font-size: 13px; font-weight: 500; color: var(--text-secondary); margin: 16px 0 8px; text-transform: uppercase; letter-spacing: 0.5px; }
  .error-banner {
    background: #fbe9e7; color: #c62828; border: 1px solid #ffcdd2;
    border-radius: 8px; padding: 10px 14px; font-size: 13px;
    display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
  }
  .search-row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .search-row input { flex: 1; min-width: 160px; }
  .search-row select { width: auto; }

  /* Floor plan editor */
  .fp-wrap { display: flex; flex-direction: column; height: calc(100vh - 52px); }
  .fp-toolbar {
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    padding: 8px 12px; background: var(--card-bg);
    border: 1px solid var(--divider); border-radius: 10px; margin-bottom: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }
  .fp-toolbar select, .fp-toolbar input[type="number"] {
    padding: 5px 8px; border: 1px solid var(--divider); border-radius: 6px;
    font-size: 13px; background: var(--card-bg); color: var(--text); outline: none;
  }
  .fp-toolbar label { font-size: 12px; color: var(--text-secondary); display: flex; align-items: center; gap: 4px; white-space: nowrap; }
  .fp-toolbar .btn { padding: 5px 12px; font-size: 12px; }
  .fp-toolbar .btn.on { outline: 2px solid var(--primary); outline-offset: 1px; }
  .fp-toolbar .sep { width: 1px; height: 22px; background: var(--divider); }
  .fp-canvas {
    flex: 1; border: 1px solid var(--divider); border-radius: 10px;
    background: var(--card-bg); overflow: hidden; position: relative;
    min-height: 300px; outline: none;
  }
  .fp-canvas svg { display: block; width: 100%; height: 100%; cursor: crosshair; }
  .fp-canvas.iso svg { cursor: default; }
  .fp-hint {
    font-size: 11px; color: var(--text-secondary); padding: 4px 12px 0;
    line-height: 1.5;
  }
  .fp-save-ind { font-size: 11px; color: var(--text-secondary); min-width: 60px; text-align: right; }
  .fp-point { cursor: pointer; }
  .fp-point.selected { fill: var(--primary); stroke: var(--primary); }
  .fp-room-label {
    font-size: 10px; fill: var(--text); font-weight: 500;
    text-anchor: middle; pointer-events: none;
  }
  .fp-length-label {
    font-size: 8px; fill: var(--text-secondary);
    text-anchor: middle; pointer-events: none;
  }
  .fp-marker { cursor: grab; }
  .fp-marker.dragging { cursor: grabbing; }
  .fp-device { pointer-events: none; }
  .fp-device-label { pointer-events: none; }
  .room-strip {
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    padding: 6px 10px; background: var(--sidebar-bg);
    border: 1px solid var(--divider); border-radius: 8px; margin-bottom: 8px;
    font-size: 13px;
  }
  .room-strip input[type="color"] {
    width: 28px; height: 28px; border: 1px solid var(--divider);
    border-radius: 6px; padding: 2px; background: var(--card-bg); cursor: pointer;
  }

  /* Modal */
  .modal-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.4);
    display: flex; align-items: center; justify-content: center; z-index: 999;
  }
  .modal {
    background: var(--card-bg); border-radius: 12px; padding: 20px;
    width: 320px; max-width: 90vw; box-shadow: 0 8px 30px rgba(0,0,0,0.3);
  }
  .modal h3 { margin: 0 0 14px; font-size: 16px; font-weight: 500; }
  .modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 14px; }
</style>
<div class="toolbar">
  <button class="toolbar-btn" id="toggleBtn">
    <svg viewBox="0 0 24 24"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>
  </button>
  <span class="toolbar-title">SpatialHA</span>
  <span class="status-chip" id="statusChip"><span class="dot"></span>Connecting...</span>
</div>
<div class="layout">
  <div class="sidebar" id="sidebar">
    <div class="sidebar-header">Navigation</div>
    <div class="nav-items">
      <div class="nav-item active" data-tab="overview">
        <svg viewBox="0 0 24 24"><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg>
        <span>Overview</span>
      </div>
      <div class="nav-item" data-tab="settings">
        <svg viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 00.12-.61l-1.92-3.32a.488.488 0 00-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 00-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.48.48 0 00-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58a.49.49 0 00-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1115.6 12 3.611 3.611 0 0112 15.6z"/></svg>
        <span>Settings</span>
      </div>
      <div class="nav-item" data-tab="ble">
        <svg viewBox="0 0 24 24"><path d="M14.24 12.01l2.76 2.76v-5.52l-2.76 2.76zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-.71-14.29L9.53 7.47 12 9.93V4.41c0-.28-.34-.42-.71-.7zM12 13.07l-2.47 2.46 1.76 1.76c.37.28.71.14.71-.28V13.07zm1.41-1.41l2.47-2.46-1.76-1.76c-.37-.28-.71-.14-.71.28v4.24c0 .28.34.42.71.7l1.76-1.76z"/></svg>
        <span>BLE</span>
      </div>
      <div class="nav-item" data-tab="floorplan">
        <svg viewBox="0 0 24 24"><path d="M14.8,12.6H19.3V17.1H14.8V12.6M19.3,9.4H14.8V13.8H19.3V9.4M19.3,6.2H14.8V10.6H19.3V6.2M12.4,9.4H7.9V13.8H12.4V9.4M12.4,6.2H7.9V10.6H12.4V6.2M12.4,12.6H7.9V17.1H12.4V12.6M20.5,3H3.5A1.5,1.5 0 0,0 2,4.5V19.5A1.5,1.5 0 0,0 3.5,21H20.5A1.5,1.5 0 0,0 22,19.5V4.5A1.5,1.5 0 0,0 20.5,3Z"/></svg>
        <span>Floor Plan</span>
      </div>
      <div class="nav-item" data-tab="about">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
        <span>About</span>
      </div>
    </div>
    <div class="sidebar-footer" id="versionFooter">...</div>
  </div>
  <div class="main">
    <div class="tab-content active" id="tab-overview"></div>
    <div class="tab-content" id="tab-settings"></div>
    <div class="tab-content" id="tab-ble"></div>
    <div class="tab-content" id="tab-floorplan"></div>
    <div class="tab-content" id="tab-about"></div>
  </div>
</div>
`;

const TAB_IDS = ["overview", "settings", "ble", "floorplan", "about"];
const M_TO_IN = 39.3700787;
const WALL_H = 3.0;
const ISO_COS = Math.cos(Math.PI / 6);
const ISO_SIN = Math.sin(Math.PI / 6);

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

const ROOM_COLORS = [
  { keywords: ["bed", "sleep", "nursery"], color: "#5C6BC0" },
  { keywords: ["kitchen", "cook", "pantry"], color: "#FFA726" },
  { keywords: ["bath", "wash", "toilet", "laundr", "shower"], color: "#26A69A" },
  { keywords: ["living", "lounge", "family", "sitting"], color: "#66BB6A" },
  { keywords: ["dining", "eat", "breakfast"], color: "#FFCA28" },
  { keywords: ["office", "study", "work", "desk"], color: "#42A5F5" },
  { keywords: ["hall", "corridor", "entry", "foyer", "landing"], color: "#90A4AE" },
  { keywords: ["garage", "car", "park"], color: "#8D6E63" },
  { keywords: ["basement", "cellar", "storage"], color: "#7E57C2" },
  { keywords: ["gym", "fitness", "sport"], color: "#EF5350" },
  { keywords: ["play", "game", "kids", "toy"], color: "#EC407A" },
  { keywords: ["media", "theater", "cinema", "tv"], color: "#455A64" },
];

function roomColor(name) {
  const n = (name || "").toLowerCase();
  for (const entry of ROOM_COLORS) {
    if (entry.keywords.some((k) => n.includes(k))) return entry.color;
  }
  return "#7E57C2";
}

function iso(x, y, z) {
  return { x: (x - y) * ISO_COS, y: (x + y) * ISO_SIN - z };
}

const _rssiClass = (rssi) => {
  if (rssi == null) return "";
  if (rssi >= -70) return "rssi-good";
  if (rssi >= -85) return "rssi-ok";
  return "rssi-weak";
};

const _rssiColor = (rssi) => {
  if (rssi == null) return "#90A4AE";
  if (rssi >= -70) return "#4caf50";
  if (rssi >= -85) return "#ff9800";
  return "#f44336";
};

const _fmt = (m, unit) => {
  const v = unit === "in" ? m * M_TO_IN : m;
  return `${Math.round(v * 100) / 100} ${unit}`;
};

const _timeAgo = (ts) => {
  if (!ts) return "never";
  const s = Math.floor(Date.now() / 1000 - ts);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ago`;
};

class FloorPlanEditor {
  constructor(panel, container) {
    this.panel = panel;
    this.container = container;
    this.plan = null;
    this.activeFloorId = null;
    this.snap = 0.05;
    this.selectedPoint = null;
    this.selectedRoom = null;
    this.viewMode = "2d";
    this.view = { minX: -1, minY: -1, w: 10, h: 8 };
    this.wallDrag = null;
    this.roomDrag = null;
    this.scannerDrag = null;
    this.panState = null;
    this.stairMode = false;
    this.devices = [];
    this.lastDeviceUpdate = null;
    this.saveTimer = null;
  }

  async init() {
    await this._load();
    this.container.innerHTML = this._toolbarHTML();
    this._bindToolbar();
    const canvas = document.createElement("div");
    canvas.className = "fp-canvas";
    canvas.tabIndex = 0;
    canvas.innerHTML = `<svg id="fp-svg"></svg>`;
    this.container.appendChild(canvas);
    const hint = document.createElement("div");
    hint.className = "fp-hint";
    hint.id = "fp-hint";
    this.container.appendChild(hint);
    this.canvas = canvas;
    this.svg = canvas.querySelector("svg");
    this._bindCanvas();
    this._updateHint();
    this._render();
    this._renderToolbar();
  }

  _toolbarHTML() {
    const u = this.plan.unit || "m";
    const floors = this.plan.floors || [];
    const f = this._floor();
    return `
      <div class="fp-toolbar" id="fp-toolbar">
        <button class="btn ${this.viewMode === "2d" ? "on" : ""}" id="fp-view2d">2D</button>
        <button class="btn btn-secondary ${this.viewMode === "iso" ? "on" : ""}" id="fp-viewiso">Iso</button>
        <span class="sep"></span>
        <button class="btn btn-secondary" id="fp-zoomout" title="Zoom out">&minus;</button>
        <button class="btn btn-secondary" id="fp-zoomin" title="Zoom in">+</button>
        <button class="btn btn-secondary" id="fp-fit" title="Fit to screen">Fit</button>
        <span class="sep"></span>
        <label>Units
          <select id="fp-unit">
            <option value="m" ${u === "m" ? "selected" : ""}>Meters</option>
            <option value="in" ${u === "in" ? "selected" : ""}>Inches</option>
          </select>
        </label>
        <label>Floor
          <select id="fp-floor">
            ${floors.length === 0 ? '<option value="">No floors</option>' : ""}
            ${floors.map((fl) => `<option value="${esc(fl.id)}" ${fl.id === this.activeFloorId ? "selected" : ""}>${esc(fl.name)}</option>`).join("")}
          </select>
        </label>
        <button class="btn" id="fp-add">+ Floor</button>
        <button class="btn btn-secondary" id="fp-rename">Rename</button>
        <button class="btn btn-secondary" id="fp-size">Set Size</button>
        <button class="btn btn-secondary" id="fp-align">Align</button>
        <button class="btn btn-secondary" id="fp-del">Delete</button>
        <span class="sep"></span>
        <label>Wall <input type="number" id="fp-wallth" step="any" value="${this._display(f ? f.wallThickness ?? this.plan.wallThickness ?? 0.15 : this.plan.wallThickness ?? 0.15)}" style="width:70px" /></label>
        <label><input type="checkbox" id="fp-lengths" ${this.plan.showLengths === false ? "" : "checked"} /> Lengths</label>
        <button class="btn btn-secondary ${this.stairMode ? "on" : ""}" id="fp-stair" title="Place staircase">Stairs</button>
        <span class="fp-save-ind" id="fp-save"></span>
      </div>
      <div class="room-strip" id="fp-roomstrip" style="display:none"></div>`;
  }

  _roomStripHTML() {
    const f = this._floor();
    if (!f || this.selectedRoom == null) return "";
    const room = f.rooms[this.selectedRoom];
    if (!room) return "";
    return `
      <span style="font-weight:500">Room: ${esc(room.name)}</span>
      <label>Color <input type="color" id="fp-room-color" value="${esc(room.color || roomColor(room.name))}" /></label>
      <button class="btn btn-secondary" id="fp-room-rename">Rename</button>
      <button class="btn btn-secondary" id="fp-room-del">Delete</button>`;
  }

  _bindToolbar() {
    const q = (id) => this.container.querySelector(id);
    q("#fp-unit").onchange = (e) => { this.plan.unit = e.target.value; this._renderToolbar(); this._render(); this._save(); };
    q("#fp-floor").onchange = (e) => { this.activeFloorId = e.target.value || null; this.selectedPoint = null; this.selectedRoom = null; this._renderToolbar(); this._render(); };
    q("#fp-view2d").onclick = () => { this.viewMode = "2d"; this._renderToolbar(); this._updateHint(); this._render(); };
    q("#fp-viewiso").onclick = () => { this.viewMode = "iso"; this._renderToolbar(); this._updateHint(); this._render(); };
    q("#fp-zoomin").onclick = () => this._zoom(1.5);
    q("#fp-zoomout").onclick = () => this._zoom(1 / 1.5);
    q("#fp-fit").onclick = () => { this._computeView(); this._render(); };
    q("#fp-add").onclick = async () => {
      const name = await this.panel._showModal({ title: "New Floor", label: "Floor name", value: `Floor ${(this.plan.floors || []).length + 1}` });
      if (name == null) return;
      const w = await this.panel._showModal({ title: "Floor Size", label: `Width (${this.plan.unit})`, value: "8", inputType: "number" });
      if (w == null) return;
      const h = await this.panel._showModal({ title: "Floor Size", label: `Height (${this.plan.unit})`, value: "6", inputType: "number" });
      if (h == null) return;
      const floor = {
        id: crypto.randomUUID(),
        name: name || `Floor ${(this.plan.floors || []).length + 1}`,
        width: this._toMeters(parseFloat(w) || 8),
        height: this._toMeters(parseFloat(h) || 6),
        offsetX: 0, offsetY: 0,
        points: [{ x: 0, y: 0 }],
        walls: [], rooms: [], stairs: [],
      };
      this.plan.floors.push(floor);
      this.activeFloorId = floor.id;
      this.selectedPoint = null;
      this.selectedRoom = null;
      this._renderToolbar();
      this._render();
      this._save();
    };
    q("#fp-rename").onclick = async () => {
      const f = this._floor();
      if (!f) return;
      const name = await this.panel._showModal({ title: "Rename Floor", label: "Floor name", value: f.name });
      if (name == null) return;
      f.name = name;
      this._renderToolbar();
      this._render();
      this._save();
    };
    q("#fp-size").onclick = async () => {
      const f = this._floor();
      if (!f) return;
      const w = await this.panel._showModal({ title: "Floor Size", label: `Width (${this.plan.unit})`, value: this._display(f.width) });
      if (w == null) return;
      const h = await this.panel._showModal({ title: "Floor Size", label: `Height (${this.plan.unit})`, value: this._display(f.height) });
      if (h == null) return;
      f.width = Math.max(0.1, this._toMeters(parseFloat(w) || 0.1));
      f.height = Math.max(0.1, this._toMeters(parseFloat(h) || 0.1));
      this._render();
      this._save();
    };
    q("#fp-align").onclick = () => {
      const f = this._floor();
      if (!f) return;
      f.offsetX = 0; f.offsetY = 0;
      this._renderToolbar();
      this._render();
      this._save();
    };
    q("#fp-del").onclick = async () => {
      const f = this._floor();
      if (!f) return;
      const ok = await this.panel._showModal({ title: "Delete Floor", label: `Type DELETE to remove "${f.name}"` });
      if (ok !== "DELETE") return;
      this.plan.floors = this.plan.floors.filter((x) => x.id !== f.id);
      this.activeFloorId = this.plan.floors.length ? this.plan.floors[0].id : null;
      this.selectedPoint = null;
      this.selectedRoom = null;
      this._renderToolbar();
      this._render();
      this._save();
    };
    q("#fp-wallth").onchange = (e) => {
      this.plan.wallThickness = Math.max(0.01, this._toMeters(parseFloat(e.target.value) || 0.15));
      this._render();
      this._save();
    };
    q("#fp-lengths").onchange = (e) => { this.plan.showLengths = e.target.checked; this._render(); this._save(); };
    q("#fp-stair").onclick = () => {
      this.stairMode = !this.stairMode;
      q("#fp-stair").classList.toggle("on", this.stairMode);
      this._updateHint();
    };
  }

  _bindCanvas() {
    this.svg.addEventListener("mousedown", (e) => this._onMouseDown(e));
    this.svg.addEventListener("mousemove", (e) => this._onMouseMove(e));
    this.svg.addEventListener("mouseup", (e) => this._onMouseUp(e));
    this.svg.addEventListener("wheel", (e) => this._onWheel(e), { passive: false });
    this.svg.addEventListener("contextmenu", (e) => e.preventDefault());
    this.canvas.addEventListener("mousedown", () => this.canvas.focus());
    this.canvas.addEventListener("keydown", (e) => this._onKeyDown(e));
  }

  _floor() {
    if (!this.plan) return null;
    return (this.plan.floors || []).find((f) => f.id === this.activeFloorId) || null;
  }

  _unit() { return this.plan?.unit || "m"; }
  _display(m) { return this._unit() === "in" ? m * M_TO_IN : m; }
  _toMeters(v) { return this._unit() === "in" ? v / M_TO_IN : v; }

  _computeView() {
    const f = this._floor();
    if (!f) { this.view = { minX: -1, minY: -1, w: 10, h: 8 }; return; }
    const pad = 0.5;
    let minX = f.offsetX, minY = f.offsetY;
    let maxX = f.offsetX + f.width, maxY = f.offsetY + f.height;
    for (const p of f.points) {
      minX = Math.min(minX, f.offsetX + p.x); minY = Math.min(minY, f.offsetY + p.y);
      maxX = Math.max(maxX, f.offsetX + p.x); maxY = Math.max(maxY, f.offsetY + p.y);
    }
    for (const r of f.rooms) for (const i of r.points) {
      const p = f.points[i];
      if (p) {
        minX = Math.min(minX, f.offsetX + p.x); minY = Math.min(minY, f.offsetY + p.y);
        maxX = Math.max(maxX, f.offsetX + p.x); maxY = Math.max(maxY, f.offsetY + p.y);
      }
    }
    for (const s of f.stairs || []) {
      minX = Math.min(minX, f.offsetX + s.x); minY = Math.min(minY, f.offsetY + s.y);
      maxX = Math.max(maxX, f.offsetX + s.x); maxY = Math.max(maxY, f.offsetY + s.y);
    }
    for (const sc of Object.values(this.plan.scanners || {})) {
      if (sc.floorId === f.id) {
        minX = Math.min(minX, sc.x); minY = Math.min(minY, sc.y);
        maxX = Math.max(maxX, sc.x); maxY = Math.max(maxY, sc.y);
      }
    }
    if (maxX - minX < 1) maxX = minX + 1;
    if (maxY - minY < 1) maxY = minY + 1;
    this.view = { minX: minX - pad, minY: minY - pad, w: maxX - minX + pad * 2, h: maxY - minY + pad * 2 };
  }

  _zoom(factor) {
    const cx = this.view.minX + this.view.w / 2;
    const cy = this.view.minY + this.view.h / 2;
    this.view.w = Math.max(0.5, this.view.w / factor);
    this.view.h = Math.max(0.5, this.view.h / factor);
    this.view.minX = cx - this.view.w / 2;
    this.view.minY = cy - this.view.h / 2;
    this._render();
  }

  _onWheel(e) {
    if (this.viewMode !== "2d") return;
    e.preventDefault();
    const rect = this.svg.getBoundingClientRect();
    const factor = e.deltaY < 0 ? 1.25 : 1 / 1.25;
    const wx = this.view.minX + (e.clientX - rect.left) * (this.view.w / rect.width);
    const wy = this.view.minY + (e.clientY - rect.top) * (this.view.h / rect.height);
    this.view.w = Math.max(0.5, this.view.w / factor);
    this.view.h = Math.max(0.5, this.view.h / factor);
    this.view.minX = wx - (e.clientX - rect.left) * (this.view.w / rect.width);
    this.view.minY = wy - (e.clientY - rect.top) * (this.view.h / rect.height);
    this._render();
  }

  _screenToWorld(clientX, clientY) {
    const rect = this.svg.getBoundingClientRect();
    const v = this.view;
    return {
      x: v.minX + (clientX - rect.left) * (v.w / rect.width),
      y: v.minY + (clientY - rect.top) * (v.h / rect.height),
    };
  }

  _worldToFloor(w) {
    const f = this._floor();
    return { x: w.x - (f ? f.offsetX : 0), y: w.y - (f ? f.offsetY : 0) };
  }

  _snap(v) { return Math.round(v / this.snap) * this.snap; }

  _pointHit(w) {
    const f = this._floor();
    if (!f) return -1;
    const rect = this.svg.getBoundingClientRect();
    const thresh = 14 * (this.view.w / rect.width);
    let best = -1, bestD = thresh;
    f.points.forEach((p, i) => {
      const d = Math.hypot(f.offsetX + p.x - w.x, f.offsetY + p.y - w.y);
      if (d < bestD) { bestD = d; best = i; }
    });
    return best;
  }

  _scannerHit(w) {
    const f = this._floor();
    if (!f) return null;
    const rect = this.svg.getBoundingClientRect();
    const thresh = 16 * (this.view.w / rect.width);
    for (const [sid, sc] of Object.entries(this.plan.scanners || {})) {
      if (sc.floorId !== f.id) continue;
      const d = Math.hypot(sc.x - w.x, sc.y - w.y);
      if (d < thresh) return sid;
    }
    return null;
  }

  _roomHit(w) {
    const f = this._floor();
    if (!f) return null;
    for (let ri = 0; ri < f.rooms.length; ri++) {
      const room = f.rooms[ri];
      if (!room.points || room.points.length < 3) continue;
      if (room.points.some((i) => !f.points[i])) continue;
      const pts = room.points.map((i) => ({ x: f.offsetX + f.points[i].x, y: f.offsetY + f.points[i].y }));
      let inside = false;
      for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
        const xi = pts[i].x, yi = pts[i].y, xj = pts[j].x, yj = pts[j].y;
        if ((yi > w.y) !== (yj > w.y) && w.x < ((xj - xi) * (w.y - yi)) / (yj - yi) + xi) inside = !inside;
      }
      if (inside) return ri;
    }
    return null;
  }

  _getOrCreatePoint(floorPos) {
    const f = this._floor();
    if (!f) return -1;
    const wx = f.offsetX + this._snap(floorPos.x);
    const wy = f.offsetY + this._snap(floorPos.y);
    const idx = this._pointHit({ x: wx, y: wy });
    if (idx >= 0) return idx;
    f.points.push({ x: this._snap(floorPos.x), y: this._snap(floorPos.y) });
    return f.points.length - 1;
  }

  async _onMouseDown(e) {
    if (this.viewMode !== "2d") return;
    const f = this._floor();
    if (!f) return;
    const w = this._screenToWorld(e.clientX, e.clientY);
    if (e.button === 1) {
      e.preventDefault();
      this.panState = { startClientX: e.clientX, startClientY: e.clientY, startView: { ...this.view } };
      return;
    }
    if (e.button === 0) {
      const sid = this._scannerHit(w);
      if (sid) {
        this.scannerDrag = { sid, startClientX: e.clientX, startClientY: e.clientY, floorId: f.id };
        return;
      }
      if (this.stairMode) {
        const fp = this._worldToFloor(w);
        const sx = this._snap(fp.x), sy = this._snap(fp.y);
        const name = await this.panel._showModal({ title: "Staircase", label: "Staircase name", value: "Stairs" });
        if (name == null || !name.trim()) return;
        const others = (this.plan.floors || []).filter((fl) => fl.id !== f.id);
        let toFloorId = null;
        if (others.length === 1) {
          toFloorId = others[0].id;
        } else if (others.length > 1) {
          toFloorId = await this.panel._showModal({
            title: "Staircase Destination",
            label: "Which floor does it lead to?",
            select: true,
            options: others.map((fl) => ({ value: fl.id, label: fl.name })),
          });
          if (toFloorId == null) return;
        }
        f.stairs.push({ x: sx, y: sy, name: name.trim(), toFloorId });
        this._save();
        return;
      }
      const idx = this._pointHit(w);
      this.wallDrag = {
        startIdx: idx >= 0 ? idx : null,
        startWorld: { x: w.x, y: w.y },
        endWorld: { x: w.x, y: w.y },
        moved: false,
        pendingCreate: idx < 0,
      };
    } else if (e.button === 2) {
      this.roomDrag = {
        startWorld: { x: w.x, y: w.y },
        endWorld: { x: w.x, y: w.y },
        moved: false,
      };
    }
  }

  async _onMouseMove(e) {
    if (this.panState) {
      const rect = this.svg.getBoundingClientRect();
      const dx = (e.clientX - this.panState.startClientX) * (this.view.w / rect.width);
      const dy = (e.clientY - this.panState.startClientY) * (this.view.h / rect.height);
      this.view.minX = this.panState.startView.minX - dx;
      this.view.minY = this.panState.startView.minY - dy;
      this._render();
      return;
    }
    if (this.viewMode !== "2d") return;
    const w = this._screenToWorld(e.clientX, e.clientY);
    if (this.scannerDrag) {
      const f = this._floor();
      if (f) {
        const fp = this._worldToFloor(w);
        this.plan.scanners[this.scannerDrag.sid] = { floorId: f.id, x: this._snap(fp.x), y: this._snap(fp.y) };
        this._render();
      }
      return;
    }
    if (this.wallDrag && e.buttons & 1) {
      this.wallDrag.endWorld = { x: w.x, y: w.y };
      const d = Math.hypot(w.x - this.wallDrag.startWorld.x, w.y - this.wallDrag.startWorld.y);
      if (d > 0.02) this.wallDrag.moved = true;
      if (this.wallDrag.startIdx == null && this.wallDrag.moved) {
        this.wallDrag.startIdx = this._getOrCreatePoint(this._worldToFloor(this.wallDrag.startWorld));
      }
      this._render();
    } else if (this.roomDrag && e.buttons & 2) {
      this.roomDrag.endWorld = { x: w.x, y: w.y };
      const d = Math.hypot(w.x - this.roomDrag.startWorld.x, w.y - this.roomDrag.startWorld.y);
      if (d > 0.02) this.roomDrag.moved = true;
      this._render();
    }
  }

  async _onMouseUp(e) {
    const f = this._floor();
    if (!f) return;
    if (e.button === 1) { this.panState = null; return; }
    if (this.viewMode !== "2d") return;
    const w = this._screenToWorld(e.clientX, e.clientY);

    if (this.scannerDrag && e.button === 0) {
      this._save();
      this.scannerDrag = null;
      return;
    }

    if (e.button === 0 && this.wallDrag) {
      const drag = this.wallDrag;
      if (!drag.moved) {
        const roomIdx = this._roomHit(w);
        if (roomIdx != null) {
          this.selectedRoom = roomIdx;
          this.selectedPoint = null;
          this._renderRoomStrip();
          this._render();
        } else {
          const idx = this._pointHit(w);
          if (idx >= 0) {
            this.selectedPoint = idx;
          } else {
            this.selectedPoint = this._getOrCreatePoint(this._worldToFloor(w));
            this._save();
          }
          this.selectedRoom = null;
          this._renderRoomStrip();
        }
      } else {
        const startIdx = drag.startIdx != null ? drag.startIdx : this._getOrCreatePoint(this._worldToFloor(drag.startWorld));
        const endIdx = this._getOrCreatePoint(this._worldToFloor(w));
        if (startIdx !== endIdx) {
          const exists = f.walls.some((wl) =>
            (wl.a === startIdx && wl.b === endIdx) || (wl.a === endIdx && wl.b === startIdx));
          if (!exists) f.walls.push({ a: startIdx, b: endIdx });
        }
        this._save();
      }
      this.wallDrag = null;
    } else if (e.button === 2 && this.roomDrag) {
      const drag = this.roomDrag;
      if (drag.moved) {
        const minX = Math.min(drag.startWorld.x, drag.endWorld.x);
        const maxX = Math.max(drag.startWorld.x, drag.endWorld.x);
        const minY = Math.min(drag.startWorld.y, drag.endWorld.y);
        const maxY = Math.max(drag.startWorld.y, drag.endWorld.y);
        if (maxX - minX >= 0.3 && maxY - minY >= 0.3) {
          const tl = this._getOrCreatePoint(this._worldToFloor({ x: minX, y: minY }));
          const tr = this._getOrCreatePoint(this._worldToFloor({ x: maxX, y: minY }));
          const br = this._getOrCreatePoint(this._worldToFloor({ x: maxX, y: maxY }));
          const bl = this._getOrCreatePoint(this._worldToFloor({ x: minX, y: maxY }));
          const name = await this.panel._showModal({ title: "New Room", label: "Room name", value: "" });
          if (name != null && name.trim()) {
            f.rooms.push({ name: name.trim(), points: [tl, tr, br, bl], color: roomColor(name) });
            this.selectedRoom = f.rooms.length - 1;
            this._renderRoomStrip();
            this._save();
          }
        }
      }
      this.roomDrag = null;
    }
    this._render();
  }

  async _onKeyDown(e) {
    if (this.viewMode !== "2d") return;
    if (e.key === "Delete" || e.key === "Backspace") {
      if (this.selectedPoint != null && this._floor()) {
        this._deletePoint(this.selectedPoint);
        this.selectedPoint = null;
        this._save();
        this._render();
      }
      return;
    }
    const dirs = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
    const dir = dirs[e.key];
    const f = this._floor();
    if (!dir || !f || this.selectedPoint == null) return;
    e.preventDefault();
    const p = f.points[this.selectedPoint];
    const dist = await this.panel._showModal({
      title: `Extend ${e.key.replace("Arrow", "").toLowerCase()}`,
      label: `Distance (${this.plan.unit}) from (${Math.round(this._display(p.x) * 100) / 100}, ${Math.round(this._display(p.y) * 100) / 100})`,
      value: "1",
      inputType: "number",
    });
    if (dist == null) return;
    const d = Math.max(0, this._toMeters(parseFloat(dist) || 0));
    const np = { x: this._snap(p.x + dir[0] * d), y: this._snap(p.y + dir[1] * d) };
    f.points.push(np);
    const newIdx = f.points.length - 1;
    const exists = f.walls.some((wl) =>
      (wl.a === this.selectedPoint && wl.b === newIdx) || (wl.a === newIdx && wl.b === this.selectedPoint));
    if (!exists) f.walls.push({ a: this.selectedPoint, b: newIdx });
    this.selectedPoint = newIdx;
    this._save();
    this._render();
  }

  _deletePoint(idx) {
    const f = this._floor();
    if (!f) return;
    f.walls = f.walls.filter((wl) => wl.a !== idx && wl.b !== idx);
    f.rooms = f.rooms.filter((r) => !r.points.includes(idx)).map((r) => ({ ...r, points: r.points.map((p) => (p > idx ? p - 1 : p)) }));
    f.points.splice(idx, 1);
    f.walls = f.walls.map((wl) => ({ a: wl.a > idx ? wl.a - 1 : wl.a, b: wl.b > idx ? wl.b - 1 : wl.b }));
  }

  _renderRoomStrip() {
    const strip = this.container?.querySelector("#fp-roomstrip");
    if (!strip) return;
    const f = this._floor();
    const room = f && this.selectedRoom != null ? f.rooms[this.selectedRoom] : null;
    if (!room) { strip.style.display = "none"; strip.innerHTML = ""; return; }
    strip.style.display = "flex";
    strip.innerHTML = this._roomStripHTML();
    strip.querySelector("#fp-room-color").oninput = (e) => {
      room.color = e.target.value;
      this._render();
      this._save();
    };
    strip.querySelector("#fp-room-rename").onclick = async () => {
      const name = await this.panel._showModal({ title: "Rename Room", label: "Room name", value: room.name });
      if (name != null && name.trim()) { room.name = name.trim(); this._renderRoomStrip(); this._render(); this._save(); }
    };
    strip.querySelector("#fp-room-del").onclick = () => {
      f.rooms.splice(this.selectedRoom, 1);
      this.selectedRoom = null;
      this._renderRoomStrip();
      this._render();
      this._save();
    };
  }

  _updateHint() {
    const hint = this.container?.querySelector("#fp-hint");
    if (!hint) return;
    if (this.viewMode === "iso") {
      hint.textContent = "Isometric view - switch to 2D to edit. Wheel/middle-drag still works to navigate.";
    } else if (this.stairMode) {
      hint.textContent = "Stair mode: click on the map to place a staircase, then choose the floor it leads to.";
    } else {
      hint.textContent = "Click: place/select point  •  Arrow keys: extend point (asks distance)  •  Drag: draw wall  •  Right-drag: draw room  •  Wheel: zoom  •  Middle-drag: pan  •  Delete: remove selected point  •  Drag scanner markers to position them";
    }
  }

  _deviceMarkers() {
    const markers = [];
    const f = this._floor();
    if (!f || !this.plan.scanners) return markers;
    for (const d of this.devices) {
      const seen = d.seen_by || {};
      const entries = Object.entries(seen).filter(([sid]) => {
        const sc = this.plan.scanners[sid];
        return sc && sc.floorId === f.id;
      });
      if (!entries.length && d.server_id) {
        const sc = this.plan.scanners[d.server_id];
        if (sc && sc.floorId === f.id) entries.push([d.server_id, d.rssi]);
      }
      if (!entries.length) continue;
      let wx = 0, wy = 0, wt = 0;
      for (const [sid, rssi] of entries) {
        const sc = this.plan.scanners[sid];
        const wgt = Math.max(0, (rssi ?? -90) + 100);
        wx += sc.x * wgt; wy += sc.y * wgt; wt += wgt;
      }
      if (!wt) continue;
      markers.push({ x: wx / wt, y: wy / wt, name: d.name || d.address, rssi: d.rssi, address: d.address });
    }
    return markers;
  }

  _render() {
    if (!this.svg) return;
    const f = this._floor();
    if (this.viewMode === "iso") { this._renderIso(f); return; }
    this._computeView();
    const v = this.view;
    const u = this._unit();
    this.svg.setAttribute("viewBox", `${v.minX} ${v.minY} ${v.w} ${v.h}`);
    let inner = "";

    const step = 0.5;
    for (let gx = Math.floor(v.minX / step) * step; gx <= v.minX + v.w; gx += step) {
      const major = Math.abs(gx / step) % 2 === 0;
      inner += `<line x1="${gx}" y1="${v.minY}" x2="${gx}" y2="${v.minY + v.h}" stroke="${major ? "rgba(0,0,0,0.12)" : "rgba(0,0,0,0.05)"}" stroke-width="${major ? 0.02 : 0.01}"/>`;
    }
    for (let gy = Math.floor(v.minY / step) * step; gy <= v.minY + v.h; gy += step) {
      const major = Math.abs(gy / step) % 2 === 0;
      inner += `<line x1="${v.minX}" y1="${gy}" x2="${v.minX + v.w}" y2="${gy}" stroke="${major ? "rgba(0,0,0,0.12)" : "rgba(0,0,0,0.05)"}" stroke-width="${major ? 0.02 : 0.01}"/>`;
    }

    if (f) {
      const offX = f.offsetX, offY = f.offsetY;
      const wt = Math.max(0.02, f.wallThickness ?? this.plan.wallThickness ?? 0.15);

      inner += `<rect x="${offX}" y="${offY}" width="${f.width}" height="${f.height}" fill="none" stroke="var(--primary, #03a9f4)" stroke-width="0.03" stroke-dasharray="0.1 0.08"/>`;

      for (const room of f.rooms) {
        if (!room.points || room.points.length < 3) continue;
        if (room.points.some((i) => !f.points[i])) continue;
        const pts = room.points.map((i) => `${offX + f.points[i].x},${offY + f.points[i].y}`).join(" ");
        const xs = room.points.map((i) => f.points[i].x);
        const ys = room.points.map((i) => f.points[i].y);
        const cx = xs.reduce((s, x) => s + x, 0) / xs.length + offX;
        const cy = ys.reduce((s, y) => s + y, 0) / ys.length + offY;
        const bw = (Math.max(...xs) - Math.min(...xs)) * (this._unit() === "in" ? M_TO_IN : 1);
        const bh = (Math.max(...ys) - Math.min(...ys)) * (this._unit() === "in" ? M_TO_IN : 1);
        const fill = room.color || roomColor(room.name);
        const isSel = this.selectedRoom === f.rooms.indexOf(room);
        inner += `<polygon points="${pts}" fill="${esc(fill)}" fill-opacity="${isSel ? 0.28 : 0.15}" stroke="${esc(fill)}" stroke-width="${isSel ? 0.045 : 0.02}"/>`;
        inner += `<text x="${cx}" y="${cy - 0.08}" class="fp-room-label">${esc(room.name)}</text>`;
        inner += `<text x="${cx}" y="${cy + 0.12}" class="fp-room-label" style="font-size:8px">${Math.round(bw * 100) / 100} x ${Math.round(bh * 100) / 100} ${this._unit()}</text>`;
      }

      for (const wall of f.walls) {
        const a = f.points[wall.a], b = f.points[wall.b];
        if (!a || !b) continue;
        inner += `<line x1="${offX + a.x}" y1="${offY + a.y}" x2="${offX + b.x}" y2="${offY + b.y}" stroke="var(--text, #212121)" stroke-width="${wt}" stroke-linecap="round"/>`;
      }

      if (this.plan.showLengths !== false) {
        for (const wall of f.walls) {
          const a = f.points[wall.a], b = f.points[wall.b];
          if (!a || !b) continue;
          const mx = offX + (a.x + b.x) / 2;
          const my = offY + (a.y + b.y) / 2;
          const len = Math.hypot(a.x - b.x, a.y - b.y);
          inner += `<text x="${mx}" y="${my - 0.1}" class="fp-length-label">${_fmt(len, this._unit())}</text>`;
        }
      }

      for (const stair of f.stairs || []) {
        const sx = offX + stair.x, sy = offY + stair.y;
        inner += `<g>`;
        inner += `<rect x="${sx - 0.25}" y="${sy - 0.25}" width="0.5" height="0.5" fill="#B39DDB" fill-opacity="0.35" stroke="#7E57C2" stroke-width="0.02"/>`;
        for (let i = 0; i < 3; i++) {
          inner += `<line x1="${sx - 0.18 + i * 0.12}" y1="${sy + 0.18 - i * 0.12}" x2="${sx + 0.18 - (2 - i) * 0.12}" y2="${sy - 0.18 + (2 - i) * 0.12}" stroke="#7E57C2" stroke-width="0.02"/>`;
        }
        const target = this.plan.floors.find((fl) => fl.id === stair.toFloorId);
        inner += `<text x="${sx}" y="${sy - 0.3}" class="fp-room-label">${esc(stair.name)} → ${target ? esc(target.name) : "?"}</text>`;
        inner += `</g>`;
      }

      for (const marker of this._deviceMarkers()) {
        inner += `<circle class="fp-device" cx="${marker.x}" cy="${marker.y}" r="0.11" fill="${_rssiColor(marker.rssi)}" opacity="0.9" stroke="#fff" stroke-width="0.02"/>`;
        inner += `<text x="${marker.x}" y="${marker.y - 0.18}" class="fp-device-label fp-length-label">${esc(marker.name)}</text>`;
      }

      for (const [sid, sc] of Object.entries(this.plan.scanners || {})) {
        if (sc.floorId !== f.id) continue;
        inner += `<circle class="fp-marker" cx="${sc.x}" cy="${sc.y}" r="0.18" fill="var(--primary)" stroke="#fff" stroke-width="0.03"/>`;
        inner += `<circle class="fp-marker" cx="${sc.x}" cy="${sc.y}" r="0.3" fill="none" stroke="var(--primary)" stroke-width="0.02" opacity="0.5"/>`;
        inner += `<text x="${sc.x}" y="${sc.y - 0.3}" class="fp-room-label">Scanner: ${esc(sid)}</text>`;
      }

      f.points.forEach((p, i) => {
        inner += `<circle class="fp-point ${i === this.selectedPoint ? "selected" : ""}" cx="${offX + p.x}" cy="${offY + p.y}" r="0.09" fill="${i === this.selectedPoint ? "var(--primary)" : "var(--card-bg)"}" stroke="var(--primary, #03a9f4)" stroke-width="0.025"/>`;
      });

      if (this.wallDrag && this.wallDrag.moved && this.wallDrag.startIdx != null) {
        const a = f.points[this.wallDrag.startIdx];
        const b = this._worldToFloor(this.wallDrag.endWorld);
        inner += `<line x1="${offX + a.x}" y1="${offY + a.y}" x2="${offX + b.x}" y2="${offY + b.y}" stroke="var(--primary)" stroke-width="${wt}" stroke-dasharray="0.08 0.05" stroke-linecap="round" opacity="0.6"/>`;
      }

      if (this.roomDrag && this.roomDrag.moved) {
        const x1 = Math.min(this.roomDrag.startWorld.x, this.roomDrag.endWorld.x);
        const y1 = Math.min(this.roomDrag.startWorld.y, this.roomDrag.endWorld.y);
        const w2 = Math.abs(this.roomDrag.endWorld.x - this.roomDrag.startWorld.x);
        const h2 = Math.abs(this.roomDrag.endWorld.y - this.roomDrag.startWorld.y);
        inner += `<rect x="${x1}" y="${y1}" width="${w2}" height="${h2}" fill="var(--primary)" fill-opacity="0.12" stroke="var(--primary)" stroke-width="0.04" stroke-dasharray="0.08 0.05"/>`;
      }
    }

    this.svg.innerHTML = inner;
  }

  _isoView() {
    const v = this.view;
    const corners = [
      [v.minX, v.minY], [v.minX + v.w, v.minY],
      [v.minX, v.minY + v.h], [v.minX + v.w, v.minY + v.h],
    ];
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const [x, y] of corners) {
      const p = iso(x, y, 0);
      minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
      minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y);
    }
    return { minX, minY, w: maxX - minX, h: maxY - minY + WALL_H };
  }

  _renderIso(f) {
    const v = this._isoView();
    const u = this._unit();
    this.svg.setAttribute("viewBox", `${v.minX} ${v.minY - WALL_H} ${v.w} ${v.h}`);
    let inner = "";
    const P = (x, y, z) => { const p = iso(x, y, z); return `${p.x.toFixed(3)},${p.y.toFixed(3)}`; };

    if (f) {
      const offX = f.offsetX, offY = f.offsetY;
      const wt = Math.max(0.02, f.wallThickness ?? this.plan.wallThickness ?? 0.15);
      const floorPts = [
        [offX, offY], [offX + f.width, offY],
        [offX + f.width, offY + f.height], [offX, offY + f.height],
      ];

      inner += `<polygon points="${floorPts.map((p) => P(p[0], p[1], 0)).join(" ")}" fill="#ECEFF1" stroke="#B0BEC5" stroke-width="0.03"/>`;

      const roomPolys = [];
      for (const room of f.rooms) {
        if (!room.points || room.points.length < 3) continue;
        if (room.points.some((i) => !f.points[i])) continue;
        const pts = room.points.map((i) => ({ x: offX + f.points[i].x, y: offY + f.points[i].y }));
        const fill = room.color || roomColor(room.name);
        const z = 0.15;
        const shadow = pts.map((p) => P(p.x, p.y, 0)).join(" ");
        const top = pts.map((p) => P(p.x, p.y, z)).join(" ");
        roomPolys.push({ fill, top, shadow, room, z });
      }

      roomPolys.sort((a, b) => {
        const sum = (rp) => rp.room.points.reduce((s, i) => s + f.points[i].x + f.points[i].y, 0) / rp.room.points.length;
        return sum(a) - sum(b);
      });
      for (const rp of roomPolys) {
        inner += `<polygon points="${rp.shadow}" fill="#455A64" fill-opacity="0.25"/>`;
        inner += `<polygon points="${rp.top}" fill="${rp.fill}" fill-opacity="0.75" stroke="${rp.fill}" stroke-width="0.02"/>`;
      }

      const walls = [];
      for (const wall of f.walls) {
        const a = f.points[wall.a], b = f.points[wall.b];
        if (!a || !b) continue;
        const p1 = { x: offX + a.x, y: offY + a.y };
        const p2 = { x: offX + b.x, y: offY + b.y };
        walls.push({ p1, p2, depth: (p1.x + p1.y + p2.x + p2.y) / 2 });
      }
      walls.sort((x, y) => x.depth - y.depth);

      for (const wl of walls) {
        const { p1, p2 } = wl;
        const dx = p2.x - p1.x, dy = p2.y - p1.y;
        const len = Math.hypot(dx, dy) || 1e-6;
        const px = (-dy / len) * (wt / 2), py = (dx / len) * (wt / 2);
        const A = { x: p1.x + px, y: p1.y + py };
        const B = { x: p2.x + px, y: p2.y + py };
        const C = { x: p2.x - px, y: p2.y - py };
        const D = { x: p1.x - px, y: p1.y - py };
        const frontIsAB = px + py >= 0;
        const front = frontIsAB ? [A, B] : [D, C];
        const back = frontIsAB ? [D, C] : [A, B];
        const h = WALL_H;
        inner += `<polygon points="${P(front[0].x, front[0].y, 0)} ${P(front[1].x, front[1].y, 0)} ${P(front[1].x, front[1].y, h)} ${P(front[0].x, front[0].y, h)}" fill="#78909C" stroke="#546E7A" stroke-width="0.02"/>`;
        inner += `<polygon points="${P(back[0].x, back[0].y, 0)} ${P(back[1].x, back[1].y, 0)} ${P(back[1].x, back[1].y, h)} ${P(back[0].x, back[0].y, h)}" fill="#607D8B" stroke="#546E7A" stroke-width="0.02"/>`;
        inner += `<polygon points="${P(A.x, A.y, h)} ${P(B.x, B.y, h)} ${P(C.x, C.y, h)} ${P(D.x, D.y, h)}" fill="#90A4AE" stroke="#78909C" stroke-width="0.02"/>`;
      }

      for (const stair of f.stairs || []) {
        const sx = offX + stair.x, sy = offY + stair.y;
        const steps = 4;
        for (let i = 0; i < steps; i++) {
          const s = 0.5 * (1 - (i / steps) * 0.6);
          const z = (i / steps) * 0.8;
          const x1 = sx - s / 2, y1 = sy - s / 2;
          const x2 = sx + s / 2, y2 = sy + s / 2;
          inner += `<polygon points="${P(x1, y1, z)} ${P(x2, y1, z)} ${P(x2, y2, z)} ${P(x1, y2, z)}" fill="#9575CD" stroke="#7E57C2" stroke-width="0.02"/>`;
          inner += `<polygon points="${P(x1, y2, z)} ${P(x2, y2, z)} ${P(x2, y2, z + 0.15)} ${P(x1, y2, z + 0.15)}" fill="#B39DDB" stroke="#7E57C2" stroke-width="0.015"/>`;
        }
        const target = this.plan.floors.find((fl) => fl.id === stair.toFloorId);
        inner += `<text class="fp-room-label" transform="translate(${iso(sx, sy, 1.1).x} ${iso(sx, sy, 1.1).y})">${esc(stair.name)} → ${target ? esc(target.name) : "?"}</text>`;
      }

      for (const marker of this._deviceMarkers()) {
        const c = _rssiColor(marker.rssi);
        inner += `<circle cx="${iso(marker.x, marker.y, 0.5).x}" cy="${iso(marker.x, marker.y, 0.5).y}" r="0.09" fill="${c}" stroke="#fff" stroke-width="0.02"/>`;
        inner += `<text class="fp-length-label" transform="translate(${iso(marker.x, marker.y, 0.8).x} ${iso(marker.x, marker.y, 0.8).y})">${esc(marker.name)}</text>`;
      }

      for (const [sid, sc] of Object.entries(this.plan.scanners || {})) {
        if (sc.floorId !== f.id) continue;
        inner += `<circle cx="${iso(sc.x, sc.y, 0.6).x}" cy="${iso(sc.x, sc.y, 0.6).y}" r="0.14" fill="var(--primary)" stroke="#fff" stroke-width="0.03"/>`;
        inner += `<text class="fp-room-label" transform="translate(${iso(sc.x, sc.y, 1).x} ${iso(sc.x, sc.y, 1).y})">${esc(sid)}</text>`;
      }
    }

    this.svg.innerHTML = inner;
  }

  updateDevices(devices) {
    this.devices = devices || [];
    this.lastDeviceUpdate = Date.now();
    if (this.svg) this._render();
  }

  async _load() {
    if (!this.panel._hass) return;
    try {
      const r = await this.panel._hass.callWS({ type: "spatialha/floorplan/get" });
      this.plan = r;
      if (!this.plan.floors || !this.plan.floors.length) this.plan.floors = [];
      if (!this.plan.unit) this.plan.unit = "m";
      if (!this.plan.scanners) this.plan.scanners = {};
      if (this.plan.wallThickness == null) this.plan.wallThickness = 0.15;
      this.activeFloorId = this.plan.floors.length ? this.plan.floors[0].id : null;
      this.selectedPoint = null;
      this.selectedRoom = null;
    } catch (e) {
      this.plan = { unit: "m", wallThickness: 0.15, floors: [], scanners: {} };
    }
  }

  _save() {
    if (!this.plan) return;
    const ind = this.container?.querySelector("#fp-save");
    if (ind) ind.textContent = "Saving...";
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(async () => {
      try {
        await this.panel._hass.callWS({ type: "spatialha/floorplan/save", plan: this.plan });
        if (ind) ind.textContent = "Saved";
      } catch {
        if (ind) ind.textContent = "Save failed";
      }
    }, 800);
  }
}

class SpatialHAPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._currentTab = "overview";
    this._sidebarOpen = true;
    this._version = "";
    this._devices = [];
    this._servers = [];
    this._config = {};
    this._editConfig = {};
    this._saveStatus = "";
    this._bleFilter = "";
    this._bleSort = "rssi";
    this._bleExpanded = new Set();
    this._editor = null;
    this._editorInit = false;
    this._pollTimer = null;
    this._pollInterval = 5;
    this._monitorUnsub = null;
    this._monitorLog = [];
    this._monitorError = "";
    this._uiState = this._loadUIState();
  }

  connectedCallback() {
    this.shadowRoot.appendChild(TPL.content.cloneNode(true));
    this.shadowRoot.getElementById("toggleBtn").onclick = () => this._toggleSidebar();
    this.shadowRoot.querySelectorAll(".nav-item").forEach((el) => {
      el.onclick = () => this._switchTab(el.dataset.tab);
    });
    if (this._uiState.tab && TAB_IDS.includes(this._uiState.tab)) {
      this._switchTab(this._uiState.tab);
    }
    if (this._uiState.sidebar === false) {
      this._sidebarOpen = false;
      this.shadowRoot.getElementById("sidebar").classList.add("collapsed");
    }
    this._fetchVersion();
    this._fetchDevices();
    this._fetchConfig();
  }

  disconnectedCallback() {
    if (this._pollTimer) clearInterval(this._pollTimer);
    if (this._monitorUnsub) {
      this._monitorUnsub();
      this._monitorUnsub = null;
    }
  }

  async _toggleMonitor() {
    if (!this._hass || !this._hass.connection) return;
    if (this._monitorUnsub) {
      this._monitorUnsub();
      this._monitorUnsub = null;
      this._updateTab("ble");
      return;
    }
    this._monitorLog = [];
    this._monitorError = "";
    try {
      this._monitorUnsub = await this._hass.connection.subscribeMessage((evt) => {
        const e = evt.event || {};
        this._monitorLog.push(`[${new Date((e.time || 0) * 1000).toLocaleTimeString()}] ${e.topic}  ${e.payload}`);
        if (this._monitorLog.length > 200) this._monitorLog.shift();
        const box = this.shadowRoot.getElementById("mqttMonitorBox");
        if (box) box.textContent = this._monitorLog.join("\n");
      }, { type: "spatialha/mqtt/monitor", subscribe: true });
    } catch (err) {
      this._monitorError = `Monitor failed to start: ${(err && err.message) || err || "unknown error"}`;
      this._monitorUnsub = null;
    }
    this._updateTab("ble");
  }

  set hass(hass) {
    this._hass = hass;
    this._fetchVersion();
    this._fetchDevices();
    this._fetchConfig();
  }

  _loadUIState() {
    try { return JSON.parse(localStorage.getItem("spatialha.ui") || "{}") || {}; } catch { return {}; }
  }

  _saveUIState() {
    try {
      localStorage.setItem("spatialha.ui", JSON.stringify({ tab: this._currentTab, sidebar: this._sidebarOpen }));
    } catch {}
  }

  _applyPollInterval() {
    const iv = Math.max(1, parseInt(this._config.update_interval) || 5);
    if (iv === this._pollInterval && this._pollTimer) return;
    this._pollInterval = iv;
    if (this._pollTimer) clearInterval(this._pollTimer);
    this._pollTimer = setInterval(() => this._fetchDevices(), this._pollInterval * 1000);
  }

  _showModal({ title, label, value, placeholder, inputType, select, options }) {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay";
      const control = select
        ? `<select>${(options || []).map((o) => `<option value="${esc(o.value)}">${esc(o.label)}</option>`).join("")}</select>`
        : `<input type="${inputType || "text"}" value="${esc(value ?? "")}" placeholder="${esc(placeholder || "")}" />`;
      overlay.innerHTML = `
        <div class="modal">
          <h3>${esc(title)}</h3>
          <div class="field">
            <label>${esc(label)}</label>
            ${control}
          </div>
          <div class="modal-actions">
            <button class="btn btn-secondary" data-act="cancel">Cancel</button>
            <button class="btn" data-act="ok">OK</button>
          </div>
        </div>`;
      const controlEl = overlay.querySelector("input, select");
      const done = (v) => { overlay.remove(); resolve(v); };
      overlay.querySelector('[data-act="ok"]').onclick = () => done(controlEl.value);
      overlay.querySelector('[data-act="cancel"]').onclick = () => done(null);
      controlEl.onkeydown = (e) => {
        if (e.key === "Enter") done(controlEl.value);
        if (e.key === "Escape") done(null);
      };
      this.shadowRoot.appendChild(overlay);
      controlEl.focus();
      if (controlEl.select) controlEl.select();
    });
  }

  _setStatusChip() {
    const chip = this.shadowRoot.getElementById("statusChip");
    if (!chip) return;
    if (!this._config.mqtt_host) {
      chip.className = "status-chip";
      chip.innerHTML = '<span class="dot"></span>MQTT: Not configured';
    } else if (this._config.mqtt_connected) {
      chip.className = "status-chip ok";
      chip.innerHTML = '<span class="dot"></span>MQTT: Connected';
    } else {
      chip.className = "status-chip bad";
      chip.innerHTML = '<span class="dot"></span>MQTT: Disconnected';
    }
  }

  async _fetchVersion() {
    if (!this._hass) return;
    try {
      const r = await this._hass.callWS({ type: "spatialha/version" });
      this._version = r.version;
      const f = this.shadowRoot.getElementById("versionFooter");
      if (f) f.textContent = `Version ${this._version}`;
      this._updateTab("overview");
      this._updateTab("about");
    } catch {}
  }

  async _fetchDevices() {
    if (!this._hass) return;
    try {
      const r = await this._hass.callWS({ type: "spatialha/ble/devices" });
      this._devices = r.devices || [];
      this._servers = r.servers || [];
      if (r.mqtt_connected !== undefined && r.mqtt_connected !== this._config.mqtt_connected) {
        this._config.mqtt_connected = r.mqtt_connected;
        this._setStatusChip();
      }
      this._updateTab("ble");
      this._updateTab("overview");
      if (this._editor) this._editor.updateDevices(this._devices);
    } catch {}
  }

  async _fetchConfig() {
    if (!this._hass) return;
    try {
      const r = await this._hass.callWS({ type: "spatialha/config" });
      this._config = r;
      this._editConfig = { ...r };
      this._setStatusChip();
      this._applyPollInterval();
      this._updateTab("settings");
      this._updateTab("overview");
    } catch {}
  }

  async _saveConfig() {
    if (!this._hass) return;
    this._saveStatus = "Saving...";
    this._updateTab("settings");
    const payload = {
      mqtt_host: this._editConfig.mqtt_host,
      mqtt_port: this._editConfig.mqtt_port,
      mqtt_username: this._editConfig.mqtt_username,
      update_interval: this._editConfig.update_interval,
    };
    if (this._editConfig.mqtt_password) payload.mqtt_password = this._editConfig.mqtt_password;
    try {
      await this._hass.callWS({ type: "spatialha/update_config", ...payload });
      this._config = { ...this._editConfig };
      this._saveStatus = "Saved";
      this._setStatusChip();
      this._applyPollInterval();
    } catch {
      this._saveStatus = "Error saving";
    }
    this._updateTab("settings");
    setTimeout(() => { this._saveStatus = ""; this._updateTab("settings"); }, 4000);
  }

  _toggleSidebar() {
    this._sidebarOpen = !this._sidebarOpen;
    this.shadowRoot.getElementById("sidebar").classList.toggle("collapsed", !this._sidebarOpen);
    this._saveUIState();
  }

  _switchTab(tab) {
    this._currentTab = tab;
    this.shadowRoot.querySelectorAll(".nav-item").forEach((el) =>
      el.classList.toggle("active", el.dataset.tab === tab)
    );
    this.shadowRoot.querySelectorAll(".tab-content").forEach((el) =>
      el.classList.toggle("active", el.id === `tab-${tab}`)
    );
    if (tab === "floorplan" && !this._editorInit) {
      this._editorInit = true;
      const container = this.shadowRoot.getElementById("tab-floorplan");
      container.innerHTML = '<div class="fp-wrap"></div>';
      this._editor = new FloorPlanEditor(this, container.querySelector(".fp-wrap"));
      this._editor.init().then(() => {
        if (this._devices.length) this._editor.updateDevices(this._devices);
      });
    }
    this._updateTab(tab);
    this._saveUIState();
  }

  _updateTab(tab) {
    if (!tab) tab = this._currentTab;
    const el = this.shadowRoot.getElementById(`tab-${tab}`);
    if (!el) return;
    if (tab === "overview") {
      const mqttOk = !!this._config.mqtt_host && !!this._config.mqtt_connected;
      const mqttStatus = !this._config.mqtt_host ? "Not configured" : (this._config.mqtt_connected ? "Connected" : "Disconnected");
      el.innerHTML = `
        <div class="stat-grid">
          <div class="stat-card">
            <div class="stat-label">MQTT Broker</div>
            <div class="stat-value" style="font-size:18px;color:${mqttOk ? "#2e7d32" : "#c62828"}">${mqttStatus}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Scanners</div>
            <div class="stat-value">${this._servers.length}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">BLE Devices</div>
            <div class="stat-value">${this._devices.length}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Version</div>
            <div class="stat-value">${this._version || "..."}</div>
          </div>
        </div>
        <div class="card">
          <h2>Overview</h2>
          <div class="label">Status</div>
          <div class="value"><span class="status-badge ${mqttOk ? "status-online" : "status-offline"}">${mqttStatus}</span></div>
          <p>SpatialHA is your spatial awareness hub for Home Assistant. Track BLE devices, build floor plans, and map your space.</p>
          ${!this._config.mqtt_host ? `<p><span class="status-badge status-idle">Tip</span> Configure your MQTT broker in the Settings tab to start detecting SpatialBLE devices.</p>` : ""}
        </div>
      `;
    } else if (tab === "settings") {
      el.innerHTML = `
        <div class="card">
          <h2>MQTT Broker</h2>
          <div class="field">
            <label>Hostname</label>
            <input id="f-host" value="${esc(this._editConfig.mqtt_host || "")}" placeholder="e.g. 192.168.1.100" />
          </div>
          <div class="field">
            <label>Port</label>
            <input id="f-port" type="number" value="${esc(this._editConfig.mqtt_port || 1883)}" />
          </div>
          <div class="field">
            <label>Username</label>
            <input id="f-user" value="${esc(this._editConfig.mqtt_username || "")}" placeholder="(optional)" />
          </div>
          <div class="field">
            <label>Password</label>
            <input id="f-pass" type="password" value="${esc(this._editConfig.mqtt_password || "")}" placeholder="(optional)" />
          </div>
          <div class="field">
            <label>Live update interval (seconds)</label>
            <input id="f-interval" type="number" min="1" value="${esc(this._editConfig.update_interval || 5)}" />
          </div>
          <button class="btn" id="saveConfigBtn">Save</button>
          ${this._saveStatus ? `<span style="margin-left:10px;font-size:13px;color:var(--text-secondary)">${esc(this._saveStatus)}</span>` : ""}
          <p style="margin-top:12px;font-size:12px;color:var(--text-secondary)">MQTT changes take effect immediately. The update interval applies to live refresh.</p>
        </div>
        <div class="card">
          <h2>Active Servers</h2>
          ${this._servers.length === 0 ? '<div class="empty">No servers detected</div>' :
            this._servers.map(s => `
              <div class="device-row">
                <div class="device-info">
                  <div class="device-name">${esc(s.server_id)}</div>
                  <div class="device-addr">OTA: ${esc(s.ota_ip)}:${esc(s.ota_port)} &middot; ${_timeAgo(s.last_seen)}</div>
                </div>
              </div>
            `).join("")
          }
        </div>
      `;
      const saveBtn = el.querySelector("#saveConfigBtn");
      if (saveBtn) saveBtn.onclick = () => this._saveConfig();
      ["host", "port", "user", "pass", "interval"].forEach((k) => {
        const inp = el.querySelector(`#f-${k}`);
        if (inp) inp.oninput = () => {
          if (k === "port") this._editConfig.mqtt_port = parseInt(inp.value) || 1883;
          else if (k === "interval") this._editConfig.update_interval = parseInt(inp.value) || 5;
          else this._editConfig[`mqtt_${k === "user" ? "username" : k}`] = inp.value;
        };
      });
    } else if (tab === "ble") {
      const q = this._bleFilter.toLowerCase();
      let devices = this._devices.filter((d) =>
        (d.name || "").toLowerCase().includes(q) || (d.address || "").toLowerCase().includes(q));
      if (this._bleSort === "rssi") devices.sort((a, b) => (b.rssi ?? -99) - (a.rssi ?? -99));
      else if (this._bleSort === "name") devices.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
      else if (this._bleSort === "seen") devices.sort((a, b) => (b.last_seen ?? 0) - (a.last_seen ?? 0));
      el.innerHTML = `
        <div class="card">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
            <h2 style="flex:1;margin:0">BLE Devices</h2>
            <button class="btn btn-secondary" id="bleRefresh">Refresh</button>
          </div>
          <div class="search-row">
            <input id="bleFilter" type="text" placeholder="Search by name or address..." value="${esc(this._bleFilter)}" />
            <select id="bleSort">
              <option value="rssi" ${this._bleSort === "rssi" ? "selected" : ""}>Sort: Signal strength</option>
              <option value="name" ${this._bleSort === "name" ? "selected" : ""}>Sort: Name</option>
              <option value="seen" ${this._bleSort === "seen" ? "selected" : ""}>Sort: Last seen</option>
            </select>
          </div>
          ${devices.length === 0 ?
            (this._devices.length === 0 ? '<div class="empty">No BLE devices detected yet. Use the MQTT Monitor below to verify messages are arriving from your SpatialBLE scanners.</div>' : '<div class="empty">No devices match your search.</div>')
            : devices.map(d => `
              <div class="device-row ${this._bleExpanded.has(d.address) ? "expanded" : ""}" data-addr="${esc(d.address)}">
                <div class="device-info">
                  <div class="device-name">${esc(d.name) || "Unknown"}</div>
                  <div class="device-addr">${esc(d.address)} &middot; ${esc(d.server_id) || "?"} &middot; ${_timeAgo(d.last_seen)}</div>
                </div>
                <div class="device-rssi ${_rssiClass(d.rssi)}">${d.rssi != null ? d.rssi + " dBm" : "—"}</div>
              </div>
              <div class="device-details" data-details="${esc(d.address)}">
                ${d.rssi != null ? `<div><span class="detail-label">RSSI:</span> ${d.rssi} dBm</div>` : ""}
                ${d.tx_power != null ? `<div><span class="detail-label">TX Power:</span> ${d.tx_power} dBm</div>` : ""}
                ${d.manufacturer_data && Object.keys(d.manufacturer_data).length ? `<div><span class="detail-label">Manufacturer Data:</span><br/><code>${Object.entries(d.manufacturer_data).map(([k, v]) => `${esc(k)}: ${esc(v)}`).join("<br/>")}</code></div>` : ""}
                ${d.service_uuids && d.service_uuids.length ? `<div><span class="detail-label">Service UUIDs:</span><br/><code>${d.service_uuids.map((u) => esc(u)).join(", ")}</code></div>` : ""}
                ${d.seen_by && Object.keys(d.seen_by).length ? `<div><span class="detail-label">Seen by:</span><br/><code>${Object.entries(d.seen_by).map(([k, v]) => `${esc(k)} (${esc(v)} dBm)`).join("<br/>")}</code></div>` : ""}
                <div><span class="detail-label">Last seen:</span> ${new Date((d.last_seen || 0) * 1000).toLocaleString()}</div>
              </div>
            `).join("")
          }
        </div>
      `;
      el.querySelector("#bleRefresh").onclick = () => this._fetchDevices();
      el.querySelector("#bleFilter").oninput = (e) => {
        this._bleFilter = e.target.value;
        const caret = e.target.selectionStart ?? e.target.value.length;
        this._updateTab("ble");
        const restored = el.querySelector("#bleFilter");
        restored.focus();
        restored.setSelectionRange(caret, caret);
      };
      el.querySelector("#bleSort").onchange = (e) => { this._bleSort = e.target.value; this._updateTab("ble"); };
      el.querySelectorAll(".device-row").forEach((row) => {
        row.onclick = () => {
          const addr = row.dataset.addr;
          if (this._bleExpanded.has(addr)) this._bleExpanded.delete(addr);
          else this._bleExpanded.add(addr);
          this._updateTab("ble");
        };
      });
      el.innerHTML += `
        <div class="card">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
            <h2 style="flex:1;margin:0">MQTT Monitor</h2>
            <button class="btn ${this._monitorUnsub ? "" : "btn-secondary"}" id="mqttMonitorToggle">${this._monitorUnsub ? "Stop" : "Start"}</button>
          </div>
          <p style="font-size:12px;color:var(--text-secondary)">Live view of every message published on the <code>spatialble/#</code> topic. Useful for verifying that scanners are actually transmitting.</p>
          <div id="mqttMonitorBox" style="font-family:monospace;font-size:11px;background:var(--sidebar-bg);border:1px solid var(--divider);border-radius:8px;padding:10px;height:200px;overflow-y:auto;white-space:pre-wrap;word-break:break-all">${this._monitorError
            ? esc(this._monitorError)
            : this._monitorUnsub
              ? (this._monitorLog.length ? esc(this._monitorLog.join("\n")) : "Monitoring... waiting for messages on spatialble/#. If nothing appears, check that your scanners are publishing and the broker is reachable.")
              : "Monitor is off. Click Start to begin capturing messages."}</div>
        </div>`;
      el.querySelector("#mqttMonitorToggle").onclick = () => this._toggleMonitor();
    } else if (tab === "about") {
      el.innerHTML = `
        <div class="card">
          <h2>About SpatialHA</h2>
          <div class="label">Version</div>
          <div class="value">${this._version || "..."}</div>
          <div class="label">Status</div>
          <div class="value"><span class="status-badge status-online">Connected</span></div>
          <div class="label">Integration</div>
          <div class="value">SpatialHA for Home Assistant</div>
          <p>A spatial awareness integration for Home Assistant, enabling BLE device tracking, floor plan mapping, and spatial computing capabilities.</p>
        </div>
      `;
    }
  }
}

customElements.define("spatialha-panel", SpatialHAPanel);
