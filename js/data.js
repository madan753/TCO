/* =========================================================
   data.js  —  Bike TCO Compare  (NEPAL edition)
   ---------------------------------------------------------
   Why Nepal edition?
     • Default currency is NPR (रू)
     • Electricity rate default: रू9.8 / kWh (Nepal Electricity Authority)
     • Petrol price default: रू175 / litre (2024 average)
     • Bike presets use real on-road prices from Nepali dealers
     • Insurance, bluebook (annual road tax) and service costs
       are Nepal-typical
   ---------------------------------------------------------
   KEY DESIGN DECISION:
   Each bike has its OWN usage profile (daily km, ride days/week,
   ownership years). Users don't ride an EV and a petrol bike the
   same way — electric is so cheap per km that owners ride more,
   and petrol owners often cut back when fuel is expensive.
   ========================================================= */

(function (global) {
  'use strict';

  /* ---------- Currency config ----------
     NPR is the default. INR and USD kept for cross-border reference,
     with realistic 2024 rates and per-unit costs. */
  const CURRENCIES = {
    NPR: {
      symbol: 'रू',
      code: 'NPR',
      locale: 'ne-NP',
      rate: 1,             // baseline (NPR is the source currency now)
      elecRate: 9.8,       // रू/kWh — Nepal Electricity Authority domestic tier
      fuelRate: 175,       // रू/litre — Nepal petrol, 2024 average
      label: 'Nepal (रू)'
    },
    INR: {
      symbol: '₹',
      code: 'INR',
      locale: 'en-IN',
      rate: 0.625,         // 1 NPR ≈ ₹0.625
      elecRate: 8.0,
      fuelRate: 105.5,
      label: 'India (₹)'
    },
    USD: {
      symbol: '$',
      code: 'USD',
      locale: 'en-US',
      rate: 0.0075,        // 1 NPR ≈ $0.0075
      elecRate: 0.12,
      fuelRate: 1.30,
      label: 'US ($)'
    }
  };

  /* ---------- Bike presets ----------
     On-road prices in NPR (Nepal). Includes typical dealer offer
     prices, government EV subsidy where applicable, and bluebook
     first-year fees. Specs are manufacturer-published.
     Source: Nepali dealer listings, 2024.
     resalePct = % of price recovered after the ownership period. */

  const EV_PRESETS = [
    {
      id: 'komaki-xgt-km',
      name: 'Komaki XGT KM',
      price: 215000,        // popular budget EV scooter in Nepal
      range: 80,            // km per full charge
      battery: 2.0,         // kWh
      service: 1500,        // annual service
      insurance: 2800,      // third-party + basic own-damage
      tax: 2500,            // bluebook renewal
      resalePct: 0.40
    },
    {
      id: 'yadea-g5',
      name: 'Yadea G5',
      price: 280000,
      range: 90,
      battery: 2.5,
      service: 1800,
      insurance: 3000,
      tax: 2500,
      resalePct: 0.38
    },
    {
      id: 'tvs-iqube-np',
      name: 'TVS iQube Electric',
      price: 335000,
      range: 100,
      battery: 3.04,
      service: 2000,
      insurance: 3500,
      tax: 2500,
      resalePct: 0.42
    },
    {
      id: 'bajaj-chetak-np',
      name: 'Bajaj Chetak Electric',
      price: 345000,
      range: 95,
      battery: 2.9,
      service: 2200,
      insurance: 3500,
      tax: 2500,
      resalePct: 0.42
    },
    {
      id: 'niu-nqi',
      name: 'NIU NQi Sport',
      price: 415000,
      range: 70,
      battery: 2.0,
      service: 2500,
      insurance: 4000,
      tax: 2500,
      resalePct: 0.40
    },
    {
      id: 'yatri-p0',
      name: 'Yatri Project Zero (motorcycle)',
      price: 600000,
      range: 120,
      battery: 4.0,
      service: 3000,
      insurance: 5000,
      tax: 3000,
      resalePct: 0.38
    },
    {
      id: 'ev-custom',
      name: 'Custom EV (enter your own)',
      price: 300000,
      range: 90,
      battery: 2.5,
      service: 2000,
      insurance: 3000,
      tax: 2500,
      resalePct: 0.40
    }
  ];

  const PETROL_PRESETS = [
    {
      id: 'honda-dio',
      name: 'Honda Dio',
      price: 240000,
      mileage: 50,           // km/litre
      service: 2500,         // annual service
      insurance: 2800,       // third-party mandatory + own damage
      tax: 2500,             // bluebook renewal
      resalePct: 0.55
    },
    {
      id: 'tvs-jupiter-np',
      name: 'TVS Jupiter',
      price: 235000,
      mileage: 50,
      service: 2500,
      insurance: 2800,
      tax: 2500,
      resalePct: 0.55
    },
    {
      id: 'honda-activa-np',
      name: 'Honda Activa 6G',
      price: 250000,
      mileage: 50,
      service: 2500,
      insurance: 2800,
      tax: 2500,
      resalePct: 0.55
    },
    {
      id: 'suzuki-access-np',
      name: 'Suzuki Access 125',
      price: 270000,
      mileage: 48,
      service: 2700,
      insurance: 3000,
      tax: 2500,
      resalePct: 0.53
    },
    {
      id: 'honda-shine-np',
      name: 'Honda CB Shine 125 (motorcycle)',
      price: 272000,
      mileage: 55,
      service: 2700,
      insurance: 3000,
      tax: 2500,
      resalePct: 0.52
    },
    {
      id: 'bajaj-pulsar-np',
      name: 'Bajaj Pulsar 150 (motorcycle)',
      price: 355000,
      mileage: 45,
      service: 3200,
      insurance: 3500,
      tax: 3000,
      resalePct: 0.50
    },
    {
      id: 'yamaha-fzs',
      name: 'Yamaha FZ-S V3 (motorcycle)',
      price: 380000,
      mileage: 45,
      service: 3200,
      insurance: 3500,
      tax: 3000,
      resalePct: 0.50
    },
    {
      id: 'petrol-custom',
      name: 'Custom petrol bike (enter your own)',
      price: 250000,
      mileage: 50,
      service: 2700,
      insurance: 3000,
      tax: 2500,
      resalePct: 0.53
    }
  ];

  /* ---------- Quick-start templates ----------
     Each template sets SEPARATE usage profiles for EV and petrol,
     because real users ride them differently. */
  const TEMPLATES = {
    city: {
      label: 'City Commuter (Kathmandu)',
      evDailyKm: 22, evRideDays: 6, evYears: 5,
      petDailyKm: 18, petRideDays: 6, petYears: 5,
      evPreset: 'komaki-xgt-km',
      petrolPreset: 'honda-dio'
    },
    delivery: {
      label: 'Delivery / Pathao Rider',
      evDailyKm: 90, evRideDays: 7, evYears: 4,
      petDailyKm: 80, petRideDays: 7, petYears: 4,
      evPreset: 'tvs-iqube-np',
      petrolPreset: 'suzuki-access-np'
    },
    occasional: {
      label: 'Weekend Rider',
      evDailyKm: 12, evRideDays: 3, evYears: 5,
      petDailyKm: 10, petRideDays: 3, petYears: 5,
      evPreset: 'yadea-g5',
      petrolPreset: 'tvs-jupiter-np'
    },
    longterm: {
      label: 'Long-Term Owner (8 yr)',
      evDailyKm: 25, evRideDays: 6, evYears: 8,
      petDailyKm: 22, petRideDays: 6, petYears: 8,
      evPreset: 'bajaj-chetak-np',
      petrolPreset: 'bajaj-pulsar-np'
    }
  };

  /* ---------- Depreciation constants ---------- */
  const DEGRADATION = {
    evBattPer10k: 0.05,    // EV range drops 5% per 10,000 km
    petrolEngPer15k: 0.05, // petrol mileage drops 5% per 15,000 km
    servicePer10k: 0.02    // service cost drifts up 2% per 10,000 km
  };

  /* ---------- Default usage (separate per bike) ---------- */
  const DEFAULT_USAGE = {
    ev:   { dailyKm: 22, rideDays: 6, years: 5 },
    petrol: { dailyKm: 18, rideDays: 6, years: 5 }
  };

  /* ---------- Export ---------- */
  global.TCOData = {
    CURRENCIES,
    EV_PRESETS,
    PETROL_PRESETS,
    TEMPLATES,
    DEGRADATION,
    DEFAULT_USAGE,
    DEFAULT_CURRENCY: 'NPR'
  };

})(window);
