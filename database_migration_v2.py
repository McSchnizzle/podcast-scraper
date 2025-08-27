#!/usr/bin/env python3
"""
Database Migration v2: Enhanced Status Tracking & Digest History
- Remove deprecated 'processed' column
- Enhance status tracking with explicit states
- Add digest inclusion history tracking
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

class DatabaseMigrationV2:
    def __init__(self, db_path="podcast_monitor.db"):
        self.db_path = db_path
        
    def backup_database(self):
        """Create backup before migration"""
        backup_path = f"podcast_monitor_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        import shutil
        shutil.copy2(self.db_path, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        return backup_path
    
    def check_current_schema(self):
        """Check current table structure"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if columns exist
        cursor.execute("PRAGMA table_info(episodes)")
        columns = cursor.fetchall()
        
        column_names = [col[1] for col in columns]
        
        has_processed = 'processed' in column_names
        has_status = 'status' in column_names
        has_digest_inclusions = 'digest_inclusions' in column_names
        
        print(f"📊 Current Schema Analysis:")
        print(f"  - processed column: {'✅ exists' if has_processed else '❌ missing'}")
        print(f"  - status column: {'✅ exists' if has_status else '❌ missing'}")  
        print(f"  - digest_inclusions column: {'✅ exists' if has_digest_inclusions else '❌ missing'}")
        
        conn.close()
        return has_processed, has_status, has_digest_inclusions
    
    def migrate_status_data(self):
        """Migrate existing processed flags to proper status values"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        print("🔄 Migrating status data...")
        
        # Get current data
        cursor.execute("SELECT id, processed, status, transcript_path FROM episodes")
        episodes = cursor.fetchall()
        
        migrations = []
        
        for episode_id, processed, current_status, transcript_path in episodes:
            # Determine new status based on current state
            if processed == 1 and transcript_path and Path(transcript_path).exists():
                new_status = 'transcribed'
            elif transcript_path and not Path(transcript_path).exists():
                new_status = 'pending'  # Transcript path set but file missing
            elif current_status == 'completed':
                new_status = 'transcribed'
            else:
                new_status = 'pending'
            
            migrations.append((new_status, episode_id))
        
        # Update all episodes with new status
        cursor.executemany("UPDATE episodes SET status = ? WHERE id = ?", migrations)
        
        print(f"  - Migrated {len(migrations)} episode statuses")
        
        # Show status distribution
        cursor.execute("SELECT status, COUNT(*) FROM episodes GROUP BY status")
        status_counts = cursor.fetchall()
        
        print("  - New status distribution:")
        for status, count in status_counts:
            print(f"    * {status}: {count}")
        
        conn.commit()
        conn.close()
    
    def add_digest_inclusions_column(self):
        """Add digest inclusion tracking column"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        print("➕ Adding digest_inclusions column...")
        
        try:
            cursor.execute("""
                ALTER TABLE episodes 
                ADD COLUMN digest_inclusions TEXT DEFAULT '[]'
            """)
            print("  ✅ digest_inclusions column added")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("  ✅ digest_inclusions column already exists")
            else:
                raise
        
        conn.commit()
        conn.close()
    
    def remove_processed_column(self):
        """Remove deprecated processed column"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        print("🗑️  Removing deprecated processed column...")
        
        try:
            # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
            # First, get the current table structure without the processed column
            cursor.execute("PRAGMA table_info(episodes)")
            columns = cursor.fetchall()
            
            # Filter out the processed column
            new_columns = []
            for col in columns:
                col_name = col[1]
                if col_name != 'processed':
                    col_type = col[2]
                    not_null = "NOT NULL" if col[3] else ""
                    default = f"DEFAULT {col[4]}" if col[4] is not None else ""
                    primary_key = "PRIMARY KEY AUTOINCREMENT" if col[5] else ""
                    
                    column_def = f"{col_name} {col_type} {not_null} {default} {primary_key}".strip()
                    new_columns.append(column_def)
            
            # Create new table without processed column
            new_table_sql = f"""
            CREATE TABLE episodes_new (
                {', '.join(new_columns)},
                FOREIGN KEY (feed_id) REFERENCES feeds (id)
            )
            """
            
            cursor.execute(new_table_sql)
            
            # Copy data (excluding processed column)
            copy_columns = [col[1] for col in columns if col[1] != 'processed']
            copy_sql = f"""
            INSERT INTO episodes_new ({', '.join(copy_columns)})
            SELECT {', '.join(copy_columns)} FROM episodes
            """
            
            cursor.execute(copy_sql)
            
            # Replace old table
            cursor.execute("DROP TABLE episodes")
            cursor.execute("ALTER TABLE episodes_new RENAME TO episodes")
            
            print("  ✅ processed column removed successfully")
            
        except Exception as e:
            print(f"  ❌ Error removing processed column: {e}")
            raise
        
        conn.commit()
        conn.close()
    
    def update_content_type_comment(self):
        """Update schema to clarify status column usage"""
        # Note: SQLite doesn't support modifying comments, but we can document the change
        print("📝 Status column now tracks processing stages:")
        print("    - 'pending': Episode discovered, awaiting transcription")
        print("    - 'transcribing': Currently being transcribed") 
        print("    - 'transcribed': Transcription completed")
        print("    - 'digested': Included in daily digest")
        print("    - 'failed': Transcription or processing failed")
    
    def validate_migration(self):
        """Validate the migration was successful"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        print("✅ Validating migration...")
        
        # Check schema
        cursor.execute("PRAGMA table_info(episodes)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        has_processed = 'processed' in column_names
        has_status = 'status' in column_names
        has_digest_inclusions = 'digest_inclusions' in column_names
        
        if has_processed:
            print("  ❌ processed column still exists!")
            return False
        
        if not has_status:
            print("  ❌ status column missing!")
            return False
            
        if not has_digest_inclusions:
            print("  ❌ digest_inclusions column missing!")
            return False
        
        # Check data integrity
        cursor.execute("SELECT COUNT(*) FROM episodes")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM episodes WHERE status IS NOT NULL")
        status_count = cursor.fetchone()[0]
        
        if total_count != status_count:
            print(f"  ❌ Data integrity issue: {total_count} total vs {status_count} with status")
            return False
        
        print("  ✅ Schema updated correctly")
        print("  ✅ Data integrity maintained")
        print(f"  ✅ {total_count} episodes migrated successfully")
        
        conn.close()
        return True
    
    def run_migration(self):
        """Execute the complete migration"""
        print("🚀 DATABASE MIGRATION v2: Enhanced Status Tracking")
        print("=" * 60)
        print(f"Database: {self.db_path}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        try:
            # 1. Backup database
            backup_path = self.backup_database()
            print()
            
            # 2. Check current schema
            has_processed, has_status, has_digest_inclusions = self.check_current_schema()
            print()
            
            # 3. Add digest_inclusions column if needed
            if not has_digest_inclusions:
                self.add_digest_inclusions_column()
                print()
            
            # 4. Migrate status data
            if has_processed:
                self.migrate_status_data()
                print()
            
            # 5. Remove processed column
            if has_processed:
                self.remove_processed_column()
                print()
            
            # 6. Update documentation
            self.update_content_type_comment()
            print()
            
            # 7. Validate migration
            success = self.validate_migration()
            print()
            
            if success:
                print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
                print(f"✅ Backup available at: {backup_path}")
                print("✅ Database schema updated")
                print("✅ Status tracking enhanced")  
                print("✅ Digest history tracking added")
            else:
                print("❌ MIGRATION VALIDATION FAILED!")
                print(f"💾 Restore from backup: {backup_path}")
                return False
                
        except Exception as e:
            print(f"❌ MIGRATION FAILED: {e}")
            print(f"💾 Restore from backup if needed")
            return False
        
        return True


def main():
    """CLI entry point"""
    import sys
    
    migrator = DatabaseMigrationV2()
    
    print("Database Migration v2 - Enhanced Status Tracking")
    print("=" * 50)
    
    # Show current state
    migrator.check_current_schema()
    print()
    
    # Check for auto-run flag
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        print("🚀 Auto-running migration...")
        success = migrator.run_migration()
    else:
        response = input("Proceed with migration? (y/N): ").strip().lower()
        if response != 'y':
            print("Migration cancelled.")
            return
        
        success = migrator.run_migration()
    
    if success:
        print("\n✅ Migration complete! You can now:")
        print("  - Use explicit status tracking (pending → transcribing → transcribed → digested)")
        print("  - Track digest inclusion history for each episode")
        print("  - Remove references to the old 'processed' column from your code")
    else:
        print("\n❌ Migration failed. Please check the backup and try again.")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())