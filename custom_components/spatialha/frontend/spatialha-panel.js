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
    const result = await this._hass.callWS({ type: "spatialha/version" });
    this.innerHTML = `<div id="content">This is the SpatialHA panel - Version ${result.version}</div>`;
  }
}

customElements.define("spatialha-panel", SpatialHAPanel);
