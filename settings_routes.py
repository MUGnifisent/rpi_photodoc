import yaml
import os
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required

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
    filepath = os.path.join(get_prompts_path(), f"{prompt_key}.txt")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        current_app.logger.error(f"Prompt file not found: {filepath}. Using empty string.")
        return "" # Or raise an error, or return a very generic default

def load_settings():
    settings_path = get_config_path(SETTINGS_FILE_NAME)
    default_settings = {
        'llm_server_url': current_app.config.get('LLM_SERVER_URL', 'http://localhost:11434/api/generate'),
        'llm_model_name': 'llama3.1:8b',
        'ocr_mode': 'local',  # 'local' or 'remote'
        'ocr_server_url': 'http://localhost:8080/ocr',
        'prompts': {key: load_prompt_from_file(key) for key in DEFAULT_PROMPT_KEYS},
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
        }
    }
    try:
        with open(settings_path, 'r') as f:
            settings = yaml.safe_load(f)
            if not settings: # File was empty or malformed
                return default_settings
            # Ensure all keys are present, falling back to defaults
            settings.setdefault('llm_server_url', default_settings['llm_server_url'])
            settings.setdefault('llm_model_name', default_settings['llm_model_name'])
            settings.setdefault('ocr_mode', default_settings['ocr_mode'])
            settings.setdefault('ocr_server_url', default_settings['ocr_server_url'])
            settings.setdefault('image_enhancement', default_settings['image_enhancement'])
            if 'prompts' not in settings or not isinstance(settings['prompts'], dict):
                settings['prompts'] = {}
            for key in DEFAULT_PROMPT_KEYS:
                 # If a prompt is missing from settings.yaml, load it from its .txt file
                settings['prompts'].setdefault(key, load_prompt_from_file(key))
            # Ensure all image enhancement settings are present
            if 'image_enhancement' not in settings or not isinstance(settings['image_enhancement'], dict):
                settings['image_enhancement'] = default_settings['image_enhancement']
            else:
                for key, value in default_settings['image_enhancement'].items():
                    settings['image_enhancement'].setdefault(key, value)
            return settings
    except (FileNotFoundError, yaml.YAMLError):
        return default_settings

def save_settings(settings_data):
    # When saving settings, save LLM, OCR and image enhancement config to settings.yaml.
    # Prompts are managed as individual files.
    config_to_save = {
        'llm_server_url': settings_data.get('llm_server_url'),
        'llm_model_name': settings_data.get('llm_model_name'),
        'ocr_mode': settings_data.get('ocr_mode', 'local'),
        'ocr_server_url': settings_data.get('ocr_server_url'),
        'image_enhancement': settings_data.get('image_enhancement', {})
    }
    with open(get_config_path(SETTINGS_FILE_NAME), 'w') as f:
        yaml.dump(config_to_save, f, indent=4, default_flow_style=False)
    
    # Save individual prompt files
    prompts_path = get_prompts_path()
    os.makedirs(prompts_path, exist_ok=True)
    if 'prompts' in settings_data:
        for key, content in settings_data['prompts'].items():
            if key in DEFAULT_PROMPT_KEYS: # Only save known prompt keys
                with open(os.path.join(prompts_path, f"{key}.txt"), 'w', encoding='utf-8') as f:
                    f.write(content)

    # Update app config immediately
    if 'llm_server_url' in settings_data: current_app.config['LLM_SERVER_URL'] = settings_data['llm_server_url']
    if 'llm_model_name' in settings_data: current_app.config['LLM_MODEL_NAME'] = settings_data['llm_model_name']
    if 'ocr_mode' in settings_data: current_app.config['OCR_MODE'] = settings_data['ocr_mode']
    if 'ocr_server_url' in settings_data: current_app.config['OCR_SERVER_URL'] = settings_data['ocr_server_url']
    if 'prompts' in settings_data: current_app.config['PROMPTS'] = settings_data['prompts']
    if 'image_enhancement' in settings_data: current_app.config['IMAGE_ENHANCEMENT'] = settings_data['image_enhancement']


