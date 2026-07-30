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
  .toolbar-title { font-size: 16px; font-weight: 500; margin-left: 12px; color: var(--text); }
  .tab-content { display: none; }
  .tab-content.active { display: block; }
  .card {
    background: var(--card-bg); border: 1px solid var(--divider);
    border-radius: 8px; padding: 16px; margin-bottom: 16px;
  }
  .card h2 { margin: 0 0 12px; font-size: 18px; font-weight: 500; }
  .card p { margin: 4px 0; color: var(--text); line-height: 1.5; }
  .label { color: var(--text-secondary); font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
  .value { font-size: 14px; font-weight: 500; margin-bottom: 10px; }
  .device-row {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 0; border-bottom: 1px solid var(--divider);
  }
  .device-row:last-child { border-bottom: none; }
  .device-info { flex: 1; }
  .device-name { font-weight: 500; font-size: 14px; }
  .device-addr { font-size: 12px; color: var(--text-secondary); font-family: monospace; }
  .device-rssi { font-size: 13px; font-weight: 500; white-space: nowrap; }
  .rssi-weak { color: #f44336; }
  .rssi-ok { color: #ff9800; }
  .rssi-good { color: #4caf50; }
  .field { margin-bottom: 12px; }
  .field label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
  .field input {
    width: 100%; padding: 8px 10px; border: 1px solid var(--divider);
    border-radius: 6px; font-size: 14px; background: var(--card-bg);
    color: var(--text); outline: none;
  }
  .field input:focus { border-color: var(--primary); }
  .btn {
    background: var(--primary); color: #fff; border: none;
    padding: 8px 20px; border-radius: 6px; font-size: 14px; cursor: pointer;
  }
  .btn:hover { opacity: 0.9; }
  .status-badge {
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 11px; font-weight: 500;
  }
  .status-online { background: #e8f5e9; color: #2e7d32; }
  .status-offline { background: #fbe9e7; color: #c62828; }
  .empty { color: var(--text-secondary); text-align: center; padding: 40px 0; font-style: italic; }
  .section-title { font-size: 13px; font-weight: 500; color: var(--text-secondary); margin: 16px 0 8px; text-transform: uppercase; letter-spacing: 0.5px; }
</style>
<div class="toolbar">
  <button class="toolbar-btn" id="toggleBtn">
    <svg viewBox="0 0 24 24"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>
  </button>
  <span class="toolbar-title">SpatialHA</span>
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
    <div class="tab-content" id="tab-about"></div>
  </div>
</div>
`;

const TAB_IDS = ["overview", "settings", "ble", "about"];

const _rssiClass = (rssi) => {
  if (rssi == null) return "";
  if (rssi >= -70) return "rssi-good";
  if (rssi >= -85) return "rssi-ok";
  return "rssi-weak";
};

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
  }

  connectedCallback() {
    this.shadowRoot.appendChild(TPL.content.cloneNode(true));
    this.shadowRoot.getElementById("toggleBtn").onclick = () => this._toggleSidebar();
    this.shadowRoot.querySelectorAll(".nav-item").forEach((el) => {
      el.onclick = () => this._switchTab(el.dataset.tab);
    });
    this.shadowRoot.getElementById("saveConfigBtn")?.addEventListener("click", () => this._saveConfig());
    this._fetchVersion();
    this._fetchDevices();
    this._fetchConfig();
    this._pollInterval = setInterval(() => this._fetchDevices(), 5000);
  }

  disconnectedCallback() {
    if (this._pollInterval) clearInterval(this._pollInterval);
  }

  set hass(hass) {
    this._hass = hass;
    this._fetchVersion();
    this._fetchDevices();
    this._fetchConfig();
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
      this._updateTab("ble");
    } catch {}
  }

  async _fetchConfig() {
    if (!this._hass) return;
    try {
      const r = await this._hass.callWS({ type: "spatialha/config" });
      this._config = r;
      this._editConfig = { ...r };
      this._updateTab("settings");
    } catch {}
  }

  async _saveConfig() {
    if (!this._hass) return;
    this._saveStatus = "Saving...";
    this._updateTab("settings");
    try {
      await this._hass.callWS({ type: "spatialha/update_config", ...this._editConfig });
      this._config = { ...this._editConfig };
      this._saveStatus = "Saved!";
    } catch {
      this._saveStatus = "Error saving";
    }
    this._updateTab("settings");
    setTimeout(() => { this._saveStatus = ""; this._updateTab("settings"); }, 3000);
  }

  _toggleSidebar() {
    this._sidebarOpen = !this._sidebarOpen;
    this.shadowRoot.getElementById("sidebar").classList.toggle("collapsed", !this._sidebarOpen);
  }

  _switchTab(tab) {
    this._currentTab = tab;
    this.shadowRoot.querySelectorAll(".nav-item").forEach((el) =>
      el.classList.toggle("active", el.dataset.tab === tab)
    );
    this.shadowRoot.querySelectorAll(".tab-content").forEach((el) =>
      el.classList.toggle("active", el.id === `tab-${tab}`)
    );
    this._updateTab(tab);
  }

  _updateTab(tab) {
    if (!tab) tab = this._currentTab;
    const el = this.shadowRoot.getElementById(`tab-${tab}`);
    if (!el) return;
    if (tab === "overview") {
      el.innerHTML = `
        <div class="card">
          <h2>Overview</h2>
          <div class="label">Status</div>
          <div class="value"><span class="status-badge status-online">Connected</span></div>
          <div class="label">Version</div>
          <div class="value">${this._version || "..."}</div>
          <p>SpatialHA is your spatial awareness hub for Home Assistant.</p>
        </div>
      `;
    } else if (tab === "settings") {
      el.innerHTML = `
        <div class="card">
          <h2>MQTT Broker</h2>
          <div class="field">
            <label>Hostname</label>
            <input id="f-host" value="${this._editConfig.mqtt_host || ""}" placeholder="e.g. 192.168.1.100" />
          </div>
          <div class="field">
            <label>Port</label>
            <input id="f-port" type="number" value="${this._editConfig.mqtt_port || 1883}" />
          </div>
          <div class="field">
            <label>Username</label>
            <input id="f-user" value="${this._editConfig.mqtt_username || ""}" placeholder="(optional)" />
          </div>
          <div class="field">
            <label>Password</label>
            <input id="f-pass" type="password" value="${this._editConfig.mqtt_password || ""}" placeholder="(optional)" />
          </div>
          <button class="btn" id="saveConfigBtn">Save</button>
          ${this._saveStatus ? `<span style="margin-left:10px;font-size:13px;color:var(--text-secondary)">${this._saveStatus}</span>` : ""}
        </div>
        <div class="card">
          <h2>Active Servers</h2>
          ${this._servers.length === 0 ? '<div class="empty">No servers detected</div>' :
            this._servers.map(s => `
              <div class="device-row">
                <div class="device-info">
                  <div class="device-name">${s.server_id}</div>
                  <div class="device-addr">OTA: ${s.ota_ip}:${s.ota_port}</div>
                </div>
              </div>
            `).join("")
          }
        </div>
      `;
      const saveBtn = el.querySelector("#saveConfigBtn");
      if (saveBtn) saveBtn.onclick = () => this._saveConfig();
      ["host", "port", "user", "pass"].forEach((k) => {
        const inp = el.querySelector(`#f-${k}`);
        if (inp) inp.oninput = () => {
          if (k === "port") this._editConfig.mqtt_port = parseInt(inp.value) || 1883;
          else this._editConfig[`mqtt_${k === "user" ? "username" : k}`] = inp.value;
        };
      });
    } else if (tab === "ble") {
      el.innerHTML = `
        <div class="card">
          <h2>BLE Devices</h2>
          ${this._devices.length === 0 ? '<div class="empty">No BLE devices detected yet. Devices seen by SpatialBLE scanners will appear here.</div>' :
            `<div class="section-title">${this._devices.length} device${this._devices.length > 1 ? "s" : ""}</div>` +
            this._devices.map(d => `
              <div class="device-row">
                <div class="device-info">
                  <div class="device-name">${d.name || "Unknown"}</div>
                  <div class="device-addr">${d.address} &middot; ${d.server_id || "?"}</div>
                </div>
                <div class="device-rssi ${_rssiClass(d.rssi)}">${d.rssi != null ? d.rssi + " dBm" : "—"}</div>
              </div>
            `).join("")
          }
        </div>
      `;
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
          <p>A spatial awareness integration for Home Assistant, enabling BLE device tracking and spatial computing capabilities.</p>
        </div>
      `;
    }
  }
}

customElements.define("spatialha-panel", SpatialHAPanel);
