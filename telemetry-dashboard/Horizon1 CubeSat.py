"""
Horizon-1 1U CubeSat - Fusion 360 assembly generator
SatForge UAE 2026, Phase 1 (Digital Design)

Run from Fusion 360: UTILITIES > ADD-INS > Scripts and Add-Ins > (create a
Python script named Horizon1_CubeSat, replace its .py contents with this file)
> Run.

What it builds
  * A new parametric Fusion design (mm) with ~60 user parameters.
  * A component tree: Primary_Structure, Mounting_Hardware, Electronics,
    Mission_Payload, External_Interfaces.
  * Real solid bodies from dimensioned sketches + extrudes, fillets and
    countersinks. Sketch dimensions are linked to the user parameters, so
    sizes (thicknesses, hole diameters, board envelopes, etc.) can be edited in
    MODIFY > Change Parameters.
  * Component POSITIONS are fixed by occurrence transforms computed from the
    parameter defaults below. To change the layout (stack heights, module
    positions), edit PARAMS / layout() here and re-run; a fresh design is
    generated in a new document.

Coordinate system (world, mm)
  Origin = centre of the -Z (bottom) face.  +Z = long axis toward the antenna.
  +X face = payload air vents, -X face = body-mounted solar cell,
  +Y face = inspection/ID panel, -Y face = service ports (USB, switch).

Everything marked PROVISIONAL is a placeholder envelope, not a datasheet
dimension. Replace with your measured / datasheet values before printing.
"""

import math
import re
import traceback

try:
    import adsk.core
    import adsk.fusion
except ImportError:          # lets the layout be checked outside Fusion
    adsk = None

# ---------------------------------------------------------------- options
DOC_NAME = 'Horizon-1_1U_CubeSat_Phase1'
SAVE_TO_CLOUD = False        # True = auto-save into the active project's root folder
ADD_SKETCH_DIMENSIONS = True # link sketch geometry to user parameters
PETG_DENSITY = 1.27          # g/cm^3, solid-equivalent (real prints use infill)

# ---------------------------------------------------------------- parameters
# (name, Fusion expression, comment).  Derived parameters reference earlier ones.
PARAMS = [
    # Envelope and structure (1U CubeSat Design Specification conventions)
    ('cube_w',        '100 mm',   '1U outer X/Y envelope incl. rails (CDS 100.0)'),
    ('cube_h',        '113.5 mm', '1U overall Z length (CDS 113.5)'),
    ('rail_w',        '8.5 mm',   'Corner rail square section (CDS min 8.5)'),
    ('rail_r',        '1 mm',     'Rail edge radius (CDS min 1.0)'),
    ('plate_t',       '3 mm',     'End plate thickness (PETG)'),
    ('plate_r',       '1 mm',     'End plate corner radius'),
    ('rail_len',      'cube_h - 2 * plate_t', 'Rail length between end plates'),
    ('insert_d',      '4 mm',     'M3 heat-set insert bore (check insert datasheet)'),
    ('insert_depth',  '6 mm',     'M3 heat-set insert bore depth'),
    ('m3_d',          '3 mm',     'M3 nominal diameter'),
    ('m3_clr',        '3.4 mm',   'M3 clearance hole'),
    ('m3_csk',        '1.3 mm',   'Countersink chamfer for M3 flat-head screws'),
    ('m3_len',        '8 mm',     'M3 screw length (plates)'),
    ('m2_clr',        '2.4 mm',   'M2 clearance hole (panels)'),
    ('m2_pilot',      '1.8 mm',   'M2 self-tapping pilot hole in PETG'),
    ('m2_head_d',     '3.8 mm',   'M2 pan head diameter'),
    ('m2_head_h',     '1.3 mm',   'M2 pan head height'),
    ('clr',           '0.25 mm',  'General assembly clearance'),
    ('panel_t',       '2 mm',     'Side panel thickness (PETG)'),
    ('panel_recess',  '0.5 mm',   'Side panel recess behind rail faces'),
    ('panel_w',       'cube_w - 2 * rail_w - 2 * clr', 'Side panel width (fits between rails)'),
    ('panel_h',       'rail_len', 'Side panel height (between end plates)'),
    ('lip_t',         '3 mm',     'End plate panel-mounting lip thickness'),
    ('lip_h',         '6 mm',     'End plate panel-mounting lip height'),
    ('lip_out',       'cube_w / 2 - panel_recess - panel_t', 'Lip outer face = panel inner face'),
    ('panel_screw_x', '35 mm',    'Lateral offset of panel M2 screws'),
    # Internal stack
    ('deck_w',        '80 mm',    'Carrier deck size (PETG or perfboard)'),
    ('deck_t',        '2 mm',     'Carrier deck thickness'),
    ('deck_r',        '3 mm',     'Carrier deck corner radius'),
    ('stack_off',     '35 mm',    'Stack standoff offset from centre (X and Y)'),
    ('so_d',          '5.5 mm',   'M3 hex standoff envelope (across flats)'),
    ('so_bore',       '3.2 mm',   'Standoff female thread envelope'),
    ('so_bore_depth', '6 mm',     'Standoff female thread depth'),
    ('stud_d',        'm3_d',     'Standoff male stud diameter'),
    ('stud_len',      '6 mm',     'Standoff male stud length'),
    ('so_a_h',        '25 mm',    'M3 standoff, levels 1 and 3'),
    ('so_b_h',        '20 mm',    'M3 standoff, level 2'),
    ('deck1_z',       'plate_t + so_a_h', 'Deck 1 (power) underside height'),
    ('deck2_z',       'deck1_z + deck_t + so_b_h', 'Deck 2 (payload) underside height'),
    ('deck3_z',       'deck2_z + deck_t + so_a_h', 'Deck 3 (OBC/comms) underside height'),
    ('nut_d',         '6.4 mm',   'M3 nut envelope'),
    ('nut_h',         '2.4 mm',   'M3 nut height'),
    ('nut_bore',      '3.1 mm',   'M3 nut bore envelope'),
    ('pcb_t',         '1.6 mm',   'Module PCB thickness'),
    # PROVISIONAL electronics envelopes
    ('bat_l',         '77 mm',    'PROVISIONAL 1x18650 holder length'),
    ('bat_w',         '21 mm',    'PROVISIONAL 1x18650 holder width'),
    ('bat_h',         '18.5 mm',  'PROVISIONAL 1x18650 holder height'),
    ('tp_w',          '17 mm',    'PROVISIONAL TP4056 USB-C charger board width'),
    ('tp_l',          '28 mm',    'PROVISIONAL TP4056 board length'),
    ('usbc_h',        '3.3 mm',   'PROVISIONAL USB-C receptacle height'),
    ('bst_w',         '17 mm',    'PROVISIONAL MT3608 boost board width'),
    ('bst_l',         '36 mm',    'PROVISIONAL MT3608 boost board length'),
    ('ina_w',         '26 mm',    'PROVISIONAL INA219 board width'),
    ('ina_l',         '21 mm',    'PROVISIONAL INA219 board length'),
    ('pm_d',          '38 mm',    'PROVISIONAL PMS5003 depth (X)'),
    ('pm_l',          '50 mm',    'PROVISIONAL PMS5003 length (Y)'),
    ('pm_h',          '21 mm',    'PROVISIONAL PMS5003 height (Z)'),
    ('esp_w',         '28 mm',    'PROVISIONAL ESP32 DevKit board width'),
    ('esp_l',         '55 mm',    'PROVISIONAL ESP32 DevKit board length incl. USB'),
    ('esp_sock_h',    '8.5 mm',   'PROVISIONAL female header socket height'),
    ('musb_h',        '3 mm',     'PROVISIONAL ESP32 USB connector height'),
    ('lora_w',        '25 mm',    'PROVISIONAL SX1278 (Ra-02) breakout width'),
    ('lora_l',        '25 mm',    'PROVISIONAL SX1278 breakout length'),
    ('sol_w',         '70 mm',    'PROVISIONAL solar cell width'),
    ('sol_h',         '80 mm',    'PROVISIONAL solar cell height'),
    ('sol_t',         '2.5 mm',   'PROVISIONAL solar cell thickness'),
    ('sma_x',         '22 mm',    'SMA bulkhead X position'),
    ('sma_y',         '18 mm',    'SMA bulkhead Y position'),
    ('sma_hole',      '6.5 mm',   'SMA bulkhead panel hole'),
    ('ant_d',         '6 mm',     'PROVISIONAL 433 MHz helical antenna diameter'),
    ('ant_h',         '30 mm',    'PROVISIONAL 433 MHz helical antenna length'),
    # External cut-outs
    ('vent_w',        '14 mm',    'PROVISIONAL payload vent width (align to sensor ports)'),
    ('vent_h',        '10 mm',    'PROVISIONAL payload vent height'),
    ('usbc_cut_w',    '13 mm',    'Charge-port cut-out width'),
    ('usbc_cut_h',    '8 mm',     'Charge-port cut-out height'),
    ('esp_cut_w',     '12 mm',    'Programming-port cut-out width'),
    ('esp_cut_h',     '8 mm',     'Programming-port cut-out height'),
    ('sw_x',          '25 mm',    'Power switch X position'),
    ('sw_z',          '42 mm',    'Power switch Z position'),
    ('sw_hole',       '6.2 mm',   'Mini toggle switch bushing hole'),
]

