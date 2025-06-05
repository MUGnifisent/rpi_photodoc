"""
Document management for RPi PhotoDoc OCR application.
Now using SQLite database instead of JSON files.
"""

import uuid
import logging
from datetime import datetime
from database import get_db, get_db_connection

logger = logging.getLogger(__name__)

def create_document(user_id, name, photo_ids):
    """Create a new document with specified photos"""
    try:
        doc_id = str(uuid.uuid4())
        
        db = get_db()
        
        # Create the document
        db.execute('''
            INSERT INTO documents (id, user_id, name, combined_text, combined_text_generated_by_user)
            VALUES (?, ?, ?, ?, ?)
        ''', (doc_id, user_id, name or f"Document {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", "", False))
        
        # Add photos to document in specified order
        for index, photo_id in enumerate(photo_ids):
            db.execute('''
                INSERT INTO document_photos (document_id, photo_id, order_index)
                VALUES (?, ?, ?)
            ''', (doc_id, photo_id, index))
        
        db.commit()
        
        logger.info(f"Document {doc_id} created for user {user_id} with {len(photo_ids)} photos")
        return get_document_by_id(doc_id, user_id)
        
    except Exception as e:
        logger.error(f"Error creating document: {e}")
        return None

def get_document_by_id(doc_id, user_id):
    """Get a specific document by ID, ensuring it belongs to the user"""
    try:
        db = get_db()
        
        # Get document info
        doc = db.execute('''
            SELECT id, user_id, name, combined_text, combined_text_generated_by_user,
                   created_at, updated_at
            FROM documents 
            WHERE id = ? AND user_id = ?
        ''', (doc_id, user_id)).fetchone()
        
        if not doc:
            return None
        
        # Get photo IDs in order
        photo_rows = db.execute('''
            SELECT photo_id
            FROM document_photos
            WHERE document_id = ?
            ORDER BY order_index
        ''', (doc_id,)).fetchall()
        
        photo_ids = [row['photo_id'] for row in photo_rows]
        
        return {
            'id': doc['id'],
            'user_id': doc['user_id'],
            'name': doc['name'],
            'combined_text': doc['combined_text'],
            'combined_text_generated_by_user': bool(doc['combined_text_generated_by_user']),
            'photo_ids': photo_ids,
            'created_at': doc['created_at'],
            'updated_at': doc['updated_at'],
            'created_at_dt': datetime.fromisoformat(doc['created_at'].replace('Z', '+00:00')) if doc['created_at'] else None
        }
        
    except Exception as e:
        logger.error(f"Error getting document {doc_id}: {e}")
        return None

