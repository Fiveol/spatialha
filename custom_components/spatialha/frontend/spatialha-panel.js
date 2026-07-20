class SpatialHAPanel extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `<div id="content">Connecting...</div>`;
    this._fetchVersion();
  }

  set hass(hass) {
    this._hass = hass;
    this._fetchVersion();
  }

  async _fetchVersion() {
    if (!this._hass) return;
    try {
      const result = await this._hass.callWS({ type: "spatialha/version" });
      this.innerHTML = `
        <ha-card>
          <div class="card-header">
            SpatialHA
          </div>
          <div class="card-content">
            <p><b>Status:</b> Connected</p>
            <p><b>Version:</b> ${result.version}</p>
          </div>
        </ha-card>`;
    } catch {
      this.innerHTML = `<ha-card><div class="card-content">Connection error</div></ha-card>`;
    }
  }

  getCardSize() {
    return 1;
  }
}

customElements.define("spatialha-panel", SpatialHAPanel);
