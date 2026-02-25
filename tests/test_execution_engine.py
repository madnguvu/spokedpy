"""
Tests for the ExecutionEngine with property-based testing.
"""

import pytest
import keyword
from hypothesis import given, strategies as st, assume
from visual_editor_core.execution_engine import (
    ExecutionEngine, ExecutionResult, ExecutionState, VisualDebugger
)
from visual_editor_core.models import (
    VisualModel, VisualNode, NodeType, InputPort, OutputPort
)


class TestExecutionEngine:
    """Test cases for ExecutionEngine class."""
    
    def test_engine_initialization(self):
        """Test basic engine initialization."""
        engine = ExecutionEngine()
        assert engine.debugger is not None
        assert engine.executor is not None
        assert engine.state_tracker is not None
        assert engine.is_executing is False
        assert engine.should_stop is False
        assert engine.hot_reload_enabled is False
    
    def test_execute_empty_model(self):
        """Test executing an empty visual model."""
        engine = ExecutionEngine()
        model = VisualModel()
        
        result = engine.execute_model(model)
        assert isinstance(result, ExecutionResult)
        assert result.success is True
    
    def test_execute_simple_variable_model(self):
        """Test executing a model with a single variable."""
        engine = ExecutionEngine()
        model = VisualModel()
        
        # Add a variable node
        var_node = VisualNode(
            type=NodeType.VARIABLE,
            parameters={'variable_name': 'x', 'default_value': 42}
        )
        model.add_node(var_node)
        
        result = engine.execute_model(model)
        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert 'x' in result.variables
        assert result.variables['x'] == 42
    
    def test_debug_mode_toggle(self):
        """Test enabling and disabling debug mode."""
        engine = ExecutionEngine()
        
        assert engine.debug_mode is False
        
        engine.enable_debug_mode()
        assert engine.debug_mode is True
        
        engine.disable_debug_mode()
        assert engine.debug_mode is False
    
    def test_breakpoint_management(self):
        """Test setting and clearing breakpoints."""
        engine = ExecutionEngine()
        
        # Set breakpoint
        engine.set_breakpoint("node1")
        assert engine.debugger.is_breakpoint_set("node1") is True
        
        # Clear breakpoint
        engine.clear_breakpoint("node1")
        assert engine.debugger.is_breakpoint_set("node1") is False
    
    def test_variable_inspection(self):
        """Test variable inspection functionality."""
        engine = ExecutionEngine()
        
        # Set a variable
        engine.set_variable_value("test_var", 123)
        
        # Inspect the variable
        var_info = engine.inspect_variable("test_var")
        assert var_info['name'] == "test_var"
        assert var_info['value'] == 123
        assert var_info['type'] == 'int'
        assert len(var_info['modification_history']) > 0
    
    def test_execution_state_reset(self):
        """Test resetting execution state."""
        engine = ExecutionEngine()
        
        # Set some state
        engine.set_variable_value("test", 42)
        engine.set_breakpoint("node1")
        
        # Reset
        engine.reset_execution_state()
        
        # Check state is reset
        assert engine.get_variable_value("test") is None
        assert engine.is_executing is False


class TestVisualDebugger:
    """Test cases for VisualDebugger class."""
    
    def test_debugger_initialization(self):
        """Test debugger initialization."""
        debugger = VisualDebugger()
        assert len(debugger.breakpoints) == 0
        assert debugger.step_mode is False
        assert debugger.current_node is None
    
    def test_step_mode_control(self):
        """Test step mode control."""
        debugger = VisualDebugger()
        
        debugger.enable_step_mode()
        assert debugger.step_mode is True
        
        debugger.disable_step_mode()
        assert debugger.step_mode is False
    
    def test_watch_list_management(self):
        """Test variable watch list management."""
        debugger = VisualDebugger()
        
        # Add to watch list
        debugger.add_to_watch_list("var1")
        assert "var1" in debugger.variable_watch_list
        
        # Remove from watch list
        debugger.remove_from_watch_list("var1")
        assert "var1" not in debugger.variable_watch_list
    
    def test_call_stack_management(self):
        """Test call stack management."""
        debugger = VisualDebugger()
        
        # Push to call stack
        debugger.push_call_stack("func1", "node1", {"x": 1})
        assert len(debugger.call_stack) == 1
        
        # Pop from call stack
        call_info = debugger.pop_call_stack()
        assert call_info is not None
        assert call_info['function_name'] == "func1"
        assert len(debugger.call_stack) == 0


# Property-based tests
import keyword