def load_all_documents_for_user(user_id):
    """Load all documents for a specific user"""
    try:
        db = get_db()
        
        docs = db.execute('''
            SELECT id, user_id, name, combined_text, combined_text_generated_by_user,
                   created_at, updated_at
            FROM documents 
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,)).fetchall()
        
        result = []
        for doc in docs:
            # Get photo IDs for each document
            photo_rows = db.execute('''
                SELECT photo_id
                FROM document_photos
                WHERE document_id = ?
                ORDER BY order_index
            ''', (doc['id'],)).fetchall()
            
            photo_ids = [row['photo_id'] for row in photo_rows]
            
            result.append({
                'id': doc['id'],
                'user_id': doc['user_id'],
                'name': doc['name'],
                'combined_text': doc['combined_text'],
                'combined_text_generated_by_user': bool(doc['combined_text_generated_by_user']),
                'photo_ids': photo_ids,
                'created_at': doc['created_at'],
                'updated_at': doc['updated_at'],
                'created_at_dt': datetime.fromisoformat(doc['created_at'].replace('Z', '+00:00')) if doc['created_at'] else None
            })
        
        logger.debug(f"Loaded {len(result)} documents for user {user_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error loading documents for user {user_id}: {e}")
        return []

def update_document(user_id, doc_id, update_data):
    """Update a document's data"""
    try:
        # Verify document belongs to user
        if not get_document_by_id(doc_id, user_id):
            logger.warning(f"Document {doc_id} not found or doesn't belong to user {user_id}")
            return False
        
        db = get_db()
        
        # Handle photo_ids update separately (affects junction table)
        if 'photo_ids' in update_data:
            photo_ids = update_data.pop('photo_ids')
            
            # Delete existing photo associations
            db.execute('DELETE FROM document_photos WHERE document_id = ?', (doc_id,))
            
            # Add new photo associations
            for index, photo_id in enumerate(photo_ids):
                db.execute('''
                    INSERT INTO document_photos (document_id, photo_id, order_index)
                    VALUES (?, ?, ?)
                ''', (doc_id, photo_id, index))
        
        # Handle other fields
        allowed_fields = ['name', 'combined_text', 'combined_text_generated_by_user']
        update_fields = []
        values = []
        
        for field, value in update_data.items():
            if field in allowed_fields:
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if update_fields:
            values.append(doc_id)
            values.append(user_id)
            
            db.execute(f'''
                UPDATE documents 
                SET {", ".join(update_fields)}
                WHERE id = ? AND user_id = ?
            ''', values)
        
        db.commit()
        
        logger.info(f"Document {doc_id} updated successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error updating document {doc_id}: {e}")
        return False

def delete_document(user_id, doc_id):
    """Delete a document and its photo associations"""
    try:
        # Verify document belongs to user
        if not get_document_by_id(doc_id, user_id):
            logger.warning(f"Document {doc_id} not found or doesn't belong to user {user_id}")
            return False
        
        db = get_db()
        
        # Delete document (CASCADE will handle document_photos)
        db.execute('DELETE FROM documents WHERE id = ? AND user_id = ?', (doc_id, user_id))
        db.commit()
        
        logger.info(f"Document {doc_id} deleted successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting document {doc_id}: {e}")
        return False

def remove_photo_from_document(user_id, doc_id, photo_id):
    """Remove a specific photo from a document"""
    try:
        # Verify document belongs to user
        doc = get_document_by_id(doc_id, user_id)
        if not doc:
            logger.warning(f"Document {doc_id} not found or doesn't belong to user {user_id}")
            return False
        
        if photo_id not in doc['photo_ids']:
            logger.warning(f"Photo {photo_id} not in document {doc_id}")
            return False
        
        db = get_db()
        
        # Remove the photo from document
        db.execute('''
            DELETE FROM document_photos 
            WHERE document_id = ? AND photo_id = ?
        ''', (doc_id, photo_id))
        
        # Reorder remaining photos
        remaining_photos = db.execute('''
            SELECT photo_id FROM document_photos
            WHERE document_id = ?
            ORDER BY order_index
        ''', (doc_id,)).fetchall()
        
        # Delete all and re-insert with correct order
        db.execute('DELETE FROM document_photos WHERE document_id = ?', (doc_id,))
        
        for index, row in enumerate(remaining_photos):
            db.execute('''
                INSERT INTO document_photos (document_id, photo_id, order_index)
                VALUES (?, ?, ?)
            ''', (doc_id, row['photo_id'], index))
        
        db.commit()
        
        logger.info(f"Photo {photo_id} removed from document {doc_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error removing photo {photo_id} from document {doc_id}: {e}")
        return False

def get_documents_containing_photo(photo_id, user_id):
    """Get all documents that contain a specific photo"""
    try:
        db = get_db()
        
        docs = db.execute('''
            SELECT d.id, d.name, d.created_at
            FROM documents d
            JOIN document_photos dp ON d.id = dp.document_id
            WHERE dp.photo_id = ? AND d.user_id = ?
            ORDER BY d.created_at DESC
        ''', (photo_id, user_id)).fetchall()
        
        result = []
        for doc in docs:
            result.append({
                'id': doc['id'],
                'name': doc['name'],
                'created_at': doc['created_at'],
                'created_at_dt': datetime.fromisoformat(doc['created_at'].replace('Z', '+00:00')) if doc['created_at'] else None
            })
        
        logger.debug(f"Found {len(result)} documents containing photo {photo_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error finding documents containing photo {photo_id}: {e}")
        return []

def get_documents_count_for_user(user_id):
    """Get total number of documents for a user"""
    try:
        db = get_db()
        count = db.execute('SELECT COUNT(*) as count FROM documents WHERE user_id = ?', (user_id,)).fetchone()
        return count['count'] if count else 0
        
    except Exception as e:
        logger.error(f"Error getting document count for user {user_id}: {e}")
        return 0

def search_documents_by_text(user_id, search_term):
    """Search documents by name or combined text"""
    try:
        db = get_db()
        search_pattern = f"%{search_term}%"
        
        docs = db.execute('''
            SELECT id, user_id, name, combined_text, combined_text_generated_by_user,
                   created_at, updated_at
            FROM documents 
            WHERE user_id = ? AND (name LIKE ? OR combined_text LIKE ?)
            ORDER BY created_at DESC
        ''', (user_id, search_pattern, search_pattern)).fetchall()
        
        result = []
        for doc in docs:
            # Get photo IDs for each document
            photo_rows = db.execute('''
                SELECT photo_id
                FROM document_photos
                WHERE document_id = ?
                ORDER BY order_index
            ''', (doc['id'],)).fetchall()
            
            photo_ids = [row['photo_id'] for row in photo_rows]
            
            result.append({
                'id': doc['id'],
                'user_id': doc['user_id'],
                'name': doc['name'],
                'combined_text': doc['combined_text'],
                'combined_text_generated_by_user': bool(doc['combined_text_generated_by_user']),
                'photo_ids': photo_ids,
                'created_at': doc['created_at'],
                'updated_at': doc['updated_at'],
                'created_at_dt': datetime.fromisoformat(doc['created_at'].replace('Z', '+00:00')) if doc['created_at'] else None
            })
        
        logger.info(f"Found {len(result)} documents matching '{search_term}' for user {user_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error searching documents for user {user_id}: {e}")
        return []