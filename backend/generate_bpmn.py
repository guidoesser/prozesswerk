#!/usr/bin/env python3
"""
BPMN 2.0 XML Generator mit ELK.js Layout (Sugiyama + orthogonale Kanten).

Liest Prozessdefinition (JSON) von stdin → BPMN 2.0 XML auf stdout.

Layout-Strategie:
  1. ELK.js (flach, direction=RIGHT, ORTHOGONAL) → X-Positionen + Intra-Lane-Kanten.
  2. Lanes vertikal stapeln, X-Positionen erhalten.
  3. Intra-Lane: ELK-Waypoints mit Y-Translation.
  4. Cross-Lane: Spine-Routing (rechts an allen Knoten vorbei),
     horizontale Ein-/Ausfahrt NUR in Lane-Gaps → keine Knoten-Überlappung.
  5. Parallele Kanten erhalten separate Spine-Offsets.

Abhängigkeiten: Node.js + elkjs

Usage:
  cat process.json | python3 generate_bpmn.py > diagram.bpmn
"""

import json
import subprocess
import sys
import os
import hashlib
import xml.etree.ElementTree as ET
from collections import defaultdict
from functools import lru_cache

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ELK_SCRIPT = os.path.join(SCRIPT_DIR, 'elk-layout.js')

NS = {
    'bpmn': ('bpmn', 'http://www.omg.org/spec/BPMN/20100524/MODEL'),
    'bpmndi': ('bpmndi', 'http://www.omg.org/spec/BPMN/20100524/DI'),
    'dc': ('dc', 'http://www.omg.org/spec/DD/20100524/DC'),
    'di': ('di', 'http://www.omg.org/spec/DD/20100524/DI'),
    'xsi': ('xsi', 'http://www.w3.org/2001/XMLSchema-instance'),
}
for _p, _u in NS.values():
    ET.register_namespace(_p, _u)

def tag(ns_key, local_name):
    return f'{{{NS[ns_key][1]}}}{local_name}'

ELEM_SIZES = {
    'task': (100, 80), 'userTask': (100, 80), 'usertask': (100, 80),
    'serviceTask': (100, 80), 'servicetask': (100, 80),
    'start': (36, 36), 'end': (36, 36), 'gateway': (50, 50),
    'subProcess': (100, 80), 'subprocess': (100, 80),
}

LANE_PAD_TOP = 25
LANE_PAD_BOT = 25
LANE_GAP = 20         # vertikaler Abstand zwischen Lanes
POOL_TOP = 50
SPINE_GAP = 50        # Abstand Spine zu rechtestem Knoten
SPINE_OFFSET = 18     # Offset pro paralleler Cross-Lane-Kante


def get_element_size(elem):
    return ELEM_SIZES.get(elem.get('type', 'task'), (100, 80))


# ─── ELK ────────────────────────────────────────────────────────────

def build_elk_graph(process_def):
    lanes_data = process_def.get('lanes', [])
    flows_data = process_def.get('flows', [])
    if not lanes_data:
        lanes_data = [{'name': 'Organisation', 'id': 'Lane_1', 'elements': []}]
    children = []
    for lane in lanes_data:
        for elem in lane.get('elements', []):
            ew, eh = get_element_size(elem)
            children.append({'id': elem['id'], 'width': ew, 'height': eh})
    edges = [{'id': f['id'], 'sources': [f['from']], 'targets': [f['to']]}
             for f in flows_data]
    return {
        'id': 'root',
        'layoutOptions': {
            'elk.algorithm': 'layered',
            'elk.direction': 'RIGHT',
            'elk.edgeRouting': 'ORTHOGONAL',
            'elk.layered.spacing.nodeNode': '70',
            'elk.layered.spacing.edgeNode': '40',
            'elk.layered.spacing.edgeEdge': '20',
            'elk.layered.spacing.nodeNodeBetweenLayers': '120',
            'elk.spacing.nodeNode': '50',
            'elk.layered.mergeEdges': 'false',
            'elk.layered.considerModelOrder.strategy': 'PREFER_EDGES',
            'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
            'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
        },
        'children': children, 'edges': edges,
    }


