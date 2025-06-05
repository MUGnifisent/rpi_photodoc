import json
import os
import uuid
from datetime import datetime
from flask import current_app

DOCUMENTS_DATA_FILE = 'config/documents.json'

def get_documents_data_path():
    return os.path.join(current_app.root_path, DOCUMENTS_DATA_FILE)

def load_all_documents_for_user(user_id):
    try:
        with open(get_documents_data_path(), 'r', encoding='utf-8') as f:
            all_docs = json.load(f)
            return [doc for doc in all_docs if doc.get('user_id') == user_id]
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def get_document_by_id(doc_id, user_id):
    user_docs = load_all_documents_for_user(user_id)
    for doc in user_docs:
        if doc['id'] == doc_id:
            return doc
    return None

def save_all_documents(all_docs_list):
    try:
        with open(get_documents_data_path(), 'w', encoding='utf-8') as f:
            json.dump(all_docs_list, f, indent=4, ensure_ascii=False)
    except Exception as e:
        current_app.logger.error(f"Error saving documents: {e}")

def create_document(user_id, name, photo_ids):
    doc_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    new_doc = {
        "id": doc_id,
        "name": name if name else f"Document {timestamp}",
        "user_id": user_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "photo_ids": photo_ids, # List of photo IDs (pages)
        "combined_text": "",
        "combined_text_generated_by_user": False
    }
    all_docs = []
    try:
        with open(get_documents_data_path(), 'r', encoding='utf-8') as f:
            all_docs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_docs = []
    all_docs.append(new_doc)
    save_all_documents(all_docs)
    return new_doc

def update_document(user_id, doc_id, updated_data):
    all_docs = []
    try:
        with open(get_documents_data_path(), 'r', encoding='utf-8') as f:
            all_docs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    doc_found = False
    for i, doc in enumerate(all_docs):
        if doc['id'] == doc_id and doc.get('user_id') == user_id:
            for key, value in updated_data.items():
                if key not in ['id', 'user_id', 'created_at']:
                    doc[key] = value
            doc['updated_at'] = datetime.utcnow().isoformat()
            all_docs[i] = doc
            doc_found = True
            break
    if doc_found:
        save_all_documents(all_docs)
        return True
    return False

def delete_document(user_id, doc_id):
    all_docs = []
    try:
        with open(get_documents_data_path(), 'r', encoding='utf-8') as f:
            all_docs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    original_len = len(all_docs)
    all_docs = [doc for doc in all_docs if not (doc['id'] == doc_id and doc.get('user_id') == user_id)]
    if len(all_docs) < original_len:
        save_all_documents(all_docs)
        return True
    return False

def remove_photo_from_document(user_id, doc_id, photo_id):
    """Remove a photo from a document without deleting the photo itself"""
    all_docs = []
    try:
        with open(get_documents_data_path(), 'r', encoding='utf-8') as f:
            all_docs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        current_app.logger.error(f"Error: {DOCUMENTS_DATA_FILE} not found when trying to remove photo from document.")
        return False

    doc_found = False
    for i, doc in enumerate(all_docs):
        if doc['id'] == doc_id and doc.get('user_id') == user_id:
            if 'photo_ids' in doc and photo_id in doc['photo_ids']:
                doc['photo_ids'].remove(photo_id)
                doc['updated_at'] = datetime.utcnow().isoformat()
                
                # Regenerate combined_text if the document had any pages
                # We need to get the remaining photos to regenerate combined text
                # This requires importing photo_manager, but we'll handle this in the route
                
                all_docs[i] = doc
                doc_found = True
                current_app.logger.info(f"Removed photo {photo_id} from document {doc_id}")
                break
            else:
                current_app.logger.warning(f"Photo {photo_id} not found in document {doc_id}")
                return False
    
    if doc_found:
        save_all_documents(all_docs)
        return True
    else:
        current_app.logger.warning(f"Document {doc_id} not found for user {user_id} when trying to remove photo.")
        return False

def get_documents_containing_photo(photo_id, user_id=None):
    """Get all documents that contain a specific photo"""
    try:
        with open(get_documents_data_path(), 'r', encoding='utf-8') as f:
            all_docs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    
    containing_docs = []
    for doc in all_docs:
        if user_id and doc.get('user_id') != user_id:
            continue
        if 'photo_ids' in doc and photo_id in doc['photo_ids']:
            containing_docs.append(doc)
    
    return containing_docs

