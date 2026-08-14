# Copyright (c) 2026 Guido Esser
# Licensed under the Elastic License 2.0 — see LICENSE file for details.
# Community Edition — self-hosting free. SaaS/Managed Service requires commercial license.
"""
Process Builder — wandelt kompakte LLM-Extraktion in volles BPMN-JSON um.
Unterstützt ID-Preservation bei Iteration (existing_definition).
"""

import re


def build_process_definition(compact: dict, existing: dict = None) -> dict:
    """Expand compact LLM output into full process_definition for generate_bpmn.py.
    
    When existing is provided, reuses IDs for elements that match by (label, role, type)
    and for flows that match by (from_label, to_label, condition)."""

    name = compact.get("name", "Prozess")
    pid = "Process_1"
    roles = compact.get("roles", [])
    steps = compact.get("steps", [])
    flows = compact.get("flow", [])

    if not roles:
        roles = ["Organisation"]

    # ── Build existing lookups ──
    existing_elem_map = {}   # (label, role, type) -> id
    existing_label_to_id = {}  # label -> id (across all lanes)
    existing_lane_ids = {}    # role_name -> lane_id
    existing_flow_map = {}    # (from_label, to_label, condition) -> flow_id
    max_counters = {"start": 0, "task": 0, "gateway": 0, "end": 0}
    max_flow_idx = 0

    if existing:
        for lane in existing.get("lanes", []):
            lane_name = lane.get("name", "").strip()
            existing_lane_ids[lane_name] = lane.get("id")
            for elem in lane.get("elements", []):
                elabel = elem.get("name", "").strip()
                etype = elem.get("type", "")
                eid = elem.get("id", "")
                existing_elem_map[(elabel, lane_name, etype)] = eid
                existing_label_to_id[elabel] = eid
                # Track max counters
                m = re.match(r'(\w+)_(\d+)', eid)
                if m:
                    ctype = m.group(1).lower()
                    cnum = int(m.group(2))
                    if ctype in max_counters and cnum > max_counters[ctype]:
                        max_counters[ctype] = cnum

        for f in existing.get("flows", []):
            from_id = f.get("from", "")
            to_id = f.get("to", "")
            cond = f.get("condition", "")
            # Reverse id->label for flow matching
            from_label = ""
            to_label = ""
            for lbl, eid in existing_label_to_id.items():
                if eid == from_id:
                    from_label = lbl
                if eid == to_id:
                    to_label = lbl
            if from_label and to_label:
                existing_flow_map[(from_label, to_label, cond)] = f.get("id")
            # Track max flow index
            m = re.match(r'Flow_(\d+)', f.get("id", ""))
            if m:
                num = int(m.group(1))
                if num > max_flow_idx:
                    max_flow_idx = num

    # ── Step 1: Assign IDs to new elements ──
    id_map = {}   # label -> id
    lane_elements = {role: [] for role in roles}
    counters = dict(max_counters)  # Start counting from existing max

    for step in steps:
        label = step.get("label", "").strip()
        stype = step.get("type", "task")
        role = step.get("role", roles[0])

        if not label:
            continue

        if stype not in counters:
            stype = "task"
            counters.setdefault("task", 0)

        # Try to reuse existing ID by (label, role, type)
        reuse_key = (label, role, stype)
        if reuse_key in existing_elem_map:
            eid = existing_elem_map[reuse_key]
        else:
            counters[stype] += 1
            eid = f"{stype.capitalize()}_{counters[stype]}"

        id_map[label] = eid

        element = {"type": stype, "id": eid, "name": label}
        if stype == "gateway":
            element["gateway_type"] = step.get("gateway_type", "XOR")

        if role in lane_elements:
            lane_elements[role].append(element)
        else:
            lane_elements.setdefault("Organisation", []).append(element)

    # ── Step 2: Build lanes ──
    lanes = []
    used_ids = set()
    for role in roles:
        elems = lane_elements.get(role, [])
        if not elems:
            continue

        # Reuse existing lane ID if role name matches
        if role.strip() in existing_lane_ids:
            lane_id = existing_lane_ids[role.strip()]
        else:
            # Generate new lane ID
            lane_idx = 1
            while f"Lane_{lane_idx}" in used_ids:
                lane_idx += 1
            lane_id = f"Lane_{lane_idx}"

        used_ids.add(lane_id)
        lanes.append({
            "name": role,
            "id": lane_id,
            "elements": elems
        })

    # ── Step 3: Build flows ──
    flow_idx = max_flow_idx
    flow_list = []
    for f in flows:
        if len(f) < 2:
            continue
        from_label = f[0].strip()
        to_label = f[1].strip()
        condition = f[2].strip() if len(f) > 2 else ""

        if from_label not in id_map or to_label not in id_map:
            continue

        # Try to reuse existing flow ID
        flow_key = (from_label, to_label, condition)
        if flow_key in existing_flow_map:
            flow_id = existing_flow_map[flow_key]
        else:
            flow_idx += 1
            flow_id = f"Flow_{flow_idx}"

        entry = {
            "id": flow_id,
            "from": id_map[from_label],
            "to": id_map[to_label],
        }
        if condition:
            entry["condition"] = condition
        flow_list.append(entry)

    # ── Step 4: Collect end events ──
    end_events = []
    for lane in lanes:
        for elem in lane["elements"]:
            if elem["type"] == "end":
                end_events.append({
                    "id": elem["id"],
                    "name": elem["name"],
                    "type": "end",
                })

    return {
        "name": name,
        "id": pid,
        "lanes": lanes,
        "flows": flow_list,
        "end_events": end_events,
    }
