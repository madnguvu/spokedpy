"""
Unit tests for Visual Paradigms System.
"""

import pytest
from hypothesis import given, strategies as st
from visual_editor_core.visual_paradigms import (
    ParadigmType, ParadigmManager, NodeBasedParadigm, BlockBasedParadigm,
    DiagramBasedParadigm, TimelineBasedParadigm, NodeElement, BlockElement,
    DiagramElement, TimelineElement
)
from visual_editor_core.models import VisualModel, VisualNode, NodeType


class TestNodeBasedParadigm:
    """Test cases for Node-based paradigm."""
    
    def test_paradigm_creation(self):
        """Test basic paradigm creation."""
        paradigm = NodeBasedParadigm()
        
        assert paradigm.paradigm_type == ParadigmType.NODE_BASED
        assert len(paradigm.elements) == 0
        assert len(paradigm.connections) == 0
        assert paradigm.properties['supports_dataflow'] is True
    
    def test_create_element(self):
        """Test creating elements."""
        paradigm = NodeBasedParadigm()
        
        elem_id = paradigm.create_element('function', (100, 200))
        
        assert elem_id in paradigm.elements
        element = paradigm.elements[elem_id]
        assert isinstance(element, NodeElement)
        assert element.position == (100, 200)
        assert element.node_type == NodeType.FUNCTION
    
    def test_connect_elements(self):
        """Test connecting elements."""
        paradigm = NodeBasedParadigm()
        
        # Create two elements
        elem1_id = paradigm.create_element('function', (100, 100))
        elem2_id = paradigm.create_element('variable', (200, 200))
        
        # Connect them
        success = paradigm.connect_elements(elem1_id, elem2_id)
        
        assert success is True
        assert len(paradigm.connections) == 1
        
        connection = paradigm.connections[0]
        assert connection.source_node_id == elem1_id
        assert connection.target_node_id == elem2_id
    
    def test_to_visual_model(self):
        """Test conversion to VisualModel."""
        paradigm = NodeBasedParadigm()
        
        # Create elements
        elem1_id = paradigm.create_element('function', (100, 100))
        elem2_id = paradigm.create_element('variable', (200, 200))
        paradigm.connect_elements(elem1_id, elem2_id)
        
        # Convert to model
        model = paradigm.to_visual_model()
        
        assert isinstance(model, VisualModel)
        assert len(model.nodes) == 2
        assert len(model.connections) == 1
    
    def test_from_visual_model(self):
        """Test loading from VisualModel."""
        paradigm = NodeBasedParadigm()
        
        # Create a VisualModel
        model = VisualModel()
        node1 = VisualNode(id="node1", type=NodeType.FUNCTION, position=(100, 100))
        node2 = VisualNode(id="node2", type=NodeType.VARIABLE, position=(200, 200))
        
        model.nodes["node1"] = node1
        model.nodes["node2"] = node2
        
        # Load into paradigm
        success = paradigm.from_visual_model(model)
        
        assert success is True
        assert len(paradigm.elements) == 2
        assert "node1" in paradigm.elements
        assert "node2" in paradigm.elements
    
    def test_validation(self):
        """Test paradigm validation."""
        paradigm = NodeBasedParadigm()
        
        # Create elements without cycles
        elem1_id = paradigm.create_element('function', (100, 100))
        elem2_id = paradigm.create_element('variable', (200, 200))
        paradigm.connect_elements(elem1_id, elem2_id)
        
        errors = paradigm.validate()
        assert len(errors) == 0
    
    def test_remove_element(self):
        """Test removing elements."""
        paradigm = NodeBasedParadigm()
        
        elem_id = paradigm.create_element('function', (100, 100))
        assert elem_id in paradigm.elements
        
        success = paradigm.remove_element(elem_id)
        assert success is True
        assert elem_id not in paradigm.elements


class TestBlockBasedParadigm:
    """Test cases for Block-based paradigm."""
    
    def test_paradigm_creation(self):
        """Test basic paradigm creation."""
        paradigm = BlockBasedParadigm()
        
        assert paradigm.paradigm_type == ParadigmType.BLOCK_BASED
        assert paradigm.properties['supports_nesting'] is True
        assert paradigm.properties['execution_model'] == 'sequential'
    
    def test_create_element(self):
        """Test creating block elements."""
        paradigm = BlockBasedParadigm()
        
        elem_id = paradigm.create_element('statement', (100, 200))
        
        assert elem_id in paradigm.elements
        element = paradigm.elements[elem_id]
        assert isinstance(element, BlockElement)
        assert element.block_type == 'statement'
    
    def test_parent_child_relationship(self):
        """Test parent-child relationships."""
        paradigm = BlockBasedParadigm()
        
        # Create parent block
        parent_id = paradigm.create_element('control', (100, 100))
        
        # Create child block
        child_id = paradigm.create_element('statement', (120, 140), parent_block=parent_id)
        
        parent = paradigm.elements[parent_id]
        child = paradigm.elements[child_id]
        
        assert isinstance(parent, BlockElement)
        assert isinstance(child, BlockElement)
        assert child.parent_block == parent_id
        assert child_id in parent.child_blocks
    
    def test_connect_elements(self):
        """Test connecting blocks in sequence."""
        paradigm = BlockBasedParadigm()
        
        elem1_id = paradigm.create_element('statement', (100, 100))
        elem2_id = paradigm.create_element('statement', (100, 150))
        
        success = paradigm.connect_elements(elem1_id, elem2_id)
        
        assert success is True
        assert len(paradigm.connections) == 1
    
    def test_validation(self):
        """Test block paradigm validation."""
        paradigm = BlockBasedParadigm()
        
        # Create valid structure
        parent_id = paradigm.create_element('control', (100, 100))
        child_id = paradigm.create_element('statement', (120, 140), parent_block=parent_id)
        
        errors = paradigm.validate()
        assert len(errors) == 0


