import json
import os
import uuid
from datetime import datetime
from flask import current_app

PHOTOS_DATA_FILE = 'config/photos.json'

def get_photos_data_path():
    return os.path.join(current_app.root_path, PHOTOS_DATA_FILE)

def load_all_photos_for_user(user_id):
    try:
        with open(get_photos_data_path(), 'r', encoding='utf-8') as f:
            all_photos = json.load(f)
            return [photo for photo in all_photos if photo.get('user_id') == user_id]
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def get_photo_by_id(photo_id, user_id):
    user_photos = load_all_photos_for_user(user_id)
    for photo in user_photos:
        if photo['id'] == photo_id:
            return photo
    return None

def save_all_photos(all_photos_list):
    try:
        with open(get_photos_data_path(), 'w', encoding='utf-8') as f:
            json.dump(all_photos_list, f, indent=4, ensure_ascii=False)
    except Exception as e:
        current_app.logger.error(f"Error saving photos: {e}")

def create_photo(user_id, image_filename, original_ocr, ai_cleaned_text):
    photo_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    new_photo = {
        "id": photo_id,
        "user_id": user_id,
        "image_filename": image_filename,
        "original_ocr_text": original_ocr,
        "ai_cleaned_text": ai_cleaned_text,
        "edited_text": ai_cleaned_text,
        "created_at": timestamp,
        "updated_at": timestamp
    }
    all_photos = []
    try:
        with open(get_photos_data_path(), 'r', encoding='utf-8') as f:
            all_photos = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_photos = []
    all_photos.append(new_photo)
    save_all_photos(all_photos)
    return new_photo

def update_photo(user_id, photo_id, updated_data):
    all_photos = []
    try:
        with open(get_photos_data_path(), 'r', encoding='utf-8') as f:
            all_photos = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    photo_found = False
    for i, photo in enumerate(all_photos):
        if photo['id'] == photo_id and photo.get('user_id') == user_id:
            for key, value in updated_data.items():
                if key not in ['id', 'user_id', 'created_at']:
                    photo[key] = value
            photo['updated_at'] = datetime.utcnow().isoformat()
            all_photos[i] = photo
            photo_found = True
            break
    if photo_found:
        save_all_photos(all_photos)
        return True
    return False

def delete_photo(user_id, photo_id):
    all_photos = []
    try:
        with open(get_photos_data_path(), 'r', encoding='utf-8') as f:
            all_photos = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    original_len = len(all_photos)
    all_photos = [photo for photo in all_photos if not (photo['id'] == photo_id and photo.get('user_id') == user_id)]
    if len(all_photos) < original_len:
        save_all_photos(all_photos)
        return True
    return False 