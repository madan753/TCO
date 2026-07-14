#!/usr/bin/env python3
"""
calc.py — Bike TCO Compare (Nepal edition) — Python mirror
==========================================================

Pure-Python implementation of the same Total-Cost-of-Ownership logic
that powers the web app. Now supports INDEPENDENT usage profiles per
bike (different daily km, ride days, and years for EV vs petrol),
because real riders don't use them the same way.

Use it three ways:

  1. As a CLI:
       python calc.py presets                           # list built-in bike presets
       python calc.py compare --ev "Komaki XGT KM" --petrol "Honda Dio"
       python calc.py compare --ev komaki-xgt-km --petrol honda-dio \\
                              --ev-km 30 --ev-years 6 \\
                              --petrol-km 18 --petrol-years 5
       python calc.py interactive                       # step-by-step prompts

  2. As an importable module:
       from calc import TCOCalculator
       calc = TCOCalculator(currency_code="NPR")
       result = calc.compare(
           ev="Komaki XGT KM", petrol="Honda Dio",
           ev_daily_km=30, ev_years=6,
           petrol_daily_km=18, petrol_years=5,
       )

  3. As a JSON pipeline:
       python calc.py compare --ev "TVS iQube Electric" --petrol "Honda Activa 6G" --json

The numbers match the web app (both use the same degradation model and
breakeven numerical sampling). Default currency is NPR (Nepal).

Requires: Python 3.8+  (stdlib only)
"""

from __future__ import annotations
import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any


# =========================================================
# Constants
# =========================================================

DEGRADATION = {
    "ev_batt_per_10k": 0.05,
    "petrol_eng_per_15k": 0.05,
    "service_per_10k": 0.02,
}

DEFAULT_USAGE = {
    "ev":     {"daily_km": 22, "ride_days": 6, "years": 5},
    "petrol": {"daily_km": 18, "ride_days": 6, "years": 5},
}


# =========================================================
# Bike presets  (Nepal on-road prices in NPR, 2024)
# Kept in sync with js/data.js
# =========================================================

EV_PRESETS: List[Dict[str, Any]] = [
    {"id": "komaki-xgt-km",  "name": "Komaki XGT KM",                    "price": 215000, "range": 80,  "battery": 2.0,  "service": 1500, "insurance": 2800, "tax": 2500, "resale_pct": 0.40},
    {"id": "yadea-g5",       "name": "Yadea G5",                         "price": 280000, "range": 90,  "battery": 2.5,  "service": 1800, "insurance": 3000, "tax": 2500, "resale_pct": 0.38},
    {"id": "tvs-iqube-np",   "name": "TVS iQube Electric",               "price": 335000, "range": 100, "battery": 3.04, "service": 2000, "insurance": 3500, "tax": 2500, "resale_pct": 0.42},
    {"id": "bajaj-chetak-np","name": "Bajaj Chetak Electric",            "price": 345000, "range": 95,  "battery": 2.9,  "service": 2200, "insurance": 3500, "tax": 2500, "resale_pct": 0.42},
    {"id": "niu-nqi",        "name": "NIU NQi Sport",                    "price": 415000, "range": 70,  "battery": 2.0,  "service": 2500, "insurance": 4000, "tax": 2500, "resale_pct": 0.40},
    {"id": "yatri-p0",       "name": "Yatri Project Zero (motorcycle)",  "price": 600000, "range": 120, "battery": 4.0,  "service": 3000, "insurance": 5000, "tax": 3000, "resale_pct": 0.38},
    {"id": "ev-custom",      "name": "Custom EV",                        "price": 300000, "range": 90,  "battery": 2.5,  "service": 2000, "insurance": 3000, "tax": 2500, "resale_pct": 0.40},
]

