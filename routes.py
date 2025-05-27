import os
import json
import uuid
import requests
from flask import render_template, Blueprint, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import easyocr
# import cv2 # cv2 is imported in app.py if needed for specific image operations there, not directly in routes.
from models import User
from settings_routes import get_prompt, get_llm_model_name, DEFAULT_PROMPT_KEYS
from photo_manager import (
    create_photo,
    load_all_photos_for_user,
    get_photo_by_id,
    update_photo,
    delete_photo
)
from document_manager import (
    create_document,
    load_all_documents_for_user,
    get_document_by_id,
    update_document,
    delete_document
)
from datetime import datetime

main_bp = Blueprint('main', __name__)

try:
    reader = easyocr.Reader(['uk', 'en'])
except Exception as e:
    print(f"Error initializing EasyOCR reader: {e}")
    reader = None

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def perform_ocr(filepath):
    if not reader:
        raise Exception("EasyOCR reader not initialized.")
    try:
        result = reader.readtext(filepath, detail=0, paragraph=True)
        return "\n".join(result)
    except Exception as e:
        current_app.logger.error(f"OCR processing failed for {filepath}: {e}")
        raise

def call_llm(prompt_text_key, text_to_process, custom_prompt_text=None):
    llm_url = current_app.config.get('LLM_SERVER_URL')
    llm_model = get_llm_model_name()
    if not llm_url:
        current_app.logger.error("LLM Server URL not configured.")
        return "Error: LLM Server URL not configured."
    prompt_to_use = custom_prompt_text if custom_prompt_text else get_prompt(prompt_text_key)
    if not prompt_to_use:
         current_app.logger.error(f"Prompt for key '{prompt_text_key}' not found.")
         return f"Error: Prompt for key '{prompt_text_key}' not found."
    full_prompt = f"{prompt_to_use}\n\n{text_to_process}"
    payload = {
        "model": llm_model, "prompt": full_prompt, "stream": False,
        "options": {"num_predict": 1024, "temperature": 0.3}
    }
    try:
        response = requests.post(llm_url, json=payload, timeout=120)
        response.raise_for_status()
        response_data = response.json()
        if 'response' in response_data:
            return response_data['response'].strip()
        elif 'message' in response_data and 'content' in response_data['message']:
             return response_data['message']['content'].strip()
        elif 'choices' in response_data and len(response_data['choices']) > 0 and 'text' in response_data['choices'][0]:
             return response_data['choices'][0]['text'].strip()
        else:
            current_app.logger.error(f"Unexpected LLM response format: {response_data}")
            return "Error: Unexpected LLM response format from server."
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"LLM request failed: {e}")
        return f"Error communicating with LLM: {e}"
    except json.JSONDecodeError:
        current_app.logger.error(f"Failed to decode LLM JSON response: {response.text}")
        return "Error: Failed to decode LLM response (not JSON). Content: " + response.text[:200]

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.gallery_view'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.get_by_username(username)
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('main.gallery_view'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.gallery_view'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if not username or not password or not confirm_password:
            flash('All fields are required.', 'error')
            return render_template('register.html')
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        existing_user = User.get_by_username(username)
        if existing_user:
            flash('Username already exists.', 'error')
            return render_template('register.html')
        user = User.create(username, password)
        if user:
            login_user(user)
            flash('Registration successful!', 'success')
            return redirect(url_for('main.gallery_view'))
        else:
            flash('An error occurred during registration.', 'error')
    return render_template('register.html')

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main_bp.route('/upload', methods=['GET'])
@login_required
def upload_page():
    return render_template('upload.html')

@main_bp.route('/process_upload', methods=['POST'])
@login_required
def process_upload():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('main.upload_page'))
    file = request.files['file']

    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('main.upload_page'))

    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            current_app.logger.info(f"Created upload folder: {upload_folder}")
        filepath = os.path.join(upload_folder, unique_filename)
        try:
            file.save(filepath)
            current_app.logger.info(f"File '{unique_filename}' uploaded by user {current_user.id}.")
        except Exception as e:
            current_app.logger.error(f"Error saving uploaded file '{unique_filename}': {e}")
            flash(f"Error saving file: {e}", "error")
            return redirect(url_for('main.upload_page'))
        original_ocr_text = None
        ai_cleaned_text = None
        try:
            current_app.logger.info(f"Performing OCR on {filepath}")
            original_ocr_text = perform_ocr(filepath)
            current_app.logger.info(f"OCR for {filepath}. Length: {len(original_ocr_text if original_ocr_text else [])}")
            if original_ocr_text and original_ocr_text.strip():
                current_app.logger.info(f"Calling LLM for cleanup of {filepath}")
                ai_cleaned_text_result = call_llm("cleanup_ocr", original_ocr_text)
                if ai_cleaned_text_result.startswith("Error:"):
                    flash(f"LLM Error: {ai_cleaned_text_result}. Using raw OCR.", "warning")
                    ai_cleaned_text = original_ocr_text
                else:
                    ai_cleaned_text = ai_cleaned_text_result
                current_app.logger.info(f"LLM for {filepath}. AI text length: {len(ai_cleaned_text if ai_cleaned_text else [])}")
            else:
                ai_cleaned_text = "No text found by OCR." if original_ocr_text is not None else "OCR failed or returned empty."
                current_app.logger.info(f"Skipping LLM for {filepath} (no/empty OCR text).")
        except Exception as e:
            current_app.logger.error(f"Error in OCR/LLM for {unique_filename}: {e}", exc_info=True)
            flash(f'Error during processing: {str(e)}', 'error')
            ai_cleaned_text = original_ocr_text if original_ocr_text else "Error processing image."
        new_photo = create_photo(current_user.id, unique_filename, original_ocr_text, ai_cleaned_text)
        if new_photo:
            flash(f'Photo "{original_filename}" processed and added to your gallery.', 'success')
            return redirect(url_for('main.gallery_view'))
        else:
            flash('Failed to save processed photo.', 'error')
            return redirect(url_for('main.upload_page'))
    else:
        flash('File type not allowed', 'error')
        return redirect(url_for('main.upload_page'))