APPEARANCES = {
    'struct':  ('H1 PETG Anthracite', (55, 58, 64)),
    'panel':   ('H1 PETG Light Grey', (196, 200, 206)),
    'deck':    ('H1 PETG Teal',       (30, 120, 150)),
    'pcb':     ('H1 PCB Green',       (20, 110, 55)),
    'pcb_blk': ('H1 PCB Black',       (25, 28, 32)),
    'metal':   ('H1 Metal Silver',    (175, 178, 182)),
    'brass':   ('H1 Brass',           (200, 160, 60)),
    'steel':   ('H1 Steel',           (120, 122, 128)),
    'battery': ('H1 Battery Blue',    (40, 80, 190)),
    'solar':   ('H1 Solar Blue',      (15, 30, 95)),
    'black':   ('H1 Black',           (20, 20, 22)),
    'chip':    ('H1 Component Dark',  (45, 45, 50)),
}

# ---------------------------------------------------------------- expressions
_MM_RE = re.compile(r'(\d+(?:\.\d+)?)\s*mm\b')


def _py(expr):
    return _MM_RE.sub(r'(\1)', expr)


def _eval_params():
    vals = {}
    for name, expr, _ in PARAMS:
        vals[name] = float(eval(_py(expr), {'__builtins__': {}}, vals))
    return vals


VALS = _eval_params()


def ev(expr):
    """Evaluate a Fusion-style expression to millimetres."""
    return float(eval(_py(expr), {'__builtins__': {}}, VALS))


def L(v):
    return '%g mm' % v


def A(*terms):
    return ' + '.join('(%s)' % t for t in terms)


def S(a, b):
    return '(%s) - (%s)' % (a, b)


def N(a):
    return '-(%s)' % a


def H(a):
    return '(%s) / 2' % a


def sg(s, e):
    return e if s > 0 else N(e)


SIGNS = [(1, 1), (-1, 1), (-1, -1), (1, -1)]

# ---------------------------------------------------------------- feature DSL


