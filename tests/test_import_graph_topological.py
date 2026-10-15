"""RED tests for import_graph topological ordering bug.

These tests expose the bug where _sort_items_by_depth only handles 2 levels,
causing foreign key violations in hierarchies >= 3 levels when foreign_keys=ON.

D1: _sort_items_by_depth separates parent_id NULL vs NOT NULL, but within the
    NOT NULL group, order is arbitrary. C (grandchild) can be inserted before B (parent).
D2: _insert_rows uses INSERT OR IGNORE, so FK violations are silently ignored,
    resulting in missing items without any exception.

Expected: These tests should FAIL on the current code and pass after fix.
"""

import uuid
from datetime import datetime

from task_orchestrator import engine


def _make_item(item_id: str, title: str, parent_id: str | None = None) -> dict:
    """Create a properly formatted item with all required fields."""
    now = datetime.now().isoformat()
    return {
        "id": item_id,
        "title": title,
        "description": "",
        "status": "queue",
        "priority": "medium",
        "parent_id": parent_id,
        "item_type": "",
        "tags": "",
        "created_at": now,
        "updated_at": now,
    }


class TestImportGraphTopological:
    """Test cases for topological ordering in import_graph with hierarchies >= 3 levels."""

    def test_3_level_hierarchy_adverse_order(self, tmp_db):
        """Case 1: 3-level hierarchy in adverse order should import all items.

        Input order: [grandchild C, grandparent A, parent B]
        Expected: All 3 items inserted successfully, count=3
        Current bug: C fails FK constraint, OR IGNORE silences it, count=2 (RED)
        """
        # Create 3-level hierarchy in worst possible order for current sort algorithm
        items_data = {
            "items": [
                _make_item("item-c-grandchild", "Grandchild Task C", "item-b-parent"),
                _make_item("item-a-grandparent", "Grandparent Task A", None),
                _make_item("item-b-parent", "Parent Task B", "item-a-grandparent"),
            ],
            "notes": [],
            "dependencies": [],
        }

        # Import with replace mode (clean slate)
        result = engine.import_graph(items_data, mode="replace")

        # Should successfully import all 3 items without FK violations
        # Current bug: count will be 2 because grandchild C is silently dropped
        assert result["imported"] is True
        assert result["mode"] == "replace"
        assert result["counts"]["items"] == 3  # This should FAIL (current: 2)

        # Verify the hierarchy structure exists in the database
        exported = engine.export_graph()
        exported_items = {item["id"]: item for item in exported["items"]}

        # All items should exist
        assert "item-a-grandparent" in exported_items
        assert "item-b-parent" in exported_items
        assert "item-c-grandchild" in exported_items  # This should FAIL (missing)

        # Parent-child relationships should be preserved
        assert exported_items["item-a-grandparent"]["parent_id"] is None
        assert exported_items["item-b-parent"]["parent_id"] == "item-a-grandparent"
        assert exported_items["item-c-grandchild"]["parent_id"] == "item-b-parent"

    def test_4_level_hierarchy_shuffled_order(self, tmp_db):
        """Case 2: 4-level hierarchy in shuffled order should import all items.

        Input order: [D, A, C, B] for hierarchy A->B->C->D
        Expected: All 4 items inserted successfully, count=4
        Current bug: Multiple FK violations, count < 4 (RED)
        """
        items_data = {
            "items": [
                _make_item("item-d-level4", "Level 4 Task D", "item-c-level3"),
                _make_item("item-a-root", "Root Task A", None),
                _make_item("item-c-level3", "Level 3 Task C", "item-b-level2"),
                _make_item("item-b-level2", "Level 2 Task B", "item-a-root"),
            ],
            "notes": [],
            "dependencies": [],
        }

        result = engine.import_graph(items_data, mode="replace")

        # Should import all 4 items successfully
        assert result["counts"]["items"] == 4  # This should FAIL (current: < 4)

    def test_cross_level_dependencies(self, tmp_db):
        """Case 3: Dependencies between items at different hierarchy levels.

        Hierarchy: A->B->C plus dependency from C to A (cross-level)
        Expected: All items and dependencies inserted without FK violations
        """
        now = datetime.now().isoformat()
        items_data = {
            "items": [
                _make_item("item-c-child", "Child C", "item-b-mid"),
                _make_item("item-a-root", "Root A", None),
                _make_item("item-b-mid", "Mid B", "item-a-root"),
            ],
            "notes": [],
            "dependencies": [
                {
                    "id": str(uuid.uuid4()),
                    "from_id": "item-c-child",
                    "to_id": "item-a-root",  # Cross-level dependency
                    "dep_type": "blocks",
                    "unblock_at": "done",
                    "created_at": now,
                }
            ],
        }

        result = engine.import_graph(items_data, mode="replace")

        # All items and dependencies should be inserted
        assert result["counts"]["items"] == 3  # This should FAIL if items are missing
        assert result["counts"]["dependencies"] == 1

    def test_orphan_parent_reference(self, tmp_db):
        """Case 4: Item references parent_id that doesn't exist in batch or DB.

        Decision (R2): Orphan parents are normalized to roots (parent_id=None)
        to avoid FK violations and ensure no data loss.
        """
        items_data = {
            "items": [
                _make_item("item-orphan", "Orphaned Item", "nonexistent-parent-id"),
                _make_item("item-good", "Good Item", None),
            ],
            "notes": [],
            "dependencies": [],
        }

        result = engine.import_graph(items_data, mode="replace")

        # Both items should be imported successfully
        assert result["counts"]["items"] == 2

        # Verify both items exist in the database
        exported = engine.export_graph()
        exported_items = {item["id"]: item for item in exported["items"]}

        # Both items should exist
        assert "item-good" in exported_items
        assert "item-orphan" in exported_items

        # Both should be roots (parent_id=None) - orphan was normalized
        assert exported_items["item-good"]["parent_id"] is None
        assert exported_items["item-orphan"]["parent_id"] is None

    def test_flat_graph_regression(self, tmp_db):
        """Case 5: Flat graph (all parent_id=NULL) should work as before.

        This is a regression test - flat graphs work today and must continue working.
        This test should PASS on current code.
        """
        items_data = {
            "items": [
                _make_item("item-1", "Flat Item 1", None),
                _make_item("item-2", "Flat Item 2", None),
                _make_item("item-3", "Flat Item 3", None),
            ],
            "notes": [],
            "dependencies": [],
        }

        result = engine.import_graph(items_data, mode="replace")

        # All flat items should import successfully (this should PASS today)
        assert result["counts"]["items"] == 3

        # Verify all items exist
        exported = engine.export_graph()
        exported_ids = {item["id"] for item in exported["items"]}
        assert exported_ids == {"item-1", "item-2", "item-3"}

    def test_idempotent_merge(self, tmp_db):
        """Case 6: Importing the same graph twice should be idempotent.

        Second import should not create duplicates, count should remain stable.
        This should PASS on current code (tests existing merge behavior).
        """
        items_data = {
            "items": [
                _make_item("item-parent", "Parent Item", None),
                _make_item("item-child", "Child Item", "item-parent"),
            ],
            "notes": [],
            "dependencies": [],
        }

        # First import
        result1 = engine.import_graph(items_data, mode="merge")
        first_count = result1["counts"]["items"]

        # Second import (should be idempotent)
        result2 = engine.import_graph(items_data, mode="merge")
        second_count = result2["counts"]["items"]

        # Count should be stable (no duplicates created)
        assert second_count == first_count

        # Verify no duplicate items in database
        exported = engine.export_graph()
        exported_ids = [item["id"] for item in exported["items"]]
        assert len(exported_ids) == len(set(exported_ids))  # No duplicates
