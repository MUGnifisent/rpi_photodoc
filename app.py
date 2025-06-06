import os
import yaml
import logging
from flask import Flask, send_from_directory
from flask_login import LoginManager, login_required
from dotenv import load_dotenv
from routes import main_bp # Changed to absolute import
from settings_routes import settings_bp, load_settings as load_app_settings, get_config_path, PROMPTS_DIR_NAME, DEFAULT_PROMPT_KEYS, get_prompts_path # Changed to absolute import
from datetime import datetime
from models import User # This is the primary import for models
import database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
# SETTINGS_FILE is now managed within settings_routes.py logic

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS
app.config['CONFIG_DIR'] = os.path.join(app.root_path, 'config')
app.config['PROMPTS_DIR'] = os.path.join(app.config['CONFIG_DIR'], 'prompts')

# Jinja filter for formatting datetime
@app.template_filter('format_datetime')
def format_datetime_filter(value, format='%Y-%m-%d %H:%M'):
    if value is None:
        return ""
    try:
        # Attempt to parse if it's an ISO string (e.g., from JSON)
        dt_object = datetime.fromisoformat(value)
        return dt_object.strftime(format)
    except (ValueError, TypeError):
        # If it's already a datetime object or unparsable, try to format directly or return as is
        try:
            return value.strftime(format) # If it's already a datetime object
        except AttributeError:
            return value # Fallback

# Initialize settings and prompts
with app.app_context():
    # Ensure config directories exist
    os.makedirs(app.config['CONFIG_DIR'], exist_ok=True)
    os.makedirs(app.config['PROMPTS_DIR'], exist_ok=True)

    current_settings = load_app_settings() # Loads from yaml and prompt files
    app.config['LLM_SERVER_URL'] = current_settings.get('llm_server_url', os.environ.get('LLM_SERVER_URL', 'http://localhost:11434/api/generate'))
    app.config['LLM_MODEL_NAME'] = current_settings.get('llm_model_name', 'llama3.1:8b')
    app.config['OCR_MODE'] = current_settings.get('ocr_mode', 'local')
    app.config['OCR_SERVER_URL'] = current_settings.get('ocr_server_url', 'http://localhost:8080/ocr')
    # Prompts are loaded dynamically by get_prompt, but we can prime app.config if needed for some other use case, or remove this line.
    app.config['PROMPTS'] = current_settings.get('prompts', {}) 

# Initialize database and users within app context
with app.app_context():
    database.init_db()  # Initialize SQLite database

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'main.login'

@login_manager.user_loader
def load_user(user_id):
    user = User.get(user_id)
    return user

app.register_blueprint(main_bp)
app.register_blueprint(settings_bp) # Registered settings blueprint

# Initialize database with Flask app
database.init_app(app)

# Initialize DocumentManager

# Route to serve uploaded files
@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')