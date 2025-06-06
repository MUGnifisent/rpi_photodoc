"""
Settings management for RPi PhotoDoc OCR application.
Hybrid approach: System settings in YAML files, user preferences in database.
"""

import yaml
import os
import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from flask_login import login_required, current_user
from user_settings import (
    get_all_user_settings, 
    set_user_settings_by_category, 
    get_image_enhancement_settings,
    reset_user_settings_to_defaults
)

logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

CONFIG_DIR = 'config'
SETTINGS_FILE_NAME = 'settings.yaml'
PROMPTS_DIR_NAME = 'prompts'

# These are the keys for prompts; the actual prompt text will be loaded from files.
DEFAULT_PROMPT_KEYS = [
    "cleanup_ocr", "summarize", "extract_numbers", 
    "translate_ua_to_en", "translate_en_to_ua", "action_items"
]

def get_config_path(filename=""):
    return os.path.join(current_app.root_path, CONFIG_DIR, filename)

def get_prompts_path():
    return os.path.join(get_config_path(), PROMPTS_DIR_NAME)

def load_prompt_from_file(prompt_key):
    """Load prompt text from individual files"""
    filepath = os.path.join(get_prompts_path(), f"{prompt_key}.txt")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {filepath}. Using empty string.")
        return ""

def load_system_settings():
    """Load system-wide settings from YAML file"""
    settings_path = get_config_path(SETTINGS_FILE_NAME)
    default_settings = {
        'llm_server_url': current_app.config.get('LLM_SERVER_URL', 'http://localhost:11434/api/generate'),
        'llm_model_name': 'llama3.1:8b',
        'ocr_mode': 'local',  # 'local' or 'remote'
        'ocr_server_url': 'http://localhost:8080/ocr',
        'prompts': {key: load_prompt_from_file(key) for key in DEFAULT_PROMPT_KEYS}
    }
    
    try:
        with open(settings_path, 'r') as f:
            settings = yaml.safe_load(f)
            if not settings:
                return default_settings
            
            # Ensure all keys are present, falling back to defaults
            settings.setdefault('llm_server_url', default_settings['llm_server_url'])
            settings.setdefault('llm_model_name', default_settings['llm_model_name'])
            settings.setdefault('ocr_mode', default_settings['ocr_mode'])
            settings.setdefault('ocr_server_url', default_settings['ocr_server_url'])
            
            if 'prompts' not in settings or not isinstance(settings['prompts'], dict):
                settings['prompts'] = {}
            for key in DEFAULT_PROMPT_KEYS:
                settings['prompts'].setdefault(key, load_prompt_from_file(key))
            
            return settings
            
    except (FileNotFoundError, yaml.YAMLError):
        logger.info("System settings file not found or invalid, using defaults")
        return default_settings

def save_system_settings(settings):
    """Save system-wide settings to YAML file"""
    try:
        settings_path = get_config_path(SETTINGS_FILE_NAME)
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        
        # Separate prompts for file storage
        prompts = settings.pop('prompts', {})
        
        # Save main settings to YAML
        with open(settings_path, 'w') as f:
            yaml.dump(settings, f, default_flow_style=False)
        
        # Save prompts to individual files
        prompts_dir = get_prompts_path()
        os.makedirs(prompts_dir, exist_ok=True)
        
        for key, text in prompts.items():
            if key in DEFAULT_PROMPT_KEYS:
                prompt_path = os.path.join(prompts_dir, f"{key}.txt")
                with open(prompt_path, 'w', encoding='utf-8') as f:
                    f.write(text)
        
        logger.info("System settings saved successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error saving system settings: {e}")
        return False

# Legacy functions for compatibility
def load_settings():
    """Legacy function - now loads system settings only"""
    return load_system_settings()

def get_prompt(prompt_key):
    """Get prompt text by key"""
    return load_prompt_from_file(prompt_key)

def get_llm_model_name():
    """Get LLM model name from system settings"""
    return load_system_settings().get('llm_model_name', 'llama3.1:8b')

def get_ocr_mode():
    """Get OCR mode from system settings"""
    return load_system_settings().get('ocr_mode', 'local')

def get_ocr_server_url():
    """Get OCR server URL from system settings"""
    return load_system_settings().get('ocr_server_url', 'http://localhost:8080/ocr')

def get_image_enhancement_settings():
    """Get image enhancement settings for current user"""
    if current_user.is_authenticated:
        from user_settings import get_user_settings_by_category
        return get_user_settings_by_category(current_user.id, 'image_enhancement')
    else:
        # Return disabled defaults for anonymous users
        from user_settings import DEFAULT_USER_SETTINGS
        return DEFAULT_USER_SETTINGS['image_enhancement']

@settings_bp.route('/', methods=['GET'])
@login_required
def settings_page():
    """Main settings page"""
    system_settings = load_system_settings()
    user_settings = get_all_user_settings(current_user.id)
    
    return render_template('settings.html', 
                         system_settings=system_settings,
                         user_settings=user_settings,
                         default_prompt_keys=DEFAULT_PROMPT_KEYS)

