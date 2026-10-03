#!/usr/bin/env python3
"""Generate the 12-unit MIMXRT1176DVMAA symbol into Kicad/Nosh.kicad_sym.

Usage:
  python3 Kicad/tools/gen_rt1176_symbol.py            # regenerate from data/*.json
  python3 Kicad/tools/gen_rt1176_symbol.py extract PSTCHIP RM_TXT
                                                      # rebuild data/*.json from sources

Data sources (checked in under data/):
  rt1176_pins.json - 289 pins (name, ball, unit, type) extracted from the
                     MIMXRT1170-EVKB RevC3 Allegro netlist (Schematic/allegro/pstchip.dat)
  rt1176_mux.json  - pad -> [[alt, function], ...] extracted from the
                     IMXRT1170RM Rev.5 text dump, Table 11-1 "Muxing Options"

After generating, bring the file up to the current KiCad format with:
  kicad-cli sym upgrade --force Kicad/Nosh.kicad_sym
"""
import json, re, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE.parent / "Nosh.kicad_sym"


def extract(pstchip, rm_txt):
    """Rebuild data/*.json from the EVKB pstchip.dat and an RM text dump."""
    L = open(pstchip).read().split("\n")
    start = next(i for i, l in enumerate(L) if "primitive 'MIMXRT1176DVMAA" in l)
    pins, cur = [], None
    for l in L[start:]:
        if l.startswith("end_primitive"):
            break
        m = re.match(r"^\s+'([^']+)':\s*$", l)
        if m:
            cur = {"name": m.group(1)}
            pins.append(cur)
            continue
        m = re.match(r"^\s+PIN_NUMBER='\((.*)\)';", l)
        if m:
            for i, s in enumerate(m.group(1).split(",")):
                if s != "0":
                    cur["ball"], cur["unit"] = s, i + 1
            continue
        m = re.match(r"^\s+(\w+)='(.*)';", l)
        if m and cur is not None:
            cur[m.group(1)] = m.group(2)
    for p in pins:
        if p.get("PINUSE") == "POWER":
            p["t"] = "PWR"
        elif p.get("BIDIRECTIONAL") or ("INPUT_LOAD" in p and "OUTPUT_LOAD" in p):
            p["t"] = "BI"
        elif "INPUT_LOAD" in p:
            p["t"] = "IN"
        elif "OUTPUT_LOAD" in p:
            p["t"] = "OUT"
        else:
            p["t"] = p.get("PINUSE", "?")
    assert len(pins) == 289, len(pins)

    T = open(rm_txt).read().split("\n")
    a = next(i for i, l in enumerate(T) if l.strip() == "Table 11-1. Muxing Options")
    b = next(i for i, l in enumerate(T) if l.strip() == "Table 11-2. Pin Assignments")
    mux = defaultdict(set)
    pat = re.compile(r"^\s*(?:\S+\s+)?([A-Z0-9_]+)\s+([A-Z0-9_]+)\s+ALT(\d+)\s*$")
    for l in T[a:b]:
        m = pat.match(l)
        if m:
            port, pad, alt = m.groups()
            mux[pad].add((int(alt), port))
    mux = {k: sorted(v) for k, v in mux.items()}
    json.dump(pins, open(DATA / "rt1176_pins.json", "w"), indent=1)
    json.dump(mux, open(DATA / "rt1176_mux.json", "w"), indent=1)
    print(f"extracted {len(pins)} pins, {len(mux)} muxed pads")


if len(sys.argv) > 1 and sys.argv[1] == "extract":
    extract(sys.argv[2], sys.argv[3])
    sys.exit(0)

pins = json.load(open(DATA / "rt1176_pins.json"))
mux = json.load(open(DATA / "rt1176_mux.json"))

UNIT_NAMES = {
    1: "SNVS / power management", 2: "Core & analog supplies", 3: "DCDC",
    4: "VSS", 5: "Clocks / DAC", 6: "GPIO_LPSR", 7: "GPIO_SD", 8: "GPIO_AD",
    9: "GPIO_DISP", 10: "GPIO_EMC", 11: "MIPI", 12: "USB",
}

def etype(p):
    n = p["name"]
    if re.match(r"(VDD|VDDA|NVCC|VSS|DCDC_GND|DCDC_IN|ADC_VREFH)", n):
        return "power_in"
    if n.startswith("PMIC_"):
        return "output"
    if n in ("WAKEUP", "ONOFF", "TEST_MODE") or n.startswith("CLK1_"):
        return "input"
    if n == "DAC_OUT":
        return "output"
    if n.startswith(("USB", "MIPI_DSI")):
        return "bidirectional"
    if n.startswith("MIPI_CSI"):
        return "input"
    return {"BI": "bidirectional", "IN": "input", "OUT": "output",
            "PWR": "power_in", "UNSPEC": "passive"}[p["t"]]

