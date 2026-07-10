/* Stundenplan Card v1.8.0 - Companion-Karte fuer den Stundenplan Manager
 * https://github.com/Melle79/ha-stundenplan
 *
 * Konfiguration:
 *   type: custom:stundenplan-card
 *   entities:\n *   - sensor.stundenplan_max_wochenplan   # weglassen = alle Kinder automatisch
 *   modus: woche          # woche | heute (Standard: woche)
 *   zeige_pausen: true    # Pausenzeilen anzeigen (Standard: true)
 *   titel: ""             # optionaler Titel, Standard: "Stundenplan {Name}"
 */
class StundenplanCard extends HTMLElement {
  static TAGE = [["mo","Mo"],["di","Di"],["mi","Mi"],["do","Do"],["fr","Fr"]];

  setConfig(config) {
    this._config = Object.assign({ modus: "woche", zeige_pausen: true, titel: "",
                                   layout: "tabs", schrift: "normal" }, config);
    if (this._config.entity && !this._config.entities)
      this._config.entities = [this._config.entity];
    this._letzterHash = null;
    this._aktivIdx = 0;
    this._wocheOffset = 0;
  }

  _entityIds(hass) {
    const c = this._config;
    if (c.entities && c.entities.length) return c.entities;
    return Object.keys(hass.states)
      .filter(id => /^sensor\.stundenplan_.+_wochenplan$/.test(id)).sort();
  }

