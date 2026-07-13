/**
 * Combustion Card — a Lovelace card styled after the Combustion Inc.
 * 2nd-generation WiFi Display: yellow housing, segmented LCD.
 *
 * Works for Predictive Probes and the Giant Grill Gauge (auto-detected).
 * Tap the LCD to open the temperature's details, including Home Assistant's
 * built-in history graph.
 *
 * Usage (any ONE of these is enough):
 *   type: custom:combustion-card
 *   serial: 10007dc0            # probe serial, or gauge serial like CR100040A8
 *   # or:
 *   entity: sensor.predictive_thermometer_10007dc0_core_temperature
 *
 * Options:
 *   name: brisket               # label shown on the LCD (probes show "1/brisket")
 *   entities: { ... }           # per-entity overrides (core, ambient, instant,
 *                               #   cooking, inserted, battery, mode,
 *                               #   temperature, sensor_connected, overheating,
 *                               #   high_alarm, low_alarm)
 *
 * The DSEG7 Classic font (c) Keshikan (https://www.keshikan.net/fonts-e.html)
 * is embedded under the SIL Open Font License 1.1.
 */

const DSEG7_B64 = "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";

(function ensureFont() {
  if (document.getElementById('combustion-card-font')) return;
  const style = document.createElement('style');
  style.id = 'combustion-card-font';
  style.textContent = '@font-face { font-family: "CombustionLCD"; src: url(data:font/woff2;base64,' + DSEG7_B64 + ') format("woff2"); font-weight: bold; }';
  document.head.appendChild(style);
})();

const PROBE_SERIAL_RE = /^[0-9a-f]{8}$/;

class CombustionCard extends HTMLElement {
  static getStubConfig(hass) {
    const core = Object.keys(hass.states).find((e) => e.endsWith('_core_temperature'));
    return core ? { entity: core } : { serial: '10007dc0' };
  }

  setConfig(config) {
    let serial = (config.serial || '').toLowerCase();
    if (!serial && config.entity) {
      const m = config.entity.match(/^(?:sensor|binary_sensor)\.(?:predictive_thermometer|grill_gauge)_([0-9a-z]+)_/);
      if (m) serial = m[1];
    }
    if (!serial && !(config.entities && (config.entities.core || config.entities.temperature))) {
      throw new Error('combustion-card: set "serial" or "entity" (any entity of the probe/gauge)');
    }

    this._config = config;
    this._isGauge = config.kind ? config.kind === 'gauge' : !PROBE_SERIAL_RE.test(serial);
    const base = (this._isGauge ? 'grill_gauge_' : 'predictive_thermometer_') + serial;
    const defaults = this._isGauge ? {
      core: 'sensor.' + base + '_temperature',
      sensor_connected: 'binary_sensor.' + base + '_sensor_connected',
      overheating: 'binary_sensor.' + base + '_overheating',
      high_alarm: 'binary_sensor.' + base + '_high_alarm',
      low_alarm: 'binary_sensor.' + base + '_low_alarm',
      battery: 'binary_sensor.' + base + '_battery',
    } : {
      core: 'sensor.' + base + '_core_temperature',
      ambient: 'sensor.' + base + '_ambient_temperature',
      instant: 'sensor.' + base + '_instant_read_temperature',
      cooking: 'binary_sensor.' + base + '_cooking',
      inserted: 'binary_sensor.' + base + '_probe_inserted',
      battery: 'binary_sensor.' + base + '_battery',
      mode: 'sensor.' + base + '_mode',
    };
    const overrides = Object.assign({}, config.entities || {});
    if (overrides.temperature && this._isGauge) overrides.core = overrides.temperature;
    this._entities = Object.assign(defaults, overrides);

    if (this.shadowRoot) { this.shadowRoot.innerHTML = ''; this._render(this.shadowRoot); }
  }

  getCardSize() { return 4; }

  set hass(hass) {
    this._hass = hass;
    if (!this.shadowRoot) this._render(this.attachShadow({ mode: 'open' }));
    this._update();
  }

  _state(key) {
    const id = this._entities[key];
    return (this._hass && id) ? this._hass.states[id] : undefined;
  }

  _num(key) {
    const st = this._state(key);
    if (!st || st.state === 'unavailable' || st.state === 'unknown') return null;
    const v = Number(st.state);
    return Number.isFinite(v) ? v : null;
  }

