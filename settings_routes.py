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
        'prompts': {key: load_prompt_from_file(key) for key in DEFAULT_PROMPT_KEYS}
    }
    try:
        with open(settings_path, 'r') as f:
            settings = yaml.safe_load(f)
            if not settings: # File was empty or malformed
                return default_settings
            # Ensure all keys are present, falling back to defaults
            settings.setdefault('llm_server_url', default_settings['llm_server_url'])
            settings.setdefault('llm_model_name', default_settings['llm_model_name'])
            if 'prompts' not in settings or not isinstance(settings['prompts'], dict):
                settings['prompts'] = {}
            for key in DEFAULT_PROMPT_KEYS:
                 # If a prompt is missing from settings.yaml, load it from its .txt file
                settings['prompts'].setdefault(key, load_prompt_from_file(key))
            return settings
    except (FileNotFoundError, yaml.YAMLError):
        return default_settings

def save_settings(settings_data):
    # When saving settings, only save llm_server_url and llm_model_name to settings.yaml.
    # Prompts are managed as individual files.
    config_to_save = {
        'llm_server_url': settings_data.get('llm_server_url'),
        'llm_model_name': settings_data.get('llm_model_name')
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
    if 'prompts' in settings_data: current_app.config['PROMPTS'] = settings_data['prompts']


@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def manage_settings():
    if request.method == 'POST':
        current_settings = load_settings() # Load existing to preserve any other settings
        current_settings['llm_server_url'] = request.form.get('llm_server_url', current_settings.get('llm_server_url'))
        current_settings['llm_model_name'] = request.form.get('llm_model_name', current_settings.get('llm_model_name'))
        
        new_prompts = {}
        for key in DEFAULT_PROMPT_KEYS:
            new_prompts[key] = request.form.get(f'prompt_{key}', load_prompt_from_file(key)) # Fallback to file content if not in form
        current_settings['prompts'] = new_prompts
            
        save_settings(current_settings)
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