@settings_bp.route('/system', methods=['POST'])
@login_required  # TODO: Add admin check
def update_system_settings():
    """Update system-wide settings (admin only)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        current_settings = load_system_settings()
        
        # Update allowed fields
        allowed_fields = ['llm_server_url', 'llm_model_name', 'ocr_mode', 'ocr_server_url']
        for field in allowed_fields:
            if field in data:
                current_settings[field] = data[field]
        
        # Handle prompts separately
        if 'prompts' in data:
            current_settings['prompts'] = data['prompts']
        
        if save_system_settings(current_settings):
            logger.info(f"System settings updated by user {current_user.id}")
            return jsonify({'success': True, 'message': 'System settings updated successfully'})
        else:
            return jsonify({'error': 'Failed to save system settings'}), 500
            
    except Exception as e:
        logger.error(f"Error updating system settings: {e}")
        return jsonify({'error': f'Error updating settings: {str(e)}'}), 500

@settings_bp.route('/user', methods=['POST'])
@login_required
def update_user_settings():
    """Update user-specific settings"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        category = data.get('category')
        settings = data.get('settings')
        
        if not category or not settings:
            return jsonify({'error': 'Category and settings are required'}), 400
        
        # Validate category
        valid_categories = ['image_enhancement', 'ocr', 'ui']
        if category not in valid_categories:
            return jsonify({'error': f'Invalid category. Must be one of: {valid_categories}'}), 400
        
        if set_user_settings_by_category(current_user.id, category, settings):
            logger.info(f"User settings updated for user {current_user.id}, category {category}")
            return jsonify({'success': True, 'message': f'{category} settings updated successfully'})
        else:
            return jsonify({'error': 'Failed to save user settings'}), 500
            
    except Exception as e:
        logger.error(f"Error updating user settings: {e}")
        return jsonify({'error': f'Error updating settings: {str(e)}'}), 500

@settings_bp.route('/user/reset', methods=['POST'])
@login_required
def reset_user_settings():
    """Reset user settings to defaults"""
    try:
        data = request.get_json()
        category = data.get('category') if data else None
        
        if reset_user_settings_to_defaults(current_user.id, category):
            category_text = category or 'all'
            logger.info(f"User settings reset to defaults for user {current_user.id}, category {category_text}")
            return jsonify({'success': True, 'message': f'{category_text} settings reset to defaults'})
        else:
            return jsonify({'error': 'Failed to reset user settings'}), 500
            
    except Exception as e:
        logger.error(f"Error resetting user settings: {e}")
        return jsonify({'error': f'Error resetting settings: {str(e)}'}), 500

@settings_bp.route('/user/<category>', methods=['GET'])
@login_required
def get_user_settings_api(category):
    """Get user settings for a specific category via API"""
    try:
        from user_settings import get_user_settings_by_category
        
        valid_categories = ['image_enhancement', 'ocr', 'ui']
        if category not in valid_categories:
            return jsonify({'error': f'Invalid category. Must be one of: {valid_categories}'}), 400
        
        settings = get_user_settings_by_category(current_user.id, category)
        return jsonify({'success': True, 'settings': settings})
        
    except Exception as e:
        logger.error(f"Error getting user settings for category {category}: {e}")
        return jsonify({'error': f'Error getting settings: {str(e)}'}), 500

@settings_bp.route('/user/<category>', methods=['POST'])
@login_required
def update_user_settings_by_category(category):
    """Update user settings for a specific category"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate category
        valid_categories = ['image_enhancement', 'ocr', 'ui']
        if category not in valid_categories:
            return jsonify({'error': f'Invalid category. Must be one of: {valid_categories}'}), 400
        
        if set_user_settings_by_category(current_user.id, category, data):
            logger.info(f"User settings updated for user {current_user.id}, category {category}")
            return jsonify({'success': True, 'message': f'{category} settings updated successfully'})
        else:
            return jsonify({'error': 'Failed to save user settings'}), 500
            
    except Exception as e:
        logger.error(f"Error updating user settings for category {category}: {e}")
        return jsonify({'error': f'Error updating settings: {str(e)}'}), 500

@settings_bp.route('/user/<category>/reset', methods=['POST'])
@login_required
def reset_user_settings_by_category(category):
    """Reset user settings for a specific category to defaults"""
    try:
        # Validate category
        valid_categories = ['image_enhancement', 'ocr', 'ui']
        if category not in valid_categories:
            return jsonify({'error': f'Invalid category. Must be one of: {valid_categories}'}), 400
        
        if reset_user_settings_to_defaults(current_user.id, category):
            logger.info(f"User settings reset to defaults for user {current_user.id}, category {category}")
            return jsonify({'success': True, 'message': f'{category} settings reset to defaults'})
        else:
            return jsonify({'error': 'Failed to reset user settings'}), 500
            
    except Exception as e:
        logger.error(f"Error resetting user settings for category {category}: {e}")
        return jsonify({'error': f'Error resetting settings: {str(e)}'}), 500