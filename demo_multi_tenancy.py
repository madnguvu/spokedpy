"""
Demo script for the Multi-Tenancy System.

This script demonstrates the key features of the multi-tenancy system including:
- Tenant creation and management
- Data isolation and access control
- Cross-tenant access prevention
- Usage metrics and monitoring
"""

import uuid
from datetime import datetime
from visual_editor_core.database import (
    DatabaseManager,
    DatabaseConfig,
    DatabaseType,
    MultiTenantManager,
    TenantInfo,
    TenantConfig
)


def demo_multi_tenancy():
    """Demonstrate multi-tenancy features."""
    print("=== Visual Editor Core Multi-Tenancy System Demo ===\n")
    
    # Initialize database manager with SQLite for demo
    print("1. Initializing Database Manager...")
    sqlite_config = DatabaseConfig(
        database_type=DatabaseType.SQLITE,
        database="demo_multitenancy.db"
    )
    
    db_manager = DatabaseManager(sqlite_config=sqlite_config)
    
    # Initialize multi-tenant manager
    print("2. Initializing Multi-Tenant Manager...")
    tenant_manager = db_manager.get_multi_tenant_manager()
    
    # Create sample tenants
    print("\n3. Creating Sample Tenants...")
    
    # Tenant 1: Acme Corp
    acme_tenant_info = TenantInfo(
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
        }
    )
    
    try:
        acme_tenant_id = tenant_manager.create_tenant(acme_tenant_info)
        print(f"   ✓ Created Acme Corp tenant: {acme_tenant_id}")
    except Exception as e:
        print(f"   ✗ Failed to create Acme Corp tenant: {e}")
        return
    
    # Tenant 2: StartupXYZ
    startup_tenant_info = TenantInfo(
        name="StartupXYZ",
        domain="startupxyz.example.com",
        configuration={
            "theme": "modern",
            "language": "en",
            "timezone": "America/Los_Angeles"
        },
        resource_limits={
            "max_models": 100,
            "max_executions_per_hour": 1000,
            "max_storage_mb": 1024
        },
        billing_info={
            "plan": "startup",
            "billing_email": "admin@startupxyz.com"
        }
    )
    
    try:
        startup_tenant_id = tenant_manager.create_tenant(startup_tenant_info)
        print(f"   ✓ Created StartupXYZ tenant: {startup_tenant_id}")
    except Exception as e:
        print(f"   ✗ Failed to create StartupXYZ tenant: {e}")
        return
    
    # Demonstrate tenant configuration
    print("\n4. Configuring Tenant Settings...")
    
    # Update Acme Corp configuration
    acme_config = tenant_manager.get_tenant_configuration(acme_tenant_id)
    acme_config.set_setting("debug_mode", False)
    acme_config.feature_flags["advanced_analytics"] = True
    acme_config.feature_flags["collaboration"] = True
    
    if tenant_manager.update_tenant_configuration(acme_tenant_id, acme_config):
        print("   ✓ Updated Acme Corp configuration")
    else:
        print("   ✗ Failed to update Acme Corp configuration")
    
    # Update StartupXYZ configuration
    startup_config = tenant_manager.get_tenant_configuration(startup_tenant_id)
    startup_config.set_setting("debug_mode", True)
    startup_config.feature_flags["advanced_analytics"] = False
    startup_config.feature_flags["collaboration"] = True
    
    if tenant_manager.update_tenant_configuration(startup_tenant_id, startup_config):
        print("   ✓ Updated StartupXYZ configuration")
    else:
        print("   ✗ Failed to update StartupXYZ configuration")
    
    # Demonstrate access control
    print("\n5. Testing Access Control...")
    
    # Create sample user IDs
    acme_user_id = str(uuid.uuid4())
    startup_user_id = str(uuid.uuid4())
    
    print(f"   Acme user: {acme_user_id}")
    print(f"   Startup user: {startup_user_id}")
    
    # Test valid access
    is_valid, error = tenant_manager.validate_tenant_access(
        acme_user_id, acme_tenant_id, "read", "visual_model"
    )
    print(f"   Acme user accessing Acme tenant: {'✓ Allowed' if is_valid else f'✗ Denied - {error}'}")
    
    # Test cross-tenant access (should be denied)
    is_valid, error = tenant_manager.validate_tenant_access(
        acme_user_id, startup_tenant_id, "read", "visual_model"
    )
    print(f"   Acme user accessing Startup tenant: {'✓ Allowed' if is_valid else f'✗ Denied - {error}'}")
    
    # Demonstrate query safety validation
    print("\n6. Testing Query Safety...")
    
    # Safe query
    safe_query = "SELECT * FROM visual_models WHERE name = 'test'"
    is_safe, violations = tenant_manager.validate_query_safety(safe_query, acme_tenant_id)
    print(f"   Safe query: {'✓ Safe' if is_safe else f'✗ Unsafe - {violations}'}")
    
    # Potentially unsafe query
    unsafe_query = "DELETE FROM visual_models"
    is_safe, violations = tenant_manager.validate_query_safety(unsafe_query, acme_tenant_id)
    print(f"   Unsafe query: {'✓ Safe' if is_safe else f'✗ Unsafe - {violations}'}")
    
    # Demonstrate tenant isolation
    print("\n7. Testing Tenant Isolation...")
    
    original_query = "SELECT * FROM visual_models"
    scoped_query = tenant_manager.enforce_tenant_isolation(original_query, acme_tenant_id)
    print(f"   Original query: {original_query}")
    print(f"   Scoped query: {scoped_query}")
    
    # Demonstrate usage metrics
    print("\n8. Getting Usage Metrics...")
    
    acme_metrics = tenant_manager.get_tenant_usage_metrics(acme_tenant_id)
    print(f"   Acme Corp metrics:")
    print(f"     - Models created: {acme_metrics.models_created}")
    print(f"     - Storage used: {acme_metrics.storage_used} bytes")
    print(f"     - Executions performed: {acme_metrics.executions_performed}")
    print(f"     - Active connections: {acme_metrics.active_connections}")
    
    startup_metrics = tenant_manager.get_tenant_usage_metrics(startup_tenant_id)
    print(f"   StartupXYZ metrics:")
    print(f"     - Models created: {startup_metrics.models_created}")
    print(f"     - Storage used: {startup_metrics.storage_used} bytes")
    print(f"     - Executions performed: {startup_metrics.executions_performed}")
    print(f"     - Active connections: {startup_metrics.active_connections}")
    
    # Demonstrate access violation monitoring
    print("\n9. Access Violation Summary...")
    
    violation_summary = tenant_manager.get_access_violation_summary()
    print(f"   Total violations: {violation_summary.get('total_violations', 0)}")
    print(f"   Blocked violations: {violation_summary.get('blocked_violations', 0)}")
    
    if violation_summary.get('violation_types'):
        print("   Violation types:")
        for vtype, count in violation_summary['violation_types'].items():
            print(f"     - {vtype}: {count}")
    
    # Demonstrate tenant operation context
    print("\n10. Using Tenant Operation Context...")
    
    try:
        with tenant_manager.tenant_operation_context(acme_user_id, acme_tenant_id) as context:
            print(f"   ✓ Operating in tenant context: {context}")
            print("   ✓ All operations in this context are automatically scoped to Acme Corp")
    except Exception as e:
        print(f"   ✗ Failed to create tenant context: {e}")
    
    # Demonstrate data export
    print("\n11. Exporting Tenant Data...")
    
    export_result = tenant_manager.export_tenant_data(acme_tenant_id)
    if export_result.success:
        print(f"   ✓ Exported Acme Corp data to: {export_result.export_path}")
        print(f"   ✓ Export size: {export_result.export_size} bytes")
        print(f"   ✓ Exported tables: {', '.join(export_result.exported_tables)}")
    else:
        print(f"   ✗ Failed to export data: {export_result.error_message}")
    
    # Cleanup
    print("\n12. Cleanup...")
    
    try:
        tenant_manager.shutdown()
        db_manager.close()
        print("   ✓ Multi-tenant manager and database manager closed")
    except Exception as e:
        print(f"   ✗ Error during cleanup: {e}")
    
    print("\n=== Multi-Tenancy Demo Complete ===")