def kname(n):
    # Allegro overline  P\O\R\  ->  KiCad ~{POR}
    if "\\" in n:
        return "~{" + n.replace("\\", "") + "}"
    return n

def display_name(p):
    pad = p["name"]
    alts = mux.get(pad, [])
    if not alts:
        return kname(pad), []
    gpio = [f for a, f in alts if re.match(r"GPIO\d+_IO\d+$", f)]
    primary = [f for a, f in alts if a == 0]
    parts = [pad] + primary[:1] + (gpio[-1:] if gpio else [])
    name = "/".join(parts)
    alternates = [f for a, f in alts if f not in parts]
    return name, alternates

def natkey(n):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", n)]

by_unit = defaultdict(list)
for p in pins:
    by_unit[p["unit"]].append(p)

def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')

PITCH = 2.54
PINLEN = 2.54
CHAR_W = 1.1  # approx mm per char at 1.27 text

def unit_geom(ps):
    rails = [p for p in ps if etype(p) == "power_in"]
    io = [p for p in ps if etype(p) != "power_in"]
    ordered = rails + io
    nl = (len(ordered) + 1) // 2
    left, right = ordered[:nl], ordered[nl:]
    names = {id(p): display_name(p) for p in ordered}
    lw = max((len(names[id(p)][0]) for p in left), default=0) * CHAR_W
    rw = max((len(names[id(p)][0]) for p in right), default=0) * CHAR_W
    body_w = PITCH * round((lw + rw + 7.62) / PITCH)
    return left, right, names, body_w / 2, PITCH * (nl + 1) / 2

geoms = {u: unit_geom(sorted(by_unit[u], key=lambda p: natkey(p["name"]))) for u in by_unit}
max_half = max(g[3] for g in geoms.values())
max_top = max(g[4] for g in geoms.values())

out = []
w = out.append
w('(kicad_symbol_lib (version 20231120) (generator "nosh_gen")')
w('  (symbol "MIMXRT1176DVMAA" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)')
w(f'    (property "Reference" "U" (at {-max_half:.2f} {max_top + 1.27:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)))')
w(f'    (property "Value" "MIMXRT1176DVMAA" (at {-max_half:.2f} {-max_top - 1.27:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)))')
w('    (property "Footprint" "Nosh:bga289_0p8_14x14_1p52mm" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
w('    (property "Datasheet" "https://www.nxp.com/docs/en/data-sheet/IMXRT1170CEC.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
w('    (property "Description" "i.MX RT1176 crossover MCU, Cortex-M7 @1GHz + Cortex-M4 @400MHz, MAPBGA-289 14x14mm 0.8mm pitch (as on MIMXRT1170-EVKB)" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
w('    (property "ki_keywords" "NXP i.MX RT1170 RT1176 Cortex-M7 Cortex-M4" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
w('    (property "ki_fp_filters" "BGA*289*" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')

for u in sorted(by_unit):
    # power rails first within a unit (they are few), then IO sorted naturally
    left, right, names, half, top = geoms[u]
    w(f'    (symbol "MIMXRT1176DVMAA_{u}_1"')
    w(f'      (rectangle (start {-half:.2f} {top:.2f}) (end {half:.2f} {-top:.2f}) (stroke (width 0.254) (type default)) (fill (type background)))')
    w(f'      (text "{UNIT_NAMES[u]}" (at 0 {top + 1.27:.2f} 0) (effects (font (size 1.27 1.27))))')
    for col, side in ((left, "L"), (right, "R")):
        for i, p in enumerate(col):
            y = top - PITCH * (i + 1)
            if side == "L":
                x, ang = -half - PINLEN, 0
            else:
                x, ang = half + PINLEN, 180
            name, alts = names[id(p)]
            t = etype(p)
            w(f'      (pin {t} line (at {x:.2f} {y:.2f} {ang}) (length {PINLEN})')
            w(f'        (name "{esc(name)}" (effects (font (size 1.27 1.27))))')
            w(f'        (number "{p["ball"]}" (effects (font (size 1.27 1.27))))')
            for a in alts:
                w(f'        (alternate "{esc(a)}" bidirectional line)')
            w('      )')
    w('    )')
w('  )')
w(')')
open(OUT, "w").write("\n".join(out) + "\n")
print(f"wrote {OUT}: {len(pins)} pins in {len(by_unit)} units")
