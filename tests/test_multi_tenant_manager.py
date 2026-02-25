"""
Tests for the Multi-Tenant Manager.
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, patch

from visual_editor_core.database import (
    MultiTenantManager,
    TenantInfo,
    TenantContext,
    TenantConfig,
    DatabaseManager,
    DatabaseConfig,
    DatabaseType,
    QueryResult,
    TransactionResult
)


class TestMultiTenantManager:
    """Test cases for MultiTenantManager."""
    
    @pytest.fixture
    def mock_database_manager(self):
        """Create a mock database manager."""
        mock_db = Mock(spec=DatabaseManager)
        mock_db.execute_query.return_value = QueryResult(success=True, data=[])
        mock_db.execute_transaction.return_value = TransactionResult(
            success=True, 
            transaction_id=str(uuid.uuid4()), 
            operations_count=1
        )
        return mock_db
    
    @pytest.fixture
    def tenant_manager(self, mock_database_manager):
        """Create a MultiTenantManager instance."""
        return MultiTenantManager(mock_database_manager)
    
    @pytest.fixture
    def sample_tenant_info(self):
        """Create sample tenant info."""
        return TenantInfo(
            name="Test Tenant",
            domain="test.example.com",
            configuration={"theme": "dark"},
            resource_limits={"max_models": 100},
            billing_info={"plan": "basic"}
        )
    
    def test_create_tenant_success(self, tenant_manager, sample_tenant_info, mock_database_manager):
        """Test successful tenant creation."""
        # Mock successful database operations
        mock_database_manager.execute_transaction.return_value = TransactionResult(
            success=True,
            transaction_id=str(uuid.uuid4()),
            operations_count=1
        )
        
        # Create tenant
        tenant_id = tenant_manager.create_tenant(sample_tenant_info)
        
        # Verify tenant ID is returned
        assert tenant_id is not None
        assert isinstance(tenant_id, str)
        
        # Verify database operations were called
        assert mock_database_manager.execute_transaction.called
    
    def test_create_tenant_invalid_info(self, tenant_manager):
        """Test tenant creation with invalid info."""
        invalid_tenant_info = TenantInfo(name="", domain="")  # Invalid: empty name and domain
        
        with pytest.raises(Exception):  # Should raise ValidationError
            tenant_manager.create_tenant(invalid_tenant_info)
    
    def test_get_tenant_context_success(self, tenant_manager, mock_database_manager):
        """Test successful tenant context retrieval."""
        user_id = str(uuid.uuid4())
        tenant_id = str(uuid.uuid4())
        
        # Mock database response
        mock_database_manager.execute_query.return_value = QueryResult(
            success=True,
            data=[{
                'tenant_id': tenant_id,
                'permissions': ['read', 'write']
            }]
        )
        
        # Get tenant context
        context = tenant_manager.get_tenant_context(user_id)
        
        # Verify context
        assert context is not None
        assert context.user_id == user_id
        assert context.tenant_id == tenant_id
        assert 'read' in context.permissions
        assert 'write' in context.permissions
    
    def test_get_tenant_context_no_access(self, tenant_manager, mock_database_manager):
        """Test tenant context retrieval when user has no access."""
        user_id = str(uuid.uuid4())
        
        # Mock database response - no access
        mock_database_manager.execute_query.return_value = QueryResult(
            success=True,
            data=[]
        )
        
        # Get tenant context
        context = tenant_manager.get_tenant_context(user_id)
        
        # Verify no context returned
        assert context is None
    
    def test_enforce_tenant_isolation(self, tenant_manager):
        """Test tenant isolation enforcement."""
        tenant_id = str(uuid.uuid4())
        original_query = "SELECT * FROM visual_models"
        
        # Enforce isolation
        scoped_query = tenant_manager.enforce_tenant_isolation(original_query, tenant_id)
        
        # Verify tenant scoping was added
        assert f"tenant_id = '{tenant_id}'" in scoped_query
        assert "WHERE" in scoped_query
    
    def test_get_tenant_usage_metrics(self, tenant_manager, mock_database_manager):
        """Test tenant usage metrics retrieval."""
        tenant_id = str(uuid.uuid4())
        
        # Mock database responses
        mock_database_manager.execute_query.side_effect = [
            QueryResult(success=True, data=[{'model_count': 5, 'storage_used': 1024}]),
            QueryResult(success=True, data=[{'execution_count': 10, 'last_activity': '2024-01-01T12:00:00'}])
        ]
        
        # Get usage metrics
        metrics = tenant_manager.get_tenant_usage_metrics(tenant_id)
        
        # Verify metrics
        assert metrics.tenant_id == tenant_id
        assert metrics.models_created == 5
        assert metrics.storage_used == 1024
        assert metrics.executions_performed == 10
        assert metrics.last_activity is not None
    
    def test_validate_tenant_access_success(self, tenant_manager):
        """Test successful tenant access validation."""
        user_id = str(uuid.uuid4())
        tenant_id = str(uuid.uuid4())
        
        # Mock the access controller validation
        with patch.object(tenant_manager.access_controller, 'validate_tenant_access') as mock_validate:
            mock_validate.return_value = (True, None)
            
            # Validate access
            is_valid, error = tenant_manager.validate_tenant_access(
                user_id, tenant_id, 'read', 'visual_model'
            )
            
            # Verify validation passed
            assert is_valid is True
            assert error is None
            assert mock_validate.called
    
    def test_validate_tenant_access_denied(self, tenant_manager):
        """Test tenant access validation when access is denied."""
        user_id = str(uuid.uuid4())
        tenant_id = str(uuid.uuid4())
        
        # Mock the access controller validation
        with patch.object(tenant_manager.access_controller, 'validate_tenant_access') as mock_validate:
            mock_validate.return_value = (False, "Access denied")
            
            # Validate access
            is_valid, error = tenant_manager.validate_tenant_access(
                user_id, tenant_id, 'delete', 'visual_model'
            )
            
            # Verify validation failed
            assert is_valid is False
            assert error == "Access denied"
            assert mock_validate.called
    
    def test_create_tenant_database_constraints(self, tenant_manager):
        """Test creation of database constraints for tenant."""
        tenant_id = str(uuid.uuid4())
        
        # Mock the access controller
        with patch.object(tenant_manager.access_controller, 'create_tenant_constraints') as mock_create:
            mock_create.return_value = True
            
            # Create constraints
            result = tenant_manager.create_tenant_database_constraints(tenant_id)
            
            # Verify constraints were created
            assert result is True
            assert mock_create.called
    
    def test_validate_query_safety(self, tenant_manager):
        """Test query safety validation."""
        tenant_id = str(uuid.uuid4())
        query = "SELECT * FROM visual_models WHERE id = '123'"
        
        # Mock the access controller
        with patch.object(tenant_manager.access_controller, 'validate_query_safety') as mock_validate:
            mock_validate.return_value = (True, [])
            
            # Validate query
            is_safe, violations = tenant_manager.validate_query_safety(query, tenant_id)
            
            # Verify query is safe
            assert is_safe is True
            assert violations == []
            assert mock_validate.called
    
    def test_get_access_violation_summary(self, tenant_manager):
        """Test access violation summary retrieval."""
        tenant_id = str(uuid.uuid4())
        
        # Mock the access controller
        with patch.object(tenant_manager.access_controller, 'get_violation_summary') as mock_summary:
            mock_summary.return_value = {
                'total_violations': 5,
                'blocked_violations': 4,
                'violation_types': {'cross_tenant_access': 3, 'permission_denied': 2}
            }
            
            # Get summary
            summary = tenant_manager.get_access_violation_summary(tenant_id)
            
            # Verify summary
            assert summary['total_violations'] == 5
            assert summary['blocked_violations'] == 4
            assert 'cross_tenant_access' in summary['violation_types']
            assert mock_summary.called
    
    def test_tenant_operation_context(self, tenant_manager):
        """Test tenant operation context manager."""
        user_id = str(uuid.uuid4())
        tenant_id = str(uuid.uuid4())
        
        # Mock the access controller context
        with patch.object(tenant_manager.access_controller, 'tenant_operation_context') as mock_context:
            mock_context.return_value.__enter__ = Mock(return_value={'user_id': user_id, 'tenant_id': tenant_id})
            mock_context.return_value.__exit__ = Mock(return_value=None)
            
            # Use context manager
            with tenant_manager.tenant_operation_context(user_id, tenant_id) as context:
                assert context is not None
            
            assert mock_context.called
    
    def test_shutdown(self, tenant_manager):
        """Test multi-tenant manager shutdown."""
        # Mock the access controller
        with patch.object(tenant_manager.access_controller, 'shutdown') as mock_shutdown:
            # Shutdown manager
            tenant_manager.shutdown()
            
            # Verify shutdown was called
            assert mock_shutdown.called
            assert len(tenant_manager._active_contexts) == 0


class TestTenantInfo:
    """Test cases for TenantInfo."""
    
    def test_valid_tenant_info(self):
        """Test valid tenant info validation."""
        tenant_info = TenantInfo(
            name="Test Tenant",
            domain="test.example.com",
            status="active"
        )
        
        errors = tenant_info.validate()
        assert len(errors) == 0
    
    def test_invalid_tenant_info_empty_name(self):
        """Test tenant info validation with empty name."""
        tenant_info = TenantInfo(
            name="",
            domain="test.example.com"
        )
        
        errors = tenant_info.validate()
        assert len(errors) > 0
        assert any("name is required" in error for error in errors)
    
    def test_invalid_tenant_info_empty_domain(self):
        """Test tenant info validation with empty domain."""
        tenant_info = TenantInfo(
            name="Test Tenant",
            domain=""
        )
        
        errors = tenant_info.validate()
        assert len(errors) > 0
        assert any("domain is required" in error for error in errors)
    
    def test_invalid_tenant_info_invalid_status(self):
        """Test tenant info validation with invalid status."""
        tenant_info = TenantInfo(
            name="Test Tenant",
            domain="test.example.com",
            status="invalid_status"
        )
        
        errors = tenant_info.validate()
        assert len(errors) > 0
        assert any("Invalid tenant status" in error for error in errors)


class TestTenantContext:
    """Test cases for TenantContext."""
    
    def test_has_permission(self):
        """Test permission checking in tenant context."""
        context = TenantContext(
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            permissions=['read', 'write', 'execute']
        )
        
        assert context.has_permission('read') is True
        assert context.has_permission('write') is True
        assert context.has_permission('delete') is False


class TestTenantConfig:
    """Test cases for TenantConfig."""
    
    def test_get_set_setting(self):
        """Test getting and setting configuration settings."""
        config = TenantConfig(tenant_id=str(uuid.uuid4()))
        
        # Test default value
        assert config.get_setting('theme', 'light') == 'light'
        
        # Test setting and getting value
        config.set_setting('theme', 'dark')
        assert config.get_setting('theme') == 'dark'
    
    def test_is_feature_enabled(self):
        """Test feature flag checking."""
        config = TenantConfig(
            tenant_id=str(uuid.uuid4()),
            feature_flags={'debug_mode': True, 'analytics': False}
        )
        
        assert config.is_feature_enabled('debug_mode') is True
        assert config.is_feature_enabled('analytics') is False
        assert config.is_feature_enabled('unknown_feature') is False


if __name__ == '__main__':
    pytest.main([__file__])