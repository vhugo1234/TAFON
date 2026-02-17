# -*- coding: utf-8 -*-
# backend/scripts/add_start_time_column.py
"""
Script to add start_time column to candidates table in ALL tenant schemas.

Usage:
    docker-compose exec backend python scripts/add_start_time_column.py
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text, inspect
from app.db.connection import engine
from app.db.models.public import Tenant

def add_start_time_column_to_all_tenants():
    """Add start_time column to all tenant schemas."""
    
    print("=" * 80)
    print("MIGRATION: Add start_time column to candidates table")
    print("=" * 80)
    
    with engine.begin() as conn:
        # 1. Get all tenants
        conn.execute(text("SET search_path TO public"))
        result = conn.execute(text("SELECT id, schema_name, nome_empresa FROM tenants ORDER BY id"))
        tenants = result.fetchall()
        
        if not tenants:
            print("\nNo tenants found in database.")
            return
        
        print(f"\nFound {len(tenants)} tenants:")
        for tenant in tenants:
            print(f"   - {tenant.id}: {tenant.schema_name} ({tenant.nome_empresa})")
        
        print("\n" + "=" * 80)
        
        # 2. Add column to each tenant schema if not exists
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for tenant in tenants:
            tenant_id, schema_name, nome_empresa = tenant
            
            try:
                # Switch to tenant schema
                conn.execute(text(f'SET search_path TO "{schema_name}"'))
                
                # Check if column already exists
                inspector = inspect(conn)
                columns = [col['name'] for col in inspector.get_columns('candidates')]
                
                if 'start_time' in columns:
                    print(f"SKIP  '{schema_name}': start_time column already exists")
                    skip_count += 1
                    continue
                
                # Add column
                conn.execute(text("""
                    ALTER TABLE candidates 
                    ADD COLUMN start_time VARCHAR(5) NULL
                """))
                
                print(f"OK    '{schema_name}': start_time column added successfully!")
                success_count += 1
                
            except Exception as e:
                print(f"ERROR '{schema_name}': {e}")
                error_count += 1
        
        # 3. Restore search_path
        conn.execute(text("SET search_path TO public"))
        
        # 4. Summary
        print("\n" + "=" * 80)
        print("MIGRATION SUMMARY:")
        print(f"   OK:    {success_count} schemas updated")
        print(f"   SKIP:  {skip_count} schemas (column already existed)")
        print(f"   ERROR: {error_count} schemas with errors")
        print(f"   TOTAL: {len(tenants)} schemas processed")
        print("=" * 80)
        
        if error_count > 0:
            print("\nSome schemas had errors. Check logs above.")
            return False
        else:
            print("\nMigration completed successfully in all schemas!")
            return True


if __name__ == "__main__":
    try:
        success = add_start_time_column_to_all_tenants()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