@main_bp.route('/gallery')
@login_required
def gallery_view():
    user_photos = load_all_photos_for_user(current_user.id)
    user_documents = load_all_documents_for_user(current_user.id)
    return render_template('gallery.html', photos=user_photos, documents=user_documents)

@main_bp.route('/create_document', methods=['POST'])
@login_required
def create_document_route():
    data = request.get_json()
    photo_ids = data.get('photo_ids')
    doc_name = data.get('doc_name', f"Document {datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    if not photo_ids or len(photo_ids) < 1:
        return jsonify({'error': 'Select at least one photo.'}), 400
    new_doc = create_document(current_user.id, doc_name, photo_ids)
    if new_doc:
        flash(f'Document "{new_doc["name"]}" created.', 'success')
        return jsonify({'message': 'Document created!', 'new_document_id': new_doc['id']}), 200
    else:
        return jsonify({'error': 'Failed to create document.'}), 500

@main_bp.route('/document/<doc_id>', methods=['GET'])
@login_required
def document_view(doc_id):
    doc = get_document_by_id(doc_id, current_user.id)
    if not doc:
        flash('Document not found or access denied.', 'error')
        return redirect(url_for('main.gallery_view'))
    # Load all photos for this document
    photos = [get_photo_by_id(pid, current_user.id) for pid in doc.get('photo_ids', [])]
    return render_template('document_view.html', document=doc, photos=photos, default_prompt_keys=DEFAULT_PROMPT_KEYS, enumerate=enumerate)

@main_bp.route('/document/<doc_id>/update_combined_text', methods=['POST'])
@login_required
def update_combined_text(doc_id):
    doc = get_document_by_id(doc_id, current_user.id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    data = request.get_json()
    combined_text = data.get('combined_text', '')
    if update_document(current_user.id, doc_id, {'combined_text': combined_text, 'combined_text_generated_by_user': True}):
        return jsonify({'message': 'Combined text saved!'})
    else:
        return jsonify({'error': 'Failed to save combined text.'}), 500

@main_bp.route('/document/<doc_id>/reorder', methods=['POST'])
@login_required
def reorder_pages(doc_id):
    doc = get_document_by_id(doc_id, current_user.id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    
    data = request.get_json()
    new_page_ids = data.get('page_ids', [])
    
    if not new_page_ids or len(new_page_ids) != len(doc.get('photo_ids', [])):
        return jsonify({'error': 'Invalid page order data'}), 400
    
    # Update document with new page order
    if update_document(current_user.id, doc_id, {'photo_ids': new_page_ids}):
        return jsonify({'message': 'Page order updated'})
    return jsonify({'error': 'Failed to update page order'}), 500

@main_bp.route('/document/<doc_id>/format', methods=['POST'])
@login_required
def format_text(doc_id):
    doc = get_document_by_id(doc_id, current_user.id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    
    data = request.get_json()
    text = data.get('text', '')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
        
    try:
        formatted_text = call_llm('format_text', text, 
            custom_prompt_text="""You are a text formatting assistant. Your task is to:
1. Fix any spelling and grammar errors
2. Improve paragraph structure and readability
3. Ensure consistent formatting
4. Preserve the original meaning and content
5. DO NOT add any notes or explanations
6. Return ONLY the formatted text

Here is the text to format:""")
        
        if formatted_text.startswith('Error:'):
            return jsonify({'error': formatted_text}), 500
            
        return jsonify({'text': formatted_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/document/<doc_id>/translate', methods=['POST'])
@login_required
def translate_text(doc_id):
    doc = get_document_by_id(doc_id, current_user.id)
    if not doc:
        return jsonify({'error': 'Document not found'}), 404
    
    data = request.get_json()
    text = data.get('text', '')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
        
    try:
        translated_text = call_llm('translate_text', text,
            custom_prompt_text="""You are a translation assistant. Your task is to:
1. Translate the text from Ukrainian to English
2. Preserve the original formatting and structure
3. Ensure natural and fluent English
4. Maintain any technical terms accurately
5. DO NOT add any notes or explanations
6. Return ONLY the translated text

Here is the text to translate:""")
        
        if translated_text.startswith('Error:'):
            return jsonify({'error': translated_text}), 500
            
        return jsonify({'text': translated_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Add routes for updating document combined text, deleting documents, updating photo text, deleting photos, etc. as needed. 