PETROL_PRESETS: List[Dict[str, Any]] = [
    {"id": "honda-dio",         "name": "Honda Dio",                            "price": 240000, "mileage": 50, "service": 2500, "insurance": 2800, "tax": 2500, "resale_pct": 0.55},
    {"id": "tvs-jupiter-np",    "name": "TVS Jupiter",                         "price": 235000, "mileage": 50, "service": 2500, "insurance": 2800, "tax": 2500, "resale_pct": 0.55},
    {"id": "honda-activa-np",   "name": "Honda Activa 6G",                     "price": 250000, "mileage": 50, "service": 2500, "insurance": 2800, "tax": 2500, "resale_pct": 0.55},
    {"id": "suzuki-access-np",  "name": "Suzuki Access 125",                   "price": 270000, "mileage": 48, "service": 2700, "insurance": 3000, "tax": 2500, "resale_pct": 0.53},
    {"id": "honda-shine-np",    "name": "Honda CB Shine 125 (motorcycle)",     "price": 272000, "mileage": 55, "service": 2700, "insurance": 3000, "tax": 2500, "resale_pct": 0.52},
    {"id": "bajaj-pulsar-np",   "name": "Bajaj Pulsar 150 (motorcycle)",       "price": 355000, "mileage": 45, "service": 3200, "insurance": 3500, "tax": 3000, "resale_pct": 0.50},
    {"id": "yamaha-fzs",        "name": "Yamaha FZ-S V3 (motorcycle)",         "price": 380000, "mileage": 45, "service": 3200, "insurance": 3500, "tax": 3000, "resale_pct": 0.50},
    {"id": "petrol-custom",     "name": "Custom petrol bike",                  "price": 250000, "mileage": 50, "service": 2700, "insurance": 3000, "tax": 2500, "resale_pct": 0.53},
]

CURRENCIES: Dict[str, Dict[str, Any]] = {
    "NPR": {"symbol": "रू", "code": "NPR", "locale": "ne-NP", "rate": 1.0,    "elec_rate": 9.8,  "fuel_rate": 175.0, "label": "Nepal (रू)"},
    "INR": {"symbol": "₹",  "code": "INR", "locale": "en-IN", "rate": 0.625,  "elec_rate": 8.0,  "fuel_rate": 105.5, "label": "India (₹)"},
    "USD": {"symbol": "$",  "code": "USD", "locale": "en-US", "rate": 0.0075, "elec_rate": 0.12, "fuel_rate": 1.30,  "label": "US ($)"},
}

PRESETS = {"ev": EV_PRESETS, "petrol": PETROL_PRESETS}


# =========================================================
# Dataclasses
# =========================================================

@dataclass
class Usage:
    daily_km: int = 20
    years: int = 5
    ride_days: int = 6

    def annual_km(self) -> float:
        return self.daily_km * self.ride_days * 52

    def daily_km_effective(self) -> float:
        return self.annual_km() / 365


@dataclass
class Bike:
    type: str
    name: str
    price: float
    service: float
    insurance: float
    tax: float
    resale: float
    include_resale: bool = True
    range_km: Optional[float] = None
    battery: Optional[float] = None
    elec_rate: Optional[float] = None
    mileage: Optional[float] = None
    fuel_rate: Optional[float] = None
    additional: Optional[List[Dict[str, Any]]] = None  # [{label, amount, year}, ...]


# =========================================================
# Calculator
# =========================================================

