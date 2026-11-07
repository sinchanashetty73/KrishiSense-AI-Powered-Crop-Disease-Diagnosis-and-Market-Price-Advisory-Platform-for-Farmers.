"""Dosage calculator. Doses live in the diseases.products column (see seed.py) and are per LITRE of
spray water. The water volume per acre is a typical knapsack-sprayer figure and can be changed by the user.
These are indicative numbers: the product label always wins."""
import math

DEFAULT_SPRAY_VOLUME_L_PER_ACRE = 200.0
TANK_LITRES = 16.0  # common knapsack sprayer


def calculate(products: list[dict], area_acres: float, spray_volume: float | None = None) -> dict:
    volume = spray_volume or DEFAULT_SPRAY_VOLUME_L_PER_ACRE
    water = round(area_acres * volume, 1)
    out = []
    for p in products:
        qty = round(water * p["dose"], 1)
        out.append({"name": p["name"], "kind": p["kind"], "dose_per_litre": p["dose"], "unit": p["unit"],
                    "quantity": qty, "per_tank": round(TANK_LITRES * p["dose"], 1),
                    "note": p.get("note", "")})
    return {"area_acres": area_acres, "spray_volume_l_per_acre": volume, "water_litres": water,
            "tanks": math.ceil(water / TANK_LITRES) if water else 0, "tank_litres": TANK_LITRES, "products": out}