def box(x0, y0, x1, y1, z0, z1, op='new'):
    return {'t': 'box', 'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'z0': z0, 'z1': z1, 'op': op}


def bc(cx, cy, w, d, z0, h, op='new'):
    """Box centred on (cx, cy) in X/Y, from z0 up by h."""
    return box(S(cx, H(w)), S(cy, H(d)), A(cx, H(w)), A(cy, H(d)), z0, A(z0, h), op)


def bxy(x0, y0, x1, y1, z0, h, op='new'):
    return box(x0, y0, x1, y1, z0, A(z0, h), op)


def cyl(cx, cy, d, z0, z1, op='new'):
    return {'t': 'cyl', 'cx': cx, 'cy': cy, 'd': d, 'z0': z0, 'z1': z1, 'op': op}


def hcyl(axis, c, u, v, d, length):
    """Horizontal through-cut. axis 'x': plane x=c, centre (y=u, z=v).
    axis 'y': plane y=c, centre (x=u, z=v). Symmetric about the plane."""
    return {'t': 'hcyl', 'axis': axis, 'c': c, 'u': u, 'v': v, 'd': d, 'len': length}


def fillet(r, corners):
    return {'t': 'fillet', 'r': r, 'corners': corners}


def csk(d, dist, z, centers):
    return {'t': 'csk', 'd': d, 'dist': dist, 'z': z, 'centers': centers}


def text(s, h, x, y, z, depth):
    return {'t': 'text', 's': s, 'h': h, 'x': x, 'y': y, 'z': z, 'depth': depth}


def body(name, app, feats, printed=False):
    return {'name': name, 'app': app, 'feats': feats, 'printed': printed}


def part(name, bodies, instances, note=''):
    return {'kind': 'part', 'name': name, 'bodies': bodies, 'instances': instances, 'note': note}


def group(name, children):
    return {'kind': 'group', 'name': name, 'children': children}


def T(x=0.0, y=0.0, z=0.0, xa=(1, 0, 0), ya=(0, 1, 0)):
    return ((x, y, z), xa, ya)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def compose(t, local):
    """Transform t moved by a local offset (same axes)."""
    (o, xa, ya) = t
    za = cross(xa, ya)
    lx, ly, lz = local
    no = tuple(o[i] + lx * xa[i] + ly * ya[i] + lz * za[i] for i in range(3))
    return (no, xa, ya)


# ---------------------------------------------------------------- layout


def layout():
    v = VALS
    hw = H('cube_w')
    RC = S(H('cube_w'), H('rail_w'))            # rail centre offset
    rc = ev(RC)
    lo, pt, ch = v['lip_out'], v['plate_t'], v['cube_h']
    so = v['stack_off']

    # ---------- end plates
    def end_plate(top):
        pw2 = H('panel_w')
        li = S('lip_out', 'lip_t')
        lz0, lz1 = 'plate_t', A('plate_t', 'lip_h')
        f = [box(N(hw), N(hw), hw, hw, L(0), 'plate_t')]
        f += [box(li, N(pw2), 'lip_out', pw2, lz0, lz1, 'join'),
              box(N('lip_out'), N(pw2), N(li), pw2, lz0, lz1, 'join'),
              box(N(pw2), li, pw2, 'lip_out', lz0, lz1, 'join'),
              box(N(pw2), N('lip_out'), pw2, N(li), lz0, lz1, 'join')]
        f.append(fillet('plate_r', [(sg(a, hw), sg(b, hw)) for a, b in SIGNS]))
        cuts = [cyl(sg(a, RC), sg(b, RC), 'm3_clr', L(0), 'plate_t', 'cut') for a, b in SIGNS]
        centers = [(sg(a, RC), sg(b, RC)) for a, b in SIGNS]
        if top:
            # local Y is flipped for the top plate (see its transform)
            cuts.append(cyl('sma_x', N('sma_y'), 'sma_hole', L(0), 'plate_t', 'cut'))
        else:
            cuts += [cyl(sg(a, 'stack_off'), sg(b, 'stack_off'), 'm3_clr', L(0), 'plate_t', 'cut')
                     for a, b in SIGNS]
            centers += [(sg(a, 'stack_off'), sg(b, 'stack_off')) for a, b in SIGNS]
            # zip-tie slots either side of the battery holder
            for a in (1, -1):
                for b in (1, -1):
                    cuts.append(bc(sg(a, L(20)), sg(b, A(H('bat_w'), L(3.5))),
                                   L(8), L(3), L(0), 'plate_t', 'cut'))
        f += cuts
        cmid = S('lip_out', H('lip_t'))
        zc = A('plate_t', H('lip_h'))
        for s in (1, -1):
            for q in (1, -1):
                f.append(hcyl('x', sg(s, cmid), sg(q, 'panel_screw_x'), zc, 'm2_pilot', A('lip_t', 'lip_t')))
                f.append(hcyl('y', sg(s, cmid), sg(q, 'panel_screw_x'), zc, 'm2_pilot', A('lip_t', 'lip_t')))
        f.append(csk('m3_clr', 'm3_csk', L(0), centers))
        return f

    bottom_plate = part('Bottom_Plate', [body('Bottom_Plate', 'struct', end_plate(False), True)],
                        [T()], 'PETG, print flat. M3 countersunk screws into rail inserts and stack.')
    top_plate = part('Top_Plate', [body('Top_Plate', 'struct', end_plate(True), True)],
                     [T(0, 0, ch, (1, 0, 0), (0, -1, 0))],
                     'PETG, print flat. Removable for top access. SMA bulkhead hole.')

    # ---------- rails
    rw2 = H('rail_w')
    rail_feats = [box(N(rw2), N(rw2), rw2, rw2, L(0), 'rail_len'),
                  fillet('rail_r', [(sg(a, rw2), sg(b, rw2)) for a, b in SIGNS]),
                  cyl(L(0), L(0), 'insert_d', L(0), 'insert_depth', 'cut'),
                  cyl(L(0), L(0), 'insert_d', S('rail_len', 'insert_depth'), 'rail_len', 'cut')]
    rails = part('Corner_Rail', [body('Corner_Rail', 'struct', rail_feats, True)],
                 [T(a * rc, b * rc, pt) for a, b in SIGNS],
                 'PETG, print vertical. M3 heat-set insert each end.')

    # ---------- side panels (local: x lateral, y up from plate, z outward)
    PANEL_T = {
        'PX': T(lo, 0, pt, (0, 1, 0), (0, 0, 1)),
        'MX': T(-lo, 0, pt, (0, -1, 0), (0, 0, 1)),
        'PY': T(0, lo, pt, (-1, 0, 0), (0, 0, 1)),
        'MY': T(0, -lo, pt, (1, 0, 0), (0, 0, 1)),
    }
    pw2 = H('panel_w')
    yb, yt = H('lip_h'), S('panel_h', H('lip_h'))
    screw_xy = [(sg(q, 'panel_screw_x'), yy) for q in (1, -1) for yy in (yb, yt)]

    def panel_base():
        f = [box(N(pw2), L(0), pw2, 'panel_h', L(0), 'panel_t')]
        f += [cyl(x, y, 'm2_clr', L(0), 'panel_t', 'cut') for x, y in screw_xy]
        return f

    vent_y = S(A('deck2_z', 'deck_t', H('pm_h')), 'plate_t')
    px = panel_base() + [bc(sg(s, L(15)), vent_y, 'vent_w', 'vent_h', L(0), 'panel_t', 'cut') for s in (1, -1)]
    mx = panel_base() + [cyl(L(0), H('panel_h'), L(5), L(0), 'panel_t', 'cut')]
    py = panel_base() + [text('HORIZON-1', L(9), L(0), A(H('panel_h'), L(8)), 'panel_t', L(0.6)),
                         text('SatForge UAE 2026', L(4.5), L(0), S(H('panel_h'), L(6)), 'panel_t', L(0.6))]
    usb_y = S(A('deck1_z', 'deck_t', 'pcb_t', H('usbc_h')), 'plate_t')
    esp_y = S(A('deck3_z', 'deck_t', 'esp_sock_h', 'pcb_t', H('musb_h')), 'plate_t')
    my = panel_base() + [bc(L(-19.5), usb_y, 'usbc_cut_w', 'usbc_cut_h', L(0), 'panel_t', 'cut'),
                         bc(L(-17), esp_y, 'esp_cut_w', 'esp_cut_h', L(0), 'panel_t', 'cut'),
                         cyl('sw_x', S('sw_z', 'plate_t'), 'sw_hole', L(0), 'panel_t', 'cut')]
    panels = [
        part('Side_Panel_PX_Payload_Vents', [body('Side_Panel_PX', 'panel', px, True)], [PANEL_T['PX']],
             'Air inlet/outlet vents for the dust sensor (PROVISIONAL positions).'),
        part('Side_Panel_MX_Solar', [body('Side_Panel_MX', 'panel', mx, True)], [PANEL_T['MX']],
             'Carries body-mounted solar cell; harness grommet hole.'),
        part('Side_Panel_PY_Inspection', [body('Side_Panel_PY', 'panel', py, True)], [PANEL_T['PY']],
             'Removable inspection panel with engraved identification.'),
        part('Side_Panel_MY_Service', [body('Side_Panel_MY', 'panel', my, True)], [PANEL_T['MY']],
             'USB-C charge port, ESP32 programming port, power switch.'),
    ]

    # ---------- decks (world frame)
    def deck(z, extra):
        dw2 = H('deck_w')
        f = [box(N(dw2), N(dw2), dw2, dw2, z, A(z, 'deck_t')),
             fillet('deck_r', [(sg(a, dw2), sg(b, dw2)) for a, b in SIGNS])]
        f += [cyl(sg(a, 'stack_off'), sg(b, 'stack_off'), 'm3_clr', z, A(z, 'deck_t'), 'cut') for a, b in SIGNS]
        f.append(box(L(-37), L(-12), L(-33), L(12), z, A(z, 'deck_t'), 'cut'))   # harness slot
        return f + extra

    deck2_extra = [bc(L(28), sg(s, A(H('pm_l'), L(2.5))), L(8), L(3), 'deck2_z', 'deck_t', 'cut')
                   for s in (1, -1)]
    decks = [
        part('Deck_1_Power', [body('Deck_1_Power', 'deck', deck('deck1_z', []), True)], [T()]),
        part('Deck_2_Payload', [body('Deck_2_Payload', 'deck', deck('deck2_z', deck2_extra), True)], [T()]),
        part('Deck_3_OBC_Comms', [body('Deck_3_OBC_Comms', 'deck', deck('deck3_z', []), True)], [T()]),
    ]

    # ---------- standoffs and fasteners
    def standoff(h):
        return [cyl(L(0), L(0), 'so_d', L(0), h),
                cyl(L(0), L(0), 'stud_d', h, A(h, 'stud_len'), 'join'),
                cyl(L(0), L(0), 'so_bore', L(0), 'so_bore_depth', 'cut')]

    sxy = [(a * so, b * so) for a, b in SIGNS]
    d1t = v['deck1_z'] + v['deck_t']
    d2t = v['deck2_z'] + v['deck_t']
    d3t = v['deck3_z'] + v['deck_t']
    so_a = part('Standoff_M3x25_MF', [body('Standoff_M3x25', 'brass', standoff('so_a_h'))],
                [T(x, y, pt) for x, y in sxy] + [T(x, y, d2t) for x, y in sxy],
                'M3 x 25 male-female hex standoff (modelled as cylinder).')
    so_b = part('Standoff_M3x20_MF', [body('Standoff_M3x20', 'brass', standoff('so_b_h'))],
                [T(x, y, d1t) for x, y in sxy], 'M3 x 20 male-female hex standoff.')

    flip = ((1, 0, 0), (0, -1, 0))
    screw_inst = ([T(a * rc, b * rc, 0) for a, b in SIGNS] + [T(x, y, 0) for x, y in sxy] +
                  [T(a * rc, b * rc, ch, *flip) for a, b in SIGNS])
    screws = part('Screw_M3x8_CSK', [body('Screw_M3x8', 'steel', [cyl(L(0), L(0), 'm3_d', L(0), 'm3_len')])],
                  screw_inst, 'DIN 7991 M3x8 shank envelope; heads sit in countersinks.')
    nuts = part('Nut_M3', [body('Nut_M3', 'steel', [cyl(L(0), L(0), 'nut_d', L(0), 'nut_h'),
                                                    cyl(L(0), L(0), 'nut_bore', L(0), 'nut_h', 'cut')])],
                [T(x, y, d3t) for x, y in sxy], 'Locks the top of the stack.')
    pv = v['panel_t']
    m2_inst = []
    for key in ('PX', 'MX', 'PY', 'MY'):
        for q in (1, -1):
            for yy in (v['lip_h'] / 2, v['panel_h'] - v['lip_h'] / 2):
                m2_inst.append(compose(PANEL_T[key], (q * v['panel_screw_x'], yy, pv)))
    m2 = part('Screw_M2x6_Pan', [body('Screw_M2_Head', 'steel', [cyl(L(0), L(0), 'm2_head_d', L(0), 'm2_head_h')])],
              m2_inst, 'M2x6 pan head, self-tapping into end-plate lips (head only modelled).')

    # ---------- electronics (world frame)
    DT1, DT2, DT3 = A('deck1_z', 'deck_t'), A('deck2_z', 'deck_t'), A('deck3_z', 'deck_t')
    B1 = A(DT1, 'pcb_t')
    battery = part('Battery_18650_Holder', [body('Battery_18650_Holder', 'battery', [
        box(N(H('bat_l')), N(H('bat_w')), H('bat_l'), H('bat_w'), 'plate_t', A('plate_t', 'bat_h'))])],
        [T()], 'PROVISIONAL 1x18650 Li-ion in holder; zip-tied to bottom plate (lowest CG).')
    tp = part('Charger_TP4056_USBC', [
        body('TP4056_PCB', 'pcb_blk', [box(L(-28), L(-44), A(L(-28), 'tp_w'), A(L(-44), 'tp_l'), DT1, B1)]),
        body('TP4056_Components', 'chip', [bxy(L(-27), L(-37), L(-12), L(-17), B1, L(3))]),
        body('TP4056_USB_C', 'metal', [bxy(L(-24), L(-45), L(-15), L(-37.5), B1, 'usbc_h')])],
        [T()], 'PROVISIONAL Li-ion charger module, USB-C faces -Y panel.')
    boost = part('Boost_MT3608', [
        body('MT3608_PCB', 'pcb_blk', [box(L(-6), L(-30), A(L(-6), 'bst_w'), A(L(-30), 'bst_l'), DT1, B1)]),
        body('MT3608_Components', 'chip', [bxy(L(-5), L(-29), L(10), L(5), B1, L(6))])],
        [T()], 'PROVISIONAL 3.7 V -> 5 V boost converter.')
    ina = part('Power_Monitor_INA219', [
        body('INA219_PCB', 'pcb', [box(L(-25), L(12), A(L(-25), 'ina_w'), A(L(12), 'ina_l'), DT1, B1)]),
        body('INA219_Components', 'chip', [bxy(L(-22), L(15), L(-2), L(30), B1, L(8))])],
        [T()], 'PROVISIONAL current/voltage monitor for the power-budget logic.')
    sw_t = T(v['sw_x'], -lo, v['sw_z'], (1, 0, 0), (0, 0, 1))
    switch = part('Power_Switch', [body('Power_Switch', 'black', [
        box(L(-4), L(-6.5), L(4), L(6.5), L(-10), L(0)),
        cyl(L(0), L(0), L(6), L(0), L(4), 'join'),
        cyl(L(0), L(0), L(2), L(4), L(8), 'join')])],
        [sw_t], 'PROVISIONAL mini toggle switch through -Y panel.')
    pms = part('Dust_Sensor_PMS5003', [body('PMS5003', 'metal', [
        box(L(9), N(H('pm_l')), A(L(9), 'pm_d'), H('pm_l'), DT2, A(DT2, 'pm_h'))])],
        [T()], 'PROVISIONAL optical particle sensor; air ports face the +X vents. Verify port positions.')
    S3 = A(DT3, 'esp_sock_h')
    B3 = A(S3, 'pcb_t')
    esp = part('OBC_ESP32_DevKit', [
        body('ESP32_Socket_L', 'black', [bxy(L(-30), L(-38), L(-27.5), L(8), DT3, 'esp_sock_h')]),
        body('ESP32_Socket_R', 'black', [bxy(L(-6.5), L(-38), L(-4), L(8), DT3, 'esp_sock_h')]),
        body('ESP32_PCB', 'pcb_blk', [box(L(-31), L(-43), A(L(-31), 'esp_w'), A(L(-43), 'esp_l'), S3, B3)]),
        body('ESP32_Module', 'metal', [bxy(L(-26), L(-14), L(-8), L(11.5), B3, L(3.2))]),
        body('ESP32_USB', 'metal', [bxy(L(-21), L(-44), L(-13), L(-38), B3, 'musb_h')])],
        [T()], 'PROVISIONAL on-board computer in female headers; USB faces -Y panel.')
    lora = part('LoRa_SX1278_Ra02', [
        body('LoRa_PCB', 'pcb', [box(L(10), L(5), A(L(10), 'lora_w'), A(L(5), 'lora_l'), DT3, A(DT3, 'pcb_t'))]),
        body('LoRa_Module', 'metal', [bxy(L(14), L(9), L(31), L(25), A(DT3, 'pcb_t'), L(3.2))])],
        [T()], 'PROVISIONAL 433 MHz LoRa radio; U.FL pigtail to SMA bulkhead.')

    # ---------- external interfaces
    sol = part('Solar_Cell_MX', [body('Solar_Cell', 'solar', [
        box(N(H('sol_w')), S(H('panel_h'), H('sol_h')), H('sol_w'), A(H('panel_h'), H('sol_h')),
            'panel_t', A('panel_t', 'sol_t'))])],
        [PANEL_T['MX']], 'PROVISIONAL body-mounted cell feeding the charger (functional, not decorative).')
    ptop = S('cube_h', 'plate_t')
    sma = part('SMA_Bulkhead', [body('SMA_Bulkhead', 'brass', [
        cyl('sma_x', 'sma_y', L(8), S(ptop, L(12)), ptop),
        cyl('sma_x', 'sma_y', L(6.2), ptop, A('cube_h', L(3)), 'join'),
        cyl('sma_x', 'sma_y', L(8), 'cube_h', A('cube_h', L(2)), 'join')])],
        [T()], 'SMA female bulkhead through top plate.')
    ant = part('UHF_Antenna_433MHz', [body('Antenna', 'black', [
        cyl('sma_x', 'sma_y', 'ant_d', A('cube_h', L(3)), A('cube_h', L(3), 'ant_h'))])],
        [T()], 'PROVISIONAL stub/helical antenna (no deployable).')

    return group('Horizon1_CubeSat', [
        group('Primary_Structure', [bottom_plate, top_plate, rails] + panels),
        group('Mounting_Hardware', [
            group('PCB_Decks', decks),
            group('PCB_Supports', [so_a, so_b]),
            group('Fastener_Locations', [screws, nuts, m2])]),
        group('Electronics', [
            group('Power_System', [battery, tp, boost, ina, switch]),
            group('Main_Controller', [esp]),
            group('Communications_Module', [lora])]),
        group('Mission_Payload', [pms]),
        group('External_Interfaces', [sol, sma, ant]),
    ])


# ================================================================ Fusion side
def _P(x, y, z):
    return adsk.core.Point3D.create(x / 10.0, y / 10.0, z / 10.0)


def _vi(expr):
    return adsk.core.ValueInput.createByString(expr)


def _matrix(t):
    (o, xa, ya) = t
    za = cross(xa, ya)
    m = adsk.core.Matrix3D.create()
    m.setWithCoordinateSystem(_P(*o), adsk.core.Vector3D.create(*map(float, xa)),
                              adsk.core.Vector3D.create(*map(float, ya)),
                              adsk.core.Vector3D.create(*map(float, za)))
    return m


class Builder:
    def __init__(self, app, design):
        self.app = app
        self.design = design
        self.warnings = []
        self.apps = {}
        self.base_appearance = None
        self.base_searched = False
        self.planes = {}
        self.printed_cm3 = 0.0
        self.n_parts = 0
        self.n_occ = 0

    def warn(self, msg):
        self.warnings.append(msg)

    # ---------------- tree
    def build(self, node, parent):
        if node['kind'] == 'group':
            occ = parent.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = node['name']
            for ch in node['children']:
                self.build(ch, comp)
        else:
            self.build_part(node, parent)

    def build_part(self, node, parent):
        mats = [_matrix(t) for t in node['instances']]
        occ = parent.occurrences.addNewComponent(mats[0])
        comp = occ.component
        comp.name = node['name']
        if node.get('note'):
            try:
                comp.description = node['note']
            except Exception:
                pass
        for b in node['bodies']:
            try:
                brep = self.build_body(comp, b)
                if brep is not None and b.get('printed'):
                    self.printed_cm3 += brep.volume * len(mats)
            except Exception:
                self.warn('%s/%s failed: %s' % (node['name'], b['name'], traceback.format_exc(limit=1)))
        occs = [occ]
        for m in mats[1:]:
            occs.append(parent.occurrences.addExistingComponent(comp, m))
        for o in occs:
            try:
                o.isGrounded = True
            except Exception:
                pass
        self.n_parts += 1
        self.n_occ += len(occs)
        adsk.doEvents()

    # ---------------- planes
    def plane(self, comp, axis, expr):
        """Offset construction plane normal to axis (0=X,1=Y,2=Z) at expr (mm)."""
        base = {0: comp.yZConstructionPlane, 1: comp.xZConstructionPlane, 2: comp.xYConstructionPlane}[axis]
        val = ev(expr)
        if abs(val) < 1e-9:
            return base
        key = (comp.name, axis, round(val, 6))
        if key in self.planes:
            return self.planes[key]
        pl = None
        for e in (expr, N(expr)):
            pin = comp.constructionPlanes.createInput()
            pin.setByOffset(base, _vi(e))
            pl = comp.constructionPlanes.add(pin)
            o = pl.geometry.origin
            actual = (o.x, o.y, o.z)[axis] * 10.0
            if abs(actual - val) < 1e-3:
                break
            pl.deleteMe()
            pl = None
        if pl is None:
            raise RuntimeError('could not place plane %s' % expr)
        try:
            pl.isLightBulbOn = False
        except Exception:
            pass
        self.planes[key] = pl
        return pl

    # ---------------- sketch helpers
    def dim_point(self, sk, spt, xe, xv, ye, yv):
        if not ADD_SKETCH_DIMENSIONS:
            return
        dims = sk.sketchDimensions
        g = spt.geometry
        H_ = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
        V_ = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
        for expr, val, pref in ((xe, xv, 'x'), (ye, yv, 'y')):
            if abs(val) < 1e-6:
                continue
            sx, sy = abs(g.x * 10.0), abs(g.y * 10.0)
            if pref == 'x':
                orient = H_ if abs(sx - abs(val)) < 1e-3 else (V_ if abs(sy - abs(val)) < 1e-3 else None)
            else:
                orient = V_ if abs(sy - abs(val)) < 1e-3 else (H_ if abs(sx - abs(val)) < 1e-3 else None)
            if orient is None:
                continue
            try:
                tp = adsk.core.Point3D.create(g.x * 0.5 + 0.2, g.y * 0.5 + 0.2, 0)
                d = dims.addDistanceDimension(sk.originPoint, spt, orient, tp)
                d.parameter.expression = expr if val > 0 else N(expr)
            except Exception:
                self.warn('dimension skipped in %s' % sk.name)

    def draw(self, sk, f, z):
        curves = sk.sketchCurves
        if f['t'] == 'box':
            x0, y0, x1, y1 = ev(f['x0']), ev(f['y0']), ev(f['x1']), ev(f['y1'])
            pa = sk.modelToSketchSpace(_P(x0, y0, z))
            pc = sk.modelToSketchSpace(_P(x1, y1, z))
            lines = curves.sketchLines.addTwoPointRectangle(pa, pc)
            if ADD_SKETCH_DIMENSIONS:
                pts = []
                for i in range(lines.count):
                    ln = lines.item(i)
                    pts += [ln.startSketchPoint, ln.endSketchPoint]
                a = min(pts, key=lambda p: p.geometry.distanceTo(pa))
                c = min(pts, key=lambda p: p.geometry.distanceTo(pc))
                self.dim_point(sk, a, f['x0'], x0, f['y0'], y0)
                self.dim_point(sk, c, f['x1'], x1, f['y1'], y1)
        else:
            cx, cy, d = ev(f['cx']), ev(f['cy']), ev(f['d'])
            circ = curves.sketchCircles.addByCenterRadius(sk.modelToSketchSpace(_P(cx, cy, z)), d / 20.0)
            if ADD_SKETCH_DIMENSIONS:
                try:
                    g = circ.centerSketchPoint.geometry
                    dd = sk.sketchDimensions.addDiameterDimension(
                        circ, adsk.core.Point3D.create(g.x + d / 20.0, g.y + d / 20.0, 0))
                    dd.parameter.expression = f['d']
                except Exception:
                    self.warn('diameter dimension skipped in %s' % sk.name)
                self.dim_point(sk, circ.centerSketchPoint, f['cx'], cx, f['cy'], cy)

    def extrude(self, comp, profiles, dist_expr, op, target=None, direction=None):
        coll = adsk.core.ObjectCollection.create()
        for p in profiles:
            coll.add(p)
        exts = comp.features.extrudeFeatures
        ext_in = exts.createInput(coll, op)
        d = _vi(dist_expr)
        if direction is None:
            direction = adsk.fusion.ExtentDirections.PositiveExtentDirection
        try:
            ext_in.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(d), direction)
        except Exception:
            if direction == adsk.fusion.ExtentDirections.NegativeExtentDirection:
                d = _vi(N(dist_expr))
            ext_in.setDistanceExtent(False, d)
        if target is not None and op != adsk.fusion.FeatureOperations.NewBodyFeatureOperation:
            ext_in.participantBodies = [target]
        return exts.add(ext_in)

    # ---------------- body
    def build_body(self, comp, b):
        OPS = {'new': adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
               'join': adsk.fusion.FeatureOperations.JoinFeatureOperation,
               'cut': adsk.fusion.FeatureOperations.CutFeatureOperation}
        feats = b['feats']
        brep = None
        i = 0
        while i < len(feats):
            f = feats[i]
            t = f['t']
            if t in ('box', 'cyl'):
                key = (round(ev(f['z0']), 5), round(ev(f['z1']), 5), f['op'])
                grp = [f]
                j = i + 1
                if f['op'] != 'new':
                    while (j < len(feats) and feats[j]['t'] in ('box', 'cyl') and
                           (round(ev(feats[j]['z0']), 5), round(ev(feats[j]['z1']), 5), feats[j]['op']) == key):
                        grp.append(feats[j])
                        j += 1
                z0 = ev(f['z0'])
                pl = self.plane(comp, 2, f['z0'])
                sk = comp.sketches.add(pl)
                sk.name = '%s_%s_z%g' % (b['name'], f['op'], z0)
                for g in grp:
                    self.draw(sk, g, z0)
                profs = [sk.profiles.item(k) for k in range(sk.profiles.count)]
                dist = f['z1'] if abs(z0) < 1e-9 else S(f['z1'], f['z0'])
                feat = self.extrude(comp, profs, dist, OPS[f['op']], brep)
                if f['op'] == 'new':
                    brep = feat.bodies.item(0)
                    brep.name = b['name']
                sk.isVisible = False
                i = j
                continue
            try:
                if t == 'hcyl':
                    self.hcut(comp, brep, f)
                elif t == 'fillet':
                    self.fillet(comp, brep, f)
                elif t == 'csk':
                    self.countersink(comp, brep, f)
                elif t == 'text':
                    self.engrave(comp, brep, f)
            except Exception:
                self.warn('%s: %s feature skipped (%s)' % (b['name'], t, traceback.format_exc(limit=1).strip()))
            i += 1
        if brep is not None:
            a = self.appearance(b['app'])
            if a is not None:
                try:
                    brep.appearance = a
                except Exception:
                    pass
        return brep

    def hcut(self, comp, brep, f):
        axis = 0 if f['axis'] == 'x' else 1
        c, u, v = ev(f['c']), ev(f['u']), ev(f['v'])
        pl = self.plane(comp, axis, f['c'])
        sk = comp.sketches.add(pl)
        sk.name = '%s_side_hole' % brep.name
        pm = _P(c, u, v) if axis == 0 else _P(u, c, v)
        sk.sketchCurves.sketchCircles.addByCenterRadius(sk.modelToSketchSpace(pm), ev(f['d']) / 20.0)
        exts = comp.features.extrudeFeatures
        ext_in = exts.createInput(sk.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation)
        try:
            ext_in.setSymmetricExtent(_vi(f['len']), True)
        except Exception:
            ext_in.setDistanceExtent(True, _vi(f['len']))
        ext_in.participantBodies = [brep]
        exts.add(ext_in)
        sk.isVisible = False

    def fillet(self, comp, brep, f):
        targets = [(ev(x) / 10.0, ev(y) / 10.0) for x, y in f['corners']]
        edges = adsk.core.ObjectCollection.create()
        for k in range(brep.edges.count):
            e = brep.edges.item(k)
            if e.geometry.objectType != adsk.core.Line3D.classType():
                continue
            a, b = e.startVertex.geometry, e.endVertex.geometry
            if abs(a.x - b.x) > 1e-5 or abs(a.y - b.y) > 1e-5:
                continue
            if any(abs(a.x - tx) < 1e-4 and abs(a.y - ty) < 1e-4 for tx, ty in targets):
                edges.add(e)
        if edges.count == 0:
            raise RuntimeError('no corner edges found')
        fins = comp.features.filletFeatures
        fin = fins.createInput()
        try:
            fin.edgeSetInputs.addConstantRadiusEdgeSet(edges, _vi(f['r']), True)
        except Exception:
            fin.addConstantRadiusEdgeSet(edges, _vi(f['r']), True)
        fins.add(fin)

    def countersink(self, comp, brep, f):
        z = ev(f['z']) / 10.0
        r = ev(f['d']) / 20.0
        cs = [(ev(x) / 10.0, ev(y) / 10.0) for x, y in f['centers']]
        edges = adsk.core.ObjectCollection.create()
        for k in range(brep.edges.count):
            e = brep.edges.item(k)
            g = e.geometry
            if g.objectType != adsk.core.Circle3D.classType():
                continue
            c = g.center
            if abs(c.z - z) > 1e-4 or abs(g.radius - r) > 1e-4:
                continue
            if any(abs(c.x - x) < 1e-4 and abs(c.y - y) < 1e-4 for x, y in cs):
                edges.add(e)
        if edges.count == 0:
            raise RuntimeError('no hole edges found')
        chs = comp.features.chamferFeatures
        try:
            cin = chs.createInput2()
            cin.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, _vi(f['dist']), False)
        except Exception:
            cin = chs.createInput(edges, False)
            cin.setToEqualDistance(_vi(f['dist']))
        chs.add(cin)

    def engrave(self, comp, brep, f):
        z = ev(f['z'])
        h = ev(f['h'])
        cx, cy = ev(f['x']), ev(f['y'])
        w = len(f['s']) * h * 0.9 + 4.0
        pl = self.plane(comp, 2, f['z'])
        sk = comp.sketches.add(pl)
        sk.name = '%s_text' % brep.name
        p1 = sk.modelToSketchSpace(_P(cx - w / 2, cy - h, z))
        p2 = sk.modelToSketchSpace(_P(cx + w / 2, cy + h, z))
        ti = sk.sketchTexts.createInput2(f['s'], h / 10.0)
        ti.setAsMultiLine(p1, p2, adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
                          adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0)
        st = sk.sketchTexts.add(ti)
        self.extrude(comp, [st], f['depth'], adsk.fusion.FeatureOperations.CutFeatureOperation, brep,
                     adsk.fusion.ExtentDirections.NegativeExtentDirection)
        sk.isVisible = False

    # ---------------- appearances
    def find_base(self):
        if self.base_searched:
            return self.base_appearance
        self.base_searched = True
        names = ['Plastic - Matte (White)', 'Plastic - Glossy (White)', 'Paint - Enamel Glossy (White)',
                 'Plastic - Matte (Black)', 'Plastic - Glossy (Black)']
        libs = self.app.materialLibraries
        for n in names:
            for k in range(libs.count):
                try:
                    a = libs.item(k).appearances.itemByName(n)
                except Exception:
                    a = None
                if a:
                    self.base_appearance = a
                    return a
        for k in range(libs.count):
            try:
                apps = libs.item(k).appearances
                for m in range(min(apps.count, 5000)):
                    a = apps.item(m)
                    if a.name.startswith('Plastic'):
                        self.base_appearance = a
                        return a
            except Exception:
                continue
        self.warn('no base appearance found; colours skipped')
        return None

    def appearance(self, key):
        if key in self.apps:
            return self.apps[key]
        self.apps[key] = None
        name, rgb = APPEARANCES[key]
        try:
            a = self.design.appearances.itemByName(name)
            if a is None:
                base = self.find_base()
                if base is None:
                    return None
                a = self.design.appearances.addByCopy(base, name)
                props = a.appearanceProperties
                target = None
                for pid in ('opaque_albedo', 'generic_diffuse', 'surface_albedo', 'layered_diffuse'):
                    p = props.itemById(pid)
                    if p:
                        target = adsk.core.ColorProperty.cast(p)
                        if target:
                            break
                if target is None:
                    for k in range(props.count):
                        target = adsk.core.ColorProperty.cast(props.item(k))
                        if target:
                            break
                if target is not None:
                    target.value = adsk.core.Color.create(rgb[0], rgb[1], rgb[2], 255)
            self.apps[key] = a
        except Exception:
            self.warn('appearance %s skipped' % name)
        return self.apps[key]


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits

        ups = design.userParameters
        for name, expr, comment in PARAMS:
            ups.add(name, _vi(expr), 'mm', comment)

        builder = Builder(app, design)
        root = design.rootComponent
        tree = layout()
        for ch in tree['children']:          # root = the document itself
            builder.build(ch, root)

        app.activeViewport.fit()

        mass = builder.printed_cm3 * PETG_DENSITY
        saved = ''
        if SAVE_TO_CLOUD:
            try:
                doc.saveAs(DOC_NAME, app.data.activeProject.rootFolder, 'Horizon-1 1U CubeSat, SatForge Phase 1', '')
                saved = '\nSaved to the active project as %s.' % DOC_NAME
            except Exception:
                saved = '\nAuto-save failed; use File > Save.'
        msg = ('Horizon-1 assembly generated.\n'
               'Parts: %d   Occurrences: %d\n'
               'Printed PETG volume: %.1f cm^3  (~%.0f g solid-equivalent at %.2f g/cm^3)\n'
               'Warnings: %d%s'
               % (builder.n_parts, builder.n_occ, builder.printed_cm3, mass, PETG_DENSITY,
                  len(builder.warnings), saved))
        if builder.warnings:
            msg += '\n\nFirst warnings:\n' + '\n'.join(builder.warnings[:8])
        ui.messageBox(msg, 'Horizon-1 CubeSat Generator')
    except Exception:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()), 'Horizon-1 CubeSat Generator')