class TCOCalculator:
    """Pure-Python TCO calculator. Mirrors js/calculator.js (Nepal edition)."""

    def __init__(self, currency_code: str = "NPR"):
        self.currency = CURRENCIES.get(currency_code, CURRENCIES["NPR"])

    # ---------- Preset helpers ----------

    def preset_to_bike(self, preset_id: str, bike_type: str) -> Bike:
        presets = EV_PRESETS if bike_type == "ev" else PETROL_PRESETS
        preset = next((p for p in presets if p["id"] == preset_id), None)
        if preset is None:
            raise ValueError(f"Unknown {bike_type} preset: {preset_id}")
        return self._preset_dict_to_bike(preset, bike_type)

    def preset_by_name(self, name: str, bike_type: str) -> Bike:
        presets = EV_PRESETS if bike_type == "ev" else PETROL_PRESETS
        preset = next((p for p in presets if p["name"].lower() == name.lower()), None)
        if preset is None:
            available = ", ".join(p["name"] for p in presets)
            raise ValueError(f"Unknown {bike_type} bike name '{name}'. Available: {available}")
        return self._preset_dict_to_bike(preset, bike_type)

    def _preset_dict_to_bike(self, p: Dict[str, Any], bike_type: str) -> Bike:
        rate = self.currency["rate"]
        if bike_type == "ev":
            return Bike(
                type="ev", name=p["name"],
                price=round(p["price"] * rate),
                service=round(p["service"] * rate),
                insurance=round(p["insurance"] * rate),
                tax=round(p["tax"] * rate),
                resale=round(p["price"] * p["resale_pct"] * rate),
                include_resale=True,
                range_km=p["range"],
                battery=p["battery"],
                elec_rate=self.currency["elec_rate"],
            )
        return Bike(
            type="petrol", name=p["name"],
            price=round(p["price"] * rate),
            service=round(p["service"] * rate),
            insurance=round(p["insurance"] * rate),
            tax=round(p["tax"] * rate),
            resale=round(p["price"] * p["resale_pct"] * rate),
            include_resale=True,
            mileage=p["mileage"],
            fuel_rate=self.currency["fuel_rate"],
        )

    # ---------- Math helpers ----------

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    @staticmethod
    def _ev_kwh_per_km(bike: Bike) -> float:
        if not bike.range_km or bike.range_km <= 0:
            return 0.0
        return bike.battery / bike.range_km

    @staticmethod
    def _petrol_litres_per_km(bike: Bike) -> float:
        if not bike.mileage or bike.mileage <= 0:
            return 0.0
        return 1.0 / bike.mileage

    @staticmethod
    def _avg_deg_multiplier(day: float, per_km: float, per_unit: float, daily_km: float) -> float:
        if per_unit <= 0 or day <= 0 or per_km <= 0:
            return 1.0
        dist = daily_km * day
        return 1.0 + (per_km * dist) / (2.0 * per_unit)

    # ---------- Core: cost at a given day (per-bike usage) ----------

    def cost_at_day(self, bike: Bike, usage: Usage, day: float, include_resale: bool = True) -> float:
        total_days = usage.years * 365
        dd = self._clamp(day, 0, total_days)
        d_km = usage.daily_km_effective()
        distance = d_km * dd

        if bike.type == "ev":
            kwh_per_km = self._ev_kwh_per_km(bike)
            avg_factor = self._avg_deg_multiplier(dd, DEGRADATION["ev_batt_per_10k"], 10000, d_km)
            running_cost = distance * kwh_per_km * bike.elec_rate * avg_factor
        else:
            l_per_km = self._petrol_litres_per_km(bike)
            avg_factor = self._avg_deg_multiplier(dd, DEGRADATION["petrol_eng_per_15k"], 15000, d_km)
            running_cost = distance * l_per_km * bike.fuel_rate * avg_factor

        avg_serv_factor = self._avg_deg_multiplier(dd, DEGRADATION["service_per_10k"], 10000, d_km)
        service_cost = (dd / 365) * bike.service * avg_serv_factor
        fixed_cost = (dd / 365) * (bike.insurance + bike.tax)

        # Additional one-time costs (battery repair, tyres, accessories, etc.)
        # Each item: { amount, year } — applied once at the start of that year.
        additional_cost = 0.0
        if bike.additional:
            for item in bike.additional:
                if not item.get("amount"):
                    continue
                item_year = item.get("year", 1)
                item_day = (item_year - 1) * 365
                if dd >= item_day:
                    additional_cost += item["amount"]

        cost = bike.price + running_cost + service_cost + fixed_cost + additional_cost

        # Resale — applied as a SINGLE sharp drop at the end of ownership.
        if include_resale and bike.include_resale and total_days > 0 and day >= total_days - 1e-6:
            cost -= bike.resale
        return cost

    def cost_at_day_no_resale(self, bike: Bike, usage: Usage, day: float) -> float:
        """Cost at a given day, ignoring resale entirely. Useful for chart rendering."""
        return self.cost_at_day(bike, usage, day, include_resale=False)

    def is_resale_day(self, bike: Bike, usage: Usage, day: float) -> bool:
        """Returns True if this is the day resale value is recovered (end of ownership)."""
        if not bike.include_resale:
            return False
        total_days = usage.years * 365
        return total_days > 0 and day >= total_days - 1e-6

    def cost_at_day_extended(self, bike: Bike, usage: Usage, day: float, include_resale: bool = True) -> float:
        """For days beyond ownership — hold cost flat at final value."""
        total_days = usage.years * 365
        if day <= total_days:
            return self.cost_at_day(bike, usage, day, include_resale)
        return self.final_cost(bike, usage, include_resale)

    def final_cost(self, bike: Bike, usage: Usage, include_resale: bool = True) -> float:
        return self.cost_at_day(bike, usage, usage.years * 365, include_resale)

    # ---------- Breakdown ----------

    def breakdown(self, bike: Bike, usage: Usage, include_resale: bool = True) -> Dict[str, float]:
        total_days = usage.years * 365
        d_km = usage.daily_km_effective()
        distance = d_km * total_days

        if bike.type == "ev":
            kwh_per_km = self._ev_kwh_per_km(bike)
            avg_factor = self._avg_deg_multiplier(total_days, DEGRADATION["ev_batt_per_10k"], 10000, d_km)
            running = distance * kwh_per_km * bike.elec_rate * avg_factor
        else:
            l_per_km = self._petrol_litres_per_km(bike)
            avg_factor = self._avg_deg_multiplier(total_days, DEGRADATION["petrol_eng_per_15k"], 15000, d_km)
            running = distance * l_per_km * bike.fuel_rate * avg_factor

        avg_serv_factor = self._avg_deg_multiplier(total_days, DEGRADATION["service_per_10k"], 10000, d_km)
        service = usage.years * bike.service * avg_serv_factor
        insurance = usage.years * bike.insurance
        tax = usage.years * bike.tax
        additional = 0.0
        if bike.additional:
            for item in bike.additional:
                if item.get("amount"):
                    additional += item["amount"]
        resale_applied = bike.resale if (include_resale and bike.include_resale) else 0
        total = bike.price + running + service + insurance + tax + additional - resale_applied
        return {
            "price": bike.price, "running": running, "service": service,
            "insurance": insurance, "tax": tax, "additional": additional,
            "resale": resale_applied, "total": total,
        }

    # ---------- Breakeven ----------

    def breakeven_day(self, ev: Bike, ev_usage: Usage, petrol: Bike, petrol_usage: Usage) -> Optional[float]:
        max_days = max(ev_usage.years, petrol_usage.years) * 365
        diff_0 = self.cost_at_day_extended(ev, ev_usage, 0) - self.cost_at_day_extended(petrol, petrol_usage, 0)
        if diff_0 <= 0:
            return 0.0
        samples = 240
        prev_diff = diff_0
        prev_day = 0.0
        for i in range(1, samples + 1):
            day = (i / samples) * max_days
            diff = self.cost_at_day_extended(ev, ev_usage, day) - self.cost_at_day_extended(petrol, petrol_usage, day)
            if diff <= 0 and prev_diff > 0:
                ratio = prev_diff / (prev_diff - diff)
                return prev_day + (day - prev_day) * ratio
            prev_diff = diff
            prev_day = day
        return None

    # ---------- Per-km costs ----------

    def per_km_running(self, bike: Bike) -> float:
        if bike.type == "ev":
            return self._ev_kwh_per_km(bike) * bike.elec_rate
        return self._petrol_litres_per_km(bike) * bike.fuel_rate

    def per_km_total(self, bike: Bike, usage: Usage, include_resale: bool = True) -> float:
        total = self.final_cost(bike, usage, include_resale)
        km = usage.annual_km() * usage.years
        return total / km if km > 0 else 0.0

    # ---------- Year-by-year ----------

    def year_by_year(self, ev: Bike, ev_usage: Usage, petrol: Bike, petrol_usage: Usage) -> List[Dict[str, Any]]:
        max_years = max(ev_usage.years, petrol_usage.years)
        rows = []
        for y in range(1, max_years + 1):
            day = y * 365
            ev_active = y <= ev_usage.years
            pet_active = y <= petrol_usage.years
            ev_cost = self.cost_at_day(ev, ev_usage, day) if ev_active else self.final_cost(ev, ev_usage)
            pet_cost = self.cost_at_day(petrol, petrol_usage, day) if pet_active else self.final_cost(petrol, petrol_usage)
            rows.append({
                "year": y, "ev_active": ev_active, "pet_active": pet_active,
                "ev": ev_cost, "petrol": pet_cost, "diff": pet_cost - ev_cost,
            })
        return rows

    # ---------- Sensitivity analysis ----------

    def sensitivity(self, ev: Bike, ev_usage: Usage, petrol: Bike, petrol_usage: Usage,
                    include_resale: bool = True) -> Dict[str, Any]:
        scenarios = [
            {"label": "Fuel +10%",  "fuel_mul": 1.10, "elec_mul": 1.00},
            {"label": "Fuel +25%",  "fuel_mul": 1.25, "elec_mul": 1.00},
            {"label": "Fuel +50%",  "fuel_mul": 1.50, "elec_mul": 1.00},
            {"label": "Elec +10%",  "fuel_mul": 1.00, "elec_mul": 1.10},
            {"label": "Elec +25%",  "fuel_mul": 1.00, "elec_mul": 1.25},
            {"label": "Elec +50%",  "fuel_mul": 1.00, "elec_mul": 1.50},
            {"label": "Both +25%",  "fuel_mul": 1.25, "elec_mul": 1.25},
            {"label": "Both −10%",  "fuel_mul": 0.90, "elec_mul": 0.90},
        ]
        baseline_ev = self.final_cost(ev, ev_usage, include_resale)
        baseline_pet = self.final_cost(petrol, petrol_usage, include_resale)
        results = []
        for s in scenarios:
            from dataclasses import replace
            ev_mod = replace(ev, elec_rate=ev.elec_rate * s["elec_mul"])
            pet_mod = replace(petrol, fuel_rate=petrol.fuel_rate * s["fuel_mul"])
            ev_final = self.final_cost(ev_mod, ev_usage, include_resale)
            pet_final = self.final_cost(pet_mod, petrol_usage, include_resale)
            diff = pet_final - ev_final
            results.append({
                "label": s["label"],
                "ev_final": ev_final, "pet_final": pet_final, "diff": diff,
                "ev_delta": ev_final - baseline_ev,
                "pet_delta": pet_final - baseline_pet,
                "winner": "ev" if diff > 0 else ("petrol" if diff < 0 else "tie"),
            })
        return {
            "baseline": {"ev": baseline_ev, "petrol": baseline_pet, "diff": baseline_pet - baseline_ev},
            "scenarios": results,
        }

    # ---------- High-level compare (per-bike usage) ----------

    def compare(
        self,
        ev: Any,
        petrol: Any,
        ev_daily_km: int = 22, ev_years: int = 5, ev_ride_days: int = 6,
        petrol_daily_km: int = 18, petrol_years: int = 5, petrol_ride_days: int = 6,
        include_resale: bool = True,
    ) -> Dict[str, Any]:
        ev_bike = self._coerce_bike(ev, "ev")
        pet_bike = self._coerce_bike(petrol, "petrol")
        ev_usage = Usage(daily_km=ev_daily_km, years=ev_years, ride_days=ev_ride_days)
        pet_usage = Usage(daily_km=petrol_daily_km, years=petrol_years, ride_days=petrol_ride_days)

        ev_final = self.final_cost(ev_bike, ev_usage, include_resale)
        pet_final = self.final_cost(pet_bike, pet_usage, include_resale)
        diff = pet_final - ev_final
        be = self.breakeven_day(ev_bike, ev_usage, pet_bike, pet_usage)
        ev_total_km = ev_usage.annual_km() * ev_usage.years
        pet_total_km = pet_usage.annual_km() * pet_usage.years
        ev_per_km = self.per_km_total(ev_bike, ev_usage, include_resale)
        pet_per_km = self.per_km_total(pet_bike, pet_usage, include_resale)

        if diff > 0:
            headline = f"Electric saves you {self.format_currency(diff)} over the ownership period."
            if be is None:
                sub = "EV is cheaper from day one and stays ahead — petrol never catches up."
            elif be <= 0.01:
                sub = f"The {ev_bike.name} is cheaper from the very first kilometre."
            else:
                be_yr = be / 365
                be_km = round(be * ev_usage.daily_km_effective())
                sub = (f"EV breaks even at year {be_yr:.1f} (around {be_km:,} km on the EV's odometer), "
                       "then keeps saving you money every kilometre after.")
        elif diff < 0:
            headline = f"Petrol saves you {self.format_currency(-diff)} over the ownership period."
            if min(ev_total_km, pet_total_km) < 12000:
                sub = (f"You ride less than ~12,000 km total — at this distance the EV's higher "
                       f"purchase price doesn't get paid back.")
            else:
                sub = (f"Based on your numbers, the EV's running-cost advantage isn't enough to "
                       f"overcome its higher sticker price.")
        else:
            headline = "Both bikes cost about the same over their ownership periods."
            sub = "Pick the one that fits your riding style — there's no clear money winner here."

        return {
            "currency": self.currency["code"],
            "ev_usage": {"daily_km": ev_daily_km, "years": ev_years, "ride_days": ev_ride_days,
                         "annual_km": ev_usage.annual_km(), "total_km": ev_total_km},
            "petrol_usage": {"daily_km": petrol_daily_km, "years": petrol_years, "ride_days": petrol_ride_days,
                             "annual_km": pet_usage.annual_km(), "total_km": pet_total_km},
            "ev": {"name": ev_bike.name, "final_cost": ev_final, "per_km": ev_per_km,
                   "breakdown": self.breakdown(ev_bike, ev_usage, include_resale)},
            "petrol": {"name": pet_bike.name, "final_cost": pet_final, "per_km": pet_per_km,
                       "breakdown": self.breakdown(pet_bike, pet_usage, include_resale)},
            "savings": diff,
            "ev_per_km": ev_per_km,
            "petrol_per_km": pet_per_km,
            "breakeven_day": be,
            "breakeven_year": (be / 365) if be else None,
            "verdict": {"headline": headline, "sub": sub},
            "year_by_year": self.year_by_year(ev_bike, ev_usage, pet_bike, pet_usage),
            "sensitivity": self.sensitivity(ev_bike, ev_usage, pet_bike, pet_usage, include_resale),
        }

    def _coerce_bike(self, value: Any, bike_type: str) -> Bike:
        if isinstance(value, Bike):
            return value
        if isinstance(value, str):
            try:
                return self.preset_to_bike(value, bike_type)
            except ValueError:
                return self.preset_by_name(value, bike_type)
        raise TypeError(f"Expected Bike object, preset id, or name; got {type(value)}")

    # ---------- Currency formatting ----------

    def format_currency(self, amount: float, decimals: int = 0) -> str:
        sym = self.currency["symbol"]
        code = self.currency["code"]
        abs_amt = abs(amount)
        if code in ("INR", "NPR"):
            num = self._indian_grouping(abs_amt, decimals)
        else:
            num = f"{abs_amt:,.{decimals}f}"
        sign = "-" if amount < 0 else ""
        return f"{sign}{sym}{num}"

    @staticmethod
    def _indian_grouping(amount: float, decimals: int = 0) -> str:
        sign = "-" if amount < 0 else ""
        amt = abs(amount)
        if decimals > 0:
            int_part, frac = f"{amt:.{decimals}f}".split(".")
        else:
            int_part, frac = str(int(round(amt))), ""
        if len(int_part) <= 3:
            grouped = int_part
        else:
            last3 = int_part[-3:]
            rest = int_part[:-3]
            chunks = []
            while len(rest) > 2:
                chunks.insert(0, rest[-2:])
                rest = rest[:-2]
            if rest:
                chunks.insert(0, rest)
            grouped = ",".join(chunks) + "," + last3 if chunks else last3
        return f"{sign}{grouped}" + (f".{frac}" if decimals > 0 else "")

    def format_currency_short(self, amount: float) -> str:
        sym = self.currency["symbol"]
        sign = "-" if amount < 0 else ""
        a = abs(amount)
        if a >= 1e7: return f"{sign}{sym}{a/1e7:.2f}Cr"
        if a >= 1e5: return f"{sign}{sym}{a/1e5:.2f}L"
        if a >= 1e3: return f"{sign}{sym}{a/1e3:.1f}K"
        return f"{sign}{sym}{round(a)}"


