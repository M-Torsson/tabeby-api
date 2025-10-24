"""
Run database migration to add is_active column to patient_profiles table
"""
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import engine
from sqlalchemy import text

def run_migration():
    print("Starting migration: add is_active column to patient_profiles")
    print("-" * 60)
    
    try:
        with engine.connect() as conn:
            # Check if column already exists
            print("Checking if is_active column exists...")
            check_sql = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='patient_profiles' AND column_name='is_active';
            """)
            result = conn.execute(check_sql)
            exists = result.fetchone()
            
            if exists:
                print("✓ Column 'is_active' already exists in patient_profiles table")
                print("Migration not needed - skipping")
            else:
                print("Column does not exist. Adding it now...")
                
                # Add column with default value TRUE
                print("Step 1: Adding is_active column...")
                alter_sql = text("""
                    ALTER TABLE patient_profiles 
                    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
                """)
                conn.execute(alter_sql)
                print("✓ Column added successfully")
                
                # Add index for performance
                print("Step 2: Creating index on is_active...")
                index_sql = text("""
                    CREATE INDEX ix_patient_profiles_is_active 
                    ON patient_profiles(is_active);
                """)
                conn.execute(index_sql)
                print("✓ Index created successfully")
                
                # Commit changes
                conn.commit()
                print("✓ Changes committed to database")
                
            # Verify the migration
            print("\nVerifying migration...")
            verify_sql = text("""
                SELECT COUNT(*) as total, 
                       SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active_count
                FROM patient_profiles;
            """)
            result = conn.execute(verify_sql)
            row = result.fetchone()
            
            if row:
                total = row[0]
                active = row[1]
                print(f"✓ Total patient profiles: {total}")
                print(f"✓ Active patients: {active}")
                print(f"✓ Inactive patients: {total - active}")
            
            print("-" * 60)
            print("✓ Migration completed successfully!")
            return True
            
    except Exception as e:
        print(f"\n✗ ERROR during migration:")
        print(f"  {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
