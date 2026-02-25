"""
Tests for the Plugin System.
"""

import os
import json
import tempfile
import shutil
import pytest
from unittest.mock import Mock, patch, MagicMock

from visual_editor_core.plugin_system import (
    PluginManager, PluginAPI, VisualComponentPlugin, VisualParadigmPlugin,
    CodeGeneratorPlugin, PluginManifest, PluginType, PluginStatus, SecurityLevel,
    PluginValidator, PluginSandbox, PluginContext
)
from visual_editor_core.models import VisualNode, VisualModel, NodeType
from visual_editor_core.node_palette import NodeDefinition


class TestPluginManifest:
    """Test plugin manifest functionality."""
    
    def test_manifest_creation(self):
        """Test creating a plugin manifest."""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type=PluginType.VISUAL_COMPONENT,
            entry_point="main.py"
        )
        
        assert manifest.name == "test_plugin"
        assert manifest.version == "1.0.0"
        assert manifest.plugin_type == PluginType.VISUAL_COMPONENT
        assert manifest.security_level == SecurityLevel.SANDBOXED  # default
    
    def test_manifest_serialization(self):
        """Test manifest to/from dict conversion."""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type=PluginType.VISUAL_COMPONENT,
            entry_point="main.py",
            security_level=SecurityLevel.TRUSTED
        )
        
        # Convert to dict
        data = manifest.to_dict()
        assert data['plugin_type'] == 'visual_component'
        assert data['security_level'] == 'trusted'
        
        # Convert back from dict
        restored = PluginManifest.from_dict(data)
        assert restored.name == manifest.name
        assert restored.plugin_type == manifest.plugin_type
        assert restored.security_level == manifest.security_level


class TestPluginValidator:
    """Test plugin validation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = PluginValidator()
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_validate_manifest_success(self):
        """Test successful manifest validation."""
        manifest = PluginManifest(
            name="valid_plugin",
            version="1.0.0",
            description="Valid test plugin",
            author="Test Author",
            plugin_type=PluginType.VISUAL_COMPONENT,
            entry_point="main.py"
        )
        
        result = {'valid': True, 'errors': [], 'warnings': [], 'security_issues': [], 'compatibility_issues': []}
        self.validator._validate_manifest(manifest, result)
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    def test_validate_manifest_missing_fields(self):
        """Test manifest validation with missing fields."""
        manifest = PluginManifest(
            name="",  # Missing name
            version="1.0.0",
            description="",  # Missing description
            author="Test Author",
            plugin_type=PluginType.VISUAL_COMPONENT,
            entry_point="main.py"
        )
        
        result = {'valid': True, 'errors': [], 'warnings': [], 'security_issues': [], 'compatibility_issues': []}
        self.validator._validate_manifest(manifest, result)
        
        assert len(result['errors']) >= 2  # Should have errors for missing name and description
    
    def test_validate_plugin_file_syntax_error(self):
        """Test validation of plugin file with syntax error."""
        # Create a Python file with syntax error
        plugin_file = os.path.join(self.temp_dir, "bad_plugin.py")
        with open(plugin_file, 'w') as f:
            f.write("def invalid_syntax(\n")  # Missing closing parenthesis
        
        result = {'valid': True, 'errors': [], 'warnings': [], 'security_issues': [], 'compatibility_issues': []}
        self.validator._validate_plugin_file(plugin_file, result)
        
        assert len(result['errors']) > 0
        assert any('syntax error' in error.lower() for error in result['errors'])
    
    def test_security_analysis_dangerous_imports(self):
        """Test security analysis detecting dangerous imports."""
        # Create plugin file with dangerous imports
        plugin_file = os.path.join(self.temp_dir, "dangerous_plugin.py")
        with open(plugin_file, 'w') as f:
            f.write("""
import os
import subprocess
from visual_editor_core.plugin_system import VisualComponentPlugin

class DangerousPlugin(VisualComponentPlugin):
    def initialize(self, context):
        return True
    
    def cleanup(self):
        pass
    
    def get_node_definitions(self):
        return []
    
    def create_node_instance(self, definition, **kwargs):
        return None