  set hass(hass) {
    this._hass = hass;
    const ids = this._entityIds(hass);
    if (!ids.length) {
      this._zeigeFehler("Keine Stundenplan-Sensoren gefunden – läuft das Add-on?");
      return;
    }
    if (this._aktivIdx >= ids.length) this._aktivIdx = 0;
    const gestapelt = this._config.layout === "untereinander" && ids.length > 1;
    const relevant = gestapelt ? ids : [ids[this._aktivIdx]];
    const attrListe = relevant.map(id => (hass.states[id] || {}).attributes || {});
    const hash = JSON.stringify([ids, this._aktivIdx, this._wocheOffset,
                                 this._config.layout, attrListe, new Date().getMinutes()]);
    if (hash === this._letzterHash) return;
    this._letzterHash = hash;
    this._render(ids, gestapelt);
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

  _wochenMontag() {
    const n = new Date(); n.setHours(0,0,0,0);
    const mo = new Date(n);
    mo.setDate(n.getDate() - ((n.getDay() + 6) % 7) + (n.getDay() === 0 || n.getDay() === 6 ? 7 : 0));
    mo.setDate(mo.getDate() + this._wocheOffset * 7);
    return mo;
  }

  _isoKW(d) {
    const t = new Date(d); t.setHours(0,0,0,0);
    t.setDate(t.getDate() + 3 - ((t.getDay() + 6) % 7));
    const w1 = new Date(t.getFullYear(), 0, 4);
    return 1 + Math.round(((t - w1) / 864e5 - 3 + ((w1.getDay() + 6) % 7)) / 7);
  }

  _tagDatum(montag, i) {
    const d = new Date(montag); d.setDate(montag.getDate() + i); return d;
  }

  _iso(d) {
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  }

  _planFuerDatum(a, isoDatum) {
    const passend = (a.plaene || []).filter(p => p.gueltig_ab <= isoDatum)
      .sort((x, y) => x.gueltig_ab.localeCompare(y.gueltig_ab));
    return passend.length ? passend[passend.length - 1].plan : (a.plan || {});
  }

  _freiGrund(a, isoDatum) {
    if (a.modus === "block")
      return (a.bloecke || []).some(b => b.von <= isoDatum && isoDatum <= b.bis)
        ? null : "🏭 Betrieb";
    const z = (a.schulfrei_zeitraeume || []).filter(x => x.von <= isoDatum && isoDatum <= x.bis);
    if (!z.length) return null;
    const mehr = z.filter(x => x.von !== x.bis);
    return "🏖 " + (mehr.length ? mehr[0] : z[0]).grund;
  }

  _jetztZeit() {
    const n = new Date();
    return `${String(n.getHours()).padStart(2,"0")}:${String(n.getMinutes()).padStart(2,"0")}`;
  }

  _inhaltFuer(id) {
    const st = this._hass.states[id];
    if (!st) return `<div class="sp-leer">Entität ${id} nicht gefunden</div>`;
    const a = st.attributes;
    if (!a.raster || !a.plan) return `<div class="sp-leer">Warte auf Plandaten…</div>`;
    return this._config.modus === "heute" ? this._renderHeute(a) : this._renderWoche(a);
  }

  _kindName(id) {
    const st = this._hass.states[id];
    return (st && st.attributes && st.attributes.kind) ||
      id.replace(/^sensor\.stundenplan_|_wochenplan$/g, "");
  }

  _render(ids, gestapelt) {
    let titel, inhalt = "", chips = "";
    if (gestapelt) {
      titel = this._config.titel || "Stundenplan";
      inhalt = ids.map(id =>
        `<div class="sp-abschnitt"><h3 class="sp-kindname">${this._kindName(id)}</h3>${this._inhaltFuer(id)}</div>`
      ).join("");
    } else {
      const id = ids[this._aktivIdx];
      titel = this._config.titel ||
        `Stundenplan ${(this._hass.states[id]?.attributes?.kind) || ""}`;
      inhalt = this._inhaltFuer(id);
      if (ids.length > 1) {
        chips = `<div class="sp-chips">` + ids.map((eid, i) =>
          `<button class="sp-chip ${i === this._aktivIdx ? "sp-chip-aktiv" : ""}" data-idx="${i}">${this._kindName(eid)}</button>`
        ).join("") + `</div>`;
      }
    }
    this.innerHTML = `
      <ha-card header="${titel}">
        <style>
          .sp-wrap { padding: 0 16px 16px; container-type: inline-size; }
          .sp-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
          .sp-chip { border: 1px solid var(--divider-color); background: none;
            color: var(--secondary-text-color); border-radius: 18px; padding: 7px 18px;
            font-size: .92rem; cursor: pointer; font-family: inherit; }
          .sp-chip-aktiv { background: var(--primary-color); border-color: var(--primary-color);
            color: var(--text-primary-color, #fff); font-weight: 600; }
          .sp-gross .sp-chip { font-size: 1.08rem; padding: 9px 22px; }
          .sp-gross .sp-tabelle th { font-size: .95rem; }
          .sp-gross .sp-zeit { font-size: .8rem; }
          .sp-gross .sp-zeit b { font-size: .98rem; }
          .sp-gross .sp-fach { font-size: .98rem; padding: 11px 6px; }
          .sp-gross .sp-fach small { font-size: .76rem; }
          .sp-gross .sp-pause .sp-plabel { font-size: .8rem; }
          .sp-gross .sp-kindname { font-size: 1.7rem; }
          .sp-gross .sp-liste .sp-lzeit { font-size: .9rem; width: 104px; }
          .sp-gross .sp-liste .sp-lname { font-size: 1.08rem; }
          .sp-gross .sp-liste .sp-lraum { font-size: .88rem; }
          .sp-gross .sp-leer, .sp-gross .sp-banner { font-size: 1.05rem; }
          .sp-tabelle { border-collapse: separate; border-spacing: 4px; width: 100%;
            table-layout: fixed; margin: 0 -4px; }
          .sp-tabelle th { color: var(--secondary-text-color); font-size: .78rem;
            font-weight: 600; padding: 2px 0 6px; }
          .sp-tabelle th.sp-heute { color: var(--primary-color); }
          .sp-punkt-heute { font-size: .5rem; vertical-align: middle; }
          .sp-tabelle td { text-align: center; padding: 0; }
          .sp-zeit { font-size: .68rem; color: var(--secondary-text-color);
            white-space: nowrap; padding-right: 6px !important; text-align: right !important;
            vertical-align: middle; }
          .sp-zeit b { display: block; font-size: .82rem; color: var(--primary-text-color); }
          .sp-fach { border-radius: 8px; padding: 8px 4px; font-weight: 600;
            font-size: .8rem; color: #fff; line-height: 1.25;
            text-shadow: 0 1px 1px rgba(0,0,0,.25); }
          .sp-fach small { display: block; font-weight: 400; font-size: .62rem; opacity: .92; }
          .sp-fach .sp-name { display: none; }
          .sp-gedimmt { opacity: .35; filter: saturate(.5); }
          .sp-tag-frei small { display: block; font-weight: 500; font-size: .64rem;
            color: var(--secondary-text-color); margin-top: 1px; }
          .sp-datum { display: block; font-weight: 400; font-size: .62rem;
            color: var(--secondary-text-color); }
          .sp-wochenkopf { display: flex; align-items: center; gap: 10px;
            justify-content: center; margin-bottom: 8px; }
          .sp-kw { font-size: .85rem; font-weight: 600; color: var(--primary-text-color); }
          .sp-nav { border: 1px solid var(--divider-color); background: none;
            color: var(--secondary-text-color); border-radius: 8px; padding: 4px 10px;
            cursor: pointer; font-family: inherit; font-size: .8rem; }
          .sp-nav:hover { color: var(--primary-text-color); }
          .sp-heute-btn { color: var(--primary-color); border-color: var(--primary-color); }
          .sp-gross .sp-kw { font-size: 1rem; }
          @container (min-width: 620px) {
            .sp-fach { padding: 8px 6px; }
            .sp-fach .sp-name { display: block; }
          }
          .sp-frei { display: block; border-radius: 8px; height: 100%; min-height: 34px;
            background: color-mix(in srgb, var(--divider-color) 30%, transparent); }
          .sp-aktuell { outline: 2px solid var(--primary-color); outline-offset: 1px;
            box-shadow: 0 0 8px color-mix(in srgb, var(--primary-color) 55%, transparent); }
          .sp-heute-spalte .sp-frei {
            background: color-mix(in srgb, var(--primary-color) 9%, transparent); }
          .sp-pause td { padding: 2px 0; }
          .sp-pause .sp-plabel { display: flex; align-items: center; gap: 10px;
            font-size: .66rem; color: var(--secondary-text-color); letter-spacing: .04em; }
          .sp-pause .sp-plabel::before, .sp-pause .sp-plabel::after {
            content: ""; flex: 1; border-top: 1px dashed var(--divider-color); }
          .sp-pause-aktiv .sp-plabel { color: var(--primary-color); font-weight: 600; }
          .sp-pause-aktiv .sp-plabel::before, .sp-pause-aktiv .sp-plabel::after {
            border-top-color: var(--primary-color); }
          .sp-zeit-aktiv { background: var(--primary-color); border-radius: 8px; }
          .sp-zeit-aktiv, .sp-zeit-aktiv b { color: var(--text-primary-color, #fff) !important; }
          .sp-abschnitt { margin-bottom: 22px; }
          .sp-abschnitt:last-child { margin-bottom: 0; }
          .sp-kindname { margin: 0 0 10px; padding-left: 58px; font-size: 1.35rem;
            font-weight: 700; color: var(--primary-text-color); }
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
        <div class="sp-wrap ${this._config.schrift === "gross" ? "sp-gross" : ""}">${chips}${inhalt}</div>
      </ha-card>`;
    this.querySelectorAll(".sp-chip").forEach(btn => {
      btn.onclick = () => {
        this._aktivIdx = +btn.dataset.idx;
        this._letzterHash = null;
        this.hass = this._hass;
      };
    });
    this.querySelectorAll(".sp-nav").forEach(btn => {
      btn.onclick = () => {
        const n = +btn.dataset.nav;
        this._wocheOffset = n === 0 ? 0 : this._wocheOffset + n;
        this._letzterHash = null;
        this.hass = this._hass;
      };
    });
  }

  _renderWoche(a) {
    const heute = this._heuteIdx();
    const zeit = this._jetztZeit();
    const montag = this._wochenMontag();
    const aktuelleWoche = this._wocheOffset === 0;
    const freitag = this._tagDatum(montag, 4);
    const fmt = d => d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
    const kw = this._isoKW(montag);

    let html = `<div class="sp-wochenkopf">
      <button class="sp-nav" data-nav="-1">◀</button>
      <span class="sp-kw">KW ${kw} · ${fmt(montag)}–${fmt(freitag)}.${freitag.getFullYear()}</span>
      ${aktuelleWoche ? "" : `<button class="sp-nav sp-heute-btn" data-nav="0">Heute</button>`}
      <button class="sp-nav" data-nav="1">▶</button>
    </div>`;

    const tage = StundenplanCard.TAGE.map(([tag, l], i) => {
      const datum = this._tagDatum(montag, i);
      const iso = this._iso(datum);
      return { tag, l, i, iso, datum, frei: this._freiGrund(a, iso),
               plan: this._planFuerDatum(a, iso) };
    });

    html += `<table class="sp-tabelle"><colgroup><col style="width:54px"><col span="5"></colgroup><thead><tr><th></th>`;
    for (const t of tage) {
      const istHeute = aktuelleWoche && t.i === heute;
      const punkt = istHeute ? `<span class="sp-punkt-heute"> ●</span>` : "";
      const frei = t.frei ? `<small>${t.frei}</small>` : "";
      html += `<th class="${istHeute ? "sp-heute" : ""} ${t.frei ? "sp-tag-frei" : ""}">${t.l}${punkt}<small class="sp-datum">${fmt(t.datum)}</small>${frei}</th>`;
    }
    html += `</tr></thead><tbody>`;

    const r = a.raster;
    r.forEach((st, si) => {
      if (this._config.zeige_pausen && si > 0 && r[si-1].bis < st.von) {
        const pauseJetzt = aktuelleWoche && heute >= 0 && !tage[heute].frei &&
          r[si-1].bis <= zeit && zeit < st.von;
        html += `<tr class="sp-pause ${pauseJetzt ? "sp-pause-aktiv" : ""}"><td colspan="6"><div class="sp-plabel">Pause ${r[si-1].bis}–${st.von}${pauseJetzt ? " · läuft" : ""}</div></td></tr>`;
      }
      const stundeJetzt = aktuelleWoche && heute >= 0 && !tage[heute].frei &&
        st.von <= zeit && zeit < st.bis;
      html += `<tr><td class="sp-zeit ${stundeJetzt ? "sp-zeit-aktiv" : ""}"><b>${st.nr}.</b>${st.von}</td>`;
      for (const t of tage) {
        const kz = (t.plan[t.tag] || [])[si] || null;
        const f = kz ? (a.faecher || {})[kz] : null;
        const istJetzt = aktuelleWoche && t.i === heute && !t.frei &&
          st.von <= zeit && zeit < st.bis && f;
        const spalte = aktuelleWoche && t.i === heute ? "sp-heute-spalte" : "";
        if (f) {
          html += `<td class="${spalte}"><div class="sp-fach ${istJetzt ? "sp-aktuell" : ""} ${t.frei ? "sp-gedimmt" : ""}"
            style="background:${f.farbe}" title="${f.name}">${kz}<small class="sp-name">${f.name}</small>${f.raum ? `<small>${f.raum}</small>` : ""}</div></td>`;
        } else {
          html += `<td class="${spalte}"><span class="sp-frei"></span></td>`;
        }
      }
      html += `</tr>`;
    });
    return html + `</tbody></table>`;
  }

  _renderHeute(a) {
    const isoHeute = this._iso(new Date());
    if (a.modus !== "block") {
      const g = this._freiGrund(a, isoHeute);
      if (g) return `<div class="sp-leer">${g.replace("🏖 ", "🏖 Heute schulfrei – ")}</div>`;
    }
    const heute = this._heuteIdx();
    if (heute < 0) return `<div class="sp-leer">🎉 Wochenende – schulfrei!</div>`;
    if (!this._imBlock(a, new Date()))
      return `<div class="sp-leer">🏭 Betriebsphase – kein Blockunterricht heute</div>`;
    const tag = StundenplanCard.TAGE[heute][0];
    const plan = this._planFuerDatum(a, isoHeute)[tag] || [];
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
  static LABELS = {
    entities: "Kinder",
    layout: "Mehrere Kinder anzeigen als",
    schrift: "Schriftgröße",
    modus: "Ansicht",
    zeige_pausen: "Pausen anzeigen",
    titel: "Titel (optional)",
  };

  setConfig(config) {
    this._config = Object.assign({ modus: "woche", zeige_pausen: true, titel: "",
                                   layout: "tabs", schrift: "normal" }, config);
    if (this._config.entity && !this._config.entities) {
      this._config.entities = [this._config.entity];
      delete this._config.entity;
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _schema() {
    const options = Object.entries((this._hass && this._hass.states) || {})
      .filter(([id]) => /^sensor\.stundenplan_.+_wochenplan$/.test(id))
      .map(([id, st]) => ({
        value: id,
        label: (st.attributes && st.attributes.kind) ||
               id.replace(/^sensor\.stundenplan_|_wochenplan$/g, ""),
      }))
      .sort((a, b) => a.label.localeCompare(b.label));
    return [
      { name: "entities", selector: { select: { multiple: true, mode: "list", options } } },
      { name: "layout", selector: { select: { mode: "dropdown", options: [
        { value: "tabs", label: "Tabs (Chips zum Umschalten)" },
        { value: "untereinander", label: "Alle untereinander" },
      ] } } },
      { name: "modus", selector: { select: { mode: "dropdown", options: [
        { value: "woche", label: "Wochenansicht (Mo–Fr)" },
        { value: "heute", label: "Heute (kompakte Liste)" },
      ] } } },
      { name: "schrift", selector: { select: { mode: "dropdown", options: [
        { value: "normal", label: "Normal" },
        { value: "gross", label: "Groß" },
      ] } } },
      { name: "zeige_pausen", selector: { boolean: {} } },
      { name: "titel", selector: { text: {} } },
    ];
  }

  _render() {
    if (!this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = s => StundenplanCardEditor.LABELS[s.name] || s.name;
      this._form.computeHelper = s => s.name === "entities"
        ? "Kein Haken = alle Kinder automatisch anzeigen" : undefined;
      this._form.addEventListener("value-changed", e => {
        this._config = e.detail.value;
        this.dispatchEvent(new CustomEvent("config-changed",
          { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = this._schema();
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
console.info("%c STUNDENPLAN-CARD %c v1.8.0", "background:#4a90d9;color:#fff;padding:2px 6px;border-radius:3px", "");
