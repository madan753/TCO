/* =========================================================
   ui.js  —  Bike TCO Compare  (Nepal edition)
   ---------------------------------------------------------
   Renders verdict, 6 KPI cards (incl. per-km cost),
   breakdown bars, sensitivity table, year-by-year table.
   Verdict honestly mentions both usage profiles.
   ========================================================= */

(function (global) {
  'use strict';

  const calc = global.TCOCalc;
  const { COLORS } = global.TCOCharts;

  const $ = (id) => document.getElementById(id);

  const els = {
    verdictHeadline: $('verdictHeadline'),
    verdictSub: $('verdictSub'),
    verdictUsage: $('verdictUsage'),
    vbarEv: $('vbarEv'),
    vbarPetrol: $('vbarPetrol'),
    vbarEvAmt: $('vbarEvAmt'),
    vbarPetrolAmt: $('vbarPetrolAmt'),

    kpiEv: $('kpiEv'),
    kpiPetrol: $('kpiPetrol'),
    kpiEvPerKm: $('kpiEvPerKm'),
    kpiPetrolPerKm: $('kpiPetrolPerKm'),
    kpiSave: $('kpiSave'),
    kpiBe: $('kpiBe'),
    kpiEvFoot: $('kpiEvFoot'),
    kpiPetrolFoot: $('kpiPetrolFoot'),
    kpiEvPerKmFoot: $('kpiEvPerKmFoot'),
    kpiPetrolPerKmFoot: $('kpiPetrolPerKmFoot'),
    kpiSaveFoot: $('kpiSaveFoot'),
    kpiBeFoot: $('kpiBeFoot'),

    breakdownBars: $('breakdownBars'),
    breakdownLegend: $('breakdownLegend'),

    sensitivityTableBody: $('sensitivityTable').querySelector('tbody'),
    yearTableBody: $('yearTable').querySelector('tbody')
  };

  /* ---------- Verdict ---------- */
  function renderVerdict(state) {
    const { ev, petrol, evUsage, petrolUsage, currency } = state;
    const evFinal = calc.finalCost(ev, evUsage);
    const petFinal = calc.finalCost(petrol, petrolUsage);
    const diff = petFinal - evFinal;
    const be = calc.breakevenDay(ev, evUsage, petrol, petrolUsage);

    const evAnnualKm = calc.annualKm(evUsage);
    const petAnnualKm = calc.annualKm(petrolUsage);
    const evTotalKm = evAnnualKm * evUsage.years;
    const petTotalKm = petAnnualKm * petrolUsage.years;

    // Headline
    let headline, sub;
    if (diff > 0) {
      headline = `Electric saves you ${calc.formatCurrency(diff, currency)} over the ownership period.`;
      if (be === null) {
        sub = `EV is cheaper from day one and stays ahead — petrol never catches up.`;
      } else if (be <= 0.01) {
        sub = `The ${ev.name} is cheaper from the very first kilometre.`;
      } else {
        const beYr = (be / 365).toFixed(1);
        const beKm = Math.round(be * calc.dailyKmEffective(evUsage)).toLocaleString(currency.locale);
        sub = `EV breaks even at year ${beYr} (around ${beKm} km on the EV's odometer), then keeps saving you money every kilometre after.`;
      }
    } else if (diff < 0) {
      headline = `Petrol saves you ${calc.formatCurrency(-diff, currency)} over the ownership period.`;
      if (evTotalKm < petTotalKm * 0.6 || petTotalKm < evTotalKm * 0.6) {
        sub = `Note: the two ownership patterns are quite different in distance. Look at the per-km cost cards below for a fairer comparison.`;
      } else if (Math.min(evTotalKm, petTotalKm) < 12000) {
        sub = `You ride less than ~12,000 km total — at this distance the EV's higher purchase price doesn't get paid back.`;
      } else {
        sub = `Based on your numbers, the EV's running-cost advantage isn't enough to overcome its higher sticker price.`;
      }
    } else {
      headline = `Both bikes cost about the same over their ownership periods.`;
      sub = `Pick the one that fits your riding style — there's no clear money winner here.`;
    }

    els.verdictHeadline.textContent = headline;
    els.verdictSub.textContent = sub;

    // Usage summary line
    els.verdictUsage.innerHTML = `
      <div class="vu-row">
        <span class="vu-tag ev">⚡ EV</span>
        <span><strong>${ev.name}</strong> · ${evAnnualKm.toLocaleString(currency.locale)} km/yr · ${evUsage.years} yr · ${evTotalKm.toLocaleString(currency.locale)} km total</span>
      </div>
      <div class="vu-row">
        <span class="vu-tag petrol">⛽ Petrol</span>
        <span><strong>${petrol.name}</strong> · ${petAnnualKm.toLocaleString(currency.locale)} km/yr · ${petrolUsage.years} yr · ${petTotalKm.toLocaleString(currency.locale)} km total</span>
      </div>
    `;

    // Bars
    const maxCost = Math.max(evFinal, petFinal, 1);
    els.vbarEv.style.width = (evFinal / maxCost * 100).toFixed(1) + '%';
    els.vbarPetrol.style.width = (petFinal / maxCost * 100).toFixed(1) + '%';
    els.vbarEvAmt.textContent = calc.formatCurrency(evFinal, currency);
    els.vbarPetrolAmt.textContent = calc.formatCurrency(petFinal, currency);
  }

  /* ---------- KPI cards ---------- */
  function renderKPIs(state) {
    const { ev, petrol, evUsage, petrolUsage, currency } = state;
    const evFinal = calc.finalCost(ev, evUsage);
    const petFinal = calc.finalCost(petrol, petrolUsage);
    const diff = petFinal - evFinal;
    const be = calc.breakevenDay(ev, evUsage, petrol, petrolUsage);

    const evAnnualKm = calc.annualKm(evUsage);
    const petAnnualKm = calc.annualKm(petrolUsage);
    const evTotalKm = evAnnualKm * evUsage.years;
    const petTotalKm = petAnnualKm * petrolUsage.years;

    const evPerKm = calc.perKmTotal(ev, evUsage);
    const petPerKm = calc.perKmTotal(petrol, petrolUsage);

    els.kpiEv.textContent = calc.formatCurrency(evFinal, currency);
    els.kpiPetrol.textContent = calc.formatCurrency(petFinal, currency);
    els.kpiEvFoot.textContent = `${evUsage.years} yr · ${evTotalKm.toLocaleString(currency.locale)} km`;
    els.kpiPetrolFoot.textContent = `${petrolUsage.years} yr · ${petTotalKm.toLocaleString(currency.locale)} km`;

    els.kpiEvPerKm.textContent = calc.formatCurrency(evPerKm, currency, { decimals: 2 });
    els.kpiPetrolPerKm.textContent = calc.formatCurrency(petPerKm, currency, { decimals: 2 });
    els.kpiEvPerKmFoot.textContent = `${evTotalKm.toLocaleString(currency.locale)} km total`;
    els.kpiPetrolPerKmFoot.textContent = `${petTotalKm.toLocaleString(currency.locale)} km total`;

    if (diff >= 0) {
      els.kpiSave.textContent = calc.formatCurrency(diff, currency);
      els.kpiSaveFoot.textContent = `EV wins by this much`;
    } else {
      els.kpiSave.textContent = '-' + calc.formatCurrency(-diff, currency).replace(/^-/, '');
      els.kpiSaveFoot.textContent = `petrol is cheaper`;
    }

    if (be === null) {
      els.kpiBe.textContent = diff > 0 ? 'Day 1' : 'Never';
      els.kpiBeFoot.textContent = diff > 0 ? `EV wins from the start` : `EV doesn't catch up`;
    } else if (be <= 0.01) {
      els.kpiBe.textContent = 'Day 1';
      els.kpiBeFoot.textContent = `EV wins from the start`;
    } else {
      const beYr = (be / 365).toFixed(1);
      els.kpiBe.textContent = `Yr ${beYr}`;
      els.kpiBeFoot.textContent = `~${Math.round(be).toLocaleString()} days`;
    }
  }

  /* ---------- Breakdown bars ---------- */
  const SEG_COLORS = {
    price: '#1b2330',
    running: '#2563eb',
    service: '#7c3aed',
    insurance: '#0891b2',
    tax: '#65a30d',
    additional: '#dc2626',
    resale: '#9ca3af'
  };
  const SEG_LABELS = {
    price: 'Purchase',
    running: 'Fuel / Electricity',
    service: 'Service',
    insurance: 'Insurance',
    tax: 'Bluebook',
    additional: 'Extra costs',
    resale: 'Resale (−)'
  };

  function renderBreakdown(state) {
    const { ev, petrol, evUsage, petrolUsage, currency } = state;
    const evBd = calc.breakdown(ev, evUsage);
    const petBd = calc.breakdown(petrol, petrolUsage);
    const maxTotal = Math.max(evBd.total, petBd.total, 1);

    let html = '';
    html += renderBdRow('ev', ev.name, evBd, maxTotal, currency);
    html += renderBdRow('petrol', petrol.name, petBd, maxTotal, currency);
    els.breakdownBars.innerHTML = html;

    let legendHtml = '';
    Object.keys(SEG_LABELS).forEach(k => {
      legendHtml += `<span class="bl-item"><span class="swatch" style="background:${SEG_COLORS[k]}"></span>${SEG_LABELS[k]}</span>`;
    });
    els.breakdownLegend.innerHTML = legendHtml;
  }

  function renderBdRow(type, name, bd, maxTotal, currency) {
    const segs = ['price', 'running', 'service', 'insurance', 'tax', 'additional', 'resale'];
    const totalNet = bd.total;
    const scale = 100 / maxTotal;
    let segHtml = '';
    segs.forEach(k => {
      const v = bd[k] || 0;
      if (v <= 0 && k === 'resale') return;
      if (v <= 0 && k === 'additional') return;
      const w = v * scale;
      if (w < 0.5) return;
      const showAmt = w > 8 ? calc.formatCurrencyShort(v, currency) : '';
      segHtml += `<div class="bd-seg" style="width:${w}%;background:${SEG_COLORS[k]}">${showAmt}</div>`;
    });
    return `
      <div class="bd-row">
        <div class="bd-row-head">
          <span class="bd-row-name ${type}">${type === 'ev' ? '⚡' : '⛽'} ${escapeHtml(name)}</span>
          <span class="bd-row-total">${calc.formatCurrency(totalNet, currency)}</span>
        </div>
        <div class="bd-bar">${segHtml}</div>
      </div>
    `;
  }

  /* ---------- Sensitivity table ---------- */
  function renderSensitivity(state) {
    const { ev, petrol, evUsage, petrolUsage, currency } = state;
    const result = calc.sensitivity(ev, evUsage, petrol, petrolUsage);

    let html = '';
    // Baseline row
    const b = result.baseline;
    html += `
      <tr class="baseline-row">
        <td>Baseline (your inputs)</td>
        <td class="ev">${calc.formatCurrency(b.ev, currency)}</td>
        <td class="petrol">${calc.formatCurrency(b.petrol, currency)}</td>
        <td class="diff ${b.diff >= 0 ? 'save' : 'lose'}">${b.diff >= 0 ? '+' : '−'} ${calc.formatCurrency(Math.abs(b.diff), currency)}</td>
        <td class="winner ${b.diff >= 0 ? 'ev' : 'petrol'}">${b.diff >= 0 ? 'EV' : 'Petrol'}</td>
      </tr>
    `;
    // Scenario rows
    result.scenarios.forEach(s => {
      const winnerCls = s.winner === 'ev' ? 'ev' : (s.winner === 'petrol' ? 'petrol' : 'tie');
      const winnerLabel = s.winner === 'ev' ? 'EV' : (s.winner === 'petrol' ? 'Petrol' : 'Tie');
      const diffCls = s.diff >= 0 ? 'save' : 'lose';
      html += `
        <tr>
          <td>${s.label}</td>
          <td class="ev">${calc.formatCurrency(s.evFinal, currency)} <span class="delta">(${s.evDelta >= 0 ? '+' : ''}${calc.formatCurrencyShort(s.evDelta, currency)})</span></td>
          <td class="petrol">${calc.formatCurrency(s.petFinal, currency)} <span class="delta">(${s.petDelta >= 0 ? '+' : ''}${calc.formatCurrencyShort(s.petDelta, currency)})</span></td>
          <td class="diff ${diffCls}">${s.diff >= 0 ? '+' : '−'} ${calc.formatCurrency(Math.abs(s.diff), currency)}</td>
          <td class="winner ${winnerCls}">${winnerLabel}</td>
        </tr>
      `;
    });
    els.sensitivityTableBody.innerHTML = html;
  }

  /* ---------- Year-by-year table ---------- */
  function renderYearTable(state) {
    const { ev, petrol, evUsage, petrolUsage, currency } = state;
    const rows = calc.yearByYear(ev, evUsage, petrol, petrolUsage);
    let html = '';
    rows.forEach((r, idx) => {
      const isLast = idx === rows.length - 1;
      const isEvLast = r.evActive && r.year === evUsage.years;
      const isPetLast = r.petActive && r.year === petrolUsage.years;
      const diffCls = r.diff >= 0 ? 'save' : 'lose';
      const diffSign = r.diff >= 0 ? '+' : '−';
      const diffAmt = calc.formatCurrency(Math.abs(r.diff), currency);
      // Mark resale drop in the last active year for each bike
      const evMark = !r.evActive ? ' <span class="held-note">(held)</span>'
                    : (isEvLast && ev.includeResale) ? ` <span class="resale-note">−${calc.formatCurrency(ev.resale, currency)} resale</span>`
                    : '';
      const petMark = !r.petActive ? ' <span class="held-note">(held)</span>'
                    : (isPetLast && petrol.includeResale) ? ` <span class="resale-note">−${calc.formatCurrency(petrol.resale, currency)} resale</span>`
                    : '';
      html += `
        <tr class="${isLast ? 'total-row' : ''}">
          <td>Year ${r.year}${isLast ? ' (final)' : ''}</td>
          <td class="ev">${calc.formatCurrency(r.ev, currency)}${evMark}</td>
          <td class="petrol">${calc.formatCurrency(r.petrol, currency)}${petMark}</td>
          <td class="diff ${diffCls}">${diffSign} ${diffAmt}</td>
        </tr>
      `;
    });
    els.yearTableBody.innerHTML = html;
  }

  /* ---------- Master update ---------- */
  function update(state) {
    if (!state.ev || !state.petrol) return;
    renderVerdict(state);
    renderKPIs(state);
    renderBreakdown(state);
    renderSensitivity(state);
    renderYearTable(state);
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  global.TCOUI = { update };

})(window);
