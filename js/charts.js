/* =========================================================
   charts.js  —  Bike TCO Compare  (Nepal edition)
   ---------------------------------------------------------
   Handles different ownership periods for EV vs petrol.
   Each bike's line stops at its own year-end; after that,
   cost is held flat (no further spending, no resale drop).
   ========================================================= */

(function (global) {
  'use strict';

  const { clamp, formatCurrency, formatCurrencyShort } = global.TCOCalc;

  const COLORS = {
    ev: '#16a34a',
    evSoft: 'rgba(22,163,74,0.12)',
    petrol: '#ea580c',
    petrolSoft: 'rgba(234,88,12,0.12)',
    gold: '#ca8a04',
    grid: 'rgba(0,0,0,0.06)',
    axis: '#9ca3af',
    ink: '#1b2330',
    ink2: '#3b4453'
  };

  class CostChart {
    constructor(canvas, tooltipEl) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.tooltip = tooltipEl;
      this.dpr = window.devicePixelRatio || 1;
      this.W = 0;
      this.H = 0;
      this.pad = { l: 64, r: 16, t: 14, b: 32 };
      this.mouseX = null;
      this.mouseY = null;
      this.lastDraw = null;

      this._resizeBound = () => this.resize();
      window.addEventListener('resize', this._resizeBound);

      canvas.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        this.mouseX = e.clientX - rect.left;
        this.mouseY = e.clientY - rect.top;
        this.draw(this.lastDraw.state);
        this.updateTooltip();
      });
      canvas.addEventListener('mouseleave', () => {
        this.mouseX = null;
        this.mouseY = null;
        this.tooltip.hidden = true;
        this.draw(this.lastDraw.state);
      });
    }

    resize() {
      const rect = this.canvas.getBoundingClientRect();
      this.W = rect.width;
      this.H = rect.height;
      this.canvas.width = this.W * this.dpr;
      this.canvas.height = this.H * this.dpr;
      this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      if (this.lastDraw) this.draw(this.lastDraw.state);
    }

    draw(state) {
      this.lastDraw = { state };
      const { ev, petrol, evUsage, petrolUsage, currency } = state;
      const { ctx, W, H, pad } = this;
      if (!ev || !petrol || W === 0) return;

      const plotW = Math.max(10, W - pad.l - pad.r);
      const plotH = Math.max(10, H - pad.t - pad.b);
      ctx.clearRect(0, 0, W, H);

      const maxDays = Math.max(evUsage.years, petrolUsage.years) * 365;
      const evDays = evUsage.years * 365;
      const petDays = petrolUsage.years * 365;

      // --- Sample both lines ---
      // We sample the NO-RESALE cost (the rising line) and separately compute
      // the final cost WITH resale (the drop). This makes the chart show:
      //   1. A rising line during ownership (no resale credit)
      //   2. A sharp vertical drop at the end-of-ownership day (resale applied)
      const sampleCount = 80;
      let yMin = Infinity, yMax = -Infinity;
      const samples = [];
      for (let i = 0; i <= sampleCount; i++) {
        const day = (i / sampleCount) * maxDays;
        const evC = global.TCOCalc.costAtDayExtended(ev, evUsage, day);
        const petC = global.TCOCalc.costAtDayExtended(petrol, petrolUsage, day);
        // Also track no-resale cost for chart line drawing
        const evCNoResale = global.TCOCalc.costAtDayExtended(ev, evUsage, day) + (global.TCOCalc.isResaleDay(ev, evUsage, day) ? ev.resale : 0);
        const petCNoResale = global.TCOCalc.costAtDayExtended(petrol, petrolUsage, day) + (global.TCOCalc.isResaleDay(petrol, petrolUsage, day) ? petrol.resale : 0);
        samples.push({ day, evC, petC, evCNoResale, petCNoResale });
        yMin = Math.min(yMin, evC, petC, evCNoResale, petCNoResale);
        yMax = Math.max(yMax, evC, petC, evCNoResale, petCNoResale);
      }
      const yPad = (yMax - yMin) * 0.08;
      yMin = Math.min(yMin - yPad, 0);
      yMax = yMax + yPad;
      const yRange = Math.max(1, yMax - yMin);

      const mapX = (day) => pad.l + (day / maxDays) * plotW;
      const mapY = (cost) => pad.t + plotH - clamp((cost - yMin) / yRange, 0, 1) * plotH;

      // --- Y-axis grid + labels ---
      ctx.font = '500 11px "JetBrains Mono", monospace';
      ctx.fillStyle = COLORS.axis;
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      const yTicks = 5;
      for (let i = 0; i <= yTicks; i++) {
        const val = yMin + (yRange / yTicks) * i;
        const y = mapY(val);
        ctx.strokeStyle = COLORS.grid;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pad.l, y);
        ctx.lineTo(pad.l + plotW, y);
        ctx.stroke();
        ctx.fillText(formatCurrencyShort(val, currency), pad.l - 8, y);
      }

      // --- X-axis labels (years) ---
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const maxYears = maxDays / 365;
      const yearTicks = Math.min(Math.ceil(maxYears), 12);
      for (let y = 0; y <= yearTicks; y++) {
        const day = y * 365;
        const x = mapX(day);
        ctx.fillStyle = COLORS.axis;
        ctx.fillText('Y' + y, x, pad.t + plotH + 8);
      }

      // --- Vertical markers for end-of-ownership (if different) ---
      if (evDays !== maxDays) {
        const x = mapX(evDays);
        ctx.strokeStyle = 'rgba(22,163,74,0.35)';
        ctx.setLineDash([2, 4]);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, pad.t);
        ctx.lineTo(x, pad.t + plotH);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = 'rgba(22,163,74,0.9)';
        ctx.font = '600 9px "Inter", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('EV ends', x, pad.t + 2);
      }
      if (petDays !== maxDays) {
        const x = mapX(petDays);
        ctx.strokeStyle = 'rgba(234,88,12,0.35)';
        ctx.setLineDash([2, 4]);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, pad.t);
        ctx.lineTo(x, pad.t + plotH);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = 'rgba(234,88,12,0.9)';
        ctx.font = '600 9px "Inter", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Petrol ends', x, pad.t + 14);
      }

      // --- Area fills (use no-resale cost so area rises during ownership) ---
      ctx.fillStyle = COLORS.evSoft;
      ctx.beginPath();
      ctx.moveTo(mapX(0), mapY(samples[0].evCNoResale));
      samples.forEach(s => ctx.lineTo(mapX(s.day), mapY(s.evCNoResale)));
      ctx.lineTo(mapX(samples[samples.length - 1].day), pad.t + plotH);
      ctx.lineTo(mapX(0), pad.t + plotH);
      ctx.closePath();
      ctx.fill();

      ctx.fillStyle = COLORS.petrolSoft;
      ctx.beginPath();
      ctx.moveTo(mapX(0), mapY(samples[0].petCNoResale));
      samples.forEach(s => ctx.lineTo(mapX(s.day), mapY(s.petCNoResale)));
      ctx.lineTo(mapX(samples[samples.length - 1].day), pad.t + plotH);
      ctx.lineTo(mapX(0), pad.t + plotH);
      ctx.closePath();
      ctx.fill();

      // --- Lines (rising, no resale) ---
      ctx.strokeStyle = COLORS.petrol;
      ctx.lineWidth = 2.6;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.beginPath();
      samples.forEach((s, i) => {
        const x = mapX(s.day), y = mapY(s.petCNoResale);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();

      ctx.strokeStyle = COLORS.ev;
      ctx.lineWidth = 2.6;
      ctx.beginPath();
      samples.forEach((s, i) => {
        const x = mapX(s.day), y = mapY(s.evCNoResale);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // --- Resale drop segments (dashed vertical at end of each ownership) ---
      // EV resale drop
      if (ev.includeResale && evUsage.years > 0) {
        const dropDay = evUsage.years * 365;
        const x = mapX(dropDay);
        const yTop = mapY(global.TCOCalc.costAtDayNoResale(ev, evUsage, dropDay));
        const yBot = mapY(global.TCOCalc.finalCost(ev, evUsage));
        ctx.strokeStyle = COLORS.ev;
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x, yTop);
        ctx.lineTo(x, yBot);
        ctx.stroke();
        ctx.setLineDash([]);
        // Small arrow head pointing down
        ctx.fillStyle = COLORS.ev;
        ctx.beginPath();
        ctx.moveTo(x, yBot);
        ctx.lineTo(x - 4, yBot - 6);
        ctx.lineTo(x + 4, yBot - 6);
        ctx.closePath();
        ctx.fill();
        // Label "Resale"
        if (yBot - yTop > 30) {
          ctx.fillStyle = COLORS.ev;
          ctx.font = '600 9px "Inter", sans-serif';
          ctx.textAlign = 'left';
          ctx.textBaseline = 'middle';
          ctx.fillText('−resale', x + 5, (yTop + yBot) / 2);
        }
      }
      // Petrol resale drop
      if (petrol.includeResale && petrolUsage.years > 0) {
        const dropDay = petrolUsage.years * 365;
        const x = mapX(dropDay);
        const yTop = mapY(global.TCOCalc.costAtDayNoResale(petrol, petrolUsage, dropDay));
        const yBot = mapY(global.TCOCalc.finalCost(petrol, petrolUsage));
        ctx.strokeStyle = COLORS.petrol;
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x, yTop);
        ctx.lineTo(x, yBot);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = COLORS.petrol;
        ctx.beginPath();
        ctx.moveTo(x, yBot);
        ctx.lineTo(x - 4, yBot - 6);
        ctx.lineTo(x + 4, yBot - 6);
        ctx.closePath();
        ctx.fill();
        if (yBot - yTop > 30) {
          ctx.fillStyle = COLORS.petrol;
          ctx.font = '600 9px "Inter", sans-serif';
          ctx.textAlign = 'left';
          ctx.textBaseline = 'middle';
          ctx.fillText('−resale', x + 5, (yTop + yBot) / 2);
        }
      }

      // --- Breakeven marker ---
      const be = global.TCOCalc.breakevenDay(ev, evUsage, petrol, petrolUsage);
      if (be !== null && be > 0 && be <= maxDays) {
        const bx = mapX(be);
        const by = mapY(global.TCOCalc.costAtDayExtended(ev, evUsage, be));
        ctx.strokeStyle = 'rgba(202,138,4,0.55)';
        ctx.setLineDash([4, 5]);
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(bx, pad.t);
        ctx.lineTo(bx, pad.t + plotH);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = COLORS.gold;
        ctx.beginPath();
        ctx.arc(bx, by, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
        // Label
        ctx.fillStyle = 'rgba(202,138,4,0.95)';
        ctx.font = '700 10px "Inter", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        const label = `Breakeven · Yr ${(be / 365).toFixed(1)}`;
        const metrics = ctx.measureText(label);
        const labelW = metrics.width + 12;
        const labelX = clamp(bx, pad.l + labelW / 2, pad.l + plotW - labelW / 2);
        roundRect(ctx, labelX - labelW / 2, by - 22, labelW, 16, 4);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.fillText(label, labelX, by - 9);
      }

      // --- Axes ---
      ctx.strokeStyle = 'rgba(0,0,0,0.18)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.l, pad.t);
      ctx.lineTo(pad.l, pad.t + plotH);
      ctx.lineTo(pad.l + plotW, pad.t + plotH);
      ctx.stroke();

      // --- Hover crosshair ---
      if (this.mouseX !== null && this.mouseX >= pad.l && this.mouseX <= pad.l + plotW) {
        const day = clamp(((this.mouseX - pad.l) / plotW) * maxDays, 0, maxDays);
        const x = mapX(day);
        ctx.strokeStyle = 'rgba(0,0,0,0.25)';
        ctx.setLineDash([3, 4]);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, pad.t);
        ctx.lineTo(x, pad.t + plotH);
        ctx.stroke();
        ctx.setLineDash([]);

        const evC = global.TCOCalc.costAtDayExtended(ev, evUsage, day);
        const petC = global.TCOCalc.costAtDayExtended(petrol, petrolUsage, day);
        ctx.fillStyle = COLORS.ev;
        ctx.beginPath();
        ctx.arc(x, mapY(evC), 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = COLORS.petrol;
        ctx.beginPath();
        ctx.arc(x, mapY(petC), 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }
    }

    updateTooltip() {
      if (this.mouseX === null) { this.tooltip.hidden = true; return; }
      const { ev, petrol, evUsage, petrolUsage, currency } = this.lastDraw.state;
      const plotW = Math.max(10, this.W - this.pad.l - this.pad.r);
      if (this.mouseX < this.pad.l || this.mouseX > this.pad.l + plotW) {
        this.tooltip.hidden = true;
        return;
      }
      const maxDays = Math.max(evUsage.years, petrolUsage.years) * 365;
      const day = clamp(((this.mouseX - this.pad.l) / plotW) * maxDays, 0, maxDays);
      const evC = global.TCOCalc.costAtDayExtended(ev, evUsage, day);
      const petC = global.TCOCalc.costAtDayExtended(petrol, petrolUsage, day);
      const diff = petC - evC;
      const yr = (day / 365).toFixed(2);
      const yrLabel = day < 365 ? `Month ${Math.round(day / 30.4)}` : `Year ${yr}`;

      const evStatus = day > evUsage.years * 365 ? ' <span style="color:#9ca3af">(held)</span>' : '';
      const petStatus = day > petrolUsage.years * 365 ? ' <span style="color:#9ca3af">(held)</span>' : '';

      const diffLabel = diff >= 0
        ? `<span style="color:#16a34a">EV saves ${formatCurrency(diff, currency)}</span>`
        : `<span style="color:#ea580c">Petrol saves ${formatCurrency(-diff, currency)}</span>`;

      this.tooltip.innerHTML = `
        <strong>${yrLabel} · Day ${Math.round(day)}</strong>
        <div class="tt-row ev"><span class="tt-name">Electric${evStatus}</span><span class="tt-amt">${formatCurrency(evC, currency)}</span></div>
        <div class="tt-row petrol"><span class="tt-name">Petrol${petStatus}</span><span class="tt-amt">${formatCurrency(petC, currency)}</span></div>
        <div style="margin-top:4px;font-weight:600">${diffLabel}</div>
      `;
      this.tooltip.hidden = false;

      const ttW = this.tooltip.offsetWidth;
      const ttH = this.tooltip.offsetHeight;
      let left = this.mouseX + 14;
      if (left + ttW > this.W - 8) left = this.mouseX - ttW - 14;
      if (left < 4) left = 4;
      let top = this.mouseY - ttH - 8;
      if (top < 4) top = this.mouseY + 14;
      this.tooltip.style.left = left + 'px';
      this.tooltip.style.top = top + 'px';
    }
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  global.TCOCharts = { CostChart, COLORS };

})(window);
