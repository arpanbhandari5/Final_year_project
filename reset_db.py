"""
Database reset script - drops and recreates all tables
Run this when you have schema mismatches with PostgreSQL
"""
import os
from pathlib import Path

# Add project to path
BASE_DIR = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(BASE_DIR))

from app import app
from storage import db, User, Upload, Feedback

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
        print(f"  - Admin: admin@prayash.local / prayash-admin")
        print(f"  - Student: student / student")