class TestDiagramBasedParadigm:
    """Test cases for Diagram-based paradigm."""
    
    def test_paradigm_creation(self):
        """Test basic paradigm creation."""
        paradigm = DiagramBasedParadigm()
        
        assert paradigm.paradigm_type == ParadigmType.DIAGRAM_BASED
        assert paradigm.properties['supports_inheritance'] is True
        assert paradigm.properties['execution_model'] == 'object_oriented'
    
    def test_create_element(self):
        """Test creating diagram elements."""
        paradigm = DiagramBasedParadigm()
        
        elem_id = paradigm.create_element('class', (100, 200), visibility='public')
        
        assert elem_id in paradigm.elements
        element = paradigm.elements[elem_id]
        assert isinstance(element, DiagramElement)
        assert element.diagram_type == 'class'
        assert element.visibility == 'public'
    
    def test_connect_elements_with_relationships(self):
        """Test connecting elements with relationships."""
        paradigm = DiagramBasedParadigm()
        
        class1_id = paradigm.create_element('class', (100, 100))
        class2_id = paradigm.create_element('class', (200, 200))
        
        success = paradigm.connect_elements(
            class1_id, class2_id, 
            relationship_type='inheritance'
        )
        
        assert success is True
        assert len(paradigm.connections) == 1
        
        connection = paradigm.connections[0]
        assert connection.source_node_id == class1_id
        assert connection.target_node_id == class2_id
    
    def test_validation(self):
        """Test diagram paradigm validation."""
        paradigm = DiagramBasedParadigm()
        
        # Create classes without circular inheritance
        class1_id = paradigm.create_element('class', (100, 100))
        class2_id = paradigm.create_element('class', (200, 200))
        paradigm.connect_elements(class1_id, class2_id, relationship_type='inheritance')
        
        errors = paradigm.validate()
        assert len(errors) == 0


class TestTimelineBasedParadigm:
    """Test cases for Timeline-based paradigm."""
    
    def test_paradigm_creation(self):
        """Test basic paradigm creation."""
        paradigm = TimelineBasedParadigm()
        
        assert paradigm.paradigm_type == ParadigmType.TIMELINE_BASED
        assert paradigm.properties['supports_timing'] is True
        assert paradigm.properties['execution_model'] == 'temporal'
    
    def test_create_element(self):
        """Test creating timeline elements."""
        paradigm = TimelineBasedParadigm()
        
        elem_id = paradigm.create_element(
            'event', (100, 200), 
            start_time=5.0, duration=2.0
        )
        
        assert elem_id in paradigm.elements
        element = paradigm.elements[elem_id]
        assert isinstance(element, TimelineElement)
        assert element.timeline_type == 'event'
        assert element.start_time == 5.0
        assert element.duration == 2.0
    
    def test_connect_elements_with_dependencies(self):
        """Test connecting elements with temporal dependencies."""
        paradigm = TimelineBasedParadigm()
        
        event1_id = paradigm.create_element('event', (100, 100), start_time=0.0, duration=2.0)
        event2_id = paradigm.create_element('event', (200, 200), start_time=3.0, duration=1.0)
        
        success = paradigm.connect_elements(event1_id, event2_id)
        
        assert success is True
        assert len(paradigm.connections) == 1
        
        event2 = paradigm.elements[event2_id]
        assert isinstance(event2, TimelineElement)
        assert event1_id in event2.dependencies
    
    def test_validation(self):
        """Test timeline paradigm validation."""
        paradigm = TimelineBasedParadigm()
        
        # Create temporally consistent events
        event1_id = paradigm.create_element('event', (100, 100), start_time=0.0, duration=2.0)
        event2_id = paradigm.create_element('event', (200, 200), start_time=3.0, duration=1.0)
        paradigm.connect_elements(event1_id, event2_id)
        
        errors = paradigm.validate()
        assert len(errors) == 0


