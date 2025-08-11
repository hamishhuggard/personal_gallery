from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text, Integer, Table, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import sqlite3
import os

DB_PATH = 'sqlite:///gallery_metadata.db'
Base = declarative_base()

# Junction table for many-to-many relationship between images and tags
image_tags = Table('image_tags', Base.metadata,
    Column('image_path', String, ForeignKey('images.path'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

class Tag(Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    images = relationship('ImageMeta', secondary=image_tags, back_populates='tags')

class ImageMeta(Base):
    __tablename__ = 'images'
    path = Column(String, primary_key=True)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=True)
    date = Column(String, nullable=True)  # ISO format string
    drawings_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tags = relationship('Tag', secondary=image_tags, back_populates='images')

engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

def migrate_database():
    """Migrate the database to add missing columns."""
    db_path = "gallery_metadata.db"
    
    if not os.path.exists(db_path):
        print("Database file not found. Creating new database...")
        return
    
    print(f"Checking database schema: {db_path}")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if drawings_count column exists
        cursor.execute("PRAGMA table_info(images)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'drawings_count' not in columns:
            print("Adding drawings_count column...")
            cursor.execute("ALTER TABLE images ADD COLUMN drawings_count INTEGER DEFAULT 1")
            print("✓ Added drawings_count column")
        
        if 'created_at' not in columns:
            print("Adding created_at column...")
            cursor.execute("ALTER TABLE images ADD COLUMN created_at DATETIME")
            print("✓ Added created_at column")
            
        if 'updated_at' not in columns:
            print("Adding updated_at column...")
            cursor.execute("ALTER TABLE images ADD COLUMN updated_at DATETIME")
            print("✓ Added updated_at column")
        
        # Commit the changes
        conn.commit()
        print("✓ Database schema check completed!")
        
    except Exception as e:
        print(f"Error during schema check: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

# Create tables if they don't exist
def init_db():
    # First create tables with current schema
    Base.metadata.create_all(engine)
    
    # Then migrate any existing database
    migrate_database()

# Helper to get a session
def get_session():
    return SessionLocal() 