class GridPilotCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error("entity is required");
    }

    this._config = config;
    if (this.shadowRoot) return;

    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          height: 100%;
        }
        ha-card {
          box-sizing: border-box;
          cursor: pointer;
          height: 100%;
          overflow: hidden;
          padding: 10px 18px;
        }
        .heading {
          margin-bottom: 6px;
          min-height: 28px;
        }
        .title {
          color: var(--primary-text-color);
          font-size: 16px;
          font-weight: 500;
          line-height: 24px;
        }
        .battery {
          height: calc(100% - 34px);
          min-height: 52px;
          padding-right: 12px;
          position: relative;
        }
        .body {
          background: color-mix(in srgb, #94a3b8 12%, transparent);
          border: 3px solid #94a3b8;
          border-radius: 14px;
          inset: 0 12px 0 0;
          overflow: hidden;
          position: absolute;
        }
        .level {
          background: var(--level-color);
          border-radius: 10px;
          height: 100%;
          overflow: hidden;
          position: relative;
          transition: width 600ms ease-out, background-color 300ms linear;
          width: var(--level);
        }
        .stripes {
          backface-visibility: hidden;
          background: repeating-linear-gradient(
            135deg,
            rgba(255, 255, 255, .18) 0 7px,
            rgba(255, 255, 255, 0) 8px 15px,
            rgba(255, 255, 255, .18) 16px
          );
          inset: -40px;
          position: absolute;
          transform: translate3d(0, 0, 0);
          will-change: transform;
        }
        .charging .stripes { animation: flow-right 1.6s linear infinite; }
        .discharging .stripes { animation: flow-left 1.6s linear infinite; }
        .zone {
          bottom: 0;
          display: none;
          pointer-events: none;
          position: absolute;
          top: 0;
          z-index: 2;
        }
        .critical-zone {
          background: color-mix(in srgb, var(--error-color, #dc2626) 58%, transparent);
        }
        .control-zone {
          background: color-mix(in srgb, #f59e0b 40%, transparent);
        }
        .target-zone {
          background: color-mix(in srgb, #64748b 40%, transparent);
        }
        .threshold {
          border-left: 2px dashed color-mix(in srgb, var(--primary-text-color) 65%, transparent);
          bottom: 0;
          display: none;
          pointer-events: none;
          position: absolute;
          top: 0;
          z-index: 3;
        }
        .minimum-threshold {
          border-left-color: color-mix(in srgb, var(--error-color, #dc2626) 88%, transparent);
          border-left-style: solid;
        }
        .normal-threshold {
          border-left-color: color-mix(in srgb, #16a34a 88%, transparent);
          border-left-style: solid;
        }
        .charge-threshold {
          border-left-color: color-mix(in srgb, #f59e0b 72%, transparent);
        }
        .target-threshold {
          border-left-color: color-mix(in srgb, #2563eb 88%, transparent);
          border-left-style: solid;
        }
        .terminal {
          background: #94a3b8;
          border-radius: 0 5px 5px 0;
          height: 24px;
          position: absolute;
          right: 0;
          top: 50%;
          transform: translateY(-50%);
          width: 12px;
        }
        .value {
          align-items: center;
          color: var(--primary-text-color);
          display: flex;
          flex-direction: column;
          inset: 0 12px 0 0;
          justify-content: center;
          pointer-events: none;
          position: absolute;
          text-shadow: 0 1px 4px var(--card-background-color);
        }
        .soc-value {
          font-size: 28px;
          font-weight: 800;
          line-height: 30px;
        }
        .control-status {
          display: none;
          font-size: 11px;
          font-weight: 600;
          line-height: 15px;
        }
        @keyframes flow-right { to { transform: translate3d(22.627px, 0, 0); } }
        @keyframes flow-left { to { transform: translate3d(-22.627px, 0, 0); } }
        @media (prefers-reduced-motion: reduce) {
          .stripes { animation: none !important; }
        }
      </style>
        <ha-card tabindex="0">
          <div class="heading">
            <div class="title"></div>
          </div>
        <div class="battery">
          <div class="body">
            <div class="level"><div class="stripes"></div></div>
            <div class="zone critical-zone"></div>
            <div class="zone control-zone"></div>
            <div class="zone target-zone"></div>
            <div class="threshold minimum-threshold"></div>
            <div class="threshold charge-threshold"></div>
            <div class="threshold normal-threshold"></div>
            <div class="threshold target-threshold"></div>
          </div>
          <div class="terminal"></div>
          <div class="value">
            <div class="soc-value"></div>
            <div class="control-status"></div>
          </div>
        </div>
      </ha-card>
    `;

    const card = this.shadowRoot.querySelector("ha-card");
    card.addEventListener("click", () => this._showMoreInfo());
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") this._showMoreInfo();
    });
  }

  _showMoreInfo() {
    const event = new Event("hass-more-info", { bubbles: true, composed: true });
    event.detail = { entityId: this._config.entity };
    this.dispatchEvent(event);
  }

  set hass(hass) {
    if (!this._config || !this.shadowRoot) return;

    const levelState = hass.states[this._config.entity];
    const rawLevel = Number.parseFloat(levelState?.state);
    const level = Number.isFinite(rawLevel) ? Math.max(0, Math.min(100, rawLevel)) : 0;
    const status = this._config.status_entity
      ? hass.states[this._config.status_entity]?.state
      : undefined;
    const powerState = this._config.power_entity
      ? hass.states[this._config.power_entity]
      : undefined;
    const signedPower = Number.parseFloat(powerState?.state);
    const powerUnit = powerState?.attributes?.unit_of_measurement;
    const activityThreshold = powerUnit === "W" ? 10 : 0.01;
    const powerActive = Number.isFinite(signedPower)
      && Math.abs(signedPower) > activityThreshold;
    const chargePositive = this._config.power_charge_positive !== false;
    const chargingFromPower = powerActive
      && (chargePositive ? signedPower > 0 : signedPower < 0);
    const dischargingFromPower = powerActive && !chargingFromPower;
    const charging = status === (this._config.charge_state || "charging")
      || (!this._config.charge_state && chargingFromPower);
    const discharging = Boolean(
      this._config.discharge_state
      && status === this._config.discharge_state,
    ) || (!this._config.discharge_state && dischargingFromPower);
    const mode = charging ? "charging" : discharging ? "discharging" : "standby";
    const defaultLabel = charging ? "Laden" : discharging ? "Ontladen" : "Stand-by";

    const power = Math.abs(signedPower);
    const powerInKw = powerUnit === "kW" ? power : powerUnit === "MW" ? power * 1000 : power / 1000;
    const activityLabel = (charging || discharging) && Number.isFinite(power)
      ? `${charging ? "Laden" : "Ontladen"} met ${new Intl.NumberFormat(hass.locale?.language, { maximumFractionDigits: 1 }).format(powerInKw)} kW`
      : defaultLabel;

    const chargeState = this._config.charge_entity
      ? hass.states[this._config.charge_entity]
      : undefined;
    const chargeCandidate = Number.parseFloat(
      chargeState?.state ?? this._config.charge_below,
    );
    const chargeBelow = Number.isFinite(chargeCandidate)
      ? Math.max(0, Math.min(100, chargeCandidate))
      : Number.NaN;
    const thresholdOffset = Number(this._config.threshold_offset ?? 0);
    const minimumState = this._config.minimum_entity
      ? hass.states[this._config.minimum_entity]
      : undefined;
    const minimumCandidate = Number.parseFloat(
      minimumState?.state ?? (
        Number.isFinite(chargeBelow) ? chargeBelow - thresholdOffset : this._config.minimum_soc
      ),
    );
    const minimum = Number.isFinite(minimumCandidate)
      ? Math.max(0, Math.min(100, minimumCandidate))
      : Number.NaN;
    const normalCandidate = Number.parseFloat(
      Number.isFinite(chargeBelow) ? chargeBelow + thresholdOffset : this._config.normal_above,
    );
    const normalAbove = Number.isFinite(normalCandidate)
      ? Math.max(0, Math.min(100, normalCandidate))
      : Number.NaN;
    const hasControlRange = Number.isFinite(minimum)
      && Number.isFinite(normalAbove)
      && normalAbove > minimum;
    const hasChargeTarget = Number.isFinite(chargeBelow)
      && chargeBelow > minimum
      && chargeBelow < normalAbove;

    const targetState = this._config.target_entity
      ? hass.states[this._config.target_entity]
      : undefined;
    const targetCandidate = Number.parseFloat(targetState?.state);
    const target = Number.isFinite(targetCandidate)
      ? Math.max(0, Math.min(100, targetCandidate))
      : Number.NaN;
    const hasTargetRange = Number.isFinite(target) && target < 100;

    const color = hasControlRange
      ? level < minimum ? "#dc2626" : level < normalAbove ? "#d97706" : "#16a34a"
      : level < 20 ? "#dc2626" : level < 50 ? "#d97706" : "#16a34a";

    this.style.setProperty("--level", `${level}%`);
    this.style.setProperty("--level-color", color);
    this.shadowRoot.querySelector(".level").className = `level ${mode}`;
    this.shadowRoot.querySelector(".title").textContent = `${this._config.name || "Batterij"} · ${activityLabel}`;
    const unit = levelState?.attributes?.unit_of_measurement || "%";
    this.shadowRoot.querySelector(".soc-value").textContent = levelState
      ? `${levelState.state} ${unit}`
      : `- ${unit}`;

    this._renderControlRange(hass, level, minimum, chargeBelow, normalAbove, hasControlRange, hasChargeTarget);
    this._renderTargetRange(target, hasTargetRange);
  }

  _renderControlRange(hass, level, minimum, chargeBelow, normalAbove, hasRange, hasChargeTarget) {
    const criticalZone = this.shadowRoot.querySelector(".critical-zone");
    const controlZone = this.shadowRoot.querySelector(".control-zone");
    const minimumMarker = this.shadowRoot.querySelector(".minimum-threshold");
    const chargeMarker = this.shadowRoot.querySelector(".charge-threshold");
    const normalMarker = this.shadowRoot.querySelector(".normal-threshold");
    const status = this.shadowRoot.querySelector(".control-status");
    const elements = [criticalZone, controlZone, minimumMarker, chargeMarker, normalMarker, status];

    if (!hasRange) {
      elements.forEach((element) => { element.style.display = "none"; });
      return;
    }

    criticalZone.style.cssText = `display:block;left:0;width:${minimum}%`;
    controlZone.style.cssText = `display:block;left:${minimum}%;width:${normalAbove - minimum}%`;
    minimumMarker.style.cssText = `display:block;left:${minimum}%`;
    normalMarker.style.cssText = `display:block;left:${normalAbove}%`;
    chargeMarker.style.display = hasChargeTarget ? "block" : "none";
    if (hasChargeTarget) chargeMarker.style.left = `${chargeBelow}%`;

    const ruleState = level < minimum
      ? "Maximaal bijladen"
      : hasChargeTarget && level < chargeBelow
        ? "Bijladen"
        : level < normalAbove ? "Afbouwen" : "Normaal";
    const setpointState = this._config.setpoint_entity
      ? hass.states[this._config.setpoint_entity]
      : undefined;
    const setpoint = Number.parseFloat(setpointState?.state);
    const setpointUnit = setpointState?.attributes?.unit_of_measurement || "W";
    const formattedSetpoint = Number.isFinite(setpoint)
      ? `${new Intl.NumberFormat(hass.locale?.language, { maximumFractionDigits: 0 }).format(setpoint)} ${setpointUnit}`
      : "-";
    status.style.display = "block";
    status.textContent = `Regeling: ${ruleState} · Setpoint ${formattedSetpoint}`;
  }

  _renderTargetRange(target, hasRange) {
    const zone = this.shadowRoot.querySelector(".target-zone");
    const marker = this.shadowRoot.querySelector(".target-threshold");
    if (!hasRange) {
      zone.style.display = "none";
      marker.style.display = "none";
      return;
    }
    zone.style.cssText = `display:block;left:${target}%;width:${100 - target}%`;
    marker.style.cssText = `display:block;left:${target}%`;
  }

  getCardSize() {
    return 2;
  }

  getGridOptions() {
    return { columns: "full", rows: 2, min_rows: 2 };
  }

  static getStubConfig() {
    return { entity: "sensor.battery_state_of_charge", name: "Batterij" };
  }
}

if (!customElements.get("gridpilot-card")) {
  customElements.define("gridpilot-card", GridPilotCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "gridpilot-card",
  name: "GridPilot Card",
  description: "Animated battery and EV state-of-charge card for GridPilot",
  preview: true,
});
