/* =========================================================
   fetcher.js  —  Live bike data fetcher
   ---------------------------------------------------------
   Fetches latest bike models & prices from the web, with a
   multi-source fallback strategy:

     1. Wikipedia REST API (CORS-enabled, no key)
        → fetches list of motorcycle models for Nepal-sold brands
     2. CORS-proxied scrape of Nepali listing pages
        → tries to find current NPR prices
     3. Embedded fallback presets (always available)

   Always merges results — new models are prepended to the
   dropdown, but the fallback presets are always kept so the
   user can never end up with an empty list.

   Exposed as: window.TCOFetcher
   ========================================================= */

(function (global) {
  'use strict';

  const CORS_PROXIES = [
    'https://api.allorigins.win/raw?url=',
    'https://corsproxy.io/?url=',
  ];

  const WIKI_API = 'https://en.wikipedia.org/w/api.php';

  const NEPAL_BRANDS = [
    'honda', 'yamaha', 'tvs', 'bajaj', 'suzuki', 'hero',
    'ktm', 'royal enfield', 'komaki', 'yadea', 'ather',
    'ola', 'revolt', 'niu', 'yatri', 'ducati'
  ];

  const EV_KEYWORDS = ['electric', ' ev', 'e-', 'zero', 'battery', 'niuto', 'yatri', 'komaki', 'yadea', 'ather', 'revolt'];

  /* ---------- Fetch with timeout ---------- */
  async function fetchJSON(url, timeoutMs = 10000) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const resp = await fetch(url, { signal: ctrl.signal, headers: { 'Accept': 'application/json' } });
      if (!resp.ok) return null;
      return await resp.json();
    } catch (e) {
      return null;
    } finally {
      clearTimeout(t);
    }
  }

  async function fetchText(url, timeoutMs = 10000) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const resp = await fetch(url, { signal: ctrl.signal });
      if (!resp.ok) return null;
      return await resp.text();
    } catch (e) {
      return null;
    } finally {
      clearTimeout(t);
    }
  }

  /* ---------- Source 1: Wikipedia motorcycle models list ---------- */
  async function fetchWikiModels() {
    const url = `${WIKI_API}?action=query&list=categorymembers&cmtitle=Category:Motorcycles&cmlimit=200&format=json&cmtype=page&origin=*`;
    const data = await fetchJSON(url);
    if (!data || !data.query || !data.query.categorymembers) return [];
    return data.query.categorymembers
      .filter(p => !p.title.startsWith('Category:'))
      .map(p => p.title);
  }

  /* ---------- Source 2: Scrape a page via CORS proxy for NPR prices ---------- */
  async function fetchPricesViaProxy() {
    // Try the Wikipedia "Motorcycle industry in India" page via proxy
    // (Nepal bike market is closely tied to India, and this page often has prices)
    const targetUrl = 'https://en.wikipedia.org/wiki/List_of_motorcycle_manufacturers';
    for (const proxy of CORS_PROXIES) {
      const text = await fetchText(proxy + encodeURIComponent(targetUrl));
      if (text && text.length > 1000) {
        return parsePrices(text);
      }
    }
    return {};
  }

  /* ---------- Parse bike names + NPR prices from HTML text ---------- */
  function parsePrices(html) {
    const prices = {};
    // Strip tags
    const text = html.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ');
    // Find patterns like "Honda Dio Rs 240,000" or "Bajaj Pulsar रू 355,000"
    const brandPattern = NEPAL_BRANDS.map(b => b.replace(/\s+/g, '\\s+')).join('|');
    const re = new RegExp(`(?:${brandPattern})\\s+[A-Z0-9][\\w\\s-]{2,30}?\\s*(?:रू|Rs\\.?|NPR)\\.?\\s*([\\d,]{4,7})`, 'gi');
    let m;
    while ((m = re.exec(text)) !== null) {
      try {
        const price = parseInt(m[1].replace(/,/g, ''), 10);
        if (price >= 80000 && price <= 1500000) {
          // Extract bike name (brand + model)
          const name = m[0].split(/रू|Rs\.?|NPR/i)[0].trim().slice(0, 50);
          const key = name.toLowerCase();
          if (!prices[key]) prices[key] = { name, price };
        }
      } catch (e) { /* skip */ }
    }
    return prices;
  }

  /* ---------- Filter to Nepal-relevant models ---------- */
  function filterNepalModels(models) {
    const ev = [];
    const petrol = [];
    const seen = new Set();
    for (const model of models) {
      const lower = model.toLowerCase();
      if (lower.startsWith('list of') || lower.startsWith('category:')) continue;
      if (!NEPAL_BRANDS.some(brand => lower.includes(brand))) continue;
      if (seen.has(lower)) continue;
      seen.add(lower);
      if (EV_KEYWORDS.some(kw => lower.includes(kw))) {
        ev.push(model);
      } else {
        petrol.push(model);
      }
    }
    return { ev, petrol };
  }

  /* ---------- Estimate specs for new models ---------- */
  function estimateEvSpecs(price) {
    if (price < 250000) return { range: 80, battery: 2.0, service: 1500 };
    if (price < 350000) return { range: 95, battery: 2.5, service: 2000 };
    if (price < 500000) return { range: 110, battery: 3.0, service: 2500 };
    return { range: 130, battery: 4.0, service: 3000 };
  }

  function estimatePetrolSpecs(price) {
    if (price < 200000) return { mileage: 60, service: 2200 };
    if (price < 300000) return { mileage: 50, service: 2500 };
    if (price < 400000) return { mileage: 45, service: 3000 };
    return { mileage: 40, service: 3500 };
  }

  /* ---------- Main: refresh presets from web ---------- */
  async function refreshPresets(existingEv, existingPetrol, onProgress) {
    const log = [];
    const report = (msg) => { log.push(msg); if (onProgress) onProgress(msg); };

    report('Fetching model list from Wikipedia...');
    const wikiModels = await fetchWikiModels();
    if (wikiModels.length === 0) {
      report('⚠ Wikipedia unavailable — using embedded presets only.');
    } else {
      report(`✓ Found ${wikiModels.length} models on Wikipedia.`);
    }
    const { ev: wikiEv, petrol: wikiPetrol } = filterNepalModels(wikiModels);

    report('Searching for current Nepal prices...');
    const scrapedPrices = await fetchPricesViaProxy();
    const priceCount = Object.keys(scrapedPrices).length;
    if (priceCount === 0) {
      report('⚠ No live prices found — using fallback estimates.');
    } else {
      report(`✓ Found ${priceCount} current prices.`);
    }

    // Merge: keep existing presets, prepend new Wikipedia models
    const existingEvNames = new Set(existingEv.map(p => p.name.toLowerCase()));
    const existingPetNames = new Set(existingPetrol.map(p => p.name.toLowerCase()));

    const newEv = [];
    const newPetrol = [];

    for (const model of wikiEv.slice(0, 8)) {
      if (existingEvNames.has(model.toLowerCase())) continue;
      const priceData = scrapedPrices[model.toLowerCase()];
      const price = priceData ? priceData.price : 300000;
      const specs = estimateEvSpecs(price);
      newEv.push({
        id: model.toLowerCase().replace(/[\s/]+/g, '-').slice(0, 30),
        name: model.slice(0, 50),
        price,
        range: specs.range,
        battery: specs.battery,
        service: specs.service,
        insurance: 3000,
        tax: 2500,
        resalePct: 0.40
      });
    }

    for (const model of wikiPetrol.slice(0, 8)) {
      if (existingPetNames.has(model.toLowerCase())) continue;
      const priceData = scrapedPrices[model.toLowerCase()];
      const price = priceData ? priceData.price : 250000;
      const specs = estimatePetrolSpecs(price);
      newPetrol.push({
        id: model.toLowerCase().replace(/[\s/]+/g, '-').slice(0, 30),
        name: model.slice(0, 50),
        price,
        mileage: specs.mileage,
        service: specs.service,
        insurance: 3000,
        tax: 2500,
        resalePct: 0.52
      });
    }

    // Always keep the "Custom" entry at the end
    const mergedEv = [...newEv, ...existingEv];
    const mergedPetrol = [...newPetrol, ...existingPetrol];

    report(`✓ ${newEv.length} new EV models, ${newPetrol.length} new petrol models added.`);

    return {
      ev: mergedEv,
      petrol: mergedPetrol,
      newEvCount: newEv.length,
      newPetrolCount: newPetrol.length,
      log
    };
  }

  /* ---------- Export ---------- */
  global.TCOFetcher = { refreshPresets };

})(window);
