"""Write the JLCPCB design rules, track/via lists and net classes into Nosh.kicad_pro.

KiCad rewrites the project file whenever it saves, so close the project in KiCad before
running this, then reopen it.   Usage: python3 Kicad/tools/write_project_rules.py
"""
import json, os
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Nosh.kicad_pro')
P = json.load(open(p))
ds = P['board'].setdefault('design_settings', {})
ds['rules'] = {"max_error": 0.005, "min_clearance": 0.09, "min_connection": 0.09, "min_copper_edge_clearance": 0.3, "min_groove_width": 0.0, "min_hole_clearance": 0.2, "min_hole_to_hole": 0.5,
               "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1, "min_resolved_spokes": 2, "min_silk_clearance": 0.0, "min_text_height": 0.8, "min_text_thickness": 0.08,
               "min_through_hole_diameter": 0.3, "min_track_width": 0.09, "min_via_annular_width": 0.05, "min_via_diameter": 0.45, "solder_mask_to_copper_clearance": 0.0, "use_height_for_length_calcs": True}
ds['track_widths'] = [0.1, 0.13, 0.15, 0.2, 0.3, 0.5, 1.0]
ds['via_dimensions'] = [{"diameter": 0.5, "drill": 0.3}, {"diameter": 0.45, "drill": 0.3}, {"diameter": 0.4, "drill": 0.2}]
ds['diff_pair_dimensions'] = [{"gap": 0.11, "via_gap": 0.5, "width": 0.13}, {"gap": 0.13, "via_gap": 0.5, "width": 0.11}]
base = P['net_settings']['classes'][0]
common = dict(clearance=0.127, track_width=0.15, via_diameter=0.5, via_drill=0.3, diff_pair_width=0.13, diff_pair_gap=0.11, diff_pair_via_gap=0.5)
def nc(name, prio, **kw):
    c = dict(base); c.update(common); c.update(name=name, priority=prio); c.update(kw); return c
default = dict(base); default.update(common); default['name'] = 'Default'
P['net_settings']['classes'] = [default,
    nc('USB_90', 0, track_width=0.13, via_diameter=0.45),
    nc('MIPI_100', 1, track_width=0.11, diff_pair_width=0.11, diff_pair_gap=0.13, via_diameter=0.45),
    nc('SDRAM', 2, track_width=0.1, via_diameter=0.45),
    nc('Power', 3, track_width=0.3)]
pat = lambda c, *ps: [{"netclass": c, "pattern": x} for x in ps]
P['net_settings']['netclass_patterns'] = (pat('USB_90', 'USB?_DP', 'USB?_DN', 'USB?_CON_DP', 'USB?_CON_DN') + pat('MIPI_100', 'MIPI_DSI_*')
    + pat('SDRAM', 'SEMC_*') + pat('Power', 'GND', '+*', 'VDD*', 'DCDC*', '*VBUS*', 'CODEC_1V8', 'WL_3V3', 'AUD_VDDA', 'NVCC*', 'SDRAM_3V3'))
json.dump(P, open(p, 'w'), indent=2)
print('wrote', os.path.relpath(p), ':', len(P['net_settings']['classes']), 'net classes,', len(P['net_settings']['netclass_patterns']), 'patterns')
