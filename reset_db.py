"""
Database reset script - drops and recreates all tables
Run this when you have schema mismatches with PostgreSQL
"""
import sys
from pathlib import Path

# Add project to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from app import app  # noqa: E402
from storage import db  # noqa: E402

if __name__ == "__main__":
    with app.app_context():
        print("⚠️  Dropping all tables...")
        db.drop_all()
        print("✓ All tables dropped")
        
        print("🔄 Creating all tables with current schema...")
        db.create_all()
        print("✓ All tables created")
        
        print("👤 Seeding default users...")
        from storage import seed_default_users
        seed_default_users()
        print("✓ Default users created")
        
        print("\n✅ Database reset complete!")
        print("\nDefault credentials:")
        print("  - Admin: admin@prayash.local / prayash-admin")
        print("  - Student: student@prayash.local / Student@123")
