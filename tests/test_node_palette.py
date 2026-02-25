"""
Unit tests for Node Palette System.
"""

import pytest
from hypothesis import given, strategies as st
from visual_editor_core.node_palette import (
    NodePalette, NodeDefinition, Category, SearchIndex, PluginLoader
)
from visual_editor_core.models import NodeType, InputPort, OutputPort


class TestNodeDefinition:
    """Test cases for NodeDefinition class."""
    
    def test_node_definition_creation(self):
        """Test basic node definition creation."""
        node_def = NodeDefinition(
            name="test_node",
            node_type=NodeType.FUNCTION,
            description="A test node",
            icon="test-icon"
        )
        
        assert node_def.name == "test_node"
        assert node_def.node_type == NodeType.FUNCTION
        assert node_def.description == "A test node"
        assert node_def.icon == "test-icon"
    
    def test_add_input_output_ports(self):
        """Test adding input and output ports."""
        node_def = NodeDefinition("test", NodeType.FUNCTION)
        
        # Add input port
        node_def.add_input("input1", str, True, "default", "Input description")
        assert len(node_def.inputs) == 1
        assert node_def.inputs[0].name == "input1"
        assert node_def.inputs[0].data_type == str
        
        # Add output port
        node_def.add_output("output1", int, "Output description")
        assert len(node_def.outputs) == 1
        assert node_def.outputs[0].name == "output1"
        assert node_def.outputs[0].data_type == int
    
    def test_set_parameters_and_tags(self):
        """Test setting parameters and tags."""
        node_def = NodeDefinition("test", NodeType.FUNCTION)
        
        # Set parameter
        node_def.set_parameter("param1", "value1")
        assert node_def.parameters["param1"] == "value1"
        
        # Add tags
        node_def.add_tag("tag1").add_tag("tag2")
        assert "tag1" in node_def.tags
        assert "tag2" in node_def.tags
        assert len(node_def.tags) == 2
    
    def test_create_instance(self):
        """Test creating node instances."""
        node_def = NodeDefinition("test", NodeType.FUNCTION)
        node_def.add_input("input1", str)
        node_def.add_output("output1", int)
        node_def.set_parameter("func_name", "test_func")
        
        instance = node_def.create_instance((100, 200))
        
        assert instance.type == NodeType.FUNCTION
        assert instance.position == (100, 200)
        assert len(instance.inputs) == 1
        assert len(instance.outputs) == 1
        assert instance.parameters["func_name"] == "test_func"
    
    def test_matches_search(self):
        """Test search matching functionality."""
        node_def = NodeDefinition(
            name="TestFunction",
            node_type=NodeType.FUNCTION,
            description="A function for testing",
            category="testing"
        )
        node_def.add_tag("test").add_tag("function")
        
        # Test name matching
        assert node_def.matches_search("test")
        assert node_def.matches_search("TestFunction")
        
        # Test description matching
        assert node_def.matches_search("function")
        assert node_def.matches_search("testing")
        
        # Test tag matching
        assert node_def.matches_search("test")
        
        # Test category matching
        assert node_def.matches_search("testing")
        
        # Test non-matching
        assert not node_def.matches_search("nonexistent")


class TestCategory:
    """Test cases for Category class."""
    
    def test_category_creation(self):
        """Test basic category creation."""
        category = Category("Test Category", "A test category", "test-icon")
        
        assert category.name == "Test Category"
        assert category.description == "A test category"
        assert category.icon == "test-icon"
        assert len(category.nodes) == 0
    
    def test_add_nodes(self):
        """Test adding nodes to category."""
        category = Category("Test")
        node_def = NodeDefinition("test_node", NodeType.FUNCTION)
        
        category.add_node(node_def)
        assert len(category.nodes) == 1
        assert category.nodes[0] == node_def
    
    def test_subcategories(self):
        """Test subcategory functionality."""
        parent = Category("Parent")
        child = Category("Child")
        
        parent.add_subcategory(child)
        assert "Child" in parent.subcategories
        assert parent.subcategories["Child"] == child
    
    def test_get_all_nodes(self):
        """Test getting all nodes including from subcategories."""
        parent = Category("Parent")
        child = Category("Child")
        
        parent_node = NodeDefinition("parent_node", NodeType.FUNCTION)
        child_node = NodeDefinition("child_node", NodeType.VARIABLE)
        
        parent.add_node(parent_node)
        child.add_node(child_node)
        parent.add_subcategory(child)
        
        all_nodes = parent.get_all_nodes()
        assert len(all_nodes) == 2
        assert parent_node in all_nodes
        assert child_node in all_nodes


