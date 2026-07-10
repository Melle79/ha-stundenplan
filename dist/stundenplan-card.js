/* Stundenplan Card v1.1.0 - Companion-Karte fuer den Stundenplan Manager
 * https://github.com/Melle79/ha-stundenplan
 *
 * Konfiguration:
 *   type: custom:stundenplan-card
 *   entity: sensor.stundenplan_max_wochenplan
 *   modus: woche          # woche | heute (Standard: woche)
 *   zeige_pausen: true    # Pausenzeilen anzeigen (Standard: true)
 *   titel: ""             # optionaler Titel, Standard: "Stundenplan {Name}"
 */
class StundenplanCard extends HTMLElement {
  static TAGE = [["mo","Mo"],["di","Di"],["mi","Mi"],["do","Do"],["fr","Fr"]];

  setConfig(config) {
    if (!config.entity) throw new Error("Bitte 'entity' angeben (Wochenplan-Sensor)");
    this._config = Object.assign({ modus: "woche", zeige_pausen: true, titel: "" }, config);
    this._letzterHash = null;
  }

  set hass(hass) {
    this._hass = hass;
    const st = hass.states[this._config.entity];
    if (!st) { this._zeigeFehler(`Entität ${this._config.entity} nicht gefunden`); return; }
    const a = st.attributes;
    if (!a.raster || !a.plan) {
      this._zeigeFehler("Warte auf Plandaten… (Add-on gestartet?)");
      return;
    }
    const hash = JSON.stringify([a.raster, a.plan, a.faecher, a.bloecke, a.modus,
                                 new Date().getMinutes(), st.state]);
    if (hash === this._letzterHash) return;
    this._letzterHash = hash;
    this._render(a);
  }

  getCardSize() { return this._config.modus === "heute" ? 3 : 6; }
  static getConfigElement() { return document.createElement("stundenplan-card-editor"); }
  static getStubConfig() { return { entity: "", modus: "woche", zeige_pausen: true, titel: "" }; }

  /* ------------------------------------------------------------------ */
  _heuteIdx() {
    const wd = new Date().getDay(); // 0=So
    return wd >= 1 && wd <= 5 ? wd - 1 : -1;
  }

  _imBlock(a, datum) {
    if (a.modus !== "block") return true;
    const d = datum.toISOString().slice(0, 10);
    return (a.bloecke || []).some(b => b.von <= d && d <= b.bis);
  }

  _jetztZeit() {
    const n = new Date();
    return `${String(n.getHours()).padStart(2,"0")}:${String(n.getMinutes()).padStart(2,"0")}`;
  }

  _render(a) {
    const titel = this._config.titel || `Stundenplan ${a.kind || ""}`;
    const inhalt = this._config.modus === "heute"
      ? this._renderHeute(a) : this._renderWoche(a);
    this.innerHTML = `
      <ha-card header="${titel}">
        <style>
          .sp-wrap { padding: 0 16px 16px; }
          .sp-tabelle { border-collapse: collapse; width: 100%; }
          .sp-tabelle th { color: var(--secondary-text-color); font-size: .75rem;
            font-weight: 600; padding: 4px 2px; border-bottom: 1px solid var(--divider-color); }
          .sp-tabelle th.sp-heute { color: var(--primary-color); }
          .sp-tabelle td { text-align: center; padding: 2px; }
          .sp-zeit { font-size: .68rem; color: var(--secondary-text-color);
            white-space: nowrap; padding-right: 6px !important; text-align: right !important; }
          .sp-zeit b { display: block; font-size: .8rem; color: var(--primary-text-color); }
          .sp-fach { border-radius: 6px; padding: 5px 2px; font-weight: 600;
            font-size: .78rem; color: #fff; line-height: 1.2; }
          .sp-fach small { display: block; font-weight: 400; font-size: .62rem; opacity: .9; }
          .sp-frei { color: var(--disabled-text-color); font-size: .75rem; }
          .sp-aktuell { outline: 2px solid var(--primary-color); outline-offset: 1px; }
          .sp-heute-spalte { background: color-mix(in srgb, var(--primary-color) 7%, transparent); }
          .sp-pause td { padding: 1px; }
          .sp-pause .sp-plabel { font-size: .62rem; color: var(--disabled-text-color);
            letter-spacing: .05em; text-align: center; }
          .sp-banner { margin: 0 0 10px; padding: 8px 12px; border-radius: 8px;
            background: color-mix(in srgb, var(--primary-color) 12%, transparent);
            color: var(--primary-text-color); font-size: .85rem; }
          .sp-liste { list-style: none; margin: 0; padding: 0; }
          .sp-liste li { display: flex; align-items: center; gap: 10px;
            padding: 6px 8px; border-radius: 8px; margin-bottom: 4px; }
          .sp-liste .sp-punkt { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
          .sp-liste .sp-lzeit { font-size: .75rem; color: var(--secondary-text-color);
            width: 86px; flex-shrink: 0; }
          .sp-liste .sp-lname { font-size: .88rem; }
          .sp-liste .sp-lraum { margin-left: auto; font-size: .72rem;
            color: var(--secondary-text-color); }
          .sp-liste li.sp-aktuell { outline-offset: 0; }
          .sp-leer { color: var(--secondary-text-color); font-size: .88rem; padding: 4px 0; }
        </style>
        <div class="sp-wrap">${inhalt}</div>
      </ha-card>`;
  }

