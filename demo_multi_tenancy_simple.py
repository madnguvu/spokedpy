"""
Simple demo script for the Multi-Tenancy System components.

This script demonstrates the key features of the multi-tenancy system without
requiring a full database setup.
"""

import uuid
from datetime import datetime
from visual_editor_core.database import (
    TenantInfo,
    TenantConfig,
    TenantContext,
    UsageMetrics,
    AccessAttempt,
    AccessViolation
)


def demo_tenant_info():
    """Demonstrate TenantInfo functionality."""
    print("=== TenantInfo Demo ===\n")
    
    # Create valid tenant info
    print("1. Creating Valid Tenant Info...")
    valid_tenant = TenantInfo(
        name="Acme Corporation",
        domain="acme.example.com",
        configuration={
            "theme": "corporate",
            "language": "en",
            "timezone": "America/New_York"
        },
        resource_limits={
            "max_models": 1000,
            "max_executions_per_hour": 5000,
            "max_storage_mb": 5120
        },
        billing_info={
            "plan": "enterprise",
            "billing_email": "billing@acme.com"
        },
        status="active"
    )
    
    errors = valid_tenant.validate()
    print(f"   Tenant Name: {valid_tenant.name}")
    print(f"   Domain: {valid_tenant.domain}")
    print(f"   Status: {valid_tenant.status}")
    print(f"   Validation Errors: {len(errors)} ({'✓ Valid' if len(errors) == 0 else '✗ Invalid'})")
    
    # Create invalid tenant info
    print("\n2. Creating Invalid Tenant Info...")
    invalid_tenant = TenantInfo(
        name="",  # Empty name - invalid
        domain="",  # Empty domain - invalid
        status="invalid_status"  # Invalid status
    )
    
    errors = invalid_tenant.validate()
    print(f"   Tenant Name: '{invalid_tenant.name}'")
    print(f"   Domain: '{invalid_tenant.domain}'")
    print(f"   Status: {invalid_tenant.status}")
    print(f"   Validation Errors: {len(errors)} ({'✓ Valid' if len(errors) == 0 else '✗ Invalid'})")
    
    if errors:
        for error in errors:
            print(f"     - {error}")


def demo_tenant_config():
    """Demonstrate TenantConfig functionality."""
    print("\n=== TenantConfig Demo ===\n")
    
    tenant_id = str(uuid.uuid4())
    config = TenantConfig(tenant_id=tenant_id)
    
    print(f"1. Created config for tenant: {tenant_id}")
    
    # Demonstrate settings management
    print("\n2. Settings Management...")
    config.set_setting("theme", "dark")
    config.set_setting("language", "en")
    config.set_setting("timezone", "UTC")
    config.set_setting("auto_save", True)
    
    print(f"   Theme: {config.get_setting('theme')}")
    print(f"   Language: {config.get_setting('language')}")
    print(f"   Timezone: {config.get_setting('timezone')}")
    print(f"   Auto Save: {config.get_setting('auto_save')}")
    print(f"   Unknown Setting (with default): {config.get_setting('unknown', 'default_value')}")
    
    # Demonstrate feature flags
    print("\n3. Feature Flags...")
    config.feature_flags["debug_mode"] = True
    config.feature_flags["analytics"] = False
    config.feature_flags["collaboration"] = True
    config.feature_flags["advanced_features"] = False
    
    print(f"   Debug Mode: {config.is_feature_enabled('debug_mode')}")
    print(f"   Analytics: {config.is_feature_enabled('analytics')}")
    print(f"   Collaboration: {config.is_feature_enabled('collaboration')}")
    print(f"   Advanced Features: {config.is_feature_enabled('advanced_features')}")
    print(f"   Unknown Feature: {config.is_feature_enabled('unknown_feature')}")
    
    # Demonstrate resource limits
    print("\n4. Resource Limits...")
    config.resource_limits["max_models"] = 500
    config.resource_limits["max_storage_mb"] = 2048
    config.resource_limits["max_concurrent_users"] = 50
    
    print(f"   Max Models: {config.resource_limits['max_models']}")
    print(f"   Max Storage (MB): {config.resource_limits['max_storage_mb']}")
    print(f"   Max Concurrent Users: {config.resource_limits['max_concurrent_users']}")