def compute_elk_layout(elk_graph):
    result = subprocess.run(
        ['node', ELK_SCRIPT],
        input=json.dumps(elk_graph),
        capture_output=True, text=True, timeout=30, cwd=SCRIPT_DIR,
    )
    if result.returncode != 0:
        print(f"ELK Layout Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


# ─── Layout ─────────────────────────────────────────────────────────

def compute_layout(layout_result, process_def):
    lanes_data = process_def.get('lanes', [])
    flows_data = process_def.get('flows', [])
    if not lanes_data:
        lanes_data = [{'name': 'Organisation', 'id': 'Lane_1', 'elements': []}]

    # ELK-Rohpositionen
    raw_positions = {}
    for node in layout_result.get('children', []):
        raw_positions[node['id']] = {
            'x': node.get('x', 0), 'y': node.get('y', 0),
            'w': node.get('width', 100), 'h': node.get('height', 80),
        }

    # Lane-Gruppen
    lane_groups = []
    for lane in lanes_data:
        min_y, max_y = float('inf'), float('-inf')
        for elem in lane.get('elements', []):
            if elem['id'] in raw_positions:
                p = raw_positions[elem['id']]
                if p['y'] < min_y: min_y = p['y']
                if p['y'] + p['h'] > max_y: max_y = p['y'] + p['h']
        if min_y == float('inf'):
            lane_height, min_y = 80, 0
        else:
            lane_height = int(max_y - min_y) + LANE_PAD_TOP + LANE_PAD_BOT
        lane_groups.append({
            'name': lane.get('name', lane['id']),
            'id': lane['id'],
            'elements': lane.get('elements', []),
            'elk_min_y': min_y,
            'height': lane_height,
        })

    # Vertikal stapeln → lane_bounds, lane_y_map, elem_lane_map
    current_y = POOL_TOP
    lane_bounds = []
    lane_y_map = {}
    elem_lane_map = {}
    for lg in lane_groups:
        lane_bounds.append((lg['name'], lg['id'], current_y, lg['height']))
        lane_y_map[lg['id']] = current_y
        for elem in lg['elements']:
            elem_lane_map[elem['id']] = lg['id']
        current_y += lg['height'] + LANE_GAP
    total_height = current_y - LANE_GAP + 20

    # Flow-Lane-Mapping
    flow_lanes = {}
    for flow in flows_data:
        flow_lanes[flow['id']] = (
            elem_lane_map.get(flow['from']),
            elem_lane_map.get(flow['to']),
        )

    # Absolute Knoten-Positionen
    all_elem_map = {}
    for lg in lane_groups:
        lane_top = lane_y_map[lg['id']]
        for elem in lg['elements']:
            eid = elem['id']
            if eid not in raw_positions: continue
            p = raw_positions[eid]
            ew, eh = get_element_size(elem)
            offset_y = p['y'] - lg['elk_min_y'] + LANE_PAD_TOP
            all_elem_map[eid] = (p['x'], lane_top + offset_y, ew, eh)

    # Spine-Position (rechts an allem)
    max_right = max(ex + ew for ex, ey, ew, eh in all_elem_map.values())
    spine_x = max_right + SPINE_GAP

    # Parallele Cross-Lane-Kanten gruppieren
    lane_pair_groups = defaultdict(list)
    cross_flows = [(f['id'], flow_lanes[f['id']][0], flow_lanes[f['id']][1])
                   for f in flows_data
                   if flow_lanes[f['id']][0] != flow_lanes[f['id']][1]]
    for fid, sl, tl in cross_flows:
        lane_pair_groups[(sl, tl)].append(fid)

    # Edge-Waypoints berechnen (minimale Richtungswechsel, orthogonal)
    edge_waypoints = {}

    for flow in flows_data:
        fid = flow['id']
        src_lane, tgt_lane = flow_lanes.get(fid, (None, None))
        ffrom, fto = flow['from'], flow['to']

        if ffrom not in all_elem_map or fto not in all_elem_map:
            continue

        sx, sy, sw, sh = all_elem_map[ffrom]
        tx, ty, tw, th = all_elem_map[fto]

        if src_lane == tgt_lane and src_lane is not None:
            # ── Intra-Lane: minimal 0–1 Richtungswechsel ──
            src_cx = sx + sw           # exit right edge
            src_cy = sy + sh / 2       # center Y
            tgt_cx = tx                # enter left edge
            tgt_cy = ty + th / 2       # center Y

            if abs(src_cy - tgt_cy) < 10:
                # Gleiche Höhe → gerade Linie (0 Richtungswechsel)
                edge_waypoints[fid] = [(src_cx, src_cy), (tgt_cx, tgt_cy)]
            else:
                # L-Shape (1 Richtungswechsel): horizontal bis Ziel-X, dann vertikal
                edge_waypoints[fid] = [
                    (src_cx, src_cy),
                    (tgt_cx, src_cy),
                    (tgt_cx, tgt_cy),
                ]

        elif src_lane != tgt_lane:
            # ── Cross-Lane routing ──
            # Offset für parallele Kanten
            pair_key = (src_lane, tgt_lane)
            pfs = lane_pair_groups[pair_key]
            pidx = pfs.index(fid) if fid in pfs else 0
            np = len(pfs)
            poff = (-(np - 1) * SPINE_OFFSET / 2 + pidx * SPINE_OFFSET) if np > 1 else 0

            src_cx = sx + sw
            src_cy = sy + sh / 2 + poff
            tgt_cx = tx
            tgt_cy = ty + th / 2 + poff

            lane_ids = [lg['id'] for lg in lane_groups]
            src_idx = lane_ids.index(src_lane)
            tgt_idx = lane_ids.index(tgt_lane)
            adjacent = abs(src_idx - tgt_idx) == 1

            if adjacent:
                # Benachbarte Lanes: L-Shape (1 Richtungswechsel)
                edge_waypoints[fid] = [
                    (src_cx, src_cy),
                    (tgt_cx, src_cy),
                    (tgt_cx, tgt_cy),
                ]
            else:
                # Entfernte Lanes: Spine mit 1 Richtungswechsel auf Spine
                # Quelle → Spine → (vertikal auf Spine) → Ziel
                edge_waypoints[fid] = [
                    (src_cx, src_cy),
                    (spine_x, src_cy),
                    (spine_x, tgt_cy),
                    (tgt_cx, tgt_cy),
                ]

    total_width = spine_x + 40
    return all_elem_map, lane_bounds, edge_waypoints, total_width, total_height


# ─── BPMN XML ───────────────────────────────────────────────────────

def make_bpmn_xml(process_def, all_elem_map, lane_bounds,
                   edge_waypoints, total_width, total_height):
    name = process_def.get('name', 'Prozess')
    pid = process_def.get('id', 'Process_1')
    lanes_data = process_def.get('lanes', [])
    flows_data = process_def.get('flows', [])

    definitions = ET.Element(tag('bpmn', 'definitions'), {
        'targetNamespace': 'http://bpmn.io/schema/bpmn',
        'id': f'{pid}_Definitions',
    })
    proc = ET.SubElement(definitions, tag('bpmn', 'process'), {
        'id': pid, 'name': name, 'isExecutable': 'true',
    })

    pool_id = None
    if lanes_data:
        collab = ET.SubElement(definitions, tag('bpmn', 'collaboration'), {
            'id': f'{pid}_Collaboration',
        })
        pool_id = f'{pid}_Pool'
        ET.SubElement(collab, tag('bpmn', 'participant'), {
            'id': pool_id, 'name': 'Pool', 'processRef': pid,
        })
        lane_set = ET.SubElement(proc, tag('bpmn', 'laneSet'), {
            'id': f'{pid}_LaneSet',
        })
        for lane in lanes_data:
            le = ET.SubElement(lane_set, tag('bpmn', 'lane'), {
                'id': lane['id'], 'name': lane.get('name', ''),
            })
            for e in lane.get('elements', []):
                ET.SubElement(le, tag('bpmn', 'flowNodeRef')).text = e['id']

    for lane in lanes_data:
        for elem in lane.get('elements', []):
            eid, ename, etype = elem['id'], elem.get('name', ''), elem.get('type', 'task')
            if etype == 'start':
                ET.SubElement(proc, tag('bpmn', 'startEvent'), {'id': eid, 'name': ename})
            elif etype == 'end':
                ET.SubElement(proc, tag('bpmn', 'endEvent'), {'id': eid, 'name': ename})
            elif etype == 'gateway':
                gt = elem.get('gateway_type', 'XOR')
                bt = 'exclusiveGateway' if gt == 'XOR' else 'parallelGateway'
                ET.SubElement(proc, tag('bpmn', bt), {
                    'id': eid, 'name': ename, 'gatewayDirection': 'Mixed',
                })
            elif etype in ('subProcess', 'subprocess'):
                sub = ET.SubElement(proc, tag('bpmn', 'subProcess'), {
                    'id': eid, 'name': ename,
                })
                sub.set('triggeredByEvent', 'false')
            elif etype in ('serviceTask', 'servicetask'):
                ET.SubElement(proc, tag('bpmn', 'serviceTask'), {'id': eid, 'name': ename})
            elif etype in ('userTask', 'usertask'):
                ET.SubElement(proc, tag('bpmn', 'userTask'), {'id': eid, 'name': ename})
            else:
                ET.SubElement(proc, tag('bpmn', 'task'), {'id': eid, 'name': ename})

    for flow in flows_data:
        sf = ET.SubElement(proc, tag('bpmn', 'sequenceFlow'), {
            'id': flow['id'], 'sourceRef': flow['from'], 'targetRef': flow['to'],
        })
        cond = flow.get('condition', '')
        if cond:
            ce = ET.SubElement(sf, tag('bpmn', 'conditionExpression'), {
                f'{{{NS["xsi"][1]}}}type': 'bpmn:tFormalExpression',
            })
            ce.text = cond

    # BPMNDiagram
    diagram = ET.SubElement(definitions, tag('bpmndi', 'BPMNDiagram'), {
        'id': f'{pid}_Diagram',
    })
    plane = ET.SubElement(diagram, tag('bpmndi', 'BPMNPlane'), {
        'id': f'{pid}_Plane', 'bpmnElement': pid,
    })
    if pool_id:
        ps = ET.SubElement(plane, tag('bpmndi', 'BPMNShape'), {
            'id': f'{pid}_Pool_Shape', 'bpmnElement': pool_id, 'isHorizontal': 'true',
        })
        ET.SubElement(ps, tag('dc', 'Bounds'), {
            'x': '0', 'y': str(POOL_TOP),
            'width': str(total_width), 'height': str(total_height - POOL_TOP),
        })
    for ln, lid, ly, lh in lane_bounds:
        s = ET.SubElement(plane, tag('bpmndi', 'BPMNShape'), {
            'id': f'{lid}_Shape', 'bpmnElement': lid, 'isHorizontal': 'true',
        })
        ET.SubElement(s, tag('dc', 'Bounds'), {
            'x': '0', 'y': str(int(ly)), 'width': str(total_width), 'height': str(int(lh)),
        })
    for eid, (ex, ey, ew, eh) in all_elem_map.items():
        s = ET.SubElement(plane, tag('bpmndi', 'BPMNShape'), {
            'id': f'{eid}_Shape', 'bpmnElement': eid,
        })
        ET.SubElement(s, tag('dc', 'Bounds'), {
            'x': f'{ex:.0f}', 'y': f'{ey:.0f}',
            'width': str(int(ew)), 'height': str(int(eh)),
        })
    for flow in flows_data:
        fid = flow['id']
        wps = edge_waypoints.get(fid)
        if not wps: continue
        e = ET.SubElement(plane, tag('bpmndi', 'BPMNEdge'), {
            'id': f'{fid}_Edge', 'bpmnElement': fid,
        })
        for wx, wy in wps:
            ET.SubElement(e, tag('di', 'waypoint'), {
                'x': f'{wx:.0f}', 'y': f'{wy:.0f}',
            })
    return definitions


def serialize_xml(tree):
    rough = ET.tostring(tree, encoding='unicode')
    lines = []
    for line in rough.replace('><', '>\n<').split('\n'):
        s = line.strip()
        if s: lines.append(s)
    result = '<?xml version="1.0" encoding="UTF-8"?>\n'
    indent = 0
    for line in lines:
        if line.startswith('</'): indent -= 1
        result += '  ' * max(0, indent) + line + '\n'
        if (line.startswith('<') and not line.startswith('</')
                and not line.startswith('<?xml') and not line.startswith('<![CDATA[')
                and not line.endswith('/>')):
            indent += 1
    return result


def generate_xml(process_def):
    """Convenience: full pipeline → XML string (for web app).
    Cached by process_definition hash for fast refinement round-trips."""
    return _generate_xml_cached(_hash_process_def(process_def), json.dumps(process_def, sort_keys=True))


def _hash_process_def(process_def):
    """Stable hash of lanes/flows structure (ignoring positions, only topology)."""
    h = hashlib.sha256()
    for lane in sorted(process_def.get('lanes', []), key=lambda l: l.get('id', '')):
        for elem in sorted(lane.get('elements', []), key=lambda e: e.get('id', '')):
            h.update(f"{lane['id']}:{elem['id']}:{elem['type']}:{elem.get('gateway_type','')}".encode())
    for flow in sorted(process_def.get('flows', []), key=lambda f: f.get('id', '')):
        h.update(f"{flow['id']}:{flow['from']}:{flow['to']}:{flow.get('condition','')}".encode())
    return h.hexdigest()


@lru_cache(maxsize=32)
def _generate_xml_cached(_hash: str, process_def_json: str):
    """Cached XML generation."""
    process_def = json.loads(process_def_json)
    elk_graph = build_elk_graph(process_def)
    layout_result = compute_elk_layout(elk_graph)
    all_elem_map, lane_bounds, edge_waypoints, total_width, total_height = \
        compute_layout(layout_result, process_def)
    xml_tree = make_bpmn_xml(
        process_def, all_elem_map, lane_bounds,
        edge_waypoints, total_width, total_height,
    )
    return serialize_xml(xml_tree)


def main():
    try:
        process_def = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Fehler: Ungültiges JSON — {e}", file=sys.stderr)
        sys.exit(1)
    sys.stdout.write(generate_xml(process_def))


if __name__ == '__main__':
    main()
