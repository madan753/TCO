/* =========================================================
   calculator.js  —  Bike TCO Compare  (Nepal edition)
   ---------------------------------------------------------
   KEY CHANGE vs prior version:
   Each bike gets its OWN usage profile (dailyKm, rideDays, years).
   The calculator no longer assumes EV and petrol riders behave
   the same way.
   ========================================================= */

(function (global) {
  'use strict';

  const { DEGRADATION } = global.TCOData;

  /* ---------- Math helpers ---------- */
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  /* ---------- Effective annual distance ----------
     dailyKm × rideDays × (52 weeks / year). */
  function annualKm(usage) {
    return usage.dailyKm * usage.rideDays * 52;
  }
  function dailyKmEffective(usage) {
    return annualKm(usage) / 365;
  }

  /* ---------- Energy / fuel per km ---------- */
  function evKwhPerKm(bike) {
    if (!bike.range || bike.range <= 0) return 0;
    return bike.battery / bike.range;
  }
  function petrolLitresPerKm(bike) {
    if (!bike.mileage || bike.mileage <= 0) return 0;
    return 1 / bike.mileage;
  }

  /* ---------- Average degradation multiplier ---------- */
  function avgDegMultiplier(day, perKm, perUnit, dailyKm) {
    if (perUnit <= 0 || day <= 0 || perKm <= 0) return 1;
    const dist = dailyKm * day;
    return 1 + (perKm * dist) / (2 * perUnit);
  }

  /* ---------- Core: cost at a given day (per-bike usage) ---------- */
  function costAtDay(bike, usage, day, opts = {}) {
    const totalDays = usage.years * 365;
    const dd = clamp(day, 0, totalDays);

    const dKm = dailyKmEffective(usage);
    const distance = dKm * dd;

    // Running cost
    let runningCost = 0;
    if (bike.type === 'ev') {
      const kwhPerKm = evKwhPerKm(bike);
      const avgFactor = avgDegMultiplier(dd, DEGRADATION.evBattPer10k, 10000, dKm);
      runningCost = distance * kwhPerKm * bike.elecRate * avgFactor;
    } else {
      const lPerKm = petrolLitresPerKm(bike);
      const avgFactor = avgDegMultiplier(dd, DEGRADATION.petrolEngPer15k, 15000, dKm);
      runningCost = distance * lPerKm * bike.fuelRate * avgFactor;
    }

    // Service cost (drifts up)
    const avgServFactor = avgDegMultiplier(dd, DEGRADATION.servicePer10k, 10000, dKm);
    const serviceCost = (dd / 365) * bike.service * avgServFactor;

    // Insurance + bluebook (annual, fixed)
    const fixedCost = (dd / 365) * (bike.insurance + bike.tax);

    // Additional costs (battery repair, tyres, accessories, etc.)
    // Each item: { amount, year } — applied once at the start of that year.
    // Year 1 = days 0–365, Year 2 = days 365–730, etc.
    let additionalCost = 0;
    if (bike.additional && Array.isArray(bike.additional)) {
      bike.additional.forEach(item => {
        if (!item.amount) return;
        const itemYear = item.year || 1;
        const itemDay = (itemYear - 1) * 365;
        if (dd >= itemDay) {
          additionalCost += item.amount;
        }
      });
    }

    let cost = bike.price + runningCost + serviceCost + fixedCost + additionalCost;

    // Resale — applied as a SINGLE sharp drop at the end of ownership.
    const includeResale = opts.includeResale !== false;
    if (includeResale && bike.includeResale !== false && totalDays > 0 && day >= totalDays - 1e-6) {
      cost -= bike.resale;
    }
    return cost;
  }

  function finalCost(bike, usage, opts) {
    return costAtDay(bike, usage, usage.years * 365, opts);
  }

  /* ---------- Cost WITHOUT resale (for chart rendering) ----------
     Returns the cumulative cost at a given day, ignoring resale entirely.
     The chart uses this to draw the rising line; resale is then drawn as
     a separate vertical drop segment at the end-of-ownership day. */
  function costAtDayNoResale(bike, usage, day) {
    return costAtDay(bike, usage, day, { includeResale: false });
  }

  /* ---------- Is this the resale-drop day? ---------- */
  function isResaleDay(bike, usage, day) {
    if (!bike.includeResale) return false;
    const totalDays = usage.years * 365;
    return totalDays > 0 && day >= totalDays - 1e-6;
  }

  /* ---------- Cost breakdown (per-bike usage) ---------- */
  function breakdown(bike, usage, opts = {}) {
    const totalDays = usage.years * 365;
    const dKm = dailyKmEffective(usage);
    const distance = dKm * totalDays;

    let running = 0;
    if (bike.type === 'ev') {
      const kwhPerKm = evKwhPerKm(bike);
      const avgFactor = avgDegMultiplier(totalDays, DEGRADATION.evBattPer10k, 10000, dKm);
      running = distance * kwhPerKm * bike.elecRate * avgFactor;
    } else {
      const lPerKm = petrolLitresPerKm(bike);
      const avgFactor = avgDegMultiplier(totalDays, DEGRADATION.petrolEngPer15k, 15000, dKm);
      running = distance * lPerKm * bike.fuelRate * avgFactor;
    }

    const avgServFactor = avgDegMultiplier(totalDays, DEGRADATION.servicePer10k, 10000, dKm);
    const service = usage.years * bike.service * avgServFactor;
    const insurance = usage.years * bike.insurance;
    const tax = usage.years * bike.tax;

    // Additional costs — sum all items
    let additional = 0;
    if (bike.additional && Array.isArray(bike.additional)) {
      bike.additional.forEach(item => {
        if (item.amount) additional += item.amount;
      });
    }

    const includeResale = opts.includeResale !== false;
    const resaleApplied = (includeResale && bike.includeResale !== false) ? bike.resale : 0;

    const total = bike.price + running + service + insurance + tax + additional - resaleApplied;
    return { price: bike.price, running, service, insurance, tax, additional, resale: resaleApplied, total };
  }

  /* ---------- Breakeven day (numerical sampling, per-bike usage) ----------
     Now this is tricky: EV and petrol have DIFFERENT ownership periods.
     We compare CUMULATIVE COST over a COMMON time horizon = max(evYears, petrolYears).
     The EV line stops at evYears; petrol line stops at petrolYears.
     For days after one bike's ownership ends, we hold its cost flat
     (no more spending, no resale drop because resale already happened). */
  function costAtDayExtended(bike, usage, day, opts = {}) {
    const totalDays = usage.years * 365;
    if (day <= totalDays) return costAtDay(bike, usage, day, opts);
    // Beyond ownership — final cost (with resale already applied)
    return finalCost(bike, usage, opts);
  }

  function breakevenDay(ev, evUsage, petrol, petrolUsage) {
    if (!ev || !petrol) return null;
    const maxDays = Math.max(evUsage.years, petrolUsage.years) * 365;

    const diff0 = costAtDayExtended(ev, evUsage, 0) - costAtDayExtended(petrol, petrolUsage, 0);
    if (diff0 <= 0) return 0;

    const samples = 240;
    let prevDiff = diff0;
    let prevDay = 0;
    for (let i = 1; i <= samples; i++) {
      const day = (i / samples) * maxDays;
      const diff = costAtDayExtended(ev, evUsage, day) - costAtDayExtended(petrol, petrolUsage, day);
      if (diff <= 0 && prevDiff > 0) {
        const ratio = prevDiff / (prevDiff - diff);
        return prevDay + (day - prevDay) * ratio;
      }
      prevDiff = diff;
      prevDay = day;
    }
    return null;
  }

  /* ---------- Year-by-year (uses max years; shows where each bike ends) ---------- */
  function yearByYear(ev, evUsage, petrol, petrolUsage, opts) {
    const maxYears = Math.max(evUsage.years, petrolUsage.years);
    const rows = [];
    for (let y = 1; y <= maxYears; y++) {
      const day = y * 365;
      const evActive = y <= evUsage.years;
      const petActive = y <= petrolUsage.years;
      const evCost = evActive
        ? costAtDay(ev, evUsage, day, opts)
        : finalCost(ev, evUsage, opts);    // hold flat after ownership
      const petCost = petActive
        ? costAtDay(petrol, petrolUsage, day, opts)
        : finalCost(petrol, petrolUsage, opts);
      rows.push({
        year: y,
        evActive, petActive,
        ev: evCost, petrol: petCost,
        diff: petCost - evCost
      });
    }
    return rows;
  }

  /* ---------- Per-km running cost (excludes purchase/resale) ---------- */
  function perKmRunning(bike) {
    if (bike.type === 'ev') {
      return evKwhPerKm(bike) * bike.elecRate;
    }
    return petrolLitresPerKm(bike) * bike.fuelRate;
  }

  /* ---------- Total per-km cost (TCO ÷ total km) ---------- */
  function perKmTotal(bike, usage, opts) {
    const total = finalCost(bike, usage, opts);
    const km = annualKm(usage) * usage.years;
    return km > 0 ? total / km : 0;
  }

  /* ---------- Sensitivity analysis ----------
     Returns verdict changes when fuel/electricity prices shift. */
  function sensitivity(ev, evUsage, petrol, petrolUsage, opts = {}) {
    const scenarios = [
      { label: 'Fuel +10%',  fuelMul: 1.10, elecMul: 1.00 },
      { label: 'Fuel +25%',  fuelMul: 1.25, elecMul: 1.00 },
      { label: 'Fuel +50%',  fuelMul: 1.50, elecMul: 1.00 },
      { label: 'Elec +10%',  fuelMul: 1.00, elecMul: 1.10 },
      { label: 'Elec +25%',  fuelMul: 1.00, elecMul: 1.25 },
      { label: 'Elec +50%',  fuelMul: 1.00, elecMul: 1.50 },
      { label: 'Both +25%',  fuelMul: 1.25, elecMul: 1.25 },
      { label: 'Both −10%',  fuelMul: 0.90, elecMul: 0.90 }
    ];
    const baseline = {
      ev: finalCost(ev, evUsage, opts),
      petrol: finalCost(petrol, petrolUsage, opts)
    };
    baseline.diff = baseline.petrol - baseline.ev;

    const results = scenarios.map(s => {
      const evMod = { ...ev, elecRate: ev.elecRate * s.elecMul };
      const petMod = { ...petrol, fuelRate: petrol.fuelRate * s.fuelMul };
      const evFinal = finalCost(evMod, evUsage, opts);
      const petFinal = finalCost(petMod, petrolUsage, opts);
      const diff = petFinal - evFinal;
      return {
        label: s.label,
        evFinal, petFinal, diff,
        evDelta: evFinal - baseline.ev,
        petDelta: petFinal - baseline.petrol,
        winner: diff > 0 ? 'ev' : (diff < 0 ? 'petrol' : 'tie')
      };
    });
    return { baseline, scenarios: results };
  }

  /* ---------- Currency formatting ---------- */
  function formatCurrency(amount, currency, opts = {}) {
    const { symbol, locale, code } = currency;
    const decimals = opts.decimals != null ? opts.decimals : 0;
    const abs = Math.abs(amount);
    let numStr;
    if (code === 'INR' || code === 'NPR') {
      numStr = indianGrouping(abs, decimals);
    } else {
      numStr = abs.toLocaleString(locale, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
      });
    }
    const sign = amount < 0 ? '-' : '';
    if (code === 'USD') return `${sign}${symbol}${numStr}`;
    return `${sign}${symbol}${numStr}`;
  }

  function indianGrouping(amount, decimals = 0) {
    const sign = amount < 0 ? '-' : '';
    const amt = Math.abs(amount);
    let intPart, frac;
    if (decimals > 0) {
      const s = amt.toFixed(decimals);
      [intPart, frac] = s.split('.');
    } else {
      intPart = String(Math.round(amt));
      frac = '';
    }
    let grouped;
    if (intPart.length <= 3) {
      grouped = intPart;
    } else {
      const last3 = intPart.slice(-3);
      let rest = intPart.slice(0, -3);
      const chunks = [];
      while (rest.length > 2) {
        chunks.unshift(rest.slice(-2));
        rest = rest.slice(0, -2);
      }
      if (rest.length) chunks.unshift(rest);
      grouped = chunks.length ? chunks.join(',') + ',' + last3 : last3;
    }
    return sign + grouped + (decimals > 0 ? '.' + frac : '');
  }

  function formatCurrencyShort(amount, currency) {
    const { symbol, locale, code } = currency;
    const a = Math.abs(amount);
    const sign = amount < 0 ? '-' : '';
    let str;
    if (a >= 1e7) str = (a / 1e7).toFixed(2) + 'Cr';
    else if (a >= 1e5) str = (a / 1e5).toFixed(2) + 'L';
    else if (a >= 1e3) str = (a / 1e3).toFixed(1) + 'K';
    else str = String(Math.round(a));
    return sign + symbol + str;
  }

  /* ---------- Export ---------- */
  global.TCOCalc = {
    clamp,
    annualKm,
    dailyKmEffective,
    evKwhPerKm,
    petrolLitresPerKm,
    costAtDay,
    costAtDayNoResale,
    costAtDayExtended,
    finalCost,
    isResaleDay,
    breakdown,
    breakevenDay,
    yearByYear,
    perKmRunning,
    perKmTotal,
    sensitivity,
    formatCurrency,
    formatCurrencyShort
  };

})(window);
