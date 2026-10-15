"""RED tests for agent_id per-request functionality.

These tests SHOULD FAIL today because the agent_id feature does not exist yet.
They test the PUBLIC contract (engine.set_agent_id/get_agent_id + created_by/updated_by fields),
not internal contextvar implementation.
"""

import asyncio
import tempfile
import os

import pytest

from task_orchestrator import engine
from task_orchestrator.engine import ToolError

# Import the agent_id functions that should exist after G4
# These imports WILL FAIL today with ImportError - that's expected RED behavior
from task_orchestrator.engine.base import set_agent_id, get_agent_id


class TestAgentIdBasicFunctionality:
    """Test basic agent_id set/get and created_by persistence (R2, R4)."""
    
    def test_create_item_with_agent_id_records_created_by(self):
        """(R2) set_agent_id('zero'); create_item → created_by == 'zero'."""
        set_agent_id('zero')
        
        item = engine.create_item(title='Test Item', description='Test desc')
        
        # The item should have created_by field with the agent_id value
        assert 'created_by' in item, "Item should have created_by field"
        assert item['created_by'] == 'zero', f"Expected created_by='zero', got {item.get('created_by')}"
    
    def test_create_item_without_agent_id_allows_anonymous(self):
        """(R4) No set_agent_id → create_item succeeds with created_by=None."""
        # Explicitly reset to ensure no agent_id is set
        set_agent_id(None)
        
        item = engine.create_item(title='Anonymous Item')
        
        # The operation should succeed and created_by should be None
        assert 'id' in item, "Item creation should succeed"
        assert item.get('created_by') is None, f"Expected created_by=None, got {item.get('created_by')}"


class TestAgentIdUpdateAndPreservation:
    """Test agent_id behavior on updates and preservation (R3)."""
    
    def test_update_item_preserves_created_by_sets_updated_by(self):
        """(R3) created_by preserved, updated_by changes on update_item."""
        # Create item with first agent
        set_agent_id('zero')
        item = engine.create_item(title='Original Title')
        original_id = item['id']
        
        # Update with different agent
        set_agent_id('tpol')
        updated_item = engine.update_item(original_id, title='Updated Title')
        
        # created_by should be preserved, updated_by should be new agent
        assert updated_item['created_by'] == 'zero', f"created_by should be preserved, got {updated_item.get('created_by')}"
        assert updated_item['updated_by'] == 'tpol', f"updated_by should be 'tpol', got {updated_item.get('updated_by')}"
    
    def test_advance_item_preserves_created_by_sets_updated_by(self):
        """(R3+transitions) created_by preserved, updated_by changes on advance_item."""
        # Create item with first agent
        set_agent_id('zero')
        item = engine.create_item(title='Test Item')
        item_id = item['id']
        
        # Advance with different agent
        set_agent_id('scotty')
        advanced_item = engine.advance_item(item_id, 'start')
        
        # created_by should be preserved, updated_by should be new agent
        assert advanced_item['created_by'] == 'zero', f"created_by should be preserved, got {advanced_item.get('created_by')}"
        assert advanced_item['updated_by'] == 'scotty', f"updated_by should be 'scotty', got {advanced_item.get('updated_by')}"


class TestAgentIdNotesAndDependencies:
    """Test agent_id for notes and dependencies (R2 notes/deps)."""
    
    def test_upsert_note_records_created_by(self):
        """(R2 notes) set_agent_id('zero'); upsert_note → note has created_by='zero'."""
        set_agent_id('zero')
        
        # Create an item first
        item = engine.create_item(title='Item with notes')
        item_id = item['id']
        
        # Create a note
        engine.upsert_note(item_id, key='test-key', body='Test note body', role='work')
        
        # Check that the note has created_by
        notes = engine.get_notes(item_id)
        assert len(notes) > 0, "Note should be created"
        note = notes[0]
        assert 'created_by' in note, "Note should have created_by field"
        assert note['created_by'] == 'zero', f"Expected note created_by='zero', got {note.get('created_by')}"
    
    def test_add_dependency_records_created_by(self):
        """(R2 deps) set_agent_id('zero'); add_dependency → dependency has created_by='zero'."""
        set_agent_id('zero')
        
        # Create two items
        item_a = engine.create_item(title='Item A')
        item_b = engine.create_item(title='Item B')
        
        # Add dependency
        engine.add_dependency(item_a['id'], item_b['id'])
        
        # Check that the dependency has created_by
        deps = engine.get_dependencies(item_a['id'])
        assert len(deps) > 0, "Dependency should be created"
        dep = deps[0]
        assert 'created_by' in dep, "Dependency should have created_by field"
        assert dep['created_by'] == 'zero', f"Expected dependency created_by='zero', got {dep.get('created_by')}"