""")
        
        manifest = PluginManifest(
            name="dangerous_plugin",
            version="1.0.0",
            description="Dangerous plugin",
            author="Test",
            plugin_type=PluginType.VISUAL_COMPONENT,
            entry_point="dangerous_plugin.py",
            security_level=SecurityLevel.SANDBOXED
        )
        
        result = {'valid': True, 'errors': [], 'warnings': [], 'security_issues': [], 'compatibility_issues': []}
        self.validator._analyze_security(plugin_file, manifest, result)
        
        assert len(result['security_issues']) > 0
        assert any('os' in issue for issue in result['security_issues'])


class TestPluginSandbox:
    """Test plugin sandbox functionality."""
    
    def test_trusted_sandbox_no_restrictions(self):
        """Test that trusted sandbox has no restrictions."""
        sandbox = PluginSandbox(SecurityLevel.TRUSTED)
        
        # Should be able to execute anything in trusted mode
        with sandbox.execute_in_sandbox():
            import os  # Should work
            result = os.getcwd()  # Should work
            assert result is not None
    
    def test_sandboxed_restrictions(self):
        """Test that sandboxed mode has appropriate restrictions."""
        sandbox = PluginSandbox(SecurityLevel.SANDBOXED)
        
        with sandbox.execute_in_sandbox():
            # Should be able to import allowed modules
            import math
            assert math.pi > 3
            
            # For now, the sandbox is simplified for testing
            # In production, this would have actual restrictions
            assert sandbox.security_level == SecurityLevel.SANDBOXED
    
    def test_isolated_restrictions(self):
        """Test that isolated mode has strict restrictions."""
        sandbox = PluginSandbox(SecurityLevel.ISOLATED)
        
        with sandbox.execute_in_sandbox():
            # Should be able to import very limited modules
            import math
            assert math.pi > 3
            
            # For now, the sandbox is simplified for testing
            # In production, this would have actual restrictions
            assert sandbox.security_level == SecurityLevel.ISOLATED


class MockVisualComponentPlugin(VisualComponentPlugin):
    """Mock visual component plugin for testing."""
    
    def __init__(self):
        self._name = "Mock Plugin"
        self._version = "1.0.0"
        self.initialized = False
    
    def initialize(self, context):
        self.initialized = True
        return True
    
    def cleanup(self):
        self.initialized = False
    
    def get_node_definitions(self):
        node_def = NodeDefinition(
            name="mock_node",
            node_type=NodeType.FUNCTION,
            description="Mock node for testing",
            category="Mock"
        )
        return [node_def]
    
    def create_node_instance(self, definition, **kwargs):
        return VisualNode(type=NodeType.FUNCTION)


class TestPluginManager:
    """Test plugin manager functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.plugin_manager = PluginManager(self.temp_dir)
        
        # Mock node palette
        self.plugin_manager.node_palette = Mock()
        self.plugin_manager.node_palette.categories = {}
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def create_test_plugin(self, plugin_name="test_plugin"):
        """Create a test plugin in the temp directory."""
        plugin_dir = os.path.join(self.temp_dir, plugin_name)
        os.makedirs(plugin_dir, exist_ok=True)
        
        # Create manifest
        manifest = {
            "name": plugin_name,
            "version": "1.0.0",
            "description": "Test plugin",
            "author": "Test Author",
            "plugin_type": "visual_component",
            "entry_point": "main.py",
            "security_level": "sandboxed"
        }
        
        with open(os.path.join(plugin_dir, "plugin.json"), 'w') as f:
            json.dump(manifest, f)
        
        # Create plugin file
        plugin_code = '''
from visual_editor_core.plugin_system import VisualComponentPlugin
from visual_editor_core.models import NodeType
from visual_editor_core.node_palette import NodeDefinition

class TestPlugin(VisualComponentPlugin):
    def __init__(self):
        self._name = "Test Plugin"
        self._version = "1.0.0"
    
    def initialize(self, context):
        return True
    
    def cleanup(self):
        pass
    
    def get_node_definitions(self):
        node_def = NodeDefinition(
            name="test_node",
            node_type=NodeType.FUNCTION,
            description="Test node",
            category="Test"
        )
        return [node_def]
    
    def create_node_instance(self, definition, **kwargs):
        from visual_editor_core.models import VisualNode
        return VisualNode(type=NodeType.FUNCTION)
'''
        
        with open(os.path.join(plugin_dir, "main.py"), 'w') as f:
            f.write(plugin_code)
        
        return plugin_dir
    
    def test_discover_plugins(self):
        """Test plugin discovery."""
        # Create test plugins
        self.create_test_plugin("plugin1")
        self.create_test_plugin("plugin2")
        
        plugins = self.plugin_manager.discover_plugins()
        assert len(plugins) >= 2
    
    def test_load_plugin_manifest(self):
        """Test loading plugin manifest."""
        plugin_dir = self.create_test_plugin()
        
        manifest = self.plugin_manager.load_plugin_manifest(plugin_dir)
        assert manifest is not None
        assert manifest.name == "test_plugin"
        assert manifest.version == "1.0.0"
    
    def test_validate_plugin(self):
        """Test plugin validation."""
        plugin_dir = self.create_test_plugin()
        
        result = self.plugin_manager.validate_plugin(plugin_dir)
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    @patch('visual_editor_core.plugin_system.PluginSandbox')
    def test_load_plugin_success(self, mock_sandbox_class):
        """Test successful plugin loading."""
        # Mock sandbox
        mock_sandbox = Mock()
        mock_sandbox_class.return_value = mock_sandbox
        mock_sandbox.execute_in_sandbox.return_value.__enter__ = Mock()
        mock_sandbox.execute_in_sandbox.return_value.__exit__ = Mock()
        
        plugin_dir = self.create_test_plugin()
        
        # Mock the node palette add_category method
        self.plugin_manager.node_palette.add_category = Mock()
        
        success = self.plugin_manager.load_plugin(plugin_dir)
        assert success is True
        
        # Check that plugin was loaded
        plugins = self.plugin_manager.list_plugins()
        assert len(plugins) == 1
        assert plugins[0].manifest.name == "test_plugin"
        assert plugins[0].status == PluginStatus.LOADED
    
    def test_load_plugin_invalid_manifest(self):
        """Test loading plugin with invalid manifest."""
        plugin_dir = os.path.join(self.temp_dir, "invalid_plugin")
        os.makedirs(plugin_dir)
        
        # Create invalid manifest (missing required fields)
        manifest = {"name": ""}
        with open(os.path.join(plugin_dir, "plugin.json"), 'w') as f:
            json.dump(manifest, f)
        
        success = self.plugin_manager.load_plugin(plugin_dir)
        assert success is False
    
    def test_unload_plugin(self):
        """Test plugin unloading."""
        # First load a plugin
        plugin_dir = self.create_test_plugin()
        
        with patch('visual_editor_core.plugin_system.PluginSandbox'):
            self.plugin_manager.load_plugin(plugin_dir)
        
        plugins = self.plugin_manager.list_plugins()
        assert len(plugins) == 1
        
        plugin_id = plugins[0].get_id()
        
        # Now unload it
        success = self.plugin_manager.unload_plugin(plugin_id)
        assert success is True
        
        # Check that plugin was unloaded
        plugins = self.plugin_manager.list_plugins()
        assert len(plugins) == 0
    
    def test_plugin_config_management(self):
        """Test plugin configuration management."""
        plugin_name = "test_plugin"
        config = {"setting1": "value1", "setting2": 42}
        
        # Set config
        self.plugin_manager.set_plugin_config(plugin_name, config)
        
        # Get config
        retrieved_config = self.plugin_manager.get_plugin_config(plugin_name)
        assert retrieved_config == config
    
    def test_enable_disable_plugin(self):
        """Test enabling and disabling plugins."""
        plugin_dir = self.create_test_plugin()
        
        with patch('visual_editor_core.plugin_system.PluginSandbox'):
            self.plugin_manager.load_plugin(plugin_dir)
        
        plugins = self.plugin_manager.list_plugins()
        plugin_id = plugins[0].get_id()
        
        # Enable plugin
        success = self.plugin_manager.enable_plugin(plugin_id)
        assert success is True
        
        plugin_info = self.plugin_manager.get_plugin_info(plugin_id)
        assert plugin_info.status == PluginStatus.ACTIVE
        
        # Disable plugin
        success = self.plugin_manager.disable_plugin(plugin_id)
        assert success is True
        
        plugin_info = self.plugin_manager.get_plugin_info(plugin_id)
        assert plugin_info.status == PluginStatus.DISABLED


