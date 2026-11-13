"""Course Directed Acyclic Graph (DAG) extraction and bottleneck analysis."""

from __future__ import annotations

from typing import Any

from core.run_dss import run_dss, _context


def build_curriculum_dag(student_id: str, dss_result: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build course dependency DAG and identify bottleneck courses for a student.
    
    Returns:
        nodes: Course nodes for the student's program/specialization with progress status.
        edges: Directed dependency edges (prerequisites and corequisites).
        bottlenecks: Failed courses locking downstream credits.
    """
    sid = str(student_id).strip()
    res = dss_result or run_dss(sid)
    ctx = _context()

    profile = res.get("profile_summary", {})
    spec = profile.get("specialization", "NW")
    progress = res.get("progress", {})
    eligible_keys = {
        item.get("course_id") or item.get("course_key")
        for item in res.get("eligible", [])
    }
    forced_retakes = set(res.get("forced_retakes", []))

    # Parse blocked reasons and root causes
    blocked_info: dict[str, dict[str, Any]] = {}
    for item in res.get("blocked", []):
        ckey = item.get("course_id") or item.get("course_key")
        reasons = []
        root_causes = []
        for r in item.get("reasons", []):
            code = r.get("code")
            reasons.append(code)
            if "root_causes" in r:
                root_causes.extend(r["root_causes"])
            elif "course_id" in r:
                root_causes.append(r["course_id"])
        blocked_info[ckey] = {
            "reasons": reasons,
            "root_causes": sorted(set(root_causes)),
        }

    # Program course map
    raw_courses = ctx["curriculum"]["courses"]
    enrichment = ctx["curriculum"]["enrichment_config"]
    course_enrich = enrichment.get("courses", {})

    # Filter courses relevant to this student (common + specialization)
    program_courses: dict[str, dict[str, Any]] = {}
    for c in raw_courses:
        cid = str(c["course_id"])
        cspec = c.get("specialization")
        if cspec and cspec not in {spec, "common"}:
            continue
        program_courses[cid] = c

    # Calculate status for each course node
    nodes = []
    unlock_map = {
        (item.get("course_id") or item.get("course_key")): item.get("unlock_value", 0.0)
        for item in res.get("eligible", [])
    }

    for cid, c in program_courses.items():
        credits = int(c.get("credits", 0))
        planned_sem = int(c.get("semester", 1))
        enr = course_enrich.get(cid, {})
        offered = enr.get("offered_semesters", "both")  # odd, even, both

        prog = progress.get(cid, {})
        raw_status = prog.get("status", "not_started")

        # Determine node status: completed | failed_bottleneck | failed | forced_retake | eligible | blocked
        b_info = blocked_info.get(cid, {})
        b_reasons = b_info.get("reasons", [])
        root_causes = b_info.get("root_causes", [])

        if raw_status == "completed":
            node_status = "completed"
        elif cid in forced_retakes:
            node_status = "forced_retake"
        elif raw_status == "failed":
            # Check if it is a root cause for other blocked courses
            node_status = "failed"
        elif cid in eligible_keys:
            node_status = "eligible"
        else:
            node_status = "blocked"

        nodes.append({
            "id": cid,
            "course_id": cid,
            "course_name": c.get("course_name", cid),
            "credits": credits,
            "planned_semester": planned_sem,
            "offered_semesters": offered,
            "status": node_status,
            "blocked_reasons": b_reasons,
            "root_causes": root_causes,
            "unlock_value": unlock_map.get(cid, 0.0),
        })

    # Find bottlenecks: failed courses that appear in root_causes of other courses
    all_root_causes: set[str] = set()
    for b in blocked_info.values():
        all_root_causes.update(b.get("root_causes", []))

    # Identify bottleneck courses
    bottlenecks = []
    node_by_id = {n["id"]: n for n in nodes}
    for cid in all_root_causes:
        if cid in program_courses:
            n = node_by_id.get(cid)
            if n and n["status"] in {"failed", "forced_retake", "blocked"}:
                n["status"] = "failed_bottleneck"
                # Count how many courses this course directly or indirectly blocks
                blocked_count = sum(1 for b in blocked_info.values() if cid in b.get("root_causes", []))
                bottlenecks.append({
                    "course_id": cid,
                    "course_name": n["course_name"],
                    "credits": n["credits"],
                    "planned_semester": n["planned_semester"],
                    "blocked_courses_count": blocked_count,
                    "status": n["status"],
                })

    bottlenecks.sort(key=lambda x: x["blocked_courses_count"], reverse=True)

    # Build edges
    raw_prereqs = ctx["curriculum"]["prerequisites"]
    edges = []
    active_node_ids = set(node_by_id.keys())

    for p in raw_prereqs:
        src = str(p["prerequisite_id"])
        tgt = str(p["course_id"])
        ptype = str(p.get("type", "prerequisite"))
        # Only include if both target and source belong to the student's curriculum
        if src in active_node_ids and tgt in active_node_ids:
            # Check if this edge is actively blocking
            src_node = node_by_id.get(src)
            tgt_node = node_by_id.get(tgt)
            is_blocking = False
            if tgt_node and tgt_node["status"] == "blocked" and src in tgt_node.get("root_causes", []):
                is_blocking = True
            elif src_node and src_node["status"] in {"failed", "failed_bottleneck", "forced_retake"}:
                is_blocking = True

            edges.append({
                "source": src,
                "target": tgt,
                "type": ptype,
                "is_blocking": is_blocking,
            })

    return {
        "student_id": sid,
        "specialization": spec,
        "nodes": nodes,
        "edges": edges,
        "bottlenecks": bottlenecks,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }
