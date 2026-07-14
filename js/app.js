/* =========================================================
   app.js  —  Bike TCO Compare  (Nepal edition)
   ---------------------------------------------------------
   Major change: separate evUsage and petrolUsage states.
   Each bike has independent daily_km, ride_days, years.
   ========================================================= */

(function (global) {
  'use strict';

  const data = global.TCOData;
  const calc = global.TCOCalc;
  const { CostChart } = global.TCOCharts;
  const ui = global.TCOUI;

  const $ = (id) => document.getElementById(id);

  /* ---------- State ----------
     ev / petrol: bike objects with all numeric fields.
     evUsage / petrolUsage: { dailyKm, rideDays, years } — INDEPENDENT.
     currency: one of CURRENCIES entries. */
  const state = {
    ev: null,
    petrol: null,
    evUsage: { ...data.DEFAULT_USAGE.ev },
    petrolUsage: { ...data.DEFAULT_USAGE.petrol },
    currency: data.CURRENCIES[data.DEFAULT_CURRENCY]
  };

  let chart = null;

  /* ---------- Convert a preset to a live bike object ---------- */
  function presetToBike(preset, type, currency) {
    const rate = currency.rate;
    const bike = {
      type,
      id: preset.id,
      name: preset.name,
      price: Math.round(preset.price * rate),
      service: Math.round(preset.service * rate),
      insurance: Math.round(preset.insurance * rate),
      tax: Math.round(preset.tax * rate),
      resale: Math.round(preset.price * preset.resalePct * rate),
      includeResale: true,
      additional: []  // user-added costs (battery repair, tyres, accessories, etc.)
    };
    if (type === 'ev') {
      bike.range = preset.range;
      bike.battery = preset.battery;
      bike.elecRate = currency.elecRate;
    } else {
      bike.mileage = preset.mileage;
      bike.fuelRate = currency.fuelRate;
    }
    return bike;
  }

  /* ---------- Populate preset dropdowns ---------- */
  function populatePresets() {
    const evSel = $('evPreset');
    const petSel = $('petrolPreset');
    const curEvId = evSel.value;
    const curPetId = petSel.value;
    evSel.innerHTML = data.EV_PRESETS.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    petSel.innerHTML = data.PETROL_PRESETS.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    // Try to preserve selection
    if (data.EV_PRESETS.find(p => p.id === curEvId)) evSel.value = curEvId;
    if (data.PETROL_PRESETS.find(p => p.id === curPetId)) petSel.value = curPetId;
  }

  function loadEvPreset(id) {
    const p = data.EV_PRESETS.find(x => x.id === id) || data.EV_PRESETS[0];
    state.ev = presetToBike(p, 'ev', state.currency);
    // Update the name input to match the preset name
    const nameInput = $('evName');
    if (nameInput) nameInput.value = state.ev.name;
    refreshDetailInputs();
    recompute();
  }
  function loadPetrolPreset(id) {
    const p = data.PETROL_PRESETS.find(x => x.id === id) || data.PETROL_PRESETS[0];
    state.petrol = presetToBike(p, 'petrol', state.currency);
    const nameInput = $('petrolName');
    if (nameInput) nameInput.value = state.petrol.name;
    refreshDetailInputs();
    recompute();
  }

  /* ---------- Refresh detail inputs from state ---------- */
  function refreshDetailInputs() {
    if (!state.ev || !state.petrol) return;
    setNum('data-ev', 'price', state.ev.price);
    setNum('data-ev', 'range', state.ev.range);
    setNum('data-ev', 'battery', state.ev.battery);
    setNum('data-ev', 'elecRate', state.ev.elecRate);
    setNum('data-ev', 'service', state.ev.service);
    setNum('data-ev', 'insurance', state.ev.insurance);
    setNum('data-ev', 'tax', state.ev.tax);
    setNum('data-ev', 'resale', state.ev.resale);
    $('evIncludeResale').checked = state.ev.includeResale;

    setNum('data-petrol', 'price', state.petrol.price);
    setNum('data-petrol', 'mileage', state.petrol.mileage);
    setNum('data-petrol', 'fuelRate', state.petrol.fuelRate);
    setNum('data-petrol', 'service', state.petrol.service);
    setNum('data-petrol', 'insurance', state.petrol.insurance);
    setNum('data-petrol', 'tax', state.petrol.tax);
    setNum('data-petrol', 'resale', state.petrol.resale);
    $('petrolIncludeResale').checked = state.petrol.includeResale;
  }
  function setNum(attr, field, val) {
    const el = document.querySelector(`[${attr}="${field}"]`);
    if (el) {
      if (field === 'elecRate' || field === 'fuelRate' || field === 'battery') {
        el.value = Number(val).toFixed(field === 'battery' ? 1 : 2);
      } else {
        el.value = Math.round(val);
      }
    }
  }

  /* ---------- Refresh usage inputs ---------- */
  function refreshUsageInputs() {
    $('evDailyKm').value = state.evUsage.dailyKm;
    $('evDailyKmNum').value = state.evUsage.dailyKm;
    $('evRideDays').value = state.evUsage.rideDays;
    $('evRideDaysNum').value = state.evUsage.rideDays;
    $('evYears').value = state.evUsage.years;
    $('evYearsNum').value = state.evUsage.years;

    $('petrolDailyKm').value = state.petrolUsage.dailyKm;
    $('petrolDailyKmNum').value = state.petrolUsage.dailyKm;
    $('petrolRideDays').value = state.petrolUsage.rideDays;
    $('petrolRideDaysNum').value = state.petrolUsage.rideDays;
    $('petrolYears').value = state.petrolUsage.years;
    $('petrolYearsNum').value = state.petrolUsage.years;
  }

  /* ---------- Update all currency symbols in the DOM ---------- */
  // Remember original unit-label templates so we can swap currency symbols
  // cleanly when the user switches currency (रू → $ → ₹ etc.)
  let _originalUnitTexts = null;

  function updateCurrencySymbols() {
    const sym = state.currency.symbol;
    // Replace all <span data-cur> placeholders (used in np-defaults paragraph)
    document.querySelectorAll('[data-cur]').forEach(el => { el.textContent = sym; });
    // On first call, capture the original "cur"-templated text of each unit label.
    // On subsequent calls, restore from the captured template and re-substitute.
    if (!_originalUnitTexts) {
      _originalUnitTexts = new Map();
      document.querySelectorAll('.unit').forEach(el => {
        _originalUnitTexts.set(el, el.textContent);
      });
    }
    document.querySelectorAll('.unit').forEach(el => {
      const original = _originalUnitTexts.get(el);
      if (original && original.includes('cur')) {
        el.textContent = original.replace(/\bcur\b/g, sym);
      }
    });
  }

  /* ---------- Refresh usage summary labels ---------- */
  function refreshUsageSummaries() {
    const evAnnual = calc.annualKm(state.evUsage);
    const petAnnual = calc.annualKm(state.petrolUsage);
    const evTotal = evAnnual * state.evUsage.years;
    const petTotal = petAnnual * state.petrolUsage.years;
    const sym = state.currency.symbol;
    $('evUsageSummary').innerHTML = `<strong>${evAnnual.toLocaleString(state.currency.locale)}</strong> km/yr · <strong>${evTotal.toLocaleString(state.currency.locale)}</strong> km over ${state.evUsage.years} yr`;
    $('petrolUsageSummary').innerHTML = `<strong>${petAnnual.toLocaleString(state.currency.locale)}</strong> km/yr · <strong>${petTotal.toLocaleString(state.currency.locale)}</strong> km over ${state.petrolUsage.years} yr`;
    // Also update resale year labels
    document.querySelectorAll('.resale-years-ev').forEach(s => s.textContent = state.evUsage.years);
    document.querySelectorAll('.resale-years-petrol').forEach(s => s.textContent = state.petrolUsage.years);
  }

  /* ---------- Full refresh ---------- */
  function fullRefresh() {
    updateCurrencySymbols();
    refreshUsageInputs();
    refreshDetailInputs();
    renderAdditionalItems();
    recompute();
  }

  /* ---------- Recompute and re-render ---------- */
  function recompute() {
    if (!state.ev || !state.petrol) return;
    refreshUsageSummaries();
    ui.update(state);
    if (chart) chart.draw(state);
  }

  /* ---------- Bindings ---------- */
  function bindAll() {
    // Presets
    $('evPreset').addEventListener('change', (e) => loadEvPreset(e.target.value));
    $('petrolPreset').addEventListener('change', (e) => loadPetrolPreset(e.target.value));

    // Bike name inputs (user can rename any bike, including presets)
    const evNameInput = $('evName');
    const petrolNameInput = $('petrolName');
    if (evNameInput) {
      evNameInput.addEventListener('input', () => {
        if (state.ev) {
          state.ev.name = evNameInput.value || 'Electric';
          recompute();
        }
      });
    }
    if (petrolNameInput) {
      petrolNameInput.addEventListener('input', () => {
        if (state.petrol) {
          state.petrol.name = petrolNameInput.value || 'Petrol';
          recompute();
        }
      });
    }

    // EV usage (independent)
    bindPair('evDailyKm', 'evDailyKmNum', (v) => state.evUsage.dailyKm = v, 1, 150);
    bindPair('evRideDays', 'evRideDaysNum', (v) => state.evUsage.rideDays = v, 1, 7);
    bindPair('evYears', 'evYearsNum', (v) => state.evUsage.years = v, 1, 12);

    // Petrol usage (independent)
    bindPair('petrolDailyKm', 'petrolDailyKmNum', (v) => state.petrolUsage.dailyKm = v, 1, 150);
    bindPair('petrolRideDays', 'petrolRideDaysNum', (v) => state.petrolUsage.rideDays = v, 1, 7);
    bindPair('petrolYears', 'petrolYearsNum', (v) => state.petrolUsage.years = v, 1, 12);

    // Detail inputs
    document.querySelectorAll('[data-ev]').forEach(el => {
      el.addEventListener('input', () => {
        const field = el.getAttribute('data-ev');
        const v = parseFloat(el.value);
        if (isNaN(v)) return;
        state.ev[field] = v;
        recompute();
      });
    });
    document.querySelectorAll('[data-petrol]').forEach(el => {
      el.addEventListener('input', () => {
        const field = el.getAttribute('data-petrol');
        const v = parseFloat(el.value);
        if (isNaN(v)) return;
        state.petrol[field] = v;
        recompute();
      });
    });
    $('evIncludeResale').addEventListener('change', (e) => {
      state.ev.includeResale = e.target.checked;
      recompute();
    });
    $('petrolIncludeResale').addEventListener('change', (e) => {
      state.petrol.includeResale = e.target.checked;
      recompute();
    });

    // Details collapsible
    const caret = $('caretDetails');
    const wrap = $('detailsWrap');
    caret.addEventListener('click', () => {
      const open = wrap.hasAttribute('hidden');
      if (open) {
        wrap.removeAttribute('hidden');
        caret.setAttribute('aria-expanded', 'true');
      } else {
        wrap.setAttribute('hidden', '');
        caret.setAttribute('aria-expanded', 'false');
      }
    });

    // Info button toggle (for "Add any other cost" section)
    const infoBtn = document.querySelector('#step-additional .info-btn');
    const infoPopup = $('additionalInfoPopup');
    if (infoBtn && infoPopup) {
      infoBtn.addEventListener('click', () => {
        infoPopup.hidden = !infoPopup.hidden;
      });
      // Close on outside click
      document.addEventListener('click', (e) => {
        if (!infoPopup.hidden && !infoPopup.contains(e.target) && !infoBtn.contains(e.target)) {
          infoPopup.hidden = true;
        }
      });
    }

    // Additional costs — add/remove items
    const addEvBtn = $('btnAddEvItem');
    const addPetBtn = $('btnAddPetrolItem');
    if (addEvBtn) addEvBtn.addEventListener('click', () => addAdditionalItem('ev'));
    if (addPetBtn) addPetBtn.addEventListener('click', () => addAdditionalItem('petrol'));

    // Currency switch (dropdown)
    const curSel = $('currencySelect');
    if (curSel) {
      curSel.addEventListener('change', () => {
        switchCurrency(curSel.value);
      });
    }

    // Quick templates
    document.querySelectorAll('.qt-btn').forEach(btn => {
      btn.addEventListener('click', () => applyTemplate(btn.dataset.template));
    });

    // Print & reset
    $('btnPrint').addEventListener('click', () => window.print());
    $('btnReset').addEventListener('click', resetAll);

    // Refresh prices from web (uses fetcher.js with CORS proxy + fallback)
    const refreshBtn = $('btnRefresh');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', refreshPricesFromWeb);
    }

    window.addEventListener('resize', () => {
      if (chart) chart.resize();
    });
  }

  function bindPair(rangeId, numId, setter, min, max) {
    const r = $(rangeId), n = $(numId);
    r.addEventListener('input', () => {
      const v = parseInt(r.value, 10);
      setter(v);
      n.value = v;
      recompute();
    });
    n.addEventListener('input', () => {
      let v = parseInt(n.value, 10);
      if (isNaN(v)) return;
      v = calc.clamp(v, min, max);
      setter(v);
      r.value = v;
      recompute();
    });
    n.addEventListener('change', () => {
      let v = parseInt(n.value, 10);
      if (isNaN(v)) v = parseInt(r.value, 10);
      v = calc.clamp(v, min, max);
      n.value = v;
      setter(v);
      r.value = v;
      recompute();
    });
  }

  /* ---------- Switch currency ---------- */
  function switchCurrency(code) {
    const newCur = data.CURRENCIES[code];
    if (!newCur) return;
    const oldRate = state.currency.rate;
    const newRate = newCur.rate;
    const factor = newRate / oldRate;

    ['price', 'service', 'insurance', 'tax', 'resale'].forEach(k => {
      if (state.ev) state.ev[k] = Math.round(state.ev[k] * factor);
      if (state.petrol) state.petrol[k] = Math.round(state.petrol[k] * factor);
    });
    if (state.ev) state.ev.elecRate = +(state.ev.elecRate * (newCur.elecRate / state.currency.elecRate)).toFixed(2);
    if (state.petrol) state.petrol.fuelRate = +(state.petrol.fuelRate * (newCur.fuelRate / state.currency.fuelRate)).toFixed(2);
    // Convert additional cost amounts too
    if (state.ev && state.ev.additional) {
      state.ev.additional.forEach(item => { if (item.amount) item.amount = Math.round(item.amount * factor); });
    }
    if (state.petrol && state.petrol.additional) {
      state.petrol.additional.forEach(item => { if (item.amount) item.amount = Math.round(item.amount * factor); });
    }

    state.currency = newCur;
    fullRefresh();
  }

  /* ---------- Apply template ---------- */
  function applyTemplate(id) {
    const t = data.TEMPLATES[id];
    if (!t) return;
    state.evUsage = { dailyKm: t.evDailyKm, rideDays: t.evRideDays, years: t.evYears };
    state.petrolUsage = { dailyKm: t.petDailyKm, rideDays: t.petRideDays, years: t.petYears };
    const evPreset = data.EV_PRESETS.find(p => p.id === t.evPreset);
    const petrolPreset = data.PETROL_PRESETS.find(p => p.id === t.petrolPreset);
    state.ev = presetToBike(evPreset, 'ev', state.currency);
    state.petrol = presetToBike(petrolPreset, 'petrol', state.currency);
    $('evPreset').value = t.evPreset;
    $('petrolPreset').value = t.petrolPreset;
    fullRefresh();
  }

  /* ---------- Reset all ---------- */
  function resetAll() {
    state.evUsage = { ...data.DEFAULT_USAGE.ev };
    state.petrolUsage = { ...data.DEFAULT_USAGE.petrol };
    state.currency = data.CURRENCIES[data.DEFAULT_CURRENCY];
    const curSel = $('currencySelect');
    if (curSel) curSel.value = data.DEFAULT_CURRENCY;
    state.ev = presetToBike(data.EV_PRESETS[0], 'ev', state.currency);
    state.petrol = presetToBike(data.PETROL_PRESETS[0], 'petrol', state.currency);
    $('evPreset').value = data.EV_PRESETS[0].id;
    $('petrolPreset').value = data.PETROL_PRESETS[0].id;
    fullRefresh();
  }

  /* ---------- Additional costs (battery repair, tyres, accessories, etc.) ---------- */
  function renderAdditionalItems() {
    renderAdditionalList('ev');
    renderAdditionalList('petrol');
  }

  function renderAdditionalList(type) {
    const bike = state[type];
    const listEl = $(type === 'ev' ? 'evAdditionalList' : 'petrolAdditionalList');
    if (!listEl || !bike) return;
    const items = bike.additional || [];
    if (items.length === 0) {
      listEl.innerHTML = '<div class="additional-empty">No extra costs added.</div>';
      return;
    }
    listEl.innerHTML = items.map((item, idx) => {
      return `
        <div class="additional-item" data-type="${type}" data-idx="${idx}">
          <input type="text" class="add-label" value="${escapeAttr(item.label || '')}" placeholder="e.g. Tyre replacement" maxlength="40">
          <input type="number" class="add-amount" value="${item.amount || ''}" placeholder="0" min="0" step="100">
          <input type="number" class="add-year" value="${item.year || 1}" placeholder="1" min="1" max="12" step="1">
          <button class="remove-item-btn" title="Remove">×</button>
        </div>
      `;
    }).join('');
    // Bind inputs
    listEl.querySelectorAll('.additional-item').forEach(row => {
      const idx = parseInt(row.dataset.idx, 10);
      const t = row.dataset.type;
      const labelInput = row.querySelector('.add-label');
      const amtInput = row.querySelector('.add-amount');
      const yrInput = row.querySelector('.add-year');
      const rmBtn = row.querySelector('.remove-item-btn');
      labelInput.addEventListener('input', () => {
        state[t].additional[idx].label = labelInput.value;
      });
      amtInput.addEventListener('input', () => {
        const v = parseFloat(amtInput.value);
        state[t].additional[idx].amount = isNaN(v) ? 0 : v;
        recompute();
      });
      yrInput.addEventListener('input', () => {
        let v = parseInt(yrInput.value, 10);
        if (isNaN(v)) v = 1;
        v = calc.clamp(v, 1, 12);
        state[t].additional[idx].year = v;
        recompute();
      });
      rmBtn.addEventListener('click', () => {
        state[t].additional.splice(idx, 1);
        renderAdditionalItems();
        recompute();
      });
    });
  }

  function addAdditionalItem(type) {
    const bike = state[type];
    if (!bike) return;
    if (!bike.additional) bike.additional = [];
    bike.additional.push({ label: '', amount: 0, year: 1 });
    renderAdditionalItems();
    // Focus the newly added label input
    const listEl = $(type === 'ev' ? 'evAdditionalList' : 'petrolAdditionalList');
    if (listEl) {
      const lastRow = listEl.querySelector('.additional-item:last-child .add-label');
      if (lastRow) lastRow.focus();
    }
  }

  function escapeAttr(s) {
    return String(s || '').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /* ---------- Refresh prices from the web ----------
     Uses TCOFetcher (fetcher.js) to fetch latest models & prices.
     Falls back gracefully to existing presets on any error.
     Shows progress in the button label. */
  async function refreshPricesFromWeb() {
    const btn = $('btnRefresh');
    const originalLabel = btn.innerHTML;
    if (!global.TCOFetcher) {
      alert('Fetcher module not loaded. Refresh unavailable.');
      return;
    }
    btn.disabled = true;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/></svg><span>Fetching...</span>`;

    try {
      const result = await global.TCOFetcher.refreshPresets(
        data.EV_PRESETS,
        data.PETROL_PRESETS,
        (msg) => { btn.querySelector('span').textContent = msg.slice(0, 24); }
      );
      // Update the data module's preset lists
      data.EV_PRESETS = result.ev;
      data.PETROL_PRESETS = result.petrol;
      // Rebuild dropdowns
      populatePresets();
      // Reload current selections (in case IDs changed)
      loadEvPreset($('evPreset').value);
      loadPetrolPreset($('petrolPreset').value);
      fullRefresh();
      btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg><span>✓ Refreshed (+${result.newEvCount + result.newPetrolCount})</span>`;
      setTimeout(() => { btn.innerHTML = originalLabel; btn.disabled = false; }, 3500);
    } catch (e) {
      console.error('Refresh failed:', e);
      btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg><span>Refresh failed</span>`;
      setTimeout(() => { btn.innerHTML = originalLabel; btn.disabled = false; }, 3500);
    }
  }

  /* ---------- Init ---------- */
  function init() {
    populatePresets();
    state.ev = presetToBike(data.EV_PRESETS[0], 'ev', state.currency);
    state.petrol = presetToBike(data.PETROL_PRESETS[0], 'petrol', state.currency);
    // Set name inputs to match default presets
    $('evName').value = state.ev.name;
    $('petrolName').value = state.petrol.name;
    updateCurrencySymbols();
    refreshUsageInputs();
    refreshDetailInputs();
    renderAdditionalItems();
    bindAll();

    chart = new CostChart($('costChart'), $('chartTooltip'));
    chart.resize();
    recompute();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})(window);