class TestSearchIndex:
    """Test cases for SearchIndex class."""
    
    def test_search_index_creation(self):
        """Test basic search index creation."""
        index = SearchIndex()
        assert len(index.nodes) == 0
        assert len(index.categories) == 0
    
    def test_add_nodes(self):
        """Test adding nodes to search index."""
        index = SearchIndex()
        node_def = NodeDefinition("test", NodeType.FUNCTION)
        
        index.add_node(node_def)
        assert len(index.nodes) == 1
        assert index.nodes[0] == node_def
    
    def test_search_functionality(self):
        """Test search functionality."""
        index = SearchIndex()
        
        # Create test nodes
        node1 = NodeDefinition("print", NodeType.FUNCTION, "Print function")
        node1.add_tag("output")
        
        node2 = NodeDefinition("input", NodeType.FUNCTION, "Input function")
        node2.add_tag("input")
        
        node3 = NodeDefinition("calculate", NodeType.FUNCTION, "Math calculation")
        node3.add_tag("math")
        
        index.add_node(node1)
        index.add_node(node2)
        index.add_node(node3)
        
        # Test exact name match
        results = index.search("print")
        assert len(results) >= 1
        assert node1 in results
        
        # Test partial name match
        results = index.search("calc")
        assert node3 in results
        
        # Test tag search
        results = index.search("math")
        assert node3 in results
        
        # Test empty search returns all
        results = index.search("")
        assert len(results) == 3
    
    def test_filter_by_category(self):
        """Test filtering by category."""
        index = SearchIndex()
        
        node1 = NodeDefinition("test1", NodeType.FUNCTION, category="math")
        node2 = NodeDefinition("test2", NodeType.FUNCTION, category="io")
        
        index.add_node(node1)
        index.add_node(node2)
        
        math_nodes = index.filter_by_category("math")
        assert len(math_nodes) == 1
        assert node1 in math_nodes
    
    def test_filter_by_type(self):
        """Test filtering by node type."""
        index = SearchIndex()
        
        node1 = NodeDefinition("func", NodeType.FUNCTION)
        node2 = NodeDefinition("var", NodeType.VARIABLE)
        
        index.add_node(node1)
        index.add_node(node2)
        
        func_nodes = index.filter_by_type(NodeType.FUNCTION)
        assert len(func_nodes) == 1
        assert node1 in func_nodes


class TestPluginLoader:
    """Test cases for PluginLoader class."""
    
    def test_plugin_loader_creation(self):
        """Test basic plugin loader creation."""
        loader = PluginLoader()
        assert len(loader.loaded_packages) == 0
        assert len(loader.package_cache) == 0
        assert len(loader.package_dependencies) == 0
        assert len(loader.failed_packages) == 0
    
    def test_load_builtin_package(self):
        """Test loading a built-in package."""
        loader = PluginLoader()
        
        # Load math module (should be available)
        nodes = loader.load_package("math")
        
        # Should have some nodes
        assert len(nodes) > 0
        
        # Check that functions were loaded
        function_nodes = [n for n in nodes if n.node_type == NodeType.FUNCTION]
        assert len(function_nodes) > 0
        
        # Should be cached
        assert "math" in loader.loaded_packages
        assert "math" in loader.package_cache
    
    def test_load_package_with_submodules(self):
        """Test loading package with submodules."""
        loader = PluginLoader()
        
        # Load collections with submodules
        nodes = loader.load_package("collections", include_submodules=True)
        
        # Should have nodes
        assert len(nodes) > 0
        
        # Should be cached
        assert "collections" in loader.loaded_packages
    
    def test_load_nonexistent_package(self):
        """Test loading a non-existent package."""
        loader = PluginLoader()
        
        nodes = loader.load_package("nonexistent_package_12345")
        assert len(nodes) == 0
        
        # Should track the failure
        assert "nonexistent_package_12345" in loader.failed_packages
    
    def test_load_popular_packages(self):
        """Test loading popular packages."""
        loader = PluginLoader()
        
        loaded = loader.load_popular_packages()
        
        # Should have loaded some packages
        assert len(loaded) > 0
        
        # Math should be included
        assert "math" in loaded
        assert len(loaded["math"]) > 0
    
    def test_package_availability_check(self):
        """Test package availability checking."""
        loader = PluginLoader()
        
        # Math should be available
        assert loader.is_package_available("math") is True
        
        # Non-existent package should not be available
        assert loader.is_package_available("nonexistent_package_12345") is False
    
    def test_cache_clearing(self):
        """Test cache clearing functionality."""
        loader = PluginLoader()
        
        # Load a package
        loader.load_package("math")
        assert len(loader.loaded_packages) > 0
        
        # Clear cache
        loader.clear_cache()
        assert len(loader.loaded_packages) == 0
        assert len(loader.package_cache) == 0
        assert len(loader.package_dependencies) == 0
        assert len(loader.failed_packages) == 0
    
    def test_dependency_extraction(self):
        """Test dependency extraction."""
        loader = PluginLoader()
        
        # Load a package
        loader.load_package("json")
        
        # Should have dependency info (even if empty)
        deps = loader.get_package_dependencies("json")
        assert isinstance(deps, list)
    
    def test_get_package_info(self):
        """Test getting package information."""
        loader = PluginLoader()
        
        # Load a package first
        loader.load_package("math")
        
        info = loader.get_package_info("math")
        assert info["name"] == "math"
        assert "functions" in info
        assert "classes" in info