  _renderWoche(a) {
    const heute = this._heuteIdx();
    const zeit = this._jetztZeit();
    const heuteImBlock = this._imBlock(a, new Date());
    let html = "";
    if (a.modus === "block" && !heuteImBlock)
      html += `<div class="sp-banner">🏭 Betriebsphase – aktuell kein Blockunterricht</div>`;
    html += `<table class="sp-tabelle"><thead><tr><th></th>`;
    StundenplanCard.TAGE.forEach(([,l], i) => {
      html += `<th class="${i === heute ? "sp-heute" : ""}">${l}</th>`;
    });
    html += `</tr></thead><tbody>`;
    const r = a.raster;
    r.forEach((st, si) => {
      if (this._config.zeige_pausen && si > 0 && r[si-1].bis < st.von) {
        html += `<tr class="sp-pause"><td colspan="6"><div class="sp-plabel">· · · Pause ${r[si-1].bis}–${st.von} · · ·</div></td></tr>`;
      }
      html += `<tr><td class="sp-zeit"><b>${st.nr}.</b>${st.von}</td>`;
      StundenplanCard.TAGE.forEach(([tag], ti) => {
        const kz = (a.plan[tag] || [])[si] || null;
        const f = kz ? (a.faecher || {})[kz] : null;
        const istJetzt = ti === heute && heuteImBlock &&
          st.von <= zeit && zeit < st.bis && f;
        const spalte = ti === heute ? "sp-heute-spalte" : "";
        if (f) {
          html += `<td class="${spalte}"><div class="sp-fach ${istJetzt ? "sp-aktuell" : ""}"
            style="background:${f.farbe}" title="${f.name}">${kz}${f.raum ? `<small>${f.raum}</small>` : ""}</div></td>`;
        } else {
          html += `<td class="${spalte}"><span class="sp-frei">–</span></td>`;
        }
      });
      html += `</tr>`;
    });
    return html + `</tbody></table>`;
  }

  _renderHeute(a) {
    const heute = this._heuteIdx();
    if (heute < 0) return `<div class="sp-leer">🎉 Wochenende – schulfrei!</div>`;
    if (!this._imBlock(a, new Date()))
      return `<div class="sp-leer">🏭 Betriebsphase – kein Blockunterricht heute</div>`;
    const tag = StundenplanCard.TAGE[heute][0];
    const plan = a.plan[tag] || [];
    const zeit = this._jetztZeit();
    const r = a.raster;
    let html = `<ul class="sp-liste">`, stunden = 0;
    r.forEach((st, si) => {
      const kz = plan[si];
      if (!kz) return;
      const f = (a.faecher || {})[kz] || { name: kz, farbe: "#888" };
      const istJetzt = st.von <= zeit && zeit < st.bis;
      stunden++;
      html += `<li class="${istJetzt ? "sp-aktuell" : ""}">
        <span class="sp-punkt" style="background:${f.farbe}"></span>
        <span class="sp-lzeit">${st.von}–${st.bis}</span>
        <span class="sp-lname">${f.name}</span>
        ${f.raum ? `<span class="sp-lraum">Raum ${f.raum}</span>` : ""}
      </li>`;
    });
    html += `</ul>`;
    return stunden ? html : `<div class="sp-leer">Heute kein Unterricht 🎈</div>`;
  }

  _zeigeFehler(msg) {
    this.innerHTML = `<ha-card><div style="padding:16px;color:var(--secondary-text-color)">${msg}</div></ha-card>`;
  }
}

class StundenplanCardEditor extends HTMLElement {
  static SCHEMA = [
    { name: "entity", selector: { entity: { domain: "sensor" } } },
    { name: "modus", selector: { select: { mode: "dropdown", options: [
      { value: "woche", label: "Wochenansicht (Mo–Fr)" },
      { value: "heute", label: "Heute (kompakte Liste)" },
    ] } } },
    { name: "zeige_pausen", selector: { boolean: {} } },
    { name: "titel", selector: { text: {} } },
  ];

  static LABELS = {
    entity: "Wochenplan-Sensor (sensor.stundenplan_…_wochenplan)",
    modus: "Ansicht",
    zeige_pausen: "Pausen anzeigen",
    titel: "Titel (optional)",
  };

  setConfig(config) {
    this._config = Object.assign({ modus: "woche", zeige_pausen: true, titel: "" }, config);
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
  }

  _render() {
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = s => StundenplanCardEditor.LABELS[s.name] || s.name;
      this._form.addEventListener("value-changed", e => {
        this._config = e.detail.value;
        this.dispatchEvent(new CustomEvent("config-changed",
          { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = StundenplanCardEditor.SCHEMA;
  }
}

customElements.define("stundenplan-card-editor", StundenplanCardEditor);
customElements.define("stundenplan-card", StundenplanCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "stundenplan-card",
  name: "Stundenplan Card",
  description: "Wochen- und Tagesansicht für den Stundenplan Manager (mit Blockunterricht)",
  preview: false,
});
console.info("%c STUNDENPLAN-CARD %c v1.1.0", "background:#4a90d9;color:#fff;padding:2px 6px;border-radius:3px", "");
