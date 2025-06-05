"""
Database initialization and management for RPi PhotoDoc OCR application.
Replaces JSON file storage with SQLite for better performance and data integrity.
"""

import sqlite3
import os
import logging
from datetime import datetime
from flask import current_app, g
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DATABASE_NAME = 'photodoc.db'

def get_db_path():
    """Get the path to the SQLite database file"""
    config_dir = os.path.join(current_app.root_path, 'config')
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, DATABASE_NAME)

def get_db():
    """Get database connection for the current request"""
    if 'db' not in g:
        g.db = sqlite3.connect(get_db_path())
        g.db.row_factory = sqlite3.Row  # Enable column access by name
    return g.db

def close_db(e=None):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

@contextmanager
def get_db_connection():
    """Context manager for database connections outside request context"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initialize the database with schema"""
    db_path = get_db_path()
    
    # Create database directory if it doesn't exist
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    with get_db_connection() as conn:
        # Create tables
        conn.executescript('''
        -- Users table
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Photos table
        CREATE TABLE IF NOT EXISTS photos (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            image_filename TEXT NOT NULL,
            original_ocr_text TEXT,
            ai_cleaned_text TEXT,
            edited_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        
        -- Documents table
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            combined_text TEXT DEFAULT '',
            combined_text_generated_by_user BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        
        -- Document photos junction table (for photo ordering in documents)
        CREATE TABLE IF NOT EXISTS document_photos (
            document_id TEXT NOT NULL,
            photo_id TEXT NOT NULL,
            order_index INTEGER NOT NULL,
            PRIMARY KEY (document_id, photo_id),
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE,
            FOREIGN KEY (photo_id) REFERENCES photos (id) ON DELETE CASCADE
        );
        
        -- User settings table (per-user preferences)
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,     -- 'image_enhancement', 'ocr', 'ui'
            setting_key TEXT NOT NULL,
            setting_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, category, setting_key),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        
        -- Indexes for better performance
        CREATE INDEX IF NOT EXISTS idx_photos_user_id ON photos(user_id);
        CREATE INDEX IF NOT EXISTS idx_photos_created_at ON photos(created_at);
        CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
        CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
        CREATE INDEX IF NOT EXISTS idx_document_photos_order ON document_photos(document_id, order_index);
        CREATE INDEX IF NOT EXISTS idx_user_settings_user_category ON user_settings(user_id, category);
        
        -- Triggers to automatically update timestamps
        CREATE TRIGGER IF NOT EXISTS update_users_timestamp 
            AFTER UPDATE ON users
        BEGIN
            UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS update_photos_timestamp 
            AFTER UPDATE ON photos
        BEGIN
            UPDATE photos SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS update_documents_timestamp 
            AFTER UPDATE ON documents
        BEGIN
            UPDATE documents SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS update_user_settings_timestamp 
            AFTER UPDATE ON user_settings
        BEGIN
            UPDATE user_settings SET updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = NEW.user_id AND category = NEW.category AND setting_key = NEW.setting_key;
        END;
        ''')
        
        logger.info(f"Database initialized successfully at {db_path}")

def reset_db():
    """Reset the database by dropping all tables and recreating them"""
    db_path = get_db_path()
    
    with get_db_connection() as conn:
        # Drop all triggers first
        conn.execute("DROP TRIGGER IF EXISTS update_users_timestamp")
        conn.execute("DROP TRIGGER IF EXISTS update_photos_timestamp") 
        conn.execute("DROP TRIGGER IF EXISTS update_documents_timestamp")
        conn.execute("DROP TRIGGER IF EXISTS update_user_settings_timestamp")
        
        # Drop all tables
        conn.execute("DROP TABLE IF EXISTS document_photos")
        conn.execute("DROP TABLE IF EXISTS documents")
        conn.execute("DROP TABLE IF EXISTS photos")
        conn.execute("DROP TABLE IF EXISTS user_settings")
        conn.execute("DROP TABLE IF EXISTS users")
        
        logger.info("Database reset - all tables dropped")
    
    # Recreate database
    init_db()

def init_app(app):
    """Initialize database with Flask app"""
    app.teardown_appcontext(close_db)
    
    # Initialize database on first run
    with app.app_context():
        init_db()