@given(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=65, max_codepoint=122)).filter(
    lambda x: x.isidentifier() and not x.startswith('__') and not keyword.iskeyword(x)
))
def test_execution_reliability_property(variable_name):
    """
    **Feature: visual-editor-core, Property 11: Execution engine reliability**
    **Validates: Requirements 5.1**
    
    For any valid variable name, the execution engine should reliably execute
    a simple variable assignment and return the correct result.
    """
    engine = ExecutionEngine()
    model = VisualModel()
    
    # Create a variable node with the generated name
    var_node = VisualNode(
        type=NodeType.VARIABLE,
        parameters={'variable_name': variable_name, 'default_value': 42}
    )
    model.add_node(var_node)
    
    # Execute the model
    result = engine.execute_model(model)
    
    # Property: Execution should always succeed for valid models
    assert result.success is True
    assert variable_name in result.variables
    assert result.variables[variable_name] == 42


@given(st.integers(min_value=-1000, max_value=1000))
def test_variable_modification_tracking_property(value):
    """
    **Feature: visual-editor-core, Property 12: Debug visualization accuracy**
    **Validates: Requirements 5.2, 5.3, 5.4**
    
    For any integer value, variable modifications should be accurately tracked
    and retrievable through the debugging interface.
    """
    engine = ExecutionEngine()
    variable_name = "test_var"
    
    # Set variable value
    engine.set_variable_value(variable_name, value)
    
    # Get variable info
    var_info = engine.inspect_variable(variable_name)
    
    # Property: Variable tracking should be accurate
    assert var_info['value'] == value
    assert var_info['type'] == 'int'
    assert len(var_info['modification_history']) > 0
    
    # Property: Modification history should contain the change
    history = var_info['modification_history']
    assert history[-1]['new_value'] == value


@given(st.lists(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'))), 
               min_size=1, max_size=5, unique=True))
def test_breakpoint_functionality_property(node_ids):
    """
    **Feature: visual-editor-core, Property 13: Breakpoint functionality**
    **Validates: Requirements 5.5, 5.6**
    
    For any list of unique node IDs, breakpoint setting and clearing should
    work consistently and maintain correct state.
    """
    engine = ExecutionEngine()
    
    # Set breakpoints on all nodes
    for node_id in node_ids:
        engine.set_breakpoint(node_id)
    
    # Property: All breakpoints should be set
    for node_id in node_ids:
        assert engine.debugger.is_breakpoint_set(node_id) is True
    
    # Clear half the breakpoints
    nodes_to_clear = node_ids[:len(node_ids)//2]
    for node_id in nodes_to_clear:
        engine.clear_breakpoint(node_id)
    
    # Property: Cleared breakpoints should not be set, others should remain
    for node_id in nodes_to_clear:
        assert engine.debugger.is_breakpoint_set(node_id) is False
    
    for node_id in node_ids[len(node_ids)//2:]:
        assert engine.debugger.is_breakpoint_set(node_id) is True


@given(st.lists(st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))), 
               min_size=0, max_size=10, unique=True))
def test_watch_list_consistency_property(variable_names):
    """
    **Feature: visual-editor-core, Property 12: Debug visualization accuracy**
    **Validates: Requirements 5.2, 5.3, 5.4**
    
    For any list of variable names, the watch list should maintain consistency
    when adding and removing variables.
    """
    # Filter to valid Python identifiers
    valid_names = [name for name in variable_names 
                   if name.isidentifier() and not name.startswith('__')]
    
    engine = ExecutionEngine()
    
    # Add all variables to watch list
    for var_name in valid_names:
        engine.add_variable_watch(var_name)
    
    # Property: All variables should be in watch list
    for var_name in valid_names:
        assert var_name in engine.debugger.variable_watch_list
    
    # Remove half the variables
    vars_to_remove = valid_names[:len(valid_names)//2]
    for var_name in vars_to_remove:
        engine.remove_variable_watch(var_name)
    
    # Property: Removed variables should not be in watch list
    for var_name in vars_to_remove:
        assert var_name not in engine.debugger.variable_watch_list
    
    # Property: Remaining variables should still be in watch list
    for var_name in valid_names[len(valid_names)//2:]:
        assert var_name in engine.debugger.variable_watch_list


@given(st.integers(min_value=1, max_value=5))
def test_execution_state_consistency_property(num_variables):
    """
    **Feature: visual-editor-core, Property 11: Execution engine reliability**
    **Validates: Requirements 5.1**
    
    For any number of variables, the execution state should remain consistent
    throughout variable modifications and state tracking.
    """
    engine = ExecutionEngine()
    
    # Create variables
    variables = {}
    for i in range(num_variables):
        var_name = f"var_{i}"
        var_value = i * 10
        variables[var_name] = var_value
        engine.set_variable_value(var_name, var_value)
    
    # Property: All variables should be retrievable
    for var_name, expected_value in variables.items():
        actual_value = engine.get_variable_value(var_name)
        assert actual_value == expected_value
    
    # Property: Execution state should contain all variables
    current_vars = engine.get_variable_values()
    for var_name, expected_value in variables.items():
        assert var_name in current_vars
        assert current_vars[var_name] == expected_value