def demo_tenant_context():
    """Demonstrate TenantContext functionality."""
    print("\n=== TenantContext Demo ===\n")
    
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    
    # Create tenant context
    context = TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        permissions=["read", "write", "execute", "admin"],
        resource_usage={
            "models_created": 25,
            "storage_used": 1024,
            "executions_today": 150
        },
        session_id=str(uuid.uuid4())
    )
    
    print(f"1. Created context for tenant: {tenant_id}")
    print(f"   User ID: {user_id}")
    print(f"   Session ID: {context.session_id}")
    print(f"   Created At: {context.created_at}")
    
    # Test permission checking
    print("\n2. Permission Checking...")
    permissions_to_test = ["read", "write", "execute", "admin", "delete", "unknown"]
    
    for permission in permissions_to_test:
        has_permission = context.has_permission(permission)
        status = "✓ Allowed" if has_permission else "✗ Denied"
        print(f"   {permission}: {status}")
    
    # Display resource usage
    print("\n3. Resource Usage...")
    for resource, usage in context.resource_usage.items():
        print(f"   {resource}: {usage}")


def demo_usage_metrics():
    """Demonstrate UsageMetrics functionality."""
    print("\n=== UsageMetrics Demo ===\n")
    
    tenant_id = str(uuid.uuid4())
    
    # Create usage metrics
    metrics = UsageMetrics(
        tenant_id=tenant_id,
        storage_used=2048576,  # ~2MB
        queries_executed=1250,
        active_connections=8,
        models_created=45,
        executions_performed=320,
        last_activity=datetime.now()
    )
    
    print(f"1. Usage Metrics for tenant: {tenant_id}")
    print(f"   Storage Used: {metrics.storage_used:,} bytes ({metrics.storage_used / 1024 / 1024:.2f} MB)")
    print(f"   Queries Executed: {metrics.queries_executed:,}")
    print(f"   Active Connections: {metrics.active_connections}")
    print(f"   Models Created: {metrics.models_created}")
    print(f"   Executions Performed: {metrics.executions_performed}")
    print(f"   Last Activity: {metrics.last_activity}")
    print(f"   Period: {metrics.period_start} to {metrics.period_end}")
    
    # Convert to dictionary
    print("\n2. Metrics as Dictionary...")
    metrics_dict = metrics.to_dict()
    for key, value in metrics_dict.items():
        print(f"   {key}: {value}")


def demo_access_control():
    """Demonstrate access control components."""
    print("\n=== Access Control Demo ===\n")
    
    # Demonstrate AccessAttempt
    print("1. Access Attempt...")
    user_id = str(uuid.uuid4())
    tenant_id_1 = str(uuid.uuid4())
    tenant_id_2 = str(uuid.uuid4())
    
    # Valid access attempt (same tenant)
    valid_attempt = AccessAttempt(
        user_id=user_id,
        requested_tenant_id=tenant_id_1,
        actual_tenant_id=tenant_id_1,
        operation_type="read",
        resource_type="visual_model",
        resource_id=str(uuid.uuid4()),
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0..."
    )
    
    print(f"   Valid Access Attempt:")
    print(f"     User: {valid_attempt.user_id}")
    print(f"     Requested Tenant: {valid_attempt.requested_tenant_id}")
    print(f"     Actual Tenant: {valid_attempt.actual_tenant_id}")
    print(f"     Is Cross-Tenant: {valid_attempt.is_cross_tenant()}")
    print(f"     Operation: {valid_attempt.operation_type}")
    print(f"     Resource: {valid_attempt.resource_type}")
    
    # Cross-tenant access attempt
    cross_tenant_attempt = AccessAttempt(
        user_id=user_id,
        requested_tenant_id=tenant_id_2,  # Different tenant
        actual_tenant_id=tenant_id_1,
        operation_type="write",
        resource_type="custom_component",
        ip_address="192.168.1.100"
    )
    
    print(f"\n   Cross-Tenant Access Attempt:")
    print(f"     User: {cross_tenant_attempt.user_id}")
    print(f"     Requested Tenant: {cross_tenant_attempt.requested_tenant_id}")
    print(f"     Actual Tenant: {cross_tenant_attempt.actual_tenant_id}")
    print(f"     Is Cross-Tenant: {cross_tenant_attempt.is_cross_tenant()}")
    print(f"     Operation: {cross_tenant_attempt.operation_type}")
    print(f"     Resource: {cross_tenant_attempt.resource_type}")
    
    # Demonstrate AccessViolation
    print("\n2. Access Violation...")
    violation = AccessViolation(
        user_id=user_id,
        attempted_tenant_id=tenant_id_2,
        actual_tenant_id=tenant_id_1,
        violation_type="cross_tenant_access",
        severity="high",
        blocked=True,
        details={
            "operation": "write",
            "resource_type": "custom_component",
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0...",
            "reason": "User attempted to access data from different tenant"
        }
    )
    
    print(f"   Access Violation:")
    print(f"     User: {violation.user_id}")
    print(f"     Attempted Tenant: {violation.attempted_tenant_id}")
    print(f"     Actual Tenant: {violation.actual_tenant_id}")
    print(f"     Violation Type: {violation.violation_type}")
    print(f"     Severity: {violation.severity}")
    print(f"     Blocked: {violation.blocked}")
    print(f"     Timestamp: {violation.timestamp}")
    
    # Convert to dictionary for logging
    print(f"\n   Violation as Dictionary:")
    violation_dict = violation.to_dict()
    for key, value in violation_dict.items():
        if key == 'details':
            print(f"     {key}:")
            for detail_key, detail_value in value.items():
                print(f"       {detail_key}: {detail_value}")
        else:
            print(f"     {key}: {value}")


