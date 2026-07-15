/**
 * Combustion Card — a Lovelace card styled after Combustion Inc. hardware.
 *
 * Predictive Probes render as the square 2nd-gen WiFi Display. The Giant Grill
 * Gauge renders as the round device with its SMOKE→INSANE temperature dial
 * (auto-detected; force the square style with `style: square`).
 *
 * Tap the LCD to open the temperature's details, including Home Assistant's
 * built-in history graph.
 *
 * Usage (any ONE of these is enough):
 *   type: custom:combustion-card
 *   serial: 10007dc0            # probe serial, or gauge serial like G000000123
 *   # or:
 *   entity: sensor.predictive_thermometer_10007dc0_core_temperature
 *
 * Options:
 *   name: brisket               # label shown on the LCD
 *   style: square               # force the square face on a gauge
 *   secondary: 10007dc0         # gauge only: a second reading below the grill
 *                               #   temp. A probe serial cycles core/surface/
 *                               #   ambient; an entity id or list cycles those.
 *   entities: { ... }           # per-entity overrides
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

// The dial is a 0–1000 °F scale drawn as 31 evenly-spaced ticks. Each zone is
// a temperature RANGE in °C (tune these freely). The grill-zone sensor in the
// integration uses the same boundaries — keep the two in sync.
const GAUGE_MAX_F = 1000;
const GAUGE_TICKS = 31;
const GAUGE_ZONES = [
  { name: 'SMOKE', from: 65, to: 108 },
  { name: 'BBQ', from: 108, to: 166 },
  { name: 'LOW GRILL', from: 166, to: 253 },
  { name: 'MED', from: 253, to: 281 },
  { name: 'HIGH', from: 281, to: 440 },
  { name: 'INSANE', from: 440, to: 538 },
];
// bold reference ticks nearest each zone boundary
const GAUGE_BOUNDARY_TICKS = new Set(
  GAUGE_ZONES.flatMap((z) => [z.from, z.to]).map(
    (c) => Math.round(((c * 9 / 5 + 32) / GAUGE_MAX_F) * GAUGE_TICKS),
  ),
);

const ARC_START_DEG = 135;   // bottom-left
const ARC_SWEEP_DEG = 270;   // clockwise over the top to bottom-right

function polar(cx, cy, r, deg) {
  const rad = (deg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function toCelsius(v, unit) {
  return (unit && unit.indexOf('F') >= 0) ? (v - 32) * 5 / 9 : v;
}

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
    this._round = this._isGauge && config.style !== 'square';

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

    this._secondary = this._resolveSecondary(config.secondary);
    this._secondaryIndex = 0;

    if (this.shadowRoot) { this.shadowRoot.innerHTML = ''; this._render(this.shadowRoot); }
  }

  _resolveSecondary(sec) {
    const list = [];
    const pushProbe = (s) => {
      const b = 'sensor.predictive_thermometer_' + String(s).toLowerCase();
      list.push({ entity: b + '_core_temperature', label: 'core' });
      list.push({ entity: b + '_surface_temperature', label: 'surface' });
      list.push({ entity: b + '_ambient_temperature', label: 'ambient' });
    };
    if (!sec) return list;
    for (const it of (Array.isArray(sec) ? sec : [sec])) {
      if (typeof it === 'string' && it.indexOf('.') >= 0) list.push({ entity: it, label: null });
      else if (typeof it === 'string' && /^[0-9a-z]+$/i.test(it)) pushProbe(it);
      else if (it && it.entity) list.push({ entity: it.entity, label: it.label || null });
    }
    return list;
  }

  getCardSize() { return this._round ? 5 : 4; }

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

  _fmt(v, decimals) {
    return v === null ? null : v.toFixed(decimals);
  }

  _fractionForC(c) {
    const f = (c * 9 / 5 + 32) / GAUGE_MAX_F;   // 0–1000 °F scale
    return Math.max(0, Math.min(1, f));
  }

  _arcPath(cx, cy, r, f0, f1) {
    if (f1 <= f0) return '';
    const a = polar(cx, cy, r, ARC_START_DEG + f0 * ARC_SWEEP_DEG);
    const b = polar(cx, cy, r, ARC_START_DEG + f1 * ARC_SWEEP_DEG);
    const large = (f1 - f0) * ARC_SWEEP_DEG > 180 ? 1 : 0;
    return `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} A ${r} ${r} 0 ${large} 1 ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
  }

  _render(root) {
    if (this._round) this._renderRound(root);
    else this._renderFlat(root);
  }

  _update() {
    if (!this.shadowRoot || !this._hass) return;
    if (this._round) this._updateRound();
    else this._updateFlat();
  }

  _moreInfo() {
    const ev = new Event('hass-more-info', { bubbles: true, composed: true });
    ev.detail = { entityId: this._entities.core };
    this.dispatchEvent(ev);
  }

  // ---- shared LCD chrome ----

  _baseStyles() {
    return `
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
      .seg {
        font-family: "CombustionLCD", monospace;
        font-weight: bold;
        font-variant-numeric: tabular-nums;
      }
      .digits { position: relative; display: inline-block; }
      .ghost { color: var(--lcd-ghost); }
      .lit { position: absolute; top: 0; right: 0; color: var(--lcd-ink); }
    `;
  }

  // ================= SQUARE FACE (probe, or gauge with style: square) =================

  _renderFlat(root) {
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
      <span class="chip state sensor" id="chip-b"><span class="dot"></span>sensor</span>
      <span class="chip state battery" id="chip-batt"><span class="dot"></span>battery low</span>`;

    root.innerHTML = `
      <style>
        ${this._baseStyles()}
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
          background: radial-gradient(120% 90% at 50% 0%, rgba(255,255,255,.35), rgba(255,255,255,0) 45%), var(--lcd-glass);
          border-radius: 10px;
          box-shadow: inset 0 2px 8px rgba(0,0,0,.4), inset 0 -1px 2px rgba(255,255,255,.35);
          padding: 12px 16px 14px;
          cursor: pointer;
          color: var(--lcd-ink);
        }
        .lcd-top { display: flex; justify-content: space-between; align-items: baseline; font-size: 13px; font-weight: 700; letter-spacing: .02em; color: var(--lcd-soft); }
        .lcd-top .probe-label { text-transform: lowercase; }
        .glyphs { display: flex; gap: 7px; align-items: center; }
        .glyphs svg { display: block; }
        .glyphs .off { opacity: .14; }
        .lcd.dead .unit { color: var(--lcd-ghost); }
        .lcd.dead .lcd-top { color: rgba(34,37,30,.28); }
        .main { position: relative; display: flex; justify-content: center; align-items: baseline; margin: 2px 0 6px; line-height: 1; }
        .main .seg { font-size: clamp(44px, 15vw, 64px); }
        .main .unit { font-size: 15px; font-weight: 800; margin-left: 10px; color: var(--lcd-ink); align-self: flex-start; margin-top: 4px; }
        .subrow { display: flex; justify-content: space-between; gap: 12px; border-top: 1.5px solid rgba(34,37,30,.15); padding-top: 9px; }
        .sub { flex: 1; min-width: 0; }
        .sub .label { font-size: 11.5px; font-weight: 700; letter-spacing: .02em; color: var(--lcd-soft); text-transform: lowercase; margin-bottom: 2px; }
        .sub .value-row { display: flex; align-items: baseline; }
        .sub .seg { font-size: 24px; }
        .sub .unit { font-size: 10px; font-weight: 800; margin-left: 5px; color: var(--lcd-ink); }
        .sub.right { text-align: right; }
        .sub.right .value-row { justify-content: flex-end; }
        .buttons { display: flex; justify-content: center; gap: 10px; margin-top: 13px; }
        .chip { display: inline-flex; align-items: center; gap: 7px; padding: 7px 14px; border-radius: 999px; font-size: 12.5px; font-weight: 700; letter-spacing: .01em; background: var(--housing-deep); box-shadow: inset 0 1px 2px rgba(0,0,0,.22), 0 1px 0 rgba(255,255,255,.35); color: rgba(33,29,23,.55); transition: background .25s ease, color .25s ease; }
        .chip .dot { width: 7px; height: 7px; border-radius: 50%; background: rgba(33,29,23,.28); transition: background .25s ease, box-shadow .25s ease; }
        .chip.on { color: #fff; }
        .chip.on .dot { background: #fff; }
        .chip.cooking.on { background: var(--accent-red); box-shadow: inset 0 1px 2px rgba(0,0,0,.3); }
        .chip.cooking.on .dot { box-shadow: 0 0 6px rgba(255,255,255,.8); animation: pulse 2.2s ease-in-out infinite; }
        .chip.inserted.on { background: var(--ink); }
        .chip.sensor.on { background: var(--ink); }
        .chip.battery { display: none; }
        .chip.battery.on { display: inline-flex; background: var(--accent-red); color: #fff; }
        @keyframes pulse { 50% { opacity: .45; } }
        @media (prefers-reduced-motion: reduce) { .chip.cooking.on .dot { animation: none; } .chip, .chip .dot { transition: none; } }
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
            <span class="digits"><span class="seg ghost">1888.8</span><span class="seg lit" id="core"></span></span>
            <span class="unit" id="core-unit">&deg;C</span>
          </div>
          <div class="subrow">${this._isGauge ? gaugeSubs : probeSubs}</div>
        </div>
        <div class="buttons">${this._isGauge ? gaugeChips : probeChips}</div>
      </div>
    `;
    const lcd = root.getElementById('lcd');
    lcd.addEventListener('click', () => this._moreInfo());
    lcd.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') this._moreInfo(); });
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

  _updateFlat() {
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
    const battLow = (() => { const s = this._state('battery'); return !!s && s.state === 'on'; })();
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
      setChip('chip-b', 'sensor_connected');
    } else {
      setChip('chip-a', 'cooking');
      setChip('chip-b', 'inserted');
    }
    setChip('chip-batt', 'battery');
  }

  // ================= ROUND FACE (Giant Grill Gauge) =================

  _buildDial() {
    const c = 150;
    const segR = 136, nameR = 102;
    const tickOut = 143, tickIn = 129, boundOut = 144, boundIn = 126;
    let out = '';

    // LCD segments that fill between the ticks, hard against the outer edge.
    // Hidden (opacity 0) until lit up to the current temperature in _update.
    for (let i = 0; i < GAUGE_TICKS; i++) {
      const f0 = (i + 0.13) / GAUGE_TICKS;
      const f1 = (i + 0.87) / GAUGE_TICKS;
      out += `<path class="seg" data-i="${i}" d="${this._arcPath(c, c, segR, f0, f1)}" fill="none" stroke="var(--lcd-ink)" stroke-width="14" stroke-linecap="butt" opacity="0"/>`;
    }

    // fixed thin reference ticks at every division, longer at zone boundaries
    for (let i = 0; i <= GAUGE_TICKS; i++) {
      const deg = ARC_START_DEG + (i / GAUGE_TICKS) * ARC_SWEEP_DEG;
      const boundary = GAUGE_BOUNDARY_TICKS.has(i);
      const a = polar(c, c, boundary ? boundOut : tickOut, deg);
      const b = polar(c, c, boundary ? boundIn : tickIn, deg);
      out += `<line x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" stroke="var(--lcd-ink)" stroke-width="${boundary ? 1.8 : 1.2}" stroke-linecap="round" opacity="${boundary ? 0.7 : 0.38}"/>`;
    }

    // zone names centred over their tick ranges
    for (const z of GAUGE_ZONES) {
      const midF = this._fractionForC((z.from + z.to) / 2);
      const deg = ARC_START_DEG + midF * ARC_SWEEP_DEG;
      const p = polar(c, c, nameR, deg);
      let rot = deg + 90;
      if (rot > 90 && rot < 270) rot -= 180;
      out += `<text x="${p.x.toFixed(1)}" y="${p.y.toFixed(1)}" transform="rotate(${rot.toFixed(1)} ${p.x.toFixed(1)} ${p.y.toFixed(1)})" text-anchor="middle" dominant-baseline="middle" class="zone-label" data-zone="${z.name}">${z.name}</text>`;
    }

    // High (red) and low (blue) alarm setpoint markers, positioned at runtime.
    out += `<line id="dial-low" x1="${c}" y1="${c}" x2="${c}" y2="${c}" stroke="#2F6FD0" stroke-width="4" stroke-linecap="round" opacity="0"/>`;
    out += `<line id="dial-high" x1="${c}" y1="${c}" x2="${c}" y2="${c}" stroke="var(--accent-red)" stroke-width="4" stroke-linecap="round" opacity="0"/>`;
    return out;
  }

  _renderRound(root) {
    root.innerHTML = `
      <style>
        ${this._baseStyles()}
        .round { position: relative; width: 100%; max-width: 340px; margin: 0 auto; aspect-ratio: 1 / 1; font-family: "Avenir Next", "Nunito", "Trebuchet MS", system-ui, sans-serif; user-select: none; }
        .bezel {
          position: absolute; inset: 0; border-radius: 50%;
          background: radial-gradient(circle at 50% 32%, var(--housing-light) 0%, var(--housing) 46%, var(--housing-deep) 100%);
          box-shadow: inset 0 2px 2px rgba(255,255,255,.5), inset 0 -4px 8px rgba(0,0,0,.18), 0 3px 8px rgba(0,0,0,.28);
        }
        .glass {
          position: absolute; inset: 7%; border-radius: 50%;
          background: radial-gradient(circle at 50% 22%, rgba(255,255,255,.4), rgba(255,255,255,0) 42%), var(--lcd-glass);
          box-shadow: inset 0 3px 10px rgba(0,0,0,.45), inset 0 -2px 3px rgba(255,255,255,.35);
          overflow: hidden;
        }
        .dial { position: absolute; inset: 0; width: 100%; height: 100%; }
        .zone-label { font-size: 9px; font-weight: 800; letter-spacing: .04em; fill: var(--lcd-soft); }
        .zone-label.active { fill: var(--lcd-ink); }
        .overlay { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--lcd-ink); cursor: pointer; }
        .glyph-row { position: absolute; top: 24%; display: flex; align-items: center; gap: 8px; }
        .glyph-row svg { display: block; }
        .glyph-row .off { opacity: .16; }
        .flame { color: var(--accent-red); }
        .stack { display: flex; flex-direction: column; align-items: center; gap: 4px; margin-top: 8%; }
        .grill-main { display: flex; align-items: baseline; }
        .grill-main .seg { font-size: clamp(40px, 20cqw, 62px); }
        .grill-main .unit { font-size: 13px; font-weight: 800; margin-left: 6px; align-self: flex-start; margin-top: 6px; }
        .no-sensor { font-size: 12px; font-weight: 700; color: var(--lcd-soft); text-transform: lowercase; letter-spacing: .03em; display: none; }
        .secondary { display: none; align-items: center; gap: 8px; }
        .secondary .cyc { border: none; background: transparent; color: var(--lcd-soft); font: inherit; font-size: 15px; font-weight: 800; cursor: pointer; padding: 2px 4px; line-height: 1; border-radius: 6px; }
        .secondary .cyc:focus-visible { outline: 2px solid var(--lcd-ink); }
        .secondary .read { text-align: center; min-width: 84px; }
        .secondary .slabel { font-size: 10px; font-weight: 700; letter-spacing: .03em; color: var(--lcd-soft); text-transform: lowercase; }
        .secondary .svalue { display: flex; align-items: baseline; justify-content: center; }
        .secondary .svalue .seg { font-size: 22px; }
        .secondary .svalue .unit { font-size: 9px; font-weight: 800; margin-left: 4px; }
        .alarm-ring { position: absolute; inset: 6%; border-radius: 50%; border: 3px solid var(--accent-red); opacity: 0; pointer-events: none; }
        .round.alarming .alarm-ring { animation: ring-pulse 1.4s ease-in-out infinite; }
        .round.dead .overlay, .round.dead .dial { opacity: .4; }
        @keyframes ring-pulse { 0%, 100% { opacity: 0; } 50% { opacity: .9; } }
        @media (prefers-reduced-motion: reduce) { .round.alarming .alarm-ring { animation: none; opacity: .8; } }
      </style>
      <div class="round" id="round" style="container-type: inline-size;">
        <div class="bezel"></div>
        <div class="glass">
          <svg class="dial" viewBox="0 0 300 300" aria-hidden="true">${this._buildDial()}</svg>
          <div class="alarm-ring"></div>
        </div>
        <div class="overlay" id="lcd" role="button" tabindex="0" aria-label="Open grill temperature details and history">
          <div class="glyph-row">
            <svg id="g-bt" width="11" height="16" viewBox="0 0 12 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">
              <path d="M3 4.5 L9 13.5 L6 16 L6 2 L9 4.5 L3 13.5"/>
            </svg>
            <svg class="flame" width="17" height="19" viewBox="0 0 20 22" fill="currentColor" aria-hidden="true">
              <path d="M10 1 C 12 6 17 8 14 14 C 13 18 10 20.5 10 20.5 C 10 20.5 7 18 6 14 C 5 11 7 9 7 9 C 7 12 10 12 10 9 C 10 5 9 4 10 1 Z"/>
            </svg>
            <svg id="g-signal" width="16" height="13" viewBox="0 0 14 12" fill="currentColor" aria-hidden="true">
              <path d="M7 9.4a1.5 1.5 0 100 3 1.5 1.5 0 000-3zM3.7 7.6l1.4 1.4a2.7 2.7 0 013.8 0l1.4-1.4a4.7 4.7 0 00-6.6 0zM1 4.9l1.4 1.4a6.5 6.5 0 019.2 0L13 4.9a8.5 8.5 0 00-12 0z"/>
            </svg>
          </div>
          <div class="stack">
            <div class="grill-main">
              <span class="digits"><span class="seg ghost">888</span><span class="seg lit" id="core"></span></span>
              <span class="unit" id="core-unit">&deg;C</span>
            </div>
            <div class="no-sensor" id="no-sensor">no sensor</div>
            <div class="secondary" id="secondary">
            <button class="cyc" id="cyc" aria-label="Cycle second reading">&#8250;</button>
            <div class="read">
              <div class="slabel" id="slabel">core</div>
              <div class="svalue"><span class="digits"><span class="seg ghost">888</span><span class="seg lit" id="sval"></span></span><span class="unit" id="sunit">&deg;C</span></div>
            </div>
          </div>
          </div>
        </div>
      </div>
    `;
    const lcd = root.getElementById('lcd');
    lcd.addEventListener('click', () => this._moreInfo());
    lcd.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') this._moreInfo(); });
    const cyc = root.getElementById('cyc');
    cyc.addEventListener('click', (ev) => {
      ev.stopPropagation();
      if (this._secondary.length) {
        this._secondaryIndex = (this._secondaryIndex + 1) % this._secondary.length;
        this._update();
      }
    });
  }

  _secondaryLabel(item, st) {
    if (item.label) return item.label;
    const fn = st && st.attributes && st.attributes.friendly_name;
    if (!fn) return 'sensor';
    return fn.split(' ').slice(-2).join(' ').toLowerCase();
  }

  _updateRound() {
    const root = this.shadowRoot;
    const core = this._state('core');
    const available = !!core && core.state !== 'unavailable';
    const unit = (core && core.attributes.unit_of_measurement) || '°C';
    const value = this._num('core');
    const sensorSt = this._state('sensor_connected');
    const sensorOff = !!sensorSt && sensorSt.state === 'off';

    root.getElementById('round').classList.toggle('dead', !available);

    // main grill temperature
    this._setSeg('core', (available && value !== null) ? this._fmt(value, 0) : '', 'core-unit', unit);
    root.getElementById('no-sensor').style.display = (available && sensorOff) ? 'block' : 'none';

    // fill the LCD segments between the ticks up to the current temperature
    const curF = (available && value !== null && !sensorOff)
      ? this._fractionForC(toCelsius(value, unit)) : null;
    root.querySelectorAll('.seg').forEach((seg) => {
      const i = parseInt(seg.getAttribute('data-i'), 10);
      const lit = curF !== null && (curF * GAUGE_TICKS) >= (i + 0.5);
      seg.setAttribute('opacity', lit ? '0.92' : '0');
    });
    if (curF !== null) {
      const curC = toCelsius(value, unit);
      let activeName = null;
      for (const z of GAUGE_ZONES) if (curC >= z.from) activeName = z.name;
      root.querySelectorAll('.zone-label').forEach((el) => {
        el.classList.toggle('active', el.getAttribute('data-zone') === activeName);
      });
    } else {
      root.querySelectorAll('.zone-label').forEach((el) => el.classList.remove('active'));
    }

    // alarm setpoint markers across the bar (high = red, low = blue)
    const marker = (id, setpoint) => {
      const el = root.getElementById(id);
      if (!available || setpoint === null) { el.setAttribute('opacity', '0'); return; }
      const f = this._fractionForC(toCelsius(setpoint, unit));
      const deg = ARC_START_DEG + f * ARC_SWEEP_DEG;
      const a = polar(150, 150, 143, deg);
      const b = polar(150, 150, 128, deg);
      el.setAttribute('x1', a.x.toFixed(1)); el.setAttribute('y1', a.y.toFixed(1));
      el.setAttribute('x2', b.x.toFixed(1)); el.setAttribute('y2', b.y.toFixed(1));
      el.setAttribute('opacity', '1');
    };
    marker('dial-high', this._alarmSetpoint('high_alarm'));
    marker('dial-low', this._alarmSetpoint('low_alarm'));

    // glyphs
    root.getElementById('g-signal').classList.toggle('off', !available);

    // alarm ring
    const hi = this._state('high_alarm');
    const lo = this._state('low_alarm');
    const alarming = available && (((hi && hi.state === 'on')) || (lo && lo.state === 'on'));
    root.getElementById('round').classList.toggle('alarming', !!alarming);

    // secondary readout
    const secEl = root.getElementById('secondary');
    if (this._secondary.length) {
      const item = this._secondary[this._secondaryIndex % this._secondary.length];
      const st = this._hass.states[item.entity];
      const sv = st && st.state !== 'unavailable' && st.state !== 'unknown' ? Number(st.state) : null;
      const sUnit = (st && st.attributes && st.attributes.unit_of_measurement) || unit;
      secEl.style.display = 'flex';
      root.getElementById('slabel').textContent = this._secondaryLabel(item, st);
      this._setSeg('sval', (sv !== null && Number.isFinite(sv)) ? sv.toFixed(0) : '', 'sunit', sUnit);
      root.getElementById('cyc').style.visibility = this._secondary.length > 1 ? 'visible' : 'hidden';
    } else {
      secEl.style.display = 'none';
    }
  }
}

customElements.define('combustion-card', CombustionCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'combustion-card',
  name: 'Combustion Card',
  description: 'Probe & Giant Grill Gauge card styled after Combustion hardware, with the round grill dial.',
});