def add_page_to_document(user_id, doc_id, page_data):
    all_docs = []
    try:
        with open(get_documents_data_path(), 'r', encoding='utf-8') as f:
            all_docs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        current_app.logger.error(f"Error: {DOCUMENTS_DATA_FILE} not found when trying to add a page.")
        return None # Or raise an error

    doc_found = False
    updated_doc = None
    for i, doc in enumerate(all_docs):
        if doc['id'] == doc_id and doc.get('user_id') == user_id:
            if 'pages' not in doc or not isinstance(doc['pages'], list):
                doc['pages'] = [] # Initialize if pages list is missing or not a list
            
            # Determine the order for the new page
            page_order = len(doc['pages'])
            page_data['order'] = page_order
            
            doc['pages'].append(page_data)
            doc['updated_at'] = datetime.utcnow().isoformat()
            
            # Update combined_text by joining edited_text of all pages
            combined_texts = []
            for page in sorted(doc['pages'], key=lambda p: p.get('order', 0)):
                combined_texts.append(page.get('edited_text', ''))
            doc['combined_text'] = "\n\n---\n\n".join(combined_texts) # Separator for clarity
            
            all_docs[i] = doc
            updated_doc = doc
            doc_found = True
            break
    
    if doc_found:
        save_all_documents(all_docs)
        return updated_doc
    else:
        current_app.logger.warning(f"Document {doc_id} not found for user {user_id} when trying to add a page.")
        return None

def update_page_in_document(user_id, doc_id, page_index, updated_page_data):
    all_docs = []
    try:
        with open(get_documents_data_path(), 'r', encoding='utf-8') as f:
            all_docs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        current_app.logger.error(f"Error: {DOCUMENTS_DATA_FILE} not found when trying to update a page.")
        return False

    doc_found = False
    for i, doc in enumerate(all_docs):
        if doc['id'] == doc_id and doc.get('user_id') == user_id:
            if 'pages' in doc and 0 <= page_index < len(doc['pages']):
                # Update specific fields in the page, don't overwrite the whole page object unless necessary
                for key, value in updated_page_data.items():
                    doc['pages'][page_index][key] = value
                
                doc['updated_at'] = datetime.utcnow().isoformat()
                
                # Recalculate combined_text if edited_text of a page changed
                if 'edited_text' in updated_page_data:
                    combined_texts = []
                    for page in sorted(doc['pages'], key=lambda p: p.get('order', 0)):
                        combined_texts.append(page.get('edited_text', ''))
                    doc['combined_text'] = "\n\n---\n\n".join(combined_texts)
                    # If combined text is auto-updated, ensure it's not marked as user-generated
                    doc['combined_text_generated_by_user'] = False 

                all_docs[i] = doc
                doc_found = True
                break
            else:
                current_app.logger.error(f"Page index {page_index} out of bounds for doc {doc_id}.")
                return False # Page not found
    
    if doc_found:
        save_all_documents(all_docs)
        return True
    else:
        current_app.logger.warning(f"Document {doc_id} not found for user {user_id} when trying to update a page.")
        return False

def create_document_from_sources(user_id, source_doc_ids, new_doc_name):
    all_user_docs = load_all_documents_for_user(user_id)
    source_docs_data = [doc for doc in all_user_docs if doc['id'] in source_doc_ids]

    if not source_docs_data or len(source_docs_data) != len(source_doc_ids):
        current_app.logger.error(f"Not all source documents found for user {user_id}. Requested: {source_doc_ids}, Found: {[d['id'] for d in source_docs_data]}")
        return None # Or raise error

    # Sort source documents by their creation date to maintain a somewhat logical order of pages
    source_docs_data.sort(key=lambda d: d.get('created_at', ''))

    new_pages = []
    current_page_order = 0
    all_original_ocr_texts = []
    all_ai_cleaned_texts = []
    all_edited_texts = []

    for src_doc in source_docs_data:
        for page in sorted(src_doc.get('pages', []), key=lambda p: p.get('order', 0)):
            new_page = page.copy() # Avoid modifying original page data directly
            new_page['order'] = current_page_order
            new_pages.append(new_page)
            
            all_original_ocr_texts.append(page.get('original_ocr_text', ''))
            all_ai_cleaned_texts.append(page.get('ai_cleaned_text', ''))
            all_edited_texts.append(page.get('edited_text', ''))
            current_page_order += 1

    if not new_pages:
        current_app.logger.warning(f"No pages found in source documents for user {user_id}. Sources: {source_doc_ids}")
        return None

    timestamp = datetime.utcnow().isoformat()
    new_doc_id = str(uuid.uuid4())
    
    # For the new combined text, use the edited_text from all pages
    combined_text = "\n\n---\n\n".join(all_edited_texts)

    new_document = {
        "id": new_doc_id,
        "name": new_doc_name if new_doc_name else f"Joined Document - {timestamp}",
        "user_id": user_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "pages": new_pages,
        "combined_text": combined_text,
        "combined_text_generated_by_user": False, # Initially auto-generated
        "source_document_ids": source_doc_ids # Keep track of sources for potential future use
    }

    # Load all documents from the file
    all_docs_in_file = []
    try:
        with open(get_documents_data_path(), 'r', encoding='utf-8') as f:
            all_docs_in_file = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_docs_in_file = []

    # Remove source documents and add the new one
    remaining_docs = [doc for doc in all_docs_in_file if not (doc['user_id'] == user_id and doc['id'] in source_doc_ids)]
    remaining_docs.append(new_document)
    
    save_all_documents(remaining_docs)

    # Optionally, delete image files associated with the source documents IF they are not used elsewhere.
    # This is complex if images could be part of multiple documents (not the case here yet).
    # For now, we are not deleting the image files of the source documents as they are referenced by their filenames.

    return new_document