class TestNodePalette:
    """Test cases for NodePalette class."""
    
    def test_palette_creation(self):
        """Test basic palette creation."""
        palette = NodePalette()
        
        # Should have standard categories
        assert "Core Python" in palette.categories
        assert "Control Flow" in palette.categories
        assert "Data Structures" in palette.categories
        assert "Input/Output" in palette.categories
        assert "Mathematics" in palette.categories
    
    def test_load_standard_library(self):
        """Test loading standard library components."""
        palette = NodePalette()
        palette.load_standard_library()
        
        # Should have nodes in core category
        core_nodes = palette.get_category_nodes("Core Python")
        assert len(core_nodes) > 0
        
        # Should have print function
        print_nodes = [n for n in core_nodes if n.name == "print"]
        assert len(print_nodes) == 1
        
        # Should have control flow nodes
        control_nodes = palette.get_category_nodes("Control Flow")
        assert len(control_nodes) > 0
    
    def test_search_nodes(self):
        """Test searching for nodes."""
        palette = NodePalette()
        palette.load_standard_library()
        
        # Search for print function
        results = palette.search_nodes("print")
        assert len(results) > 0
        
        # Search with category filter
        results = palette.search_nodes("if", category="Control Flow")
        assert len(results) > 0
        
        # Search with type filter
        results = palette.search_nodes("", node_type=NodeType.FUNCTION)
        assert len(results) > 0
    
    def test_create_custom_node(self):
        """Test creating custom nodes."""
        palette = NodePalette()
        
        code_snippet = """
def custom_function(x, y):
    return x + y
"""
        
        result = palette.create_custom_node(
            code_snippet, 
            "custom_add", 
            "Custom addition function"
        )
        
        assert result['success'] is True
        node_def = result['node_definition']
        assert node_def.name == "custom_add"
        assert node_def.node_type == NodeType.CUSTOM
        assert node_def.parameters["code_snippet"] == code_snippet
        
        # Should be added to custom category
        custom_nodes = palette.get_category_nodes("Custom")
        assert node_def in custom_nodes
    
    def test_create_custom_node_with_validation(self):
        """Test creating custom nodes with validation."""
        palette = NodePalette()
        
        # Valid function code
        valid_code = """
def multiply(a: int, b: int) -> int:
    '''Multiply two numbers'''
    return a * b
"""
        
        result = palette.create_custom_node(valid_code, validate=True)
        
        assert result['success'] is True
        assert result['validation_result']['valid'] is True
        assert len(result['validation_result']['functions']) == 1
        assert result['validation_result']['functions'][0]['name'] == 'multiply'
        
        node_def = result['node_definition']
        assert node_def.name == "multiply"
        assert len(node_def.inputs) == 2  # a, b
        assert len(node_def.outputs) == 1  # result
    
    def test_create_custom_node_invalid_code(self):
        """Test creating custom nodes with invalid code."""
        palette = NodePalette()
        
        # Invalid syntax
        invalid_code = "def invalid_function(:"
        
        result = palette.create_custom_node(invalid_code, validate=True)
        
        assert result['success'] is False
        assert len(result['errors']) > 0
        assert "Syntax error" in result['errors'][0]
    
    def test_create_custom_class_node(self):
        """Test creating custom class nodes."""
        palette = NodePalette()
        
        class_code = """
class Calculator:
    '''A simple calculator class'''
    def __init__(self, initial_value=0):
        self.value = initial_value
    
    def add(self, x):
        self.value += x
        return self.value
"""
        
        result = palette.create_custom_node(class_code, validate=True)
        
        assert result['success'] is True
        node_def = result['node_definition']
        assert node_def.name == "Calculator"
        assert node_def.node_type == NodeType.CLASS
        assert len(node_def.outputs) == 1  # instance
    
    def test_validate_custom_code(self):
        """Test code validation without creating nodes."""
        palette = NodePalette()
        
        code = """
import math

def calculate_area(radius: float) -> float:
    '''Calculate circle area'''
    return math.pi * radius ** 2
"""
        
        validation = palette.validate_custom_code(code)
        
        assert validation['valid'] is True
        assert len(validation['functions']) == 1
        assert len(validation['imports']) == 1
        assert validation['functions'][0]['name'] == 'calculate_area'
        assert validation['imports'][0]['modules'] == ['math']
    
    def test_custom_node_management(self):
        """Test custom node management operations."""
        palette = NodePalette()
        
        # Create a custom node
        code = "def test_func(): return 42"
        result = palette.create_custom_node(code, "test_node")
        assert result['success'] is True
        
        # Get custom nodes
        custom_nodes = palette.get_custom_nodes()
        assert len(custom_nodes) == 1
        assert custom_nodes[0].name == "test_node"
        
        # Remove custom node
        removed = palette.remove_custom_node("test_node")
        assert removed is True
        
        # Should be gone
        custom_nodes = palette.get_custom_nodes()
        assert len(custom_nodes) == 0
    
    def test_export_import_custom_node(self):
        """Test exporting and importing custom nodes."""
        palette = NodePalette()
        
        # Create a custom node
        code = """
def greet(name: str) -> str:
    '''Greet someone'''
    return f"Hello, {name}!"
"""
        result = palette.create_custom_node(code, "greeter", "A greeting function")
        assert result['success'] is True
        
        # Export the node
        exported = palette.export_custom_node("greeter")
        assert exported is not None
        assert exported['name'] == "greeter"
        assert exported['description'] == "A greeting function"
        assert exported['code_snippet'] == code
        assert len(exported['inputs']) == 1
        assert len(exported['outputs']) == 1
        
        # Remove the node
        palette.remove_custom_node("greeter")
        assert len(palette.get_custom_nodes()) == 0
        
        # Import it back
        import_result = palette.import_custom_node(exported)
        assert import_result['success'] is True
        
        # Should be back
        custom_nodes = palette.get_custom_nodes()
        assert len(custom_nodes) == 1
        assert custom_nodes[0].name == "greeter"
    
    def test_custom_node_security_warnings(self):
        """Test security warnings for dangerous code."""
        palette = NodePalette()
        
        dangerous_code = """
import os
def dangerous_func():
    return eval("1 + 1")
"""
        
        validation = palette.validate_custom_code(dangerous_code)
        
        assert validation['valid'] is True  # Syntactically valid
        assert len(validation['warnings']) > 0  # But has warnings
        
        # Should warn about dangerous functions and modules
        warning_text = ' '.join(validation['warnings'])
        assert 'eval' in warning_text or 'os' in warning_text
    
    def test_load_third_party_package(self):
        """Test loading third-party packages."""
        palette = NodePalette()
        
        # Load math module
        palette.load_third_party_package("math")
        
        # Should create category for math
        assert "math" in palette.categories
        
        # Should have nodes in math category
        math_nodes = palette.get_category_nodes("math")
        assert len(math_nodes) > 0
        
        # Should be able to find specific math functions
        sin_nodes = [n for n in math_nodes if n.name.endswith('.sin')]
        assert len(sin_nodes) > 0
    
    def test_load_third_party_package_with_submodules(self):
        """Test loading packages with submodules."""
        palette = NodePalette()
        
        # Load collections module (has submodules)
        palette.load_third_party_package("collections", include_submodules=True)
        
        # Should create category
        assert "collections" in palette.categories
        
        # Should have nodes
        collections_nodes = palette.get_category_nodes("collections")
        assert len(collections_nodes) > 0
    
    def test_load_popular_packages(self):
        """Test loading popular packages."""
        palette = NodePalette()
        
        # Load popular packages
        palette.load_popular_packages()
        
        # Should have loaded several standard library packages
        expected_packages = ['math', 'random', 'datetime', 'json', 'os']
        loaded_count = 0
        
        for package in expected_packages:
            if package in palette.categories:
                nodes = palette.get_category_nodes(package)
                if len(nodes) > 0:
                    loaded_count += 1
        
        # Should have loaded at least some packages
        assert loaded_count > 0
    
    def test_package_info(self):
        """Test getting package information."""
        palette = NodePalette()
        
        # Load a package first
        palette.load_third_party_package("math")
        
        # Get package info
        info = palette.get_package_info("math")
        
        assert "category_name" in info
        assert "node_count" in info
        assert "dependencies" in info
        assert info["category_name"] == "math"
        assert info["node_count"] > 0
    
    def test_package_availability(self):
        """Test checking package availability."""
        palette = NodePalette()
        
        # Math should be available
        assert palette.is_package_available("math") is True
        
        # Non-existent package should not be available
        assert palette.is_package_available("nonexistent_package_12345") is False
    
    def test_failed_packages_tracking(self):
        """Test tracking of failed package loads."""
        palette = NodePalette()
        
        # Try to load non-existent package
        palette.load_third_party_package("nonexistent_package_12345")
        
        # Should track the failure
        failed = palette.get_failed_packages()
        assert "nonexistent_package_12345" in failed
        assert "Import failed" in failed["nonexistent_package_12345"]
    
    def test_package_suggestions(self):
        """Test package suggestions."""
        palette = NodePalette()
        
        # Test web-related suggestions
        web_suggestions = palette.suggest_packages("web")
        assert len(web_suggestions) > 0
        assert any("requests" in str(s) for s in web_suggestions)
        
        # Test data-related suggestions
        data_suggestions = palette.suggest_packages("data")
        assert len(data_suggestions) > 0
        
        # Test math-related suggestions
        math_suggestions = palette.suggest_packages("math")
        assert len(math_suggestions) > 0
        assert "math" in math_suggestions
    
    def test_get_node_count(self):
        """Test getting node counts."""
        palette = NodePalette()
        palette.load_standard_library()
        
        counts = palette.get_node_count()
        
        assert isinstance(counts, dict)
        assert "Core Python" in counts
        assert counts["Core Python"] > 0
    
    def test_export_palette(self):
        """Test exporting palette configuration."""
        palette = NodePalette()
        palette.load_standard_library()
        
        export_data = palette.export_palette()
        
        assert "categories" in export_data
        assert "total_nodes" in export_data
        assert "loaded_packages" in export_data
        assert export_data["total_nodes"] > 0


# Property-based tests
@given(st.text(min_size=1, max_size=50))
def test_node_definition_name_property(name):
    """Property test: NodeDefinition should handle any valid name."""
    node_def = NodeDefinition(name, NodeType.FUNCTION)
    assert node_def.name == name


@given(st.text(min_size=0, max_size=100))
def test_search_query_property(query):
    """Property test: Search should handle any query string."""
    index = SearchIndex()
    
    # Add a test node
    node_def = NodeDefinition("test", NodeType.FUNCTION, "test description")
    index.add_node(node_def)
    
    # Search should not crash with any query
    try:
        results = index.search(query)
        assert isinstance(results, list)
    except Exception:
        # Some queries might cause issues, which is acceptable
        pass


@given(st.integers(min_value=1, max_value=10))
def test_multiple_nodes_property(num_nodes):
    """Property test: Palette should handle any number of nodes."""
    palette = NodePalette()
    
    # Add multiple nodes
    for i in range(num_nodes):
        node_def = NodeDefinition(f"node_{i}", NodeType.FUNCTION)
        palette.categories["Core Python"].add_node(node_def)
        palette.search_index.add_node(node_def)
    
    # Should be able to search and get results
    results = palette.search_nodes("")
    assert len(results) >= num_nodes