"""
User models for RPi PhotoDoc OCR application.
Now using SQLite database instead of JSON files.
"""

import logging
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, get_db_connection

logger = logging.getLogger(__name__)

class User(UserMixin):
    def __init__(self, id, username, password_hash, created_at=None, updated_at=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.created_at = created_at
        self.updated_at = updated_at

    def set_password(self, password):
        """Set user password with proper hashing"""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        """Check if provided password matches stored hash"""
        return check_password_hash(self.password_hash, password)

    def save(self):
        """Save user changes to database"""
        try:
            db = get_db()
            db.execute(
                'UPDATE users SET username = ?, password_hash = ? WHERE id = ?',
                (self.username, self.password_hash, self.id)
            )
            db.commit()
            logger.info(f"User {self.id} updated successfully")
            return True
        except Exception as e:
            logger.error(f"Error updating user {self.id}: {e}")
            return False

    @staticmethod
    def get(user_id):
        """Get user by ID"""
        try:
            db = get_db()
            user_row = db.execute(
                'SELECT id, username, password_hash, created_at, updated_at FROM users WHERE id = ?',
                (user_id,)
            ).fetchone()
            
            if user_row:
                return User(
                    id=user_row['id'],
                    username=user_row['username'], 
                    password_hash=user_row['password_hash'],
                    created_at=user_row['created_at'],
                    updated_at=user_row['updated_at']
                )
            return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None

    @staticmethod
    def get_by_username(username):
        """Get user by username"""
        try:
            db = get_db()
            user_row = db.execute(
                'SELECT id, username, password_hash, created_at, updated_at FROM users WHERE username = ?',
                (username,)
            ).fetchone()
            
            if user_row:
                return User(
                    id=user_row['id'],
                    username=user_row['username'],
                    password_hash=user_row['password_hash'],
                    created_at=user_row['created_at'],
                    updated_at=user_row['updated_at']
                )
            return None
        except Exception as e:
            logger.error(f"Error getting user by username {username}: {e}")
            return None

    @staticmethod
    def create(username, password):
        """Create a new user"""
        try:
            # Check if user already exists
            if User.get_by_username(username):
                logger.warning(f"User {username} already exists")
                return None
            
            password_hash = generate_password_hash(password, method='pbkdf2:sha256')
            
            db = get_db()
            cursor = db.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                (username, password_hash)
            )
            db.commit()
            
            user_id = cursor.lastrowid
            logger.info(f"User {username} created with ID {user_id}")
            
            return User.get(user_id)
            
        except Exception as e:
            logger.error(f"Error creating user {username}: {e}")
            return None

    @staticmethod
    def get_all():
        """Get all users (admin function)"""
        try:
            db = get_db()
            users = db.execute(
                'SELECT id, username, password_hash, created_at, updated_at FROM users ORDER BY created_at'
            ).fetchall()
            
            return [User(
                id=row['id'],
                username=row['username'],
                password_hash=row['password_hash'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            ) for row in users]
            
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []

    @staticmethod
    def delete(user_id):
        """Delete a user and all associated data"""
        try:
            db = get_db()
            db.execute('DELETE FROM users WHERE id = ?', (user_id,))
            db.commit()
            logger.info(f"User {user_id} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False

    def __repr__(self):
        return f'<User {self.username}>'