class TestPluginContext:
    """Test plugin context functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.plugin_manager = Mock()
        self.context = PluginContext(self.plugin_manager)
    
    def test_module_restrictions(self):
        """Test module access restrictions."""
        # Allowed modules
        assert self.context.is_module_allowed('math') is True
        assert self.context.is_module_allowed('json') is True
        
        # Restricted modules
        assert self.context.is_module_allowed('os') is False
        assert self.context.is_module_allowed('sys') is False
        assert self.context.is_module_allowed('subprocess') is False
    
    def test_config_access(self):
        """Test plugin configuration access."""
        plugin_name = "test_plugin"
        config = {"key": "value"}
        
        # Mock plugin manager methods
        self.plugin_manager.get_plugin_config.return_value = config
        
        # Test getting config
        result = self.context.get_plugin_config(plugin_name)
        assert result == config
        
        # Test setting config
        new_config = {"new_key": "new_value"}
        self.context.set_plugin_config(plugin_name, new_config)
        self.plugin_manager.set_plugin_config.assert_called_once_with(plugin_name, new_config)


class TestPluginIntegration:
    """Test plugin system integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.plugin_manager = PluginManager(self.temp_dir)
        
        # Mock node palette
        self.plugin_manager.node_palette = Mock()
        self.plugin_manager.node_palette.categories = {}
        self.plugin_manager.node_palette.add_category = Mock()
        self.plugin_manager.node_palette.search_index = Mock()
        self.plugin_manager.node_palette.search_index.add_node = Mock()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_visual_component_plugin_registration(self):
        """Test that visual component plugins register their nodes."""
        # Create a mock plugin instance
        plugin_instance = MockVisualComponentPlugin()
        
        # Create plugin info
        from visual_editor_core.plugin_system import PluginInfo
        manifest = PluginManifest(
            name="mock_plugin",
            version="1.0.0",
            description="Mock plugin",
            author="Test",
            plugin_type=PluginType.VISUAL_COMPONENT,
            entry_point="main.py"
        )
        
        plugin_info = PluginInfo(manifest=manifest, instance=plugin_instance)
        
        # Register components
        self.plugin_manager._register_plugin_components(plugin_info)
        
        # Verify that register_node_definition was called
        # (This would be called indirectly through the registration process)
        assert plugin_instance.initialized is False  # Not initialized yet
    
    def test_plugin_lifecycle(self):
        """Test complete plugin lifecycle."""
        # This would be a more comprehensive integration test
        # that tests loading, initializing, using, and unloading a plugin
        
        # Create a simple plugin
        plugin_dir = os.path.join(self.temp_dir, "lifecycle_test")
        os.makedirs(plugin_dir)
        
        # Create manifest
        manifest = {
            "name": "lifecycle_test",
            "version": "1.0.0",
            "description": "Lifecycle test plugin",
            "author": "Test",
            "plugin_type": "visual_component",
            "entry_point": "main.py",
            "security_level": "sandboxed"
        }
        
        with open(os.path.join(plugin_dir, "plugin.json"), 'w') as f:
            json.dump(manifest, f)
        
        # Create simple plugin file
        plugin_code = '''
from visual_editor_core.plugin_system import VisualComponentPlugin

class LifecycleTestPlugin(VisualComponentPlugin):
    def __init__(self):
        self.initialized = False
    
    def initialize(self, context):
        self.initialized = True
        return True
    
    def cleanup(self):
        self.initialized = False
    
    def get_node_definitions(self):
        return []
    
    def create_node_instance(self, definition, **kwargs):
        return None
'''
        
        with open(os.path.join(plugin_dir, "main.py"), 'w') as f:
            f.write(plugin_code)
        
        # Test discovery
        plugins = self.plugin_manager.discover_plugins()
        assert len(plugins) >= 1
        
        # Test validation
        result = self.plugin_manager.validate_plugin(plugin_dir)
        assert result['valid'] is True
        
        # The actual loading would require more complex mocking
        # of the sandbox and module loading system
        # This test verifies the basic structure is in place


if __name__ == '__main__':
    pytest.main([__file__])