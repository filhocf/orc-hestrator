"""Characterization tests for functions that lack direct test coverage.

These tests fix the current behavior as a contract before the engine.py refactor.
They call functions via the engine namespace to remain valid after the split into modules.
"""

from task_orchestrator import engine


class TestQueryDependenciesBfs:
    """Characterization tests for query_dependencies_bfs function."""

    def test_query_dependencies_bfs_outbound_empty(self, tmp_db):
        """query_dependencies_bfs with non-existent item should return empty list."""
        result = engine.query_dependencies_bfs("nonexistent-id", direction="outbound")
        assert result == []

    def test_query_dependencies_bfs_inbound_empty(self, tmp_db):
        """query_dependencies_bfs with non-existent item inbound should return empty list."""
        result = engine.query_dependencies_bfs("nonexistent-id", direction="inbound")
        assert result == []

    def test_query_dependencies_bfs_outbound_with_dependencies(self, tmp_db):
        """query_dependencies_bfs should traverse outbound dependencies in BFS order."""
        # Create items with dependency chain: A -> B -> C
        item_a = engine.create_item("Task A", "open", "medium")
        item_b = engine.create_item("Task B", "open", "medium")
        item_c = engine.create_item("Task C", "open", "medium")

        # Add dependencies: A depends on B, B depends on C
        engine.add_dependency(item_a["id"], item_b["id"])
        engine.add_dependency(item_b["id"], item_c["id"])

        # Query outbound dependencies from A
        result = engine.query_dependencies_bfs(item_a["id"], direction="outbound")

        # Should return B (depth 1) and C (depth 2) in BFS order
        assert len(result) == 2
        assert result[0]["to_id"] == item_b["id"]
        assert result[0]["depth"] == 1
        assert result[1]["to_id"] == item_c["id"]
        assert result[1]["depth"] == 2

        # Each result should include joined work_item fields
        assert "title" in result[0]
        assert "status" in result[0]
        assert "priority" in result[0]
        assert result[0]["title"] == "Task B"
        assert result[0]["status"] == "queue"  # New items start in "queue" status
        assert result[0]["priority"] == "medium"

    def test_query_dependencies_bfs_inbound_with_dependencies(self, tmp_db):
        """query_dependencies_bfs should traverse inbound dependencies in BFS order."""
        # Create items with dependency chain: A -> B -> C
        item_a = engine.create_item("Task A", "open", "medium")
        item_b = engine.create_item("Task B", "open", "medium")
        item_c = engine.create_item("Task C", "open", "medium")

        # Add dependencies: A depends on B, B depends on C
        engine.add_dependency(item_a["id"], item_b["id"])
        engine.add_dependency(item_b["id"], item_c["id"])

        # Query inbound dependencies from C (who depends on C?)
        result = engine.query_dependencies_bfs(item_c["id"], direction="inbound")

        # Should return B (depth 1) and A (depth 2) in BFS order
        assert len(result) == 2
        assert result[0]["from_id"] == item_b["id"]
        assert result[0]["depth"] == 1
        assert result[1]["from_id"] == item_a["id"]
        assert result[1]["depth"] == 2

        # Each result should include joined work_item fields
        assert result[0]["title"] == "Task B"
        assert result[1]["title"] == "Task A"

    def test_query_dependencies_bfs_max_depth_limit(self, tmp_db):
        """query_dependencies_bfs should respect max_depth parameter (current behavior includes depth+1 of traversed nodes)."""
        # Create a chain of 4 items: A -> B -> C -> D
        item_a = engine.create_item("Task A", "open", "medium")
        item_b = engine.create_item("Task B", "open", "medium")
        item_c = engine.create_item("Task C", "open", "medium")
        item_d = engine.create_item("Task D", "open", "medium")

        engine.add_dependency(item_a["id"], item_b["id"])
        engine.add_dependency(item_b["id"], item_c["id"])
        engine.add_dependency(item_c["id"], item_d["id"])

        # Query with max_depth=2 - current implementation returns 3 items with depths 1,2,3
        # (because it processes nodes up to depth 2, but adds their children at depth+1)
        result = engine.query_dependencies_bfs(
            item_a["id"], direction="outbound", max_depth=2
        )

        assert len(result) == 3  # This is the current behavior
        assert result[0]["to_id"] == item_b["id"]
        assert result[0]["depth"] == 1
        assert result[1]["to_id"] == item_c["id"]
        assert result[1]["depth"] == 2
        assert result[2]["to_id"] == item_d["id"]
        assert result[2]["depth"] == 3

    def test_query_dependencies_bfs_default_max_depth(self, tmp_db):
        """query_dependencies_bfs should use default max_depth=10."""
        # Create single dependency to verify default parameter works
        item_a = engine.create_item("Task A", "open", "medium")
        item_b = engine.create_item("Task B", "open", "medium")
        engine.add_dependency(item_a["id"], item_b["id"])

        # Call without max_depth parameter (should use default=10)
        result = engine.query_dependencies_bfs(item_a["id"], direction="outbound")

        assert len(result) == 1
        assert result[0]["to_id"] == item_b["id"]
        assert result[0]["depth"] == 1