  _render(root) {
    const probeSubs = `
      <div class="sub">
        <div class="label">ambient</div>
        <div class="value-row">
          <span class="digits"><span class="seg ghost">888</span><span class="seg lit" id="sub-left"></span></span>
          <span class="unit" id="sub-left-unit">&deg;C</span>
        </div>
      </div>
      <div class="sub right">
        <div class="label">instant read</div>
        <div class="value-row">
          <span class="digits"><span class="seg ghost">888</span><span class="seg lit" id="sub-right"></span></span>
          <span class="unit" id="sub-right-unit">&deg;C</span>
        </div>
      </div>`;
    const gaugeSubs = `
      <div class="sub">
        <div class="label">low alarm</div>
        <div class="value-row">
          <span class="digits"><span class="seg ghost">888</span><span class="seg lit" id="sub-left"></span></span>
          <span class="unit" id="sub-left-unit">&deg;C</span>
        </div>
      </div>
      <div class="sub right">
        <div class="label">high alarm</div>
        <div class="value-row">
          <span class="digits"><span class="seg ghost">888</span><span class="seg lit" id="sub-right"></span></span>
          <span class="unit" id="sub-right-unit">&deg;C</span>
        </div>
      </div>`;
    const probeChips = `
      <span class="chip state cooking" id="chip-a"><span class="dot"></span>cooking</span>
      <span class="chip state inserted" id="chip-b"><span class="dot"></span>probe in</span>
      <span class="chip state battery" id="chip-batt"><span class="dot"></span>battery low</span>`;
    const gaugeChips = `
      <span class="chip state cooking" id="chip-a"><span class="dot"></span>alarm</span>
      <span class="chip state nosensor" id="chip-b"><span class="dot"></span>no sensor</span>
      <span class="chip state battery" id="chip-batt"><span class="dot"></span>battery low</span>`;

    root.innerHTML = `
      <style>
        :host {
          --housing: #F7C544;
          --housing-deep: #DFA92E;
          --housing-light: #FFDA6B;
          --lcd-glass: #C9CEC0;
          --lcd-ink: #22251E;
          --lcd-ghost: rgba(34, 37, 30, 0.09);
          --lcd-soft: rgba(34, 37, 30, 0.55);
          --ink: #211D17;
          --accent-red: #C93A2E;
          display: block;
        }
        .housing {
          background: linear-gradient(178deg, var(--housing-light) 0%, var(--housing) 22%, var(--housing) 78%, var(--housing-deep) 100%);
          border-radius: 24px;
          padding: 16px 16px 14px;
          box-shadow: inset 0 1px 0 rgba(255,255,255,.45), inset 0 -2px 3px rgba(0,0,0,.12), 0 1px 3px rgba(0,0,0,.25);
          font-family: "Avenir Next", "Nunito", "Trebuchet MS", system-ui, sans-serif;
          color: var(--ink);
          user-select: none;
        }
        .lcd {
          background:
            radial-gradient(120% 90% at 50% 0%, rgba(255,255,255,.35), rgba(255,255,255,0) 45%),
            var(--lcd-glass);
          border-radius: 10px;
          box-shadow: inset 0 2px 8px rgba(0,0,0,.4), inset 0 -1px 2px rgba(255,255,255,.35);
          padding: 12px 16px 14px;
          cursor: pointer;
          color: var(--lcd-ink);
        }
        .lcd-top {
          display: flex; justify-content: space-between; align-items: baseline;
          font-size: 13px; font-weight: 700; letter-spacing: .02em;
          color: var(--lcd-soft);
        }
        .lcd-top .probe-label { text-transform: lowercase; }
        .glyphs { display: flex; gap: 7px; align-items: center; }
        .glyphs svg { display: block; }
        .glyphs .off { opacity: .14; }
        .lcd.dead .unit { color: var(--lcd-ghost); }
        .lcd.dead .lcd-top { color: rgba(34,37,30,.28); }
        .main {
          position: relative;
          display: flex; justify-content: center; align-items: baseline;
          margin: 2px 0 6px;
          line-height: 1;
        }
        .seg {
          font-family: "CombustionLCD", monospace;
          font-weight: bold;
          font-variant-numeric: tabular-nums;
        }
        .digits { position: relative; display: inline-block; }
        .ghost { color: var(--lcd-ghost); }
        .lit { position: absolute; top: 0; right: 0; color: var(--lcd-ink); }
        .main .seg { font-size: clamp(44px, 15vw, 64px); }
        .main .unit {
          font-size: 15px; font-weight: 800; margin-left: 10px;
          color: var(--lcd-ink);
          align-self: flex-start; margin-top: 4px;
        }
        .subrow {
          display: flex; justify-content: space-between; gap: 12px;
          border-top: 1.5px solid rgba(34,37,30,.15);
          padding-top: 9px;
        }
        .sub { flex: 1; min-width: 0; }
        .sub .label {
          font-size: 11.5px; font-weight: 700; letter-spacing: .02em;
          color: var(--lcd-soft); text-transform: lowercase;
          margin-bottom: 2px;
        }
        .sub .value-row { display: flex; align-items: baseline; }
        .sub .seg { font-size: 24px; }
        .sub .unit { font-size: 10px; font-weight: 800; margin-left: 5px; color: var(--lcd-ink); }
        .sub.right { text-align: right; }
        .sub.right .value-row { justify-content: flex-end; }
        .buttons {
          display: flex; justify-content: center; gap: 10px;
          margin-top: 13px;
        }
        .chip {
          display: inline-flex; align-items: center; gap: 7px;
          padding: 7px 14px;
          border-radius: 999px;
          border: none;
          font: inherit;
          font-size: 12.5px; font-weight: 700; letter-spacing: .01em;
          background: var(--housing-deep);
          box-shadow: inset 0 1px 2px rgba(0,0,0,.22), 0 1px 0 rgba(255,255,255,.35);
          color: rgba(33,29,23,.55);
          transition: background .25s ease, color .25s ease;
        }
        .chip .dot {
          width: 7px; height: 7px; border-radius: 50%;
          background: rgba(33,29,23,.28);
          transition: background .25s ease, box-shadow .25s ease;
        }
        .chip.on { color: #fff; }
        .chip.on .dot { background: #fff; }
        .chip.cooking.on { background: var(--accent-red); box-shadow: inset 0 1px 2px rgba(0,0,0,.3); }
        .chip.cooking.on .dot { box-shadow: 0 0 6px rgba(255,255,255,.8); animation: pulse 2.2s ease-in-out infinite; }
        .chip.inserted.on { background: var(--ink); }
        .chip.nosensor.on { background: var(--accent-red); }
        .chip.battery { display: none; }
        .chip.battery.on { display: inline-flex; background: var(--accent-red); color: #fff; }
        @keyframes pulse { 50% { opacity: .45; } }
        @media (prefers-reduced-motion: reduce) {
          .chip.cooking.on .dot { animation: none; }
          .chip, .chip .dot { transition: none; }
        }
      </style>
      <div class="housing">
        <div class="lcd" id="lcd" role="button" tabindex="0" aria-label="Open temperature details and history">
          <div class="lcd-top">
            <span class="probe-label" id="label"></span>
            <span class="glyphs">
              <svg id="g-signal" width="14" height="12" viewBox="0 0 14 12" fill="currentColor" aria-hidden="true">
                <path d="M7 9.4a1.5 1.5 0 100 3 1.5 1.5 0 000-3zM3.7 7.6l1.4 1.4a2.7 2.7 0 013.8 0l1.4-1.4a4.7 4.7 0 00-6.6 0zM1 4.9l1.4 1.4a6.5 6.5 0 019.2 0L13 4.9a8.5 8.5 0 00-12 0z"/>
              </svg>
              <svg id="g-batt" width="18" height="10" viewBox="0 0 18 10" aria-hidden="true">
                <rect x="0.75" y="0.75" width="14" height="8.5" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/>
                <rect x="16.4" y="3" width="1.6" height="4" rx="0.8" fill="currentColor"/>
                <rect id="batt-fill" x="2.5" y="2.5" width="10.5" height="5" rx="1" fill="currentColor"/>
              </svg>
            </span>
          </div>
          <div class="main">
            <span class="digits">
              <span class="seg ghost">1888.8</span>
              <span class="seg lit" id="core"></span>
            </span>
            <span class="unit" id="core-unit">&deg;C</span>
          </div>
          <div class="subrow">${this._isGauge ? gaugeSubs : probeSubs}</div>
        </div>
        <div class="buttons">
          ${this._isGauge ? gaugeChips : probeChips}
        </div>
      </div>
    `;
    root.getElementById('lcd').addEventListener('click', () => this._moreInfo());
    root.getElementById('lcd').addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ' ') this._moreInfo();
    });
  }

  _moreInfo() {
    const ev = new Event('hass-more-info', { bubbles: true, composed: true });
    ev.detail = { entityId: this._entities.core };
    this.dispatchEvent(ev);
  }

  _fmt(v, decimals) {
    return v === null ? null : v.toFixed(decimals);
  }

  _setSeg(id, text, unitId, unit) {
    const el = this.shadowRoot.getElementById(id);
    if (!el) return;
    el.textContent = text === null || text === undefined ? '' : text;
    if (unitId && unit) {
      const u = this.shadowRoot.getElementById(unitId);
      if (u) u.textContent = unit;
    }
  }

  _alarmSetpoint(key) {
    const st = this._state(key);
    if (!st || st.state === 'unavailable') return null;
    if (!st.attributes || st.attributes.set !== true) return null;
    const v = Number(st.attributes.alarm_temperature);
    return Number.isFinite(v) ? v : null;
  }

  _probeLabel(available) {
    const name = this._config.name;
    if (!available) return (name ? name + ' · ' : '') + 'offline';
    if (this._isGauge) return name || 'gauge';
    const mode = this._state('mode');
    const pid = mode && mode.attributes && mode.attributes.probe_id;
    return (pid || 1) + '/' + (name || 'core');
  }

  _update() {
    if (!this.shadowRoot || !this._hass) return;
    const core = this._state('core');
    const available = !!core && core.state !== 'unavailable';
    const unit = (core && core.attributes.unit_of_measurement) || '°C';
    const lcd = this.shadowRoot.getElementById('lcd');

    lcd.classList.toggle('dead', !available);
    this.shadowRoot.getElementById('label').textContent = this._probeLabel(available);

    this._setSeg('core', available ? this._fmt(this._num('core'), 1) : '', 'core-unit', unit);
    if (this._isGauge) {
      const lo = this._alarmSetpoint('low_alarm');
      const hi = this._alarmSetpoint('high_alarm');
      this._setSeg('sub-left', available && lo !== null ? this._fmt(lo, 0) : '', 'sub-left-unit', unit);
      this._setSeg('sub-right', available && hi !== null ? this._fmt(hi, 0) : '', 'sub-right-unit', unit);
    } else {
      this._setSeg('sub-left', available ? this._fmt(this._num('ambient'), 0) : '', 'sub-left-unit', unit);
      this._setSeg('sub-right', available ? this._fmt(this._num('instant'), 0) : '', 'sub-right-unit', unit);
    }

    this.shadowRoot.getElementById('g-signal').classList.toggle('off', !available);
    const battState = this._state('battery');
    const battLow = !!battState && battState.state === 'on';
    this.shadowRoot.getElementById('g-batt').classList.toggle('off', !available);
    this.shadowRoot.getElementById('batt-fill').setAttribute('width', battLow ? '3.5' : '10.5');

    const setChip = (id, key, invert) => {
      const el = this.shadowRoot.getElementById(id);
      if (!el) return;
      const st = this._state(key);
      let on = !!st && st.state === 'on';
      if (invert) on = !!st && st.state === 'off';
      el.classList.toggle('on', on && available);
    };
    if (this._isGauge) {
      const hi = this._state('high_alarm');
      const lo = this._state('low_alarm');
      const alarming = (hi && hi.state === 'on') || (lo && lo.state === 'on');
      this.shadowRoot.getElementById('chip-a').classList.toggle('on', !!alarming && available);
      setChip('chip-b', 'sensor_connected', true);
    } else {
      setChip('chip-a', 'cooking');
      setChip('chip-b', 'inserted');
    }
    setChip('chip-batt', 'battery');
  }

}

customElements.define('combustion-card', CombustionCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'combustion-card',
  name: 'Combustion Card',
  description: 'Probe & Grill Gauge card styled after the Combustion WiFi Display, with an LCD graph view.',
});
