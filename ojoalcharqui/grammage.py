"""Parse net content / grammage from product names and netContent strings.

Returns a normalized base measure so prices are comparable across pack sizes and
so shrinkflation (same price, smaller pack) is detectable longitudinally.

Base units: g (mass), ml (volume), un (count). 1 kg -> 1000 g, 1 L -> 1000 ml.
Packs ("6x350 ml", "pack 12 un") yield pack_units and total base measure.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# unit -> (base_unit, factor to base)
_UNIT = {
    "kg": ("g", 1000.0), "kgs": ("g", 1000.0), "kilo": ("g", 1000.0), "kilos": ("g", 1000.0),
    "g": ("g", 1.0), "gr": ("g", 1.0), "grs": ("g", 1.0), "grm": ("g", 1.0), "gramos": ("g", 1.0),
    "mg": ("g", 0.001),
    "l": ("ml", 1000.0), "lt": ("ml", 1000.0), "lts": ("ml", 1000.0), "litro": ("ml", 1000.0),
    "litros": ("ml", 1000.0),
    "ml": ("ml", 1.0), "cc": ("ml", 1.0), "cm3": ("ml", 1.0),
    "un": ("un", 1.0), "uni": ("un", 1.0), "und": ("un", 1.0), "unid": ("un", 1.0),
    "unidad": ("un", 1.0), "unidades": ("un", 1.0), "u": ("un", 1.0),
    "rollos": ("un", 1.0), "rollo": ("un", 1.0), "capsulas": ("un", 1.0),
    "caps": ("un", 1.0), "pañales": ("un", 1.0), "tabletas": ("un", 1.0),
    "sobres": ("un", 1.0), "sobre": ("un", 1.0), "huevos": ("un", 1.0),
}

_UNIT_ALT = sorted(_UNIT.keys(), key=len, reverse=True)
_UNIT_RE = "|".join(re.escape(u) for u in _UNIT_ALT)

# "6x350 ml", "6 x 350ml", "12x1,5 L", "pack 24"
_PACK_RE = re.compile(
    rf"(?P<n>\d+)\s*[xX×]\s*(?P<val>\d+(?:[.,]\d+)?)\s*(?P<unit>{_UNIT_RE})\b", re.I)
# "350 ml", "1,5 L", "1 kg", "250g"
_SINGLE_RE = re.compile(
    rf"(?P<val>\d+(?:[.,]\d+)?)\s*(?P<unit>{_UNIT_RE})\b", re.I)
# "pack 12", "x12", "12 un"
_COUNT_RE = re.compile(r"(?:pack\s*|x\s*)(?P<n>\d{1,3})\b", re.I)


@dataclass
class Grammage:
    value: float | None = None        # numeric as written (e.g. 1.5)
    unit: str | None = None           # unit as written (e.g. "L")
    base: float | None = None         # total in base unit (e.g. 1500 ml)
    base_unit: str | None = None      # g | ml | un
    pack_units: int | None = None     # number of items in pack

    def as_product_fields(self) -> dict:
        return {
            "grammage_value": self.value,
            "grammage_unit": self.unit,
            "grammage_base": self.base,
            "grammage_base_unit": self.base_unit,
            "pack_units": self.pack_units,
        }


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", ".")) if "," in s and "." in s \
        else float(s.replace(",", "."))


def parse(*texts: str) -> Grammage:
    """Parse the first usable grammage from any of the given strings (in order).
    Pass netContent first (most reliable), then the product name as fallback."""
    for text in texts:
        if not text:
            continue
        g = _parse_one(text)
        if g.base is not None:
            return g
    return Grammage()


def _parse_one(text: str) -> Grammage:
    t = text.strip()

    m = _PACK_RE.search(t)
    if m:
        n = int(m["n"])
        val = _num(m["val"])
        unit = m["unit"].lower()
        base_unit, factor = _UNIT[unit]
        return Grammage(value=val, unit=m["unit"], base=round(n * val * factor, 4),
                        base_unit=base_unit, pack_units=n)

    m = _SINGLE_RE.search(t)
    if m:
        val = _num(m["val"])
        unit = m["unit"].lower()
        base_unit, factor = _UNIT[unit]
        g = Grammage(value=val, unit=m["unit"], base=round(val * factor, 4),
                     base_unit=base_unit)
        # a trailing/leading count like "Leche 1 L x6" or "pack 6"
        cm = _COUNT_RE.search(t)
        if cm and base_unit != "un":
            n = int(cm["n"])
            if 1 < n <= 144:
                g.pack_units = n
                g.base = round(g.base * n, 4)
        return g

    m = _COUNT_RE.search(t)
    if m:
        n = int(m["n"])
        if 1 <= n <= 144:
            return Grammage(value=float(n), unit="un", base=float(n), base_unit="un",
                            pack_units=n)
    return Grammage()
