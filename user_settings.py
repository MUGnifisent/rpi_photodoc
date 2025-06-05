"""
User settings management for RPi PhotoDoc OCR application.
Handles per-user preferences stored in SQLite database.
"""

import json
import logging
from typing import Dict, Any, Optional
from database import get_db, get_db_connection

logger = logging.getLogger(__name__)

# Default user settings (fallback values)
DEFAULT_USER_SETTINGS = {
    'image_enhancement': {
        'enabled': False,
        'denoise_enabled': False,
        'denoise_strength': 3,
        'denoise_fast_mode': True,
        'contrast_enabled': False,
        'contrast_clip_limit': 1.5,
        'contrast_preserve_tone': True,
        'sharpen_enabled': False,
        'sharpen_strength': 0.3,
        'color_correction_enabled': False,
        'color_white_balance': False,
        'color_saturation_factor': 1.0,
        'color_temperature_adjustment': 0.0,
        'camera_optimal_settings': False,
        'camera_exposure_time': 33000,
        'camera_analog_gain': 1.0,
        'camera_awb_mode': 'auto',
        'camera_sharpness': 1.0,
        # Experimental features - disabled by default
        'experimental_hdr_enabled': False,
        'experimental_hdr_exposure_times': [5000, 20000, 50000],
        'experimental_hdr_gamma': 2.2,
        'experimental_stacking_enabled': False,
        'experimental_stacking_num_images': 5,
        'experimental_stacking_alignment_threshold': 0.7
    },
    'ocr': {
        'preferred_mode': 'local',  # 'local' or 'remote'
        'languages': ['uk', 'en'],
        'detail_level': 0,
        'paragraph_mode': True
    },
    'ui': {
        'gallery_sort_order': 'created_desc',  # created_desc, created_asc, name_asc, name_desc
        'default_view': 'gallery',  # gallery, documents
        'items_per_page': 20,
        'show_preview_text': True
    }
}

def get_user_setting(user_id: int, category: str, setting_key: str, default=None) -> Any:
    """Get a specific user setting value"""
    try:
        db = get_db()
        result = db.execute('''
            SELECT setting_value FROM user_settings 
            WHERE user_id = ? AND category = ? AND setting_key = ?
        ''', (user_id, category, setting_key)).fetchone()
        
        if result:
            # Try to parse JSON for complex types
            try:
                return json.loads(result['setting_value'])
            except (json.JSONDecodeError, TypeError):
                return result['setting_value']
        
        # Return default value if not found
        if default is not None:
            return default
        
        # Fall back to system default
        return DEFAULT_USER_SETTINGS.get(category, {}).get(setting_key)
        
    except Exception as e:
        logger.error(f"Error getting user setting {category}.{setting_key} for user {user_id}: {e}")
        return default or DEFAULT_USER_SETTINGS.get(category, {}).get(setting_key)

def set_user_setting(user_id: int, category: str, setting_key: str, value: Any) -> bool:
    """Set a specific user setting value"""
    try:
        # Convert complex types to JSON
        if isinstance(value, (dict, list)):
            setting_value = json.dumps(value)
        else:
            setting_value = str(value)
        
        db = get_db()
        db.execute('''
            INSERT OR REPLACE INTO user_settings (user_id, category, setting_key, setting_value)
            VALUES (?, ?, ?, ?)
        ''', (user_id, category, setting_key, setting_value))
        db.commit()
        
        logger.debug(f"Set user setting {category}.{setting_key} = {value} for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error setting user setting {category}.{setting_key} for user {user_id}: {e}")
        return False