def demo_tenant_features():
    """Demonstrate specific tenant features."""
    print("\n=== Tenant Features Demo ===\n")
    
    # Demonstrate TenantInfo validation
    print("1. Tenant Info Validation...")
    
    # Valid tenant info
    valid_tenant = TenantInfo(
        name="Valid Tenant",
        domain="valid.example.com",
        status="active"
    )
    errors = valid_tenant.validate()
    print(f"   Valid tenant errors: {len(errors)} ({'✓ Valid' if len(errors) == 0 else '✗ Invalid'})")
    
    # Invalid tenant info
    invalid_tenant = TenantInfo(
        name="",  # Empty name
        domain="",  # Empty domain
        status="invalid_status"  # Invalid status
    )
    errors = invalid_tenant.validate()
    print(f"   Invalid tenant errors: {len(errors)} ({'✓ Valid' if len(errors) == 0 else '✗ Invalid'})")
    for error in errors:
        print(f"     - {error}")
    
    # Demonstrate TenantConfig features
    print("\n2. Tenant Configuration Features...")
    
    config = TenantConfig(tenant_id=str(uuid.uuid4()))
    
    # Setting and getting configuration values
    config.set_setting("theme", "dark")
    config.set_setting("language", "en")
    theme = config.get_setting("theme")
    language = config.get_setting("language")
    unknown = config.get_setting("unknown_setting", "default_value")
    
    print(f"   Theme setting: {theme}")
    print(f"   Language setting: {language}")
    print(f"   Unknown setting (with default): {unknown}")
    
    # Feature flags
    config.feature_flags["debug_mode"] = True
    config.feature_flags["analytics"] = False
    
    print(f"   Debug mode enabled: {config.is_feature_enabled('debug_mode')}")
    print(f"   Analytics enabled: {config.is_feature_enabled('analytics')}")
    print(f"   Unknown feature enabled: {config.is_feature_enabled('unknown_feature')}")
    
    print("\n=== Tenant Features Demo Complete ===")


if __name__ == "__main__":
    try:
        demo_multi_tenancy()
        demo_tenant_features()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()