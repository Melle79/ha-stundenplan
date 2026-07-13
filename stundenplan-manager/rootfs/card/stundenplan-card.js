/* Stundenplan Card v1.16.2 - Companion-Karte fuer den Stundenplan Manager
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
    const schulschluss = this._config.modus === "schulschluss";
    const gestapelt = this._config.layout === "untereinander" && ids.length > 1;
    const relevant = (gestapelt || schulschluss) ? ids : [ids[this._aktivIdx]];
    const attrListe = relevant.map(id => (hass.states[id] || {}).attributes || {});
    const schwestern = schulschluss ? relevant.flatMap(id =>
      ["_schulschluss_heute", "_aktuelle_stunde"].map(s =>
        ((hass.states[id.replace(/_wochenplan$/, s)] || {}).state) || "")) : [];
    const hash = JSON.stringify([ids, this._aktivIdx, this._wocheOffset,
                                 this._config.layout, attrListe, schwestern,
                                 new Date().getMinutes()]);
    if (hash === this._letzterHash) return;
    this._letzterHash = hash;
    this._render(ids, gestapelt && !schulschluss);
  }

  getCardSize() { return this._config.modus === "heute" ? 3 : this._config.modus === "schulschluss" ? 2 : 6; }
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
    if (this._config.modus === "schulschluss") {
      titel = this._config.titel || "Schulschluss heute";
      inhalt = this._renderSchulschluss(ids);
    } else if (gestapelt) {
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
          .sp-entfall { position: relative; opacity: .6; }
          .sp-entfall::after { content: ""; position: absolute; left: 6%; right: 6%;
            top: 50%; border-top: 2px solid var(--error-color, #e05d5d); transform: rotate(-4deg); }
          .sp-entfall .sp-aend { color: var(--error-color, #ff8a80); }
          .sp-vertretung { outline: 2px dashed var(--warning-color, #e0b34c); outline-offset: 1px; }
          .sp-aend { display: block; font-weight: 600; font-size: .6rem; margin-top: 1px; }
          .sp-orig { display: block; font-size: .62rem; font-weight: 500; margin-top: 1px;
            color: var(--error-color, #ff8a80); text-decoration: line-through; }
          .sp-neu { display: block; font-size: .66rem; font-weight: 700; margin-top: 1px;
            color: #fff; }
          .sp-arbeit-kopf { display: block; font-weight: 600; font-size: .62rem; margin-top: 1px;
            color: var(--error-color, #e05d5d); }
          .sp-arbeit { box-shadow: inset 0 0 0 2px var(--error-color, #e05d5d); }
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
          .sp-liste li.sp-liste-entfall { opacity: .55; }
          .sp-laend { color: var(--warning-color, #e0b34c); font-size: .78rem; font-weight: 600; }
          .sp-orig-inline { color: var(--error-color, #ff8a80); }
          .sp-notiz { display: inline-block; font-size: .72rem; font-weight: 700; margin-top: 3px;
            color: #fff; background: rgba(0,0,0,.5); padding: 1px 8px; border-radius: 9px;
            text-decoration: none; }
          .sp-notiz-inline { color: #fff; background: rgba(0,0,0,.35); padding: 0 7px;
            border-radius: 9px; font-size: .78rem; font-weight: 600; }
          .sp-stand { text-align: right; font-size: .65rem; color: var(--secondary-text-color, #9ab);
            opacity: .75; margin-top: 4px; }
          .sp-leer { color: var(--secondary-text-color); font-size: .88rem; padding: 4px 0; }
          .sp-info { margin-top: 8px; padding: 6px 12px; border-radius: 8px;
            font-size: .8rem; color: var(--secondary-text-color);
            border: 1px solid var(--divider-color); }
          .sp-gross .sp-info { font-size: .92rem; }
          .sp-ha-liste { list-style: none; margin: 6px 0 0; padding: 0; }
          .sp-ha-liste li { display: flex; gap: 8px; align-items: baseline;
            font-size: .8rem; color: var(--primary-text-color); padding: 3px 2px;
            border-bottom: 1px dashed var(--divider-color); }
          .sp-ha-liste li:last-child { border-bottom: none; }
          .sp-ha-due { flex: 0 0 auto; min-width: 62px; font-weight: 600;
            font-size: .72rem; color: var(--primary-color); }
          .sp-ha-due.sp-ha-spaet { color: var(--error-color, #e05d5d); }
          .sp-gross .sp-ha-liste li { font-size: .95rem; }
          .sp-ha-badge { font-size: .72rem; font-weight: 600; margin-left: 8px;
            padding: 2px 7px; border-radius: 10px; vertical-align: 2px;
            background: color-mix(in srgb, var(--primary-color) 14%, transparent);
            color: var(--primary-color); }
          .sp-material { margin-top: 8px; padding: 8px 12px; border-radius: 8px;
            font-size: .82rem; color: var(--primary-text-color);
            background: color-mix(in srgb, var(--primary-color) 10%, transparent); }
          .sp-gross .sp-material { font-size: .95rem; }
          .sp-schluss { list-style: none; margin: 0; padding: 0; }
          .sp-schluss li { display: flex; align-items: baseline; gap: 12px;
            padding: 10px 4px; border-bottom: 1px solid var(--divider-color); }
          .sp-schluss li:last-child { border-bottom: none; }
          .sp-schluss-name { font-size: 1.05rem; font-weight: 600; }
          .sp-schluss-sub { color: var(--secondary-text-color); font-size: .78rem; flex: 1; }
          .sp-schluss-zeit { font-size: 1.5rem; font-weight: 700; font-variant-numeric: tabular-nums;
            color: var(--primary-color); }
          .sp-schluss-zeit.sp-schluss-vorbei { color: var(--secondary-text-color); }
          .sp-schluss-zeit.sp-schluss-frei { font-size: 1.05rem; font-weight: 600;
            color: var(--secondary-text-color); }
          .sp-gross .sp-schluss-name { font-size: 1.25rem; }
          .sp-gross .sp-schluss-zeit { font-size: 1.9rem; }
          .sp-gross .sp-schluss-sub { font-size: .9rem; }
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
    const aend = {};
    for (const x of a.aenderungen || [])
      if (x.stunde != null) aend[`${x.datum}|${x.stunde}`] = x;
    const arbTag = {};
    for (const x of a.arbeiten || [])
      (arbTag[x.datum] = arbTag[x.datum] || []).push(x);
    const arbKz = x => (x.kuerzel || x.fach || "").toUpperCase();

    html += `<table class="sp-tabelle"><colgroup><col style="width:54px"><col span="5"></colgroup><thead><tr><th></th>`;
    for (const t of tage) {
      const istHeute = aktuelleWoche && t.i === heute;
      const punkt = istHeute ? `<span class="sp-punkt-heute"> ●</span>` : "";
      const frei = t.frei ? `<small>${t.frei}</small>` : "";
      const arb = (arbTag[t.iso] || []).map(x =>
        `<small class="sp-arbeit-kopf" title="${x.typ}${x.fach ? " " + x.fach : ""}">📝 ${x.kuerzel || x.fach || x.typ}</small>`).join("");
      html += `<th class="${istHeute ? "sp-heute" : ""} ${t.frei ? "sp-tag-frei" : ""}">${t.l}${punkt}<small class="sp-datum">${fmt(t.datum)}</small>${frei}${arb}</th>`;
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
        const x = aend[`${t.iso}|${st.nr}`];
        const arbeit = kz && (arbTag[t.iso] || []).find(w => arbKz(w) === kz.toUpperCase()
          || (w.fach && f && w.fach.toUpperCase() === f.name.toUpperCase()));
        const entfall = x && (x.entfall || x.typ === "cancelledLesson");
        const vertretung = x && !entfall;
        const details = x ? [x.fach, x.lehrer, x.raum].filter(Boolean).join(" · ") : "";
        let badge = "";
        const info = x && x.grund ? `<small class="sp-notiz">ℹ️ ${x.grund}</small>` : "";
        if (entfall) {
          badge = `<small class="sp-aend">✕ ${x.label || "Entfall"}</small>${info}`;
        } else if (vertretung) {
          // Schulmanager-Optik: Originaldaten rot durchgestrichen, neue Angaben hervorgehoben
          const fNeu = x.fach && f && x.fach.toUpperCase() !== kz.toUpperCase()
            && x.fach.toUpperCase() !== f.name.toUpperCase() ? x.fach : "";
          const altDetail = f ? [fNeu ? kz : "", f.raum, f.lehrer].filter(Boolean).join(" · ") : "";
          const neuDetail = [fNeu, x.raum, x.lehrer].filter(Boolean).join(" · ");
          badge = (altDetail ? `<small class="sp-orig">${altDetail}</small>` : "")
            + (neuDetail ? `<small class="sp-neu">🔁 ${neuDetail}</small>`
                         : `<small class="sp-aend">🔁 ${x.label}</small>`) + info;
        }
        const aCls = (entfall ? "sp-entfall" : vertretung ? "sp-vertretung" : "") + (arbeit ? " sp-arbeit" : "");
        if (f) {
          const tip = `${f.name}${x ? " – " + x.label + (details ? " (" + details + ")" : "") + (x.grund ? ": " + x.grund : "") : ""}${arbeit ? " – " + arbeit.typ : ""}`;
          html += `<td class="${spalte}"><div class="sp-fach ${istJetzt ? "sp-aktuell" : ""} ${t.frei ? "sp-gedimmt" : ""} ${aCls}"
            style="background:${f.farbe}" title="${tip}">${kz}${arbeit ? " 📝" : ""}<small class="sp-name">${f.name}</small>${(f.raum || f.lehrer) && !vertretung ? `<small>${[f.raum, f.lehrer].filter(Boolean).join(" · ")}</small>` : ""}${badge}</div></td>`;
        } else if (x) {
          html += `<td class="${spalte}"><div class="sp-fach ${aCls}" style="background:var(--secondary-background-color,#444)">${badge}</div></td>`;
        } else {
          html += `<td class="${spalte}"><span class="sp-frei"></span></td>`;
        }
      }
      html += `</tr>`;
    });
    return html + `</tbody></table>` + this._standHTML(a);
  }

  _renderSchulschluss(ids) {
    const isoHeute = this._iso(new Date());
    const heute = this._heuteIdx();
    const zeit = this._jetztZeit();
    let html = `<ul class="sp-schluss">`;
    for (const id of ids) {
      const a = (this._hass.states[id] || {}).attributes;
      const name = this._kindName(id);
      const sensor = s => {
        const st = this._hass.states[id.replace(/_wochenplan$/, s)];
        return st && !["unavailable", "unknown"].includes(st.state) ? st.state : null;
      };
      let wert = "–", sub = "", cls = "";

      // Primaerquelle: die Backend-Sensoren (Single Source of Truth)
      let schluss = sensor("_schulschluss_heute");
      const aktuell = sensor("_aktuelle_stunde") || "";

      if (schluss === null && a && a.raster && a.plan) {
        // Fallback: lokal berechnen, falls der Sensor deaktiviert ist
        const frei = this._freiGrund(a, isoHeute);
        if (frei) schluss = "–";
        else if (heute < 0) schluss = "–";
        else {
          const plan = this._planFuerDatum(a, isoHeute)[StundenplanCard.TAGE[heute][0]] || [];
          const belegte = plan.map((kz, i) => kz && i < a.raster.length ? i : null)
            .filter(i => i !== null);
          schluss = belegte.length ? a.raster[belegte[belegte.length - 1]].bis : "–";
        }
      }

      if (schluss === null) {
        sub = "keine Daten";
      } else if (/^\d{2}:\d{2}$/.test(schluss)) {
        wert = schluss;
        if (zeit >= schluss) { sub = "Schule ist aus"; cls = "sp-schluss-vorbei"; }
        else {
          sub = "noch bis " + schluss;
          if (a && a.raster && a.plan && heute >= 0) {
            const plan = this._planFuerDatum(a, isoHeute)[StundenplanCard.TAGE[heute][0]] || [];
            const belegte = plan.map((kz, i) => kz && i < a.raster.length ? i : null)
              .filter(i => i !== null);
            const f = belegte.length ? (a.faecher || {})[plan[belegte[belegte.length - 1]]] : null;
            if (f) sub += " · zuletzt " + f.name;
          }
        }
      } else {
        // Kein Schulschluss heute: Grund aus dem Aktuelle-Stunde-Sensor
        const m = aktuell.match(/^Schulfrei \((.+)\)$/);
        wert = m ? m[1] : (aktuell === "Betrieb" ? "Betrieb"
          : heute < 0 ? "Wochenende" : "Schulfrei");
        cls = "sp-schluss-frei";
      }

      const ha = a && a.hausaufgaben_offen > 0
        ? `<span class="sp-ha-badge" title="offene Hausaufgaben">📚 ${a.hausaufgaben_offen}</span>` : "";
      html += `<li>
        <span class="sp-schluss-name">${name}${ha}</span>
        <span class="sp-schluss-sub">${sub}</span>
        <span class="sp-schluss-zeit ${cls}">${wert}</span>
      </li>`;
    }
    return html + `</ul>`;
  }

  _schuleInfoZeile(a) {
    const teile = [];
    if (a.hausaufgaben_offen > 0)
      teile.push(`📚 ${a.hausaufgaben_offen} offene Hausaufgabe${a.hausaufgaben_offen === 1 ? "" : "n"}`);
    const heuteIso = this._iso(new Date());
    const grenze = this._iso(new Date(Date.now() + 14 * 864e5));
    const liste = (a.arbeiten && a.arbeiten.length) ? a.arbeiten
      : a.naechste_arbeit ? [a.naechste_arbeit] : [];
    for (const arb of liste) {
      const d = arb.datum;
      if (!d || d < heuteIso || d > grenze) continue;
      const tage = Math.round((new Date(d + "T00:00") - new Date(heuteIso + "T00:00")) / 864e5);
      const wann = tage === 0 ? "heute" : tage === 1 ? "morgen" : `in ${tage} Tagen`;
      teile.push(`📝 ${arb.typ}${arb.fach ? " " + arb.fach : ""} ${wann}`);
    }
    let html = teile.length ? `<div class="sp-info">${teile.join(" · ")}</div>` : "";
    const faellig = a.hausaufgaben_faellig || [];
    if (faellig.length) {
      const heute = this._iso(new Date());
      const morgen = this._iso(new Date(Date.now() + 864e5));
      const label = d => d < heute ? "überfällig!" : d === heute ? "heute"
        : d === morgen ? "morgen" : new Date(d + "T00:00").toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" });
      html += `<ul class="sp-ha-liste">` + faellig.map(h =>
        `<li><span class="sp-ha-due ${h.due < heute ? "sp-ha-spaet" : ""}">${label(h.due)}</span>${h.titel}</li>`).join("") + `</ul>`;
    }
    return html;
  }

  _renderHeute(a) {
    const isoHeute = this._iso(new Date());
    if (a.modus !== "block") {
      const g = this._freiGrund(a, isoHeute);
      if (g) return `<div class="sp-leer">${g.replace("🏖 ", "🏖 Heute schulfrei – ")}</div>` + this._schuleInfoZeile(a) + this._standHTML(a);
    }
    const heute = this._heuteIdx();
    if (heute < 0) return `<div class="sp-leer">🎉 Wochenende – schulfrei!</div>` + this._schuleInfoZeile(a) + this._standHTML(a);
    if (!this._imBlock(a, new Date()))
      return `<div class="sp-leer">🏭 Betriebsphase – kein Blockunterricht heute</div>` + this._standHTML(a);
    const tag = StundenplanCard.TAGE[heute][0];
    const plan = this._planFuerDatum(a, isoHeute)[tag] || [];
    const zeit = this._jetztZeit();
    const r = a.raster;
    const aendH = {};
    for (const x of a.aenderungen || [])
      if (x.datum === isoHeute && x.stunde != null) aendH[x.stunde] = x;
    let html = `<ul class="sp-liste">`, stunden = 0;
    r.forEach((st, si) => {
      const kz = plan[si];
      const x = aendH[st.nr];
      if (!kz && !x) return;
      const f = kz ? ((a.faecher || {})[kz] || { name: kz, farbe: "#888" }) : { name: "", farbe: "#888" };
      const istJetzt = st.von <= zeit && zeit < st.bis;
      stunden++;
      const entf = x && (x.entfall || x.typ === "cancelledLesson");
      html += `<li class="${istJetzt ? "sp-aktuell" : ""} ${entf ? "sp-liste-entfall" : ""}">
        <span class="sp-punkt" style="background:${f.farbe}"></span>
        <span class="sp-lzeit">${st.von}–${st.bis}</span>
        <span class="sp-lname">${entf ? `<s>${f.name}</s> ✕ ${x.label || "Entfall"}` : f.name}${x && x.grund ? ` <span class="sp-notiz-inline">ℹ️ ${x.grund}</span>` : ""}${x && !entf && x.fach && x.fach.toUpperCase() !== (kz || "").toUpperCase() ? ` <span class="sp-laend">🔁 ${x.fach}</span>` : ""}</span>
        ${x && !entf && (x.raum || x.lehrer) ? `<span class="sp-lraum">🔁 ${(f.raum || f.lehrer) ? `<s class="sp-orig-inline">${[f.raum, f.lehrer].filter(Boolean).join(" · ")}</s> → ` : ""}${[x.raum, x.lehrer].filter(Boolean).join(" · ")}</span>` : (f.raum || f.lehrer) ? `<span class="sp-lraum">${[f.raum ? "Raum " + f.raum : "", f.lehrer].filter(Boolean).join(" · ")}</span>` : ""}
      </li>`;
    });
    html += `</ul>`;
    const material = [];
    r.forEach((st, si) => {
      const f = plan[si] ? (a.faecher || {})[plan[si]] : null;
      const m = f && (f.material || "").trim();
      if (m && !material.includes(m)) material.push(m);
    });
    if (stunden && material.length)
      html += `<div class="sp-material">🎒 Heute dabei: ${material.join(", ")}</div>`;
    html += this._schuleInfoZeile(a) + this._standHTML(a);
    return stunden ? html : `<div class="sp-leer">Heute kein Unterricht 🎈</div>` + this._schuleInfoZeile(a) + this._standHTML(a);
  }

  _standHTML(a) {
    if (!a || !a.daten_stand) return "";
    const d = new Date(a.daten_stand);
    if (isNaN(d)) return "";
    const txt = d.toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" })
      + ", " + d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    return `<div class="sp-stand" title="Letzter Datenabruf aus der Schul-Integration">Daten: ${txt}</div>`;
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
        { value: "schulschluss", label: "Schulschluss heute (alle Kinder)" },
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
console.info("%c STUNDENPLAN-CARD %c v1.16.2", "background:#4a90d9;color:#fff;padding:2px 6px;border-radius:3px", "");