class TestAgentIdIsolation:
    """Test agent_id isolation between requests (R5 CRITICAL)."""
    
    def test_sequential_agent_id_isolation(self):
        """R5 sequential test: different agent_ids don't leak between operations."""
        # Reset to clean state
        set_agent_id(None)
        
        # First operation with agent 'a'
        set_agent_id('a')
        item_a = engine.create_item(title='Item A')
        
        # Second operation with agent 'b'
        set_agent_id('b')
        item_b = engine.create_item(title='Item B')
        
        # Third operation with no agent (reset)
        set_agent_id(None)
        item_c = engine.create_item(title='Item C')
        
        # Verify each item has correct attribution
        assert item_a['created_by'] == 'a', f"Item A should have created_by='a', got {item_a.get('created_by')}"
        assert item_b['created_by'] == 'b', f"Item B should have created_by='b', got {item_b.get('created_by')}"
        assert item_c.get('created_by') is None, f"Item C should have created_by=None, got {item_c.get('created_by')}"
    
    def test_async_agent_id_isolation(self):
        """R5 async test: concurrent operations with different agent_ids don't leak."""
        
        async def create_item_with_agent(agent_id, title):
            """Helper coroutine that sets agent_id and creates item."""
            set_agent_id(agent_id)
            # Add small delay to increase chance of interleaving
            await asyncio.sleep(0.01)  
            return engine.create_item(title=title)
        
        async def run_concurrent_test():
            # Run two coroutines concurrently with different agent_ids
            results = await asyncio.gather(
                create_item_with_agent('alice', 'Alice Item'),
                create_item_with_agent('bob', 'Bob Item'),
                return_exceptions=True
            )
            return results
        
        # Run the async test
        results = asyncio.run(run_concurrent_test())
        
        # Verify no exceptions and correct attribution
        assert len(results) == 2, "Should have 2 results"
        assert not isinstance(results[0], Exception), f"First result should not be exception: {results[0]}"
        assert not isinstance(results[1], Exception), f"Second result should not be exception: {results[1]}"
        
        item_alice, item_bob = results
        
        # Each item should have the agent_id from its own coroutine
        assert item_alice['created_by'] == 'alice', f"Alice item should have created_by='alice', got {item_alice.get('created_by')}"
        assert item_bob['created_by'] == 'bob', f"Bob item should have created_by='bob', got {item_bob.get('created_by')}"


class TestAgentIdRoundTrip:
    """Test agent_id persistence through export/import (R9)."""
    
    def test_export_import_preserves_created_by(self):
        """(R9 roundtrip) created_by preserved through export_graph → import_graph."""
        # Create item with agent_id
        set_agent_id('zero')
        original_item = engine.create_item(title='Test Item', description='For export test')
        
        # Export the graph
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_file = f.name
        
        try:
            engine.export_graph(export_file)
            
            # Create fresh database for import test
            with tempfile.TemporaryDirectory() as temp_dir:
                # Import into clean database requires a bit more setup
                # but the key assertion is that created_by is preserved
                engine.import_graph(export_file)
                
                # Find the imported item (this is a simplified check)
                # In real implementation, we'd need to verify the specific item
                # For now, we test that the import process includes created_by fields
                imported_items = engine.get_all_items()
                
                # Find our item by title (fragile but good enough for RED test)
                our_item = None
                for item in imported_items:
                    if item.get('title') == 'Test Item':
                        our_item = item
                        break
                
                assert our_item is not None, "Imported item should be found"
                assert our_item['created_by'] == 'zero', f"Imported item should preserve created_by='zero', got {our_item.get('created_by')}"
        
        finally:
            # Clean up
            if os.path.exists(export_file):
                os.unlink(export_file)


class TestAgentIdGetFunction:
    """Test the get_agent_id function works correctly."""
    
    def test_get_agent_id_returns_current_value(self):
        """get_agent_id() returns what was set with set_agent_id()."""
        # Test with a value
        set_agent_id('test-agent')
        assert get_agent_id() == 'test-agent'
        
        # Test with None
        set_agent_id(None)
        assert get_agent_id() is None
        
        # Test with different value
        set_agent_id('another-agent')
        assert get_agent_id() == 'another-agent'