def get_user_settings_by_category(user_id: int, category: str) -> Dict[str, Any]:
    """Get all user settings for a specific category"""
    try:
        db = get_db()
        results = db.execute('''
            SELECT setting_key, setting_value FROM user_settings 
            WHERE user_id = ? AND category = ?
        ''', (user_id, category)).fetchall()
        
        settings = {}
        for row in results:
            try:
                # Try to parse JSON for complex types
                settings[row['setting_key']] = json.loads(row['setting_value'])
            except (json.JSONDecodeError, TypeError):
                settings[row['setting_key']] = row['setting_value']
        
        # Merge with defaults for missing keys
        defaults = DEFAULT_USER_SETTINGS.get(category, {})
        for key, default_value in defaults.items():
            if key not in settings:
                settings[key] = default_value
        
        return settings
        
    except Exception as e:
        logger.error(f"Error getting user settings for category {category}, user {user_id}: {e}")
        return DEFAULT_USER_SETTINGS.get(category, {})

def set_user_settings_by_category(user_id: int, category: str, settings: Dict[str, Any]) -> bool:
    """Set multiple user settings for a specific category"""
    try:
        db = get_db()
        
        for setting_key, value in settings.items():
            # Convert complex types to JSON
            if isinstance(value, (dict, list)):
                setting_value = json.dumps(value)
            else:
                setting_value = str(value)
            
            db.execute('''
                INSERT OR REPLACE INTO user_settings (user_id, category, setting_key, setting_value)
                VALUES (?, ?, ?, ?)
            ''', (user_id, category, setting_key, setting_value))
        
        db.commit()
        
        logger.info(f"Updated {len(settings)} settings in category {category} for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error setting user settings for category {category}, user {user_id}: {e}")
        return False

def get_all_user_settings(user_id: int) -> Dict[str, Dict[str, Any]]:
    """Get all user settings organized by category"""
    try:
        db = get_db()
        results = db.execute('''
            SELECT category, setting_key, setting_value FROM user_settings 
            WHERE user_id = ?
        ''', (user_id,)).fetchall()
        
        settings = {}
        for row in results:
            category = row['category']
            if category not in settings:
                settings[category] = {}
            
            try:
                # Try to parse JSON for complex types
                settings[category][row['setting_key']] = json.loads(row['setting_value'])
            except (json.JSONDecodeError, TypeError):
                settings[category][row['setting_key']] = row['setting_value']
        
        # Merge with defaults for missing categories/keys
        for category, defaults in DEFAULT_USER_SETTINGS.items():
            if category not in settings:
                settings[category] = {}
            
            for key, default_value in defaults.items():
                if key not in settings[category]:
                    settings[category][key] = default_value
        
        return settings
        
    except Exception as e:
        logger.error(f"Error getting all user settings for user {user_id}: {e}")
        return DEFAULT_USER_SETTINGS.copy()

def delete_user_settings(user_id: int, category: str = None) -> bool:
    """Delete user settings for a category or all settings for a user"""
    try:
        db = get_db()
        
        if category:
            db.execute('DELETE FROM user_settings WHERE user_id = ? AND category = ?', (user_id, category))
            logger.info(f"Deleted {category} settings for user {user_id}")
        else:
            db.execute('DELETE FROM user_settings WHERE user_id = ?', (user_id,))
            logger.info(f"Deleted all settings for user {user_id}")
        
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error deleting user settings for user {user_id}, category {category}: {e}")
        return False

def reset_user_settings_to_defaults(user_id: int, category: str = None) -> bool:
    """Reset user settings to system defaults"""
    try:
        # Delete existing settings
        if not delete_user_settings(user_id, category):
            return False
        
        # Settings will now fall back to defaults automatically
        logger.info(f"Reset user {user_id} settings to defaults for category {category or 'all'}")
        return True
        
    except Exception as e:
        logger.error(f"Error resetting user settings for user {user_id}, category {category}: {e}")
        return False

def get_image_enhancement_settings(user_id: int) -> Dict[str, Any]:
    """Get image enhancement settings for a specific user (compatibility function)"""
    return get_user_settings_by_category(user_id, 'image_enhancement')

def get_ocr_settings(user_id: int) -> Dict[str, Any]:
    """Get OCR settings for a specific user"""
    return get_user_settings_by_category(user_id, 'ocr')

def get_ui_settings(user_id: int) -> Dict[str, Any]:
    """Get UI settings for a specific user"""
    return get_user_settings_by_category(user_id, 'ui')