@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def manage_settings():
    if request.method == 'POST':
        current_settings = load_settings() # Load existing to preserve any other settings
        current_settings['llm_server_url'] = request.form.get('llm_server_url', current_settings.get('llm_server_url'))
        current_settings['llm_model_name'] = request.form.get('llm_model_name', current_settings.get('llm_model_name'))
        current_settings['ocr_mode'] = request.form.get('ocr_mode', 'local')
        current_settings['ocr_server_url'] = request.form.get('ocr_server_url', current_settings.get('ocr_server_url'))
        
        # Handle image enhancement settings
        image_enhancement = current_settings.get('image_enhancement', {})
        image_enhancement['enabled'] = 'enhancement_enabled' in request.form
        image_enhancement['denoise_enabled'] = 'denoise_enabled' in request.form
        image_enhancement['denoise_strength'] = int(request.form.get('denoise_strength', 5))
        image_enhancement['denoise_fast_mode'] = 'denoise_fast_mode' in request.form
        image_enhancement['contrast_enabled'] = 'contrast_enabled' in request.form
        image_enhancement['contrast_clip_limit'] = float(request.form.get('contrast_clip_limit', 2.0))
        image_enhancement['contrast_preserve_tone'] = 'contrast_preserve_tone' in request.form
        image_enhancement['sharpen_enabled'] = 'sharpen_enabled' in request.form
        image_enhancement['sharpen_strength'] = float(request.form.get('sharpen_strength', 0.8))
        image_enhancement['color_correction_enabled'] = 'color_correction_enabled' in request.form
        image_enhancement['color_white_balance'] = 'color_white_balance' in request.form
        image_enhancement['color_saturation_factor'] = float(request.form.get('color_saturation_factor', 1.1))
        image_enhancement['color_temperature_adjustment'] = float(request.form.get('color_temperature_adjustment', 0.0))
        image_enhancement['camera_optimal_settings'] = 'camera_optimal_settings' in request.form
        image_enhancement['camera_exposure_time'] = int(request.form.get('camera_exposure_time', 20000))
        image_enhancement['camera_analog_gain'] = float(request.form.get('camera_analog_gain', 1.0))
        image_enhancement['camera_awb_mode'] = request.form.get('camera_awb_mode', 'auto')
        image_enhancement['camera_sharpness'] = float(request.form.get('camera_sharpness', 1.5))
        # Experimental features
        image_enhancement['experimental_hdr_enabled'] = 'experimental_hdr_enabled' in request.form
        image_enhancement['experimental_hdr_gamma'] = float(request.form.get('experimental_hdr_gamma', 2.2))
        image_enhancement['experimental_stacking_enabled'] = 'experimental_stacking_enabled' in request.form
        image_enhancement['experimental_stacking_num_images'] = int(request.form.get('experimental_stacking_num_images', 5))
        image_enhancement['experimental_stacking_alignment_threshold'] = float(request.form.get('experimental_stacking_alignment_threshold', 0.7))
        # Parse exposure times from comma-separated values
        exposure_times_str = request.form.get('experimental_hdr_exposure_times', '5000,20000,50000')
        try:
            image_enhancement['experimental_hdr_exposure_times'] = [int(x.strip()) for x in exposure_times_str.split(',')]
        except ValueError:
            image_enhancement['experimental_hdr_exposure_times'] = [5000, 20000, 50000]  # fallback
        current_settings['image_enhancement'] = image_enhancement
        
        new_prompts = {}
        for key in DEFAULT_PROMPT_KEYS:
            new_prompts[key] = request.form.get(f'prompt_{key}', load_prompt_from_file(key)) # Fallback to file content if not in form
        current_settings['prompts'] = new_prompts
            
        save_settings(current_settings)
        
        # Refresh image enhancement settings
        try:
            from image_enhancement import enhancement_manager
            enhancement_manager.refresh_settings()
        except ImportError:
            pass  # Enhancement manager not available
        
        flash('Settings and prompts updated successfully!', 'success')
        return redirect(url_for('settings.manage_settings'))
    
    settings_data = load_settings()
    # Ensure prompts are loaded for the template even if settings file is minimal
    if not settings_data.get('prompts') or len(settings_data['prompts']) < len(DEFAULT_PROMPT_KEYS):
        settings_data['prompts'] = {key: load_prompt_from_file(key) for key in DEFAULT_PROMPT_KEYS}

    return render_template('settings.html', settings=settings_data, default_prompt_keys=DEFAULT_PROMPT_KEYS)

def get_prompt(action_key):
    # This function now directly loads from the specific file for the most up-to-date version.
    # It bypasses settings.yaml for reading prompts, as settings.yaml no longer stores them.
    return load_prompt_from_file(action_key)

def get_llm_model_name():
    settings = load_settings() # This will load from settings.yaml
    return settings.get('llm_model_name', 'llama3.1:8b')

def get_ocr_mode():
    settings = load_settings()
    return settings.get('ocr_mode', 'local')

def get_ocr_server_url():
    settings = load_settings()
    return settings.get('ocr_server_url', 'http://localhost:8080/ocr')

def get_image_enhancement_settings():
    settings = load_settings()
    return settings.get('image_enhancement', {})