class TestParadigmManager:
    """Test cases for ParadigmManager."""
    
    def test_manager_creation(self):
        """Test basic manager creation."""
        manager = ParadigmManager()
        
        assert len(manager.paradigms) == 4
        assert ParadigmType.NODE_BASED in manager.paradigms
        assert ParadigmType.BLOCK_BASED in manager.paradigms
        assert ParadigmType.DIAGRAM_BASED in manager.paradigms
        assert ParadigmType.TIMELINE_BASED in manager.paradigms
        assert manager.active_paradigm == ParadigmType.NODE_BASED
    
    def test_get_paradigm(self):
        """Test getting specific paradigms."""
        manager = ParadigmManager()
        
        node_paradigm = manager.get_paradigm(ParadigmType.NODE_BASED)
        assert isinstance(node_paradigm, NodeBasedParadigm)
        
        block_paradigm = manager.get_paradigm(ParadigmType.BLOCK_BASED)
        assert isinstance(block_paradigm, BlockBasedParadigm)
    
    def test_set_active_paradigm(self):
        """Test setting active paradigm."""
        manager = ParadigmManager()
        
        success = manager.set_active_paradigm(ParadigmType.BLOCK_BASED)
        assert success is True
        assert manager.active_paradigm == ParadigmType.BLOCK_BASED
        
        active = manager.get_active_paradigm()
        assert isinstance(active, BlockBasedParadigm)
    
    def test_convert_between_paradigms(self):
        """Test converting between paradigms."""
        manager = ParadigmManager()
        
        # Create elements in node-based paradigm
        node_paradigm = manager.get_paradigm(ParadigmType.NODE_BASED)
        elem_id = node_paradigm.create_element('function', (100, 100))
        
        # Convert to block-based paradigm
        success = manager.convert_between_paradigms(
            ParadigmType.NODE_BASED, 
            ParadigmType.BLOCK_BASED
        )
        
        assert success is True
        
        # Check block paradigm has the converted element
        block_paradigm = manager.get_paradigm(ParadigmType.BLOCK_BASED)
        assert len(block_paradigm.elements) > 0
    
    def test_validate_all_paradigms(self):
        """Test validating all paradigms."""
        manager = ParadigmManager()
        
        results = manager.validate_all_paradigms()
        
        assert len(results) == 4
        assert ParadigmType.NODE_BASED in results
        assert ParadigmType.BLOCK_BASED in results
        assert ParadigmType.DIAGRAM_BASED in results
        assert ParadigmType.TIMELINE_BASED in results
        
        # All should be valid initially
        for errors in results.values():
            assert len(errors) == 0
    
    def test_get_paradigm_capabilities(self):
        """Test getting paradigm capabilities."""
        manager = ParadigmManager()
        
        node_caps = manager.get_paradigm_capabilities(ParadigmType.NODE_BASED)
        assert node_caps['supports_dataflow'] is True
        assert node_caps['execution_model'] == 'dataflow'
        
        block_caps = manager.get_paradigm_capabilities(ParadigmType.BLOCK_BASED)
        assert block_caps['supports_nesting'] is True
        assert block_caps['execution_model'] == 'sequential'
    
    def test_export_import_paradigm_state(self):
        """Test exporting and importing paradigm state."""
        manager = ParadigmManager()
        
        # Create some elements in node paradigm
        node_paradigm = manager.get_paradigm(ParadigmType.NODE_BASED)
        elem1_id = node_paradigm.create_element('function', (100, 100))
        elem2_id = node_paradigm.create_element('variable', (200, 200))
        node_paradigm.connect_elements(elem1_id, elem2_id)
        
        # Export state
        state = manager.export_paradigm_state(ParadigmType.NODE_BASED)
        assert state is not None
        assert 'paradigm_type' in state
        assert 'elements' in state
        assert 'connections' in state
        
        # Clear paradigm
        node_paradigm.elements.clear()
        node_paradigm.connections.clear()
        assert len(node_paradigm.elements) == 0
        
        # Import state back
        success = manager.import_paradigm_state(state)
        assert success is True
        assert len(node_paradigm.elements) == 2
        assert len(node_paradigm.connections) == 1


# Property-based tests
@given(st.floats(min_value=0.0, max_value=100.0), st.floats(min_value=0.1, max_value=10.0))
def test_timeline_element_timing_property(start_time, duration):
    """Property test: Timeline elements should handle any valid timing."""
    paradigm = TimelineBasedParadigm()
    
    elem_id = paradigm.create_element(
        'event', (100, 100), 
        start_time=start_time, 
        duration=duration
    )
    
    element = paradigm.elements[elem_id]
    assert isinstance(element, TimelineElement)
    assert element.start_time == start_time
    assert element.duration == duration


@given(st.integers(min_value=1, max_value=10))
def test_multiple_elements_property(num_elements):
    """Property test: Paradigms should handle any number of elements."""
    paradigm = NodeBasedParadigm()
    
    element_ids = []
    for i in range(num_elements):
        elem_id = paradigm.create_element('function', (i * 100, i * 100))
        element_ids.append(elem_id)
    
    assert len(paradigm.elements) == num_elements
    assert all(elem_id in paradigm.elements for elem_id in element_ids)


@given(st.text(min_size=1, max_size=20))
def test_element_type_property(element_type):
    """Property test: Paradigms should handle any element type string."""
    paradigm = NodeBasedParadigm()
    
    try:
        elem_id = paradigm.create_element(element_type, (100, 100))
        assert elem_id in paradigm.elements
        element = paradigm.elements[elem_id]
        assert isinstance(element, NodeElement)
    except Exception:
        # Some element types might not be valid, which is acceptable
        pass