def demo_tenant_isolation():
    """Demonstrate tenant isolation concepts."""
    print("\n=== Tenant Isolation Demo ===\n")
    
    tenant_1 = str(uuid.uuid4())
    tenant_2 = str(uuid.uuid4())
    
    print(f"1. Tenant Isolation Scenarios...")
    print(f"   Tenant 1: {tenant_1}")
    print(f"   Tenant 2: {tenant_2}")
    
    # Demonstrate query scoping
    print("\n2. Query Scoping Examples...")
    
    queries = [
        "SELECT * FROM visual_models",
        "SELECT * FROM visual_models WHERE name = 'test'",
        "UPDATE visual_models SET name = 'updated' WHERE id = '123'",
        "DELETE FROM visual_models WHERE status = 'draft'"
    ]
    
    for query in queries:
        print(f"\n   Original Query: {query}")
        
        # Simulate tenant scoping (simplified version)
        if "WHERE" in query.upper():
            scoped_query = query + f" AND tenant_id = '{tenant_1}'"
        else:
            scoped_query = query + f" WHERE tenant_id = '{tenant_1}'"
        
        print(f"   Scoped Query:   {scoped_query}")
    
    # Demonstrate data validation
    print("\n3. Data Validation Examples...")
    
    # Valid data (correct tenant)
    valid_data = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_1,
        "name": "My Visual Model",
        "description": "A sample visual model",
        "owner_id": str(uuid.uuid4())
    }
    
    print(f"   Valid Data (Tenant 1):")
    print(f"     Tenant ID in data: {valid_data['tenant_id']}")
    print(f"     Expected Tenant: {tenant_1}")
    print(f"     Validation: {'✓ Valid' if valid_data['tenant_id'] == tenant_1 else '✗ Invalid'}")
    
    # Invalid data (wrong tenant)
    invalid_data = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_2,  # Wrong tenant!
        "name": "Another Visual Model",
        "description": "This should be blocked",
        "owner_id": str(uuid.uuid4())
    }
    
    print(f"\n   Invalid Data (Wrong Tenant):")
    print(f"     Tenant ID in data: {invalid_data['tenant_id']}")
    print(f"     Expected Tenant: {tenant_1}")
    print(f"     Validation: {'✓ Valid' if invalid_data['tenant_id'] == tenant_1 else '✗ Invalid - Cross-tenant data access'}")


def main():
    """Run all demos."""
    print("=== Visual Editor Core Multi-Tenancy Components Demo ===\n")
    
    try:
        demo_tenant_info()
        demo_tenant_config()
        demo_tenant_context()
        demo_usage_metrics()
        demo_access_control()
        demo_tenant_isolation()
        
        print("\n=== All Demos Complete ===")
        
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()