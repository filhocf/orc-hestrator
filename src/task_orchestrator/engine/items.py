from datetime import UTC, datetime

from croniter import CroniterBadCronError, croniter

from ..db import get_connection
from .base import (
    ToolError,
    _now,
    _row_to_dict,
    _uid,
    _validate_due_at,
    _validate_priority,
    get_agent_id,
)


def create_item(
    title: str,
    description: str = "",
    summary: str = "",
    parent_id: str | None = None,
    priority: str = "medium",
    complexity: int | None = None,
    item_type: str = "",
    tags: str = "",
    metadata: str | None = None,
    properties: str | None = None,
    due_at: str | None = None,
    schedule: str | None = None,
) -> dict:
    _validate_priority(priority)
    _validate_due_at(due_at)
    if complexity is not None and not (1 <= complexity <= 10):
        raise ToolError(
            "VALIDATION", f"Complexity must be 1-10, got {complexity}", "complexity"
        )
    conn = get_connection()
    try:
        item_id = _uid()
        now = _now()
        agent_id = get_agent_id()  # Get current agent_id for created_by
        if parent_id:
            parent = conn.execute(
                "SELECT id FROM work_items WHERE id=?", (parent_id,)
            ).fetchone()
            if not parent:
                raise ToolError(
                    "NOT_FOUND", f"Parent {parent_id} not found", "parent_id"
                )
            depth = _get_depth(conn, parent_id)
            if depth >= 3:
                raise ToolError(
                    "VALIDATION",
                    f"Max depth 4 reached (parent at depth {depth})",
                    "parent_id",
                )
        next_run_at = None
        if schedule:
            try:
                next_run_at = (
                    croniter(schedule, datetime.now(UTC)).get_next(datetime).isoformat()
                )
            except CroniterBadCronError:
                raise ToolError(
                    "VALIDATION", f"Invalid cron expression: {schedule}", "schedule"
                )
        conn.execute(
            """INSERT INTO work_items (id,parent_id,title,description,summary,status,priority,
               complexity,item_type,tags,metadata,properties,role_changed_at,due_at,schedule,next_run_at,created_at,updated_at,created_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                item_id,
                parent_id,
                title,
                description,
                summary,
                "queue",
                priority,
                complexity,
                item_type,
                tags,
                metadata,
                properties,
                now,
                due_at,
                schedule,
                next_run_at,
                now,
                now,
                agent_id,
            ),
        )
        conn.commit()
        return _row_to_dict(
            conn.execute("SELECT * FROM work_items WHERE id=?", (item_id,)).fetchone()
        )
    finally:
        conn.close()


def create_items_batch(items: list[dict], parent_id: str | None = None) -> dict:
    """Batch create multiple items. Returns created items and failure count."""
    created = []
    failed = 0
    for item in items:
        try:
            pid = item.pop("parent_id", None) or parent_id
            result = create_item(parent_id=pid, **item)
            created.append(result)
        except Exception:
            failed += 1
    return {"items": created, "created": len(created), "failed": failed}


def update_item(item_id: str, **fields) -> dict:
    if "priority" in fields:
        _validate_priority(fields["priority"])
    if "due_at" in fields:
        _validate_due_at(fields["due_at"])
    if (
        "complexity" in fields
        and fields["complexity"] is not None
        and not (1 <= fields["complexity"] <= 10)
    ):
        raise ToolError(
            "VALIDATION",
            f"Complexity must be 1-10, got {fields['complexity']}",
            "complexity",
        )
    conn = get_connection()
    try:
        allowed = {
            "title",
            "description",
            "summary",
            "priority",
            "complexity",
            "item_type",
            "tags",
            "metadata",
            "properties",
            "due_at",
            "schedule",
            "parent_id",
        }
        if "parent_id" in fields:
            new_parent = fields["parent_id"]
            if new_parent:
                row = conn.execute(
                    "SELECT id FROM work_items WHERE id=?", (new_parent,)
                ).fetchone()
                if not row:
                    raise ToolError(
                        "NOT_FOUND", f"Parent {new_parent} not found", "parent_id"
                    )
                if new_parent == item_id:
                    raise ToolError(
                        "VALIDATION", "Item cannot be its own parent", "parent_id"
                    )
                depth = _get_depth(conn, new_parent)
                if depth >= 3:
                    raise ToolError(
                        "VALIDATION", "Max nesting depth (4) exceeded", "parent_id"
                    )
            else:
                fields["parent_id"] = None
        updates = {
            k: v
            for k, v in fields.items()
            if k in allowed and (v is not None or k == "parent_id")
        }
        if not updates:
            raise ToolError("VALIDATION", "No valid fields to update")
        if "schedule" in updates:
            try:
                updates["next_run_at"] = (
                    croniter(updates["schedule"], datetime.now(UTC))
                    .get_next(datetime)
                    .isoformat()
                )
            except CroniterBadCronError:
                raise ToolError(
                    "VALIDATION",
                    f"Invalid cron expression: {updates['schedule']}",
                    "schedule",
                )
        updates["updated_at"] = _now()
        updates["updated_by"] = get_agent_id()  # Set updated_by to current agent_id
        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(
            f"UPDATE work_items SET {set_clause} WHERE id=?",
            (*updates.values(), item_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM work_items WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise ToolError("NOT_FOUND", f"Item {item_id} not found", "item_id")
        return _row_to_dict(row)
    finally:
        conn.close()


def delete_item(item_id: str, recursive: bool = False) -> dict:
    conn = get_connection()
    try:
        descendants_deleted = 0
        if recursive:
            descendants_deleted = _delete_descendants(conn, item_id)
        else:
            child_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM work_items WHERE parent_id=?", (item_id,)
            ).fetchone()["cnt"]
            if child_count > 0:
                raise ToolError(
                    "VALIDATION",
                    f"Item has {child_count} children. Use recursive=true to delete them.",
                    "item_id",
                )
        cur = conn.execute("DELETE FROM work_items WHERE id=?", (item_id,))
        conn.commit()
        result = {"deleted": cur.rowcount > 0}
        if recursive:
            result["descendants_deleted"] = descendants_deleted
        return result
    finally:
        conn.close()


def delete_items_batch(ids: list[str], recursive: bool = False) -> dict:
    """Batch delete multiple items."""
    total_deleted = 0
    total_descendants = 0
    failed = 0
    for item_id in ids:
        try:
            result = delete_item(item_id, recursive=recursive)
            if result.get("deleted"):
                total_deleted += 1
            total_descendants += result.get("descendants_deleted", 0)
        except Exception:
            failed += 1
    result = {"deleted": total_deleted, "failed": failed}
    if recursive:
        result["descendants_deleted"] = total_descendants
    return result


def _delete_descendants(conn, parent_id: str) -> int:
    """Recursively delete all descendants, returns count deleted."""
    children = conn.execute(
        "SELECT id FROM work_items WHERE parent_id=?", (parent_id,)
    ).fetchall()
    count = 0
    for child in children:
        count += _delete_descendants(conn, child["id"])
    cur = conn.execute("DELETE FROM work_items WHERE parent_id=?", (parent_id,))
    count += cur.rowcount
    return count


def get_item(item_id: str) -> dict | None:
    conn = get_connection()
    try:
        return _row_to_dict(
            conn.execute("SELECT * FROM work_items WHERE id=?", (item_id,)).fetchone()
        )
    finally:
        conn.close()


# Colunas projetáveis de work_items (schema + migrações aditivas de autoria).
# Um teste compara esta lista com as chaves reais de _row_to_dict, para a
# constante não divergir do banco em silêncio.
ITEM_FIELDS = (
    "id",
    "parent_id",
    "title",
    "description",
    "summary",
    "status",
    "status_label",
    "previous_status",
    "priority",
    "complexity",
    "item_type",
    "tags",
    "metadata",
    "properties",
    "role_changed_at",
    "due_at",
    "schedule",
    "next_run_at",
    "created_at",
    "updated_at",
    "created_by",
    "updated_by",
)
# Campos do modo compacto: o que decide o próximo passo, sem o peso do resto.
COMPACT_FIELDS = ("id", "title", "status", "priority", "parent_id", "due_at")
# Medido no board real: títulos de 94 chars levavam o item compacto a 242 chars,
# contra o teto de 150. Truncar a 80 mantém o item identificável e sob o teto.
COMPACT_TITLE = 50


def _projection_names(fields: str, compact: bool) -> tuple[str, ...] | None:
    """Nomes de campo a projetar; None = linha completa (default histórico).

    Projeção é opt-in: sem `fields` e sem `compact`, nada muda — `web/api.py`
    chama esta função direto e alimenta a UI React.
    """
    if fields:
        names = tuple(name.strip() for name in fields.split(",") if name.strip())
        if not names:
            raise ToolError("VALIDATION", "fields is empty", "fields")
        unknown = [name for name in names if name not in ITEM_FIELDS]
        if unknown:
            raise ToolError(
                "VALIDATION",
                f"unknown field(s): {', '.join(sorted(unknown))}",
                "fields",
            )
        return names
    return COMPACT_FIELDS if compact else None


def project_items(
    items: list[dict], fields: str = "", compact: bool = False
) -> list[dict]:
    """Aplica a projeção a itens já carregados (adapter ou engine).

    No modo compacto o `id` sai com 8 caracteres, como no `get_context`: UUID
    completo custa 36 e sozinho consome um quarto do teto de 150 por item.
    `resolve_short_id` aceita 4+ na entrada, então o prefixo é utilizável.
    """
    names = _projection_names(fields, compact)
    if names is None:
        return items
    projected = [{name: item.get(name) for name in names} for item in items]
    if compact and not fields:
        for row in projected:
            row["id"] = (row.get("id") or "")[:8]
            # parent_id também é id: 36 chars por item comia o orçamento.
            if row.get("parent_id"):
                row["parent_id"] = row["parent_id"][:8]
            title = row.get("title") or ""
            if len(title) > COMPACT_TITLE:
                row["title"] = title[: COMPACT_TITLE - 1] + "…"
    return projected


def query_items(
    status: str | None = None,
    parent_id: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    tags: str | None = None,
    limit: int = 50,
    offset: int = 0,
    fields: str = "",
    compact: bool = False,
) -> list[dict]:
    conn = get_connection()
    try:
        clauses, params = [], []
        if status:
            clauses.append("status=?")
            params.append(status)
        if parent_id:
            clauses.append("parent_id=?")
            params.append(parent_id)
        if priority:
            clauses.append("priority=?")
            params.append(priority)
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            tag_clauses = ["tags LIKE ?" for _ in tag_list]
            clauses.append(f"({' OR '.join(tag_clauses)})")
            params.extend([f"%{t}%" for t in tag_list])

        if search:
            # FTS5 match on title/description + LIKE on notes body, deduplicated
            fts_ids = _fts_search(conn, search)
            note_rows = conn.execute(
                "SELECT DISTINCT item_id FROM notes WHERE body LIKE ?",
                (f"%{search}%",),
            ).fetchall()
            matched_ids = list(fts_ids | {r["item_id"] for r in note_rows})
            if not matched_ids:
                return []
            # Batch IN clause in chunks of 500 to avoid SQLITE_LIMIT_VARIABLE_NUMBER
            id_clauses = []
            for i in range(0, len(matched_ids), 500):
                chunk = matched_ids[i : i + 500]
                id_clauses.append(f"id IN ({','.join('?' for _ in chunk)})")
                params.extend(chunk)
            clauses.append(f"({' OR '.join(id_clauses)})")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        # Valida antes de consultar: campo inexistente é erro do chamador, não
        # motivo para devolver silenciosamente a linha inteira.
        _projection_names(fields, compact)
        rows = conn.execute(
            f"SELECT * FROM work_items {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return project_items([_row_to_dict(r) for r in rows], fields, compact)
    finally:
        conn.close()


def _fts_search(conn, search: str) -> set[str]:
    """Search FTS5 index with MATCH, fallback to LIKE on failure."""
    try:
        fts_term = search.replace('"', '""')
        rows = conn.execute(
            "SELECT id FROM items_fts WHERE items_fts MATCH ?",
            (f'"{fts_term}" OR {fts_term}*',),
        ).fetchall()
        return {r["id"] for r in rows}
    except Exception:
        rows = conn.execute(
            "SELECT id FROM work_items WHERE title LIKE ? OR description LIKE ?",
            (f"%{search}%", f"%{search}%"),
        ).fetchall()
        return {r["id"] for r in rows}


def get_children(parent_id: str) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM work_items WHERE parent_id=? ORDER BY created_at",
            (parent_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_ancestors(item_id: str) -> list[dict]:
    """Walk up the parent chain, returning ancestors from immediate parent to root."""
    conn = get_connection()
    try:
        ancestors = []
        current = item_id
        while current:
            row = conn.execute(
                "SELECT * FROM work_items WHERE id=?", (current,)
            ).fetchone()
            if not row or not row["parent_id"]:
                break
            parent = conn.execute(
                "SELECT * FROM work_items WHERE id=?", (row["parent_id"],)
            ).fetchone()
            if parent:
                ancestors.append(_row_to_dict(parent))
                current = parent["id"]
            else:
                break
        return ancestors
    finally:
        conn.close()


def _get_depth(conn, item_id: str) -> int:
    depth = 0
    current = item_id
    while current:
        row = conn.execute(
            "SELECT parent_id FROM work_items WHERE id=?", (current,)
        ).fetchone()
        if not row or not row["parent_id"]:
            break
        current = row["parent_id"]
        depth += 1
    return depth