# =========================================================
# CLI
# =========================================================

def cmd_presets(args) -> int:
    print("\n⚡ ELECTRIC BIKE PRESETS (Nepal, NPR on-road)")
    print("-" * 78)
    print(f"{'ID':<22} {'Name':<38} {'Price':>10}  {'Range':>6}  {'Battery':>7}")
    print("-" * 78)
    for p in EV_PRESETS:
        print(f"{p['id']:<22} {p['name']:<38} {p['price']:>10,}  {p['range']:>5}km  {p['battery']:>5}kWh")

    print("\n⛽ PETROL BIKE PRESETS (Nepal, NPR on-road)")
    print("-" * 78)
    print(f"{'ID':<22} {'Name':<38} {'Price':>10}  {'Mileage':>8}")
    print("-" * 78)
    for p in PETROL_PRESETS:
        print(f"{p['id']:<22} {p['name']:<38} {p['price']:>10,}  {p['mileage']:>5} km/L")

    print("\n💱 CURRENCIES:", ", ".join(f"{c['code']} ({c['symbol']})" for c in CURRENCIES.values()))
    print("\n💡 Nepal defaults: electricity रू9.8/unit · petrol रू175/litre · bluebook रू2,500/yr")
    return 0


def cmd_compare(args) -> int:
    calc = TCOCalculator(currency_code=args.currency)
    try:
        result = calc.compare(
            ev=args.ev, petrol=args.petrol,
            ev_daily_km=args.ev_km, ev_years=args.ev_years, ev_ride_days=args.ev_ride_days,
            petrol_daily_km=args.petrol_km, petrol_years=args.petrol_years, petrol_ride_days=args.petrol_ride_days,
            include_resale=not args.no_resale,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Run 'python calc.py presets' to see available options.", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0

    print()
    print("=" * 78)
    print(" 🏍️  BIKE TCO COMPARISON  (Nepal edition)")
    print("=" * 78)
    print(f"  Currency: {result['currency']}   |   Independent usage per bike")
    print()
    print(f"  ⚡ EV:     {result['ev']['name']}")
    print(f"            {args.ev_km} km/day, {args.ev_ride_days} days/week, {args.ev_years} years "
          f"→ {result['ev_usage']['annual_km']:,} km/yr, {result['ev_usage']['total_km']:,} km total")
    print(f"  ⛽ Petrol: {result['petrol']['name']}")
    print(f"            {args.petrol_km} km/day, {args.petrol_ride_days} days/week, {args.petrol_years} years "
          f"→ {result['petrol_usage']['annual_km']:,} km/yr, {result['petrol_usage']['total_km']:,} km total")
    print("=" * 78)
    print()
    print(f"  ➤ {result['verdict']['headline']}")
    print(f"    {result['verdict']['sub']}")
    print()
    print("-" * 78)
    print(f"  {'BIKE':<34} {'TOTAL':>16} {'PER KM':>14}")
    print("-" * 78)
    print(f"  ⚡ {result['ev']['name']:<32} {calc.format_currency(result['ev']['final_cost']):>16} {calc.format_currency(result['ev_per_km'], decimals=2):>14}")
    print(f"  ⛽ {result['petrol']['name']:<32} {calc.format_currency(result['petrol']['final_cost']):>16} {calc.format_currency(result['petrol_per_km'], decimals=2):>14}")
    print("-" * 78)
    save = result['savings']
    if save >= 0:
        print(f"  💰 You save with Electric:        {calc.format_currency(save):>16}")
    else:
        print(f"  💰 You save with Petrol:          {calc.format_currency(-save):>16}")
    be = result['breakeven_day']
    if be is None:
        be_str = "Never (within ownership period)" if save < 0 else "Day 1 (EV cheaper from start)"
    elif be <= 0.01:
        be_str = "Day 1 (EV cheaper from start)"
    else:
        be_str = f"Year {be/365:.2f}  (~{round(be):,} days)"
    print(f"  ⏱️  Breakeven point:               {be_str:>16}")
    print()
    print("  📊 YEAR-BY-YEAR  (held = ownership ended, cost flat)")
    print("  " + "-" * 76)
    print(f"  {'Year':<6} {'Electric':>18} {'Petrol':>18} {'Difference':>18}")
    print("  " + "-" * 76)
    for row in result['year_by_year']:
        diff_str = ("+" if row['diff'] >= 0 else "−") + " " + calc.format_currency(abs(row['diff']))
        ev_mark = "" if row['ev_active'] else " (held)"
        pet_mark = "" if row['pet_active'] else " (held)"
        print(f"  Y{row['year']:<5} {calc.format_currency(row['ev'])+ev_mark:>18} "
              f"{calc.format_currency(row['petrol'])+pet_mark:>18} {diff_str:>18}")
    print("  " + "-" * 76)
    print("  (Difference: + means EV is cheaper, − means petrol is cheaper)")
    print()
    return 0


def cmd_interactive(args) -> int:
    print("\n🏍️  Bike TCO Compare — Interactive Mode (Nepal)")
    print("=" * 50)
    calc = TCOCalculator(currency_code=args.currency)

    print("\nAvailable ELECTRIC bikes:")
    for i, p in enumerate(EV_PRESETS, 1):
        print(f"  {i}. {p['name']}  (रू{p['price']:,})")
    while True:
        try:
            ev_idx = int(input(f"\nPick an EV (1-{len(EV_PRESETS)}): "))
            if 1 <= ev_idx <= len(EV_PRESETS):
                ev = EV_PRESETS[ev_idx - 1]["name"]
                break
        except ValueError:
            pass
        print("  Invalid choice, try again.")

    print("\nAvailable PETROL bikes:")
    for i, p in enumerate(PETROL_PRESETS, 1):
        print(f"  {i}. {p['name']}  (रू{p['price']:,})")
    while True:
        try:
            pet_idx = int(input(f"\nPick a petrol bike (1-{len(PETROL_PRESETS)}): "))
            if 1 <= pet_idx <= len(PETROL_PRESETS):
                petrol = PETROL_PRESETS[pet_idx - 1]["name"]
                break
        except ValueError:
            pass
        print("  Invalid choice, try again.")

    try:
        print("\n--- EV usage (independent from petrol) ---")
        ev_km = int(input("EV daily km [22]: ").strip() or "22")
        ev_rd = int(input("EV ride days/week [6]: ").strip() or "6")
        ev_yr = int(input("EV years of ownership [5]: ").strip() or "5")
        print("\n--- Petrol usage (independent from EV) ---")
        pet_km = int(input("Petrol daily km [18]: ").strip() or "18")
        pet_rd = int(input("Petrol ride days/week [6]: ").strip() or "6")
        pet_yr = int(input("Petrol years of ownership [5]: ").strip() or "5")
    except ValueError:
        print("Invalid number, using defaults.")
        ev_km, ev_rd, ev_yr = 22, 6, 5
        pet_km, pet_rd, pet_yr = 18, 6, 5

    fake_args = argparse.Namespace(
        ev=ev, petrol=petrol,
        ev_km=ev_km, ev_ride_days=ev_rd, ev_years=ev_yr,
        petrol_km=pet_km, petrol_ride_days=pet_rd, petrol_years=pet_yr,
        currency=args.currency, no_resale=False, json=False,
    )
    return cmd_compare(fake_args)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="calc.py",
        description="Bike TCO Compare (Nepal edition) — Python CLI with independent per-bike usage.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python calc.py presets
  python calc.py compare --ev "Komaki XGT KM" --petrol "Honda Dio"
  python calc.py compare --ev komaki-xgt-km --petrol honda-dio \\
                          --ev-km 30 --ev-years 6 --petrol-km 18 --petrol-years 5
  python calc.py compare --ev "TVS iQube Electric" --petrol "Honda Activa 6G" --currency NPR --json
  python calc.py interactive
""",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("presets", help="List all built-in bike presets").set_defaults(func=cmd_presets)

    p_cmp = sub.add_parser("compare", help="Compare two bikes with independent usage")
    p_cmp.add_argument("--ev", required=True, help="EV preset id or name")
    p_cmp.add_argument("--petrol", required=True, help="Petrol preset id or name")
    # EV usage (independent)
    p_cmp.add_argument("--ev-km", type=int, default=22, help="EV daily km (default 22)")
    p_cmp.add_argument("--ev-years", type=int, default=5, help="EV ownership years (default 5)")
    p_cmp.add_argument("--ev-ride-days", type=int, default=6, help="EV ride days/week (default 6)")
    # Petrol usage (independent)
    p_cmp.add_argument("--petrol-km", type=int, default=18, help="Petrol daily km (default 18)")
    p_cmp.add_argument("--petrol-years", type=int, default=5, help="Petrol ownership years (default 5)")
    p_cmp.add_argument("--petrol-ride-days", type=int, default=6, help="Petrol ride days/week (default 6)")
    # Currency & misc
    p_cmp.add_argument("--currency", default="NPR", choices=list(CURRENCIES.keys()),
                       help="Currency (default NPR)")
    p_cmp.add_argument("--no-resale", action="store_true", help="Exclude resale from final cost")
    p_cmp.add_argument("--json", action="store_true", help="Output as JSON")
    p_cmp.set_defaults(func=cmd_compare)

    p_int = sub.add_parser("interactive", help="Step-by-step interactive prompts")
    p_int.add_argument("--currency", default="NPR", choices=list(CURRENCIES.keys()))
    p_int.set_defaults(func=cmd_interactive)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
