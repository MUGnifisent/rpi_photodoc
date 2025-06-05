"""
Photo management for RPi PhotoDoc OCR application.
Now using SQLite database instead of JSON files.
"""

import uuid
import logging
from datetime import datetime
from database import get_db, get_db_connection

logger = logging.getLogger(__name__)

def create_photo(user_id, image_filename, original_ocr, ai_cleaned_text):
    """Create a new photo record"""
    try:
        photo_id = str(uuid.uuid4())
        
        db = get_db()
        db.execute('''
            INSERT INTO photos (id, user_id, image_filename, original_ocr_text, ai_cleaned_text, edited_text)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (photo_id, user_id, image_filename, original_ocr, ai_cleaned_text, ai_cleaned_text))
        db.commit()
        
        logger.info(f"Photo {photo_id} created for user {user_id}")
        return get_photo_by_id(photo_id, user_id)
        
    except Exception as e:
        logger.error(f"Error creating photo: {e}")
        return None

def get_photo_by_id(photo_id, user_id):
    """Get a specific photo by ID, ensuring it belongs to the user"""
    try:
        db = get_db()
        photo = db.execute('''
            SELECT id, user_id, image_filename, original_ocr_text, ai_cleaned_text, edited_text, 
                   created_at, updated_at
            FROM photos 
            WHERE id = ? AND user_id = ?
        ''', (photo_id, user_id)).fetchone()
        
        if photo:
            return {
                'id': photo['id'],
                'user_id': photo['user_id'],
                'image_filename': photo['image_filename'],
                'original_ocr_text': photo['original_ocr_text'],
                'ai_cleaned_text': photo['ai_cleaned_text'],
                'edited_text': photo['edited_text'],
                'created_at': photo['created_at'],
                'updated_at': photo['updated_at'],
                'created_at_dt': datetime.fromisoformat(photo['created_at'].replace('Z', '+00:00')) if photo['created_at'] else None
            }
        return None
        
    except Exception as e:
        logger.error(f"Error getting photo {photo_id}: {e}")
        return None

def load_all_photos_for_user(user_id):
    """Load all photos for a specific user"""
    try:
        db = get_db()
        photos = db.execute('''
            SELECT id, user_id, image_filename, original_ocr_text, ai_cleaned_text, edited_text,
                   created_at, updated_at
            FROM photos 
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,)).fetchall()
        
        result = []
        for photo in photos:
            result.append({
                'id': photo['id'],
                'user_id': photo['user_id'],
                'image_filename': photo['image_filename'],
                'original_ocr_text': photo['original_ocr_text'],
                'ai_cleaned_text': photo['ai_cleaned_text'],
                'edited_text': photo['edited_text'],
                'created_at': photo['created_at'],
                'updated_at': photo['updated_at'],
                'created_at_dt': datetime.fromisoformat(photo['created_at'].replace('Z', '+00:00')) if photo['created_at'] else None
            })
        
        logger.debug(f"Loaded {len(result)} photos for user {user_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error loading photos for user {user_id}: {e}")
        return []

def update_photo(user_id, photo_id, update_data):
    """Update a photo's data"""
    try:
        # Verify photo belongs to user
        if not get_photo_by_id(photo_id, user_id):
            logger.warning(f"Photo {photo_id} not found or doesn't belong to user {user_id}")
            return False
        
        # Build update query dynamically
        allowed_fields = ['edited_text', 'ai_cleaned_text', 'original_ocr_text']
        update_fields = []
        values = []
        
        for field, value in update_data.items():
            if field in allowed_fields:
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if not update_fields:
            logger.warning("No valid fields to update")
            return False
        
        values.append(photo_id)
        values.append(user_id)
        
        db = get_db()
        db.execute(f'''
            UPDATE photos 
            SET {", ".join(update_fields)}
            WHERE id = ? AND user_id = ?
        ''', values)
        db.commit()
        
        logger.info(f"Photo {photo_id} updated successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error updating photo {photo_id}: {e}")
        return False

def delete_photo(user_id, photo_id):
    """Delete a photo"""
    try:
        # Verify photo belongs to user
        if not get_photo_by_id(photo_id, user_id):
            logger.warning(f"Photo {photo_id} not found or doesn't belong to user {user_id}")
            return False
        
        db = get_db()
        db.execute('DELETE FROM photos WHERE id = ? AND user_id = ?', (photo_id, user_id))
        db.commit()
        
        logger.info(f"Photo {photo_id} deleted successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting photo {photo_id}: {e}")
        return False

def get_photos_count_for_user(user_id):
    """Get total number of photos for a user"""
    try:
        db = get_db()
        count = db.execute('SELECT COUNT(*) as count FROM photos WHERE user_id = ?', (user_id,)).fetchone()
        return count['count'] if count else 0
        
    except Exception as e:
        logger.error(f"Error getting photo count for user {user_id}: {e}")
        return 0

def search_photos_by_text(user_id, search_term):
    """Search photos by text content"""
    try:
        db = get_db()
        search_pattern = f"%{search_term}%"
        
        photos = db.execute('''
            SELECT id, user_id, image_filename, original_ocr_text, ai_cleaned_text, edited_text,
                   created_at, updated_at
            FROM photos 
            WHERE user_id = ? AND (
                original_ocr_text LIKE ? OR 
                ai_cleaned_text LIKE ? OR 
                edited_text LIKE ?
            )
            ORDER BY created_at DESC
        ''', (user_id, search_pattern, search_pattern, search_pattern)).fetchall()
        
        result = []
        for photo in photos:
            result.append({
                'id': photo['id'],
                'user_id': photo['user_id'],
                'image_filename': photo['image_filename'],
                'original_ocr_text': photo['original_ocr_text'],
                'ai_cleaned_text': photo['ai_cleaned_text'],
                'edited_text': photo['edited_text'],
                'created_at': photo['created_at'],
                'updated_at': photo['updated_at'],
                'created_at_dt': datetime.fromisoformat(photo['created_at'].replace('Z', '+00:00')) if photo['created_at'] else None
            })
        
        logger.info(f"Found {len(result)} photos matching '{search_term}' for user {user_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error searching photos for user {user_id}: {e}")
        return []