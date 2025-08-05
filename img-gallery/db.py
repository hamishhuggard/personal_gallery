from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text, Integer, Table, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

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

# Create tables if they don't exist
def init_db():
    Base.metadata.create_all(engine)

# Helper to get a session
def get_session():
    return SessionLocal() 