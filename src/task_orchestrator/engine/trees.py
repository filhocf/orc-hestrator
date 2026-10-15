from ..db import get_connection
from ..schemas import get_schema_for_item
from .base import TERMINAL, _row_to_dict
from .items import create_item
from .dependencies import add_dependency
from .notes import upsert_note
from .transitions import advance_item


def create_work_tree(
    root: dict,
    children: list[dict] | None = None,
    deps: list[dict] | None = None,
    create_notes: bool = False,
) -> dict:
    root_item = create_item(**root)
    ref_map = {"root": root_item["id"]}
    created = [root_item]
    for child in children or []:
        ref = child.pop("ref", None)
        child["parent_id"] = root_item["id"]
        item = create_item(**child)
        if ref:
            ref_map[ref] = item["id"]
        created.append(item)
    dep_results = []
    for dep in deps or []:
        fid = ref_map.get(dep["from"], dep["from"])
        tid = ref_map.get(dep["to"], dep["to"])
        dep_results.append(
            add_dependency(
                fid,
                tid,
                dep_type=dep.get("type", "blocks"),
                unblock_at=dep.get("unblock_at", "done"),
            )
        )
    # Auto-create blank notes from schemas
    notes_created = []
    if create_notes:
        for item in created:
            schema = get_schema_for_item(
                item.get("item_type", ""), item.get("tags", "")
            )
            if schema:
                for note_def in schema["notes"]:
                    note = upsert_note(
                        item["id"], note_def["key"], "", note_def["role"]
                    )
                    notes_created.append(
                        {
                            "item_id": item["id"],
                            "key": note_def["key"],
                            "role": note_def["role"],
                            "id": note["id"],
                        }
                    )
    return {
        "root": root_item,
        "children": created[1:],
        "dependencies": dep_results,
        "ref_map": ref_map,
        "notes": notes_created,
    }


def complete_tree(parent_id: str) -> dict:
    """Batch-complete all non-terminal descendants in topological order."""
    conn = get_connection()
    try:
        # Get all descendants
        def _get_all_descendants(pid):
            items = []
            rows = conn.execute(
                "SELECT * FROM work_items WHERE parent_id=?", (pid,)
            ).fetchall()
            for r in rows:
                items.append(_row_to_dict(r))
                items.extend(_get_all_descendants(r["id"]))
            return items

        descendants = _get_all_descendants(parent_id)
        completed = []
        skipped = []
        for item in descendants:
            if item["status"] in TERMINAL:
                skipped.append(
                    {"id": item["id"], "title": item["title"], "status": item["status"]}
                )
                continue
            try:
                result = advance_item(item["id"], "complete")
                completed.append(
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "new_status": result["status"],
                    }
                )
            except ValueError as e:
                skipped.append(
                    {"id": item["id"], "title": item["title"], "reason": str(e)}
                )
        return {"completed": completed, "skipped": skipped}
    finally:
        conn.close()