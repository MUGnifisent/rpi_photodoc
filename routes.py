import os
import json
import uuid
import requests
import time # For camera feed
from flask import render_template, Blueprint, request, redirect, url_for, flash, current_app, jsonify, Response
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from urllib.parse import urlparse  # URL validation for Werkzeug 3.x compatibility
import easyocr
# import cv2 # cv2 is imported in app.py if needed for specific image operations there, not directly in routes.
from models import User
from settings_routes import get_prompt, get_llm_model_name, get_ocr_mode, get_ocr_server_url, DEFAULT_PROMPT_KEYS
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
    delete_document,
    remove_photo_from_document,
    get_documents_containing_photo
)
from datetime import datetime
from camera_rpi import rpi_camera_instance # Import the camera instance
from image_enhancement import enhancement_manager # Import the enhancement manager
import logging

logger = logging.getLogger(__name__)

# Debug camera import
logger.info("=== Routes module initializing ===")
logger.info(f"Camera instance imported: {type(rpi_camera_instance)}")
logger.info(f"Camera available at import: {rpi_camera_instance.is_available()}")

main_bp = Blueprint('main', __name__)

try:
    reader = easyocr.Reader(['uk', 'en'])
except Exception as e:
    print(f"Error initializing EasyOCR reader: {e}")
    reader = None

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def perform_ocr_local(filepath):
    """Perform OCR using local EasyOCR"""
    if not reader:
        logger.error("EasyOCR reader not initialized. OCR cannot be performed.")
        raise Exception("EasyOCR reader not initialized.")
    try:
        result = reader.readtext(filepath, detail=0, paragraph=True, workers=0)
        return "\n".join(result)
    except Exception as e:
        logger.error(f"Local OCR processing failed for {filepath}: {e}")
        raise

def perform_ocr_remote(filepath):
    """Perform OCR using remote OCR server"""
    ocr_server_url = get_ocr_server_url()
    
    try:
        with open(filepath, 'rb') as f:
            files = {'image': (os.path.basename(filepath), f, 'image/jpeg')}
            response = requests.post(ocr_server_url, files=files, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            if result.get('success'):
                return result.get('text', '')
            else:
                error_msg = result.get('error', 'Unknown error from OCR server')
                logger.error(f"Remote OCR server error: {error_msg}")
                raise Exception(f"OCR Server Error: {error_msg}")
                
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to OCR server at {ocr_server_url}: {e}")
        raise Exception(f"Failed to connect to OCR server: {e}")
    except Exception as e:
        logger.error(f"Remote OCR processing failed for {filepath}: {e}")
        raise

def perform_ocr(filepath):
    """Perform OCR using either local or remote method based on settings"""
    ocr_mode = get_ocr_mode()
    
    if ocr_mode == 'remote':
        logger.info(f"Using remote OCR for {filepath}")
        return perform_ocr_remote(filepath)
    else:
        logger.info(f"Using local OCR for {filepath}")
        return perform_ocr_local(filepath)

def call_llm(prompt_text_key, text_to_process, custom_prompt_text=None):
    llm_url = current_app.config.get('LLM_SERVER_URL')
    llm_model = get_llm_model_name() # Ensure this function exists and is imported from settings_routes
    if not llm_url:
        logger.error("LLM Server URL not configured.")
        return "Error: LLM Server URL not configured."

    prompt_to_use = custom_prompt_text if custom_prompt_text else get_prompt(prompt_text_key)
    if not prompt_to_use:
         logger.error(f"Prompt for key '{prompt_text_key}' not found.")
         return f"Error: Prompt for key '{prompt_text_key}' not found."

    full_prompt = f"{prompt_to_use}\n\n{text_to_process}"

    payload = {
        "model": llm_model, "prompt": full_prompt, "stream": False,
        "options": {"num_predict": 1024, "temperature": 0.3} # Example options
    }
    try:
        response = requests.post(llm_url, json=payload, timeout=120) # Timeout can be configured
        response.raise_for_status()
        response_data = response.json()

        # Adapt based on actual LLM response structure (Ollama, OpenAI, etc.)
        if 'response' in response_data: # Common for Ollama
            return response_data['response'].strip()
        elif 'message' in response_data and 'content' in response_data['message']: # Possible other structures
             return response_data['message']['content'].strip()
        elif 'choices' in response_data and len(response_data['choices']) > 0 and 'text' in response_data['choices'][0]:
             return response_data['choices'][0]['text'].strip() # OpenAI-like
        else:
            logger.error(f"Unexpected LLM response format: {response_data}")
            return "Error: Unexpected LLM response format from server."

    except requests.exceptions.RequestException as e:
        logger.error(f"LLM request failed: {e}")
        return f"Error communicating with LLM: {e}"
    except json.JSONDecodeError: # If response is not JSON
        logger.error(f"Failed to decode LLM JSON response: {response.text}")
        return "Error: Failed to decode LLM response (not JSON). Content: " + response.text[:200]

def is_safe_url(target):
    """Check if the target URL is safe for redirects"""
    if not target:
        return False
    
    # Parse the target URL
    try:
        parsed = urlparse(target)
    except Exception:
        return False
    
    # Allow relative URLs (no scheme or netloc)
    if not parsed.netloc and not parsed.scheme:
        return True
    
    # For absolute URLs, check if they match our host
    if parsed.scheme in ('http', 'https'):
        ref_url = urlparse(request.host_url)
        return parsed.netloc == ref_url.netloc
    
    return False

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
            
            # Handle redirect after login
            next_page = request.args.get('next') or request.form.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            else:
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
        
        # Create user (assuming User.create handles hashing and saving)
        user = User.create(username, password)
        if user:
            login_user(user)
            flash('Registration successful!', 'success')
            
            # Handle redirect after registration
            next_page = request.args.get('next') or request.form.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            else:
                return redirect(url_for('main.gallery_view'))
        else:
            # This case might indicate an issue with User.create itself
            flash('An error occurred during registration. Please try again.', 'error')
            logger.error(f"User creation failed for username: {username}")

    return render_template('register.html')

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    # flash('You have been logged out.', 'info') # Optional
    return redirect(url_for('main.login'))

# New route to check camera availability
@main_bp.route('/camera_status', methods=['GET'])
@login_required
def camera_status():
    logger.info("=== Camera status endpoint called ===")
    try:
        logger.info("Checking camera availability...")
        
        # Add detailed debug info
        logger.info(f"Camera instance type: {type(rpi_camera_instance)}")
        logger.info(f"Camera _is_initialized: {getattr(rpi_camera_instance, '_is_initialized', 'Not set')}")
        logger.info(f"Camera _camera object: {getattr(rpi_camera_instance, '_camera', 'Not set')}")
        
        available = rpi_camera_instance.is_available()
        logger.info(f"Camera available: {available}")
        
        if available:
            streaming = rpi_camera_instance._is_streaming
            logger.info(f"Camera streaming: {streaming}")
            response_data = {'available': True, 'streaming': streaming}
            logger.info(f"Returning positive response: {response_data}")
            return jsonify(response_data)
        else:
            logger.info("Camera not available, returning error response")
            response_data = {'available': False, 'message': 'RPi Camera not detected or failed to initialize.'}
            logger.info(f"Returning negative response: {response_data}")
            return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in camera_status: {e}", exc_info=True)
        response_data = {'available': False, 'message': f'Camera status error: {e}'}
        logger.error(f"Returning error response: {response_data}")
        return jsonify(response_data), 500

@main_bp.route('/start_camera_stream', methods=['POST'])
@login_required
def start_camera_stream():
    logger.info(f"Start camera stream requested by user {current_user.id}")
    
    if not rpi_camera_instance.is_available():
        logger.error("Start stream requested but camera not available")
        return jsonify({'success': False, 'error': 'Camera not available.'}), 503
    
    logger.info("Attempting to start camera stream")
    if rpi_camera_instance.start_streaming():
        logger.info("Camera stream started successfully")
        return jsonify({'success': True, 'message': 'Camera stream started.'})
    else:
        logger.error("Failed to start camera stream")
        return jsonify({'success': False, 'error': 'Failed to start camera stream.'}), 500

@main_bp.route('/stop_camera_stream', methods=['POST'])
@login_required
def stop_camera_stream():
    if not rpi_camera_instance.is_available(): # Should not happen if stream was started
        return jsonify({'success': False, 'error': 'Camera not available.'}), 503
    rpi_camera_instance.stop_streaming()
    return jsonify({'success': True, 'message': 'Camera stream stopped.'})

def gen_camera_feed():
    """Video streaming generator function."""
    logger.info("gen_camera_feed called.")
    if not rpi_camera_instance.is_available():
        logger.warning("gen_camera_feed: Camera feed requested but camera not available.")
        return
    
    if not rpi_camera_instance._is_streaming:
        logger.warning("gen_camera_feed: Camera feed requested but stream not active. Client should start stream first.")
        return

    logger.info("gen_camera_feed: Starting frame loop.")
    frames_yielded = 0
    while True:
        # Check camera state inside the loop
        if not rpi_camera_instance.is_available() or not rpi_camera_instance._is_streaming:
            logger.warning("gen_camera_feed: Camera became unavailable or stopped streaming. Exiting feed loop.")
            break
        frame = rpi_camera_instance.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue
        if not isinstance(frame, bytes):
            logger.error("gen_camera_feed: Frame is not bytes, skipping frame.")
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        frames_yielded += 1
        if frames_yielded == 1:
            logger.info(f"gen_camera_feed: Successfully yielded first frame of size {len(frame)} bytes.")

@main_bp.route('/camera_feed')
@login_required
def camera_feed():
    """Video streaming route."""
    logger.info(f"Camera feed requested by user {current_user.id}")
    
    if not rpi_camera_instance.is_available():
        logger.error("Camera feed requested but camera not available")
        flash("RPi Camera is not available.", "warning")
        return Response("Camera not available", status=503) # Service Unavailable

    if not rpi_camera_instance._is_streaming:
        logger.error("Camera feed requested but streaming not active")
        return Response("Camera streaming not active", status=503)

    logger.info("Serving camera feed stream")
    return Response(gen_camera_feed(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@main_bp.route('/capture_rpi_photo', methods=['POST'])
@login_required
def capture_rpi_photo():
    logger.info("=== Starting RPi photo capture process ===")
    
    if not rpi_camera_instance.is_available():
        logger.error("Camera not available for capture")
        return jsonify({'success': False, 'error': 'Camera not available.'}), 503

    upload_folder = current_app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
        logger.info(f"Created upload folder: {upload_folder}")

    original_filename = f"rpi_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
    filepath = os.path.join(upload_folder, unique_filename)

    try:
        # Step 0.5: Apply optimal camera settings if enabled
        logger.info(f"Step 0.5: Applying camera enhancement settings")
        try:
            enhancement_manager.apply_camera_settings(rpi_camera_instance._camera)
            logger.info(f"Step 0.5 SUCCESS: Camera settings applied")
        except Exception as e:
            logger.warning(f"Step 0.5 WARNING: Camera settings error: {e}, continuing with default settings")
        
        # Step 1: Check for experimental enhancers first
        logger.info(f"Step 1: Checking for experimental capture enhancers")
        experimental_result = None
        try:
            experimental_result = enhancement_manager.apply_experimental_capture(rpi_camera_instance._camera, filepath)
            if experimental_result:
                logger.info(f"Step 1 SUCCESS: Experimental enhancement captured to {experimental_result}")
                # Skip normal capture since experimental enhancer handled it
                capture_success = True
            else:
                logger.info(f"Step 1: No experimental enhancers enabled, proceeding with normal capture")
        except Exception as e:
            logger.warning(f"Step 1 WARNING: Experimental capture error: {e}, falling back to normal capture")
        
        # Step 1 (continued): Normal capture if experimental didn't handle it
        if not experimental_result:
            logger.info(f"Step 1: Attempting normal capture to {filepath}")
            capture_success = rpi_camera_instance.capture_image(filepath)
        
        if not capture_success:
            logger.error(f"Step 1 FAILED: Camera capture returned False")
            return jsonify({'success': False, 'error': 'Failed to capture image from camera.'}), 500
        
        # Verify file exists and has reasonable size
        if not os.path.exists(filepath):
            logger.error(f"Step 1 FAILED: Image file not created at {filepath}")
            return jsonify({'success': False, 'error': 'Image file was not created.'}), 500
        
        file_size = os.path.getsize(filepath)
        logger.info(f"Step 1 SUCCESS: Image captured, file size: {file_size} bytes")
        
        if file_size < 10000:  # Less than 10KB is probably an error
            logger.error(f"Step 1 FAILED: Image file too small: {file_size} bytes")
            return jsonify({'success': False, 'error': f'Captured image file too small: {file_size} bytes'}), 500

        # Step 1.5: Apply image enhancement if enabled (skip if experimental was used)
        if experimental_result:
            logger.info(f"Step 1.5: Skipping standard enhancement (experimental enhancement already applied)")
        else:
            logger.info(f"Step 1.5: Applying standard image enhancement")
            try:
                enhancement_success = enhancement_manager.enhance_image(filepath)
                if enhancement_success:
                    logger.info(f"Step 1.5 SUCCESS: Image enhancement completed")
                else:
                    logger.warning(f"Step 1.5 WARNING: Image enhancement failed, continuing with original image")
            except Exception as e:
                logger.error(f"Step 1.5 WARNING: Image enhancement error: {e}, continuing with original image")

        # Step 2: Perform OCR
        ocr_mode = get_ocr_mode()
        logger.info(f"Step 2: Starting OCR on {filepath} using {ocr_mode} mode")
        original_ocr_text = None
        ai_cleaned_text = "Error during processing or no text found."

        try:
            original_ocr_text = perform_ocr(filepath)
            logger.info(f"Step 2 SUCCESS: OCR completed. Text length: {len(original_ocr_text if original_ocr_text else '')}")
            
            if original_ocr_text:
                logger.info(f"OCR preview: {original_ocr_text[:100]}...")
            else:
                logger.warning("OCR returned empty or None")

        except Exception as e:
            logger.error(f"Step 2 FAILED: OCR error: {e}", exc_info=True)
            original_ocr_text = ""
            ai_cleaned_text = f"OCR Error: {str(e)}"

        # Step 3: LLM Processing (only if we have OCR text)
        if original_ocr_text and original_ocr_text.strip():
            try:
                logger.info(f"Step 3: Starting LLM cleanup")
                ai_cleaned_text_result = call_llm("cleanup_ocr", original_ocr_text)
                
                if ai_cleaned_text_result.startswith("Error:"):
                    logger.warning(f"Step 3 WARNING: LLM returned error: {ai_cleaned_text_result}")
                    ai_cleaned_text = original_ocr_text  # Fallback to raw OCR
                else:
                    ai_cleaned_text = ai_cleaned_text_result
                    logger.info(f"Step 3 SUCCESS: LLM cleanup completed. Length: {len(ai_cleaned_text)}")
                    
            except Exception as e:
                logger.error(f"Step 3 FAILED: LLM error: {e}", exc_info=True)
                ai_cleaned_text = original_ocr_text if original_ocr_text else f"LLM Error: {str(e)}"
        else:
            logger.info("Step 3 SKIPPED: No OCR text to process")
            ai_cleaned_text = "No text found by OCR."

        # Step 4: Create Photo record
        logger.info(f"Step 4: Creating photo record in database")
        try:
            new_photo = create_photo(current_user.id, unique_filename, original_ocr_text, ai_cleaned_text)
            if not new_photo:
                logger.error(f"Step 4 FAILED: create_photo returned None")
                return jsonify({'success': False, 'error': 'Failed to save photo metadata to database.'}), 500
            
            logger.info(f"Step 4 SUCCESS: Photo record created with ID {new_photo['id']}")
            
        except Exception as e:
            logger.error(f"Step 4 FAILED: Database error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500

        # All steps successful!
        logger.info("=== Photo capture process completed successfully ===")
        flash(f'Photo "{original_filename}" captured and processed successfully!', 'success')
        
        return jsonify({
            'success': True,
            'message': 'Photo captured and processed.',
            'photo_id': new_photo['id'],
            'filename': unique_filename,
            'redirect_url': url_for('main.gallery_view')
        }), 200

    except Exception as e:
        logger.error(f"=== OVERALL CAPTURE PROCESS FAILED ===: {e}", exc_info=True)
        # Clean up the file if it was created but process failed
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                logger.info(f"Cleaned up failed capture file: {filepath}")
            except:
                pass
        
        return jsonify({'success': False, 'error': f'Unexpected error during capture: {str(e)}'}), 500

@main_bp.route('/upload', methods=['GET'])
@login_required
def upload_page():
    # Pass camera availability to the template
    camera_available = rpi_camera_instance.is_available()
    logger.info(f"Upload page accessed by user {current_user.id}")
    logger.info(f"Camera available for template: {camera_available}")
    return render_template('upload.html', camera_available=camera_available)

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
        # Sanitize filename further if necessary, e.g. limit length or char set
        unique_filename = f"{uuid.uuid4().hex}_{original_filename[:100]}" # Example: truncate original filename part
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            logger.info(f"Created upload folder: {upload_folder}")
        
        filepath = os.path.join(upload_folder, unique_filename)
        
        try:
            file.save(filepath)
            logger.info(f"File '{unique_filename}' uploaded by user {current_user.id}.")
        except Exception as e:
            logger.error(f"Error saving uploaded file '{unique_filename}': {e}")
            flash(f"Error saving file: {e}", "error")
            return redirect(url_for('main.upload_page'))

        # Apply image enhancement if enabled
        logger.info(f"Applying image enhancement to uploaded file")
        try:
            enhancement_success = enhancement_manager.enhance_image(filepath)
            if enhancement_success:
                logger.info(f"Image enhancement completed for uploaded file")
            else:
                logger.warning(f"Image enhancement failed for uploaded file, continuing with original")
        except Exception as e:
            logger.error(f"Image enhancement error for uploaded file: {e}, continuing with original")

        original_ocr_text = None
        ai_cleaned_text = "Error during processing or no text found." # Default

        try:
            ocr_mode = get_ocr_mode()
            logger.info(f"Performing OCR on {filepath} using {ocr_mode} mode")
            original_ocr_text = perform_ocr(filepath) # This can raise an exception
            logger.info(f"OCR for {filepath}. Length: {len(original_ocr_text if original_ocr_text else [])}")

            if original_ocr_text and original_ocr_text.strip():
                logger.info(f"Calling LLM for cleanup of {filepath}")
                ai_cleaned_text_result = call_llm("cleanup_ocr", original_ocr_text)
                if ai_cleaned_text_result.startswith("Error:"):
                    flash(f"LLM Error: {ai_cleaned_text_result}. Using raw OCR.", "warning")
                    ai_cleaned_text = original_ocr_text # Fallback to raw OCR
                else:
                    ai_cleaned_text = ai_cleaned_text_result
                logger.info(f"LLM for {filepath}. AI text length: {len(ai_cleaned_text if ai_cleaned_text else [])}")
            elif original_ocr_text is None: # OCR itself failed or returned None
                 ai_cleaned_text = "OCR process failed or returned no data."
                 logger.warning(f"OCR returned None for {filepath}.")
            else: # OCR returned empty string
                ai_cleaned_text = "No text found by OCR."
                logger.info(f"Skipping LLM for {filepath} (no/empty OCR text).")
        
        except Exception as e: # Catch errors from perform_ocr or call_llm
            logger.error(f"Error in OCR/LLM for {unique_filename}: {e}", exc_info=True)
            flash(f'Error during processing: {str(e)}', 'error')
            # Fallback: save original OCR text if available, otherwise the error message
            ai_cleaned_text = original_ocr_text if original_ocr_text else f"Processing Error: {str(e)}"

        new_photo = create_photo(current_user.id, unique_filename, original_ocr_text, ai_cleaned_text)

        if new_photo:
            flash(f'Photo "{original_filename}" processed and added to your gallery.', 'success')
            return redirect(url_for('main.gallery_view'))
        else:
            flash('Failed to save processed photo to the database.', 'error')
            # Image is on disk, but not in DB. Consider cleanup or admin alert.
            return redirect(url_for('main.upload_page'))
    else:
        flash('File type not allowed.', 'error')
        return redirect(url_for('main.upload_page'))

@main_bp.route('/gallery')
@login_required
def gallery_view():
    user_photos = load_all_photos_for_user(current_user.id)
    user_documents = load_all_documents_for_user(current_user.id)
    # Sort photos by creation date, newest first (optional)
    # user_photos.sort(key=lambda p: p.get('created_at_dt', datetime.min), reverse=True)
    return render_template('gallery.html', photos=user_photos, documents=user_documents)

@main_bp.route('/create_document', methods=['POST'])
@login_required
def create_document_route():
    data = request.get_json()
    photo_ids = data.get('photo_ids')
    doc_name_input = data.get('doc_name', '').strip()

    if not doc_name_input: # Generate default name if empty or just whitespace
        doc_name = f"Document {datetime.utcnow().strftime('%Y-%m-%d %H%M%S')}"
    else:
        doc_name = doc_name_input
        
    if not photo_ids or len(photo_ids) < 1:
        return jsonify({'error': 'Select at least one photo.'}), 400

    # Validate photo_ids belong to the current user (important for security)
    # This might be better done within create_document or by fetching photos first
    # For now, assuming create_document handles this or photo_manager functions do.

    new_doc = create_document(current_user.id, doc_name, photo_ids)
    if new_doc:
        flash(f'Document "{new_doc.get("name", "Untitled")}" created.', 'success') # Use .get for safety
        return jsonify({'message': 'Document created!', 'new_document_id': new_doc['id']}), 200
    else:
        logger.error(f"Failed to create document for user {current_user.id} with photo_ids: {photo_ids}")
        return jsonify({'error': 'Failed to create document.'}), 500

@main_bp.route('/document/<doc_id>', methods=['GET'])
@login_required
def document_view(doc_id):
    doc = get_document_by_id(doc_id, current_user.id)
    if not doc:
        flash('Document not found or access denied.', 'error')
        return redirect(url_for('main.gallery_view'))

    # Load all photos for this document, ensuring they belong to the user
    photos_in_doc = []
    if doc.get('photo_ids'):
        for pid in doc['photo_ids']:
            photo = get_photo_by_id(pid, current_user.id) # Ensures user owns photo
            if photo:
                photos_in_doc.append(photo)
            else:
                logger.warning(f"Photo ID {pid} in document {doc_id} not found or not owned by user {current_user.id}.")
    
    # Sort photos by the order in doc['photo_ids'] - important if reordering is implemented
    # photos_in_doc.sort(key=lambda p: doc['photo_ids'].index(p['id']))


    return render_template('document_view.html', document=doc, photos=photos_in_doc, 
                           default_prompt_keys=DEFAULT_PROMPT_KEYS, enumerate=enumerate)

@main_bp.route('/document/<doc_id>/update_combined_text', methods=['POST'])
@login_required
def update_combined_text(doc_id):
    doc = get_document_by_id(doc_id, current_user.id) # Verifies ownership
    if not doc:
        return jsonify({'error': 'Document not found or access denied.'}), 404 # 403 if access denied specifically

    data = request.get_json()
    combined_text = data.get('combined_text', '') # Default to empty string

    # Potentially sanitize combined_text if it's displayed as HTML later without escaping
    
    update_data = {
        'combined_text': combined_text, 
        'combined_text_generated_by_user': True,
        'updated_at': datetime.utcnow().isoformat() # Explicitly set update time
    }

    if update_document(current_user.id, doc_id, update_data):
        return jsonify({'message': 'Combined text saved!'})
    else:
        logger.error(f"Failed to update combined text for doc {doc_id}, user {current_user.id}")
        return jsonify({'error': 'Failed to save combined text.'}), 500

@main_bp.route('/document/<doc_id>/reorder', methods=['POST'])
@login_required
def reorder_pages(doc_id):
    doc = get_document_by_id(doc_id, current_user.id)
    if not doc:
        return jsonify({'error': 'Document not found or access denied.'}), 404
    
    data = request.get_json()
    new_photo_ids_order = data.get('photo_ids')

    if not isinstance(new_photo_ids_order, list):
        return jsonify({'error': 'Invalid data format for photo IDs.'}), 400

    # Validate that all IDs in new_photo_ids_order are currently in the document
    # and that the set of IDs matches (no additions/deletions via this route)
    current_photo_ids_set = set(doc.get('photo_ids', []))
    new_photo_ids_set = set(new_photo_ids_order)

    if current_photo_ids_set != new_photo_ids_set:
        return jsonify({'error': 'Mismatch in photo IDs. Reordering should not add or remove photos.'}), 400
    
    # All IDs are valid and present, just reordered
    update_data = {
        'photo_ids': new_photo_ids_order,
        'updated_at': datetime.utcnow().isoformat()
    }

    if update_document(current_user.id, doc_id, update_data):
        return jsonify({'success': True, 'message': 'Page order updated successfully.'})
    else:
        logger.error(f"Failed to reorder pages for doc {doc_id}, user {current_user.id}")
        return jsonify({'error': 'Failed to update page order.'}), 500

@main_bp.route('/document/<doc_id>/format', methods=['POST'])
@login_required
def format_text(doc_id):
    doc = get_document_by_id(doc_id, current_user.id)
    if not doc:
        return jsonify({'error': 'Document not found or access denied.'}), 404

    data = request.get_json()
    text_to_format = data.get('text')
    format_prompt_key = data.get('prompt_key', 'summarize') # Default to summarize if no key
    custom_prompt_text = data.get('custom_prompt') # Allow entirely custom prompt

    if not text_to_format:
        return jsonify({'error': 'No text provided to format.'}), 400
    
    if not custom_prompt_text and format_prompt_key not in DEFAULT_PROMPT_KEYS:
        return jsonify({'error': f'Invalid prompt key: {format_prompt_key}. Please use a valid key or provide a custom prompt.'}), 400

    logger.info(f"Formatting text for doc {doc_id} using prompt key: {format_prompt_key or 'custom'}")
    formatted_text_result = call_llm(format_prompt_key, text_to_format, custom_prompt_text=custom_prompt_text)

    if formatted_text_result.startswith("Error:"):
        return jsonify({'error': formatted_text_result}), 500 # LLM or config error
    
    return jsonify({'formatted_text': formatted_text_result})

@main_bp.route('/document/<doc_id>/translate', methods=['POST'])
@login_required
def translate_text(doc_id): # Renamed from /document/<doc_id>/format
    doc = get_document_by_id(doc_id, current_user.id) # Ensures doc exists and user has access
    if not doc:
        return jsonify({'error': 'Document not found or access denied.'}), 404

    data = request.get_json()
    text_to_translate = data.get('text')
    # Example: prompt_key could be 'translate_ua_to_en' or 'translate_en_to_ua'
    translation_prompt_key = data.get('prompt_key') 
    custom_prompt_text = data.get('custom_prompt') # Allow entirely custom prompt

    if not text_to_translate:
        return jsonify({'error': 'No text provided for translation.'}), 400
    
    if not custom_prompt_text and (not translation_prompt_key or translation_prompt_key not in DEFAULT_PROMPT_KEYS):
        return jsonify({'error': f'Invalid or missing prompt key for translation. Please select a valid translation prompt or provide a custom one.'}), 400
    
    logger.info(f"Translating text for doc {doc_id} using prompt: {translation_prompt_key or 'custom'}")
    translated_text_result = call_llm(translation_prompt_key, text_to_translate, custom_prompt_text=custom_prompt_text)

    if translated_text_result.startswith("Error:"): # Check if LLM call returned an error string
        return jsonify({'error': translated_text_result}), 500
        
    return jsonify({'translated_text': translated_text_result})

@main_bp.route('/toggle_camera_orientation', methods=['POST'])
@login_required
def toggle_camera_orientation():
    data = request.get_json()
    enabled = data.get('enabled', False)
    rpi_camera_instance.set_portrait_mode(bool(enabled))
    return jsonify({'success': True, 'portrait_mode': rpi_camera_instance.portrait_mode})

# DELETION ROUTES

@main_bp.route('/document/<doc_id>/delete', methods=['DELETE', 'POST'])
@login_required
def delete_document_route(doc_id):
    """Delete an entire document"""
    doc = get_document_by_id(doc_id, current_user.id)
    if not doc:
        return jsonify({'error': 'Document not found or access denied.'}), 404

    if delete_document(current_user.id, doc_id):
        logger.info(f"Document {doc_id} deleted by user {current_user.id}")
        return jsonify({'success': True, 'message': 'Document deleted successfully.'})
    else:
        logger.error(f"Failed to delete document {doc_id} for user {current_user.id}")
        return jsonify({'error': 'Failed to delete document.'}), 500

@main_bp.route('/photo/<photo_id>/delete', methods=['DELETE', 'POST'])
@login_required
def delete_photo_route(photo_id):
    """Delete a photo entirely (from database and filesystem)"""
    photo = get_photo_by_id(photo_id, current_user.id)
    if not photo:
        return jsonify({'error': 'Photo not found or access denied.'}), 404

    # Check if photo is used in any documents
    containing_docs = get_documents_containing_photo(photo_id, current_user.id)
    if containing_docs:
        doc_names = [doc.get('name', 'Untitled') for doc in containing_docs]
        return jsonify({
            'error': f'Cannot delete photo. It is used in the following documents: {", ".join(doc_names)}. Remove it from these documents first.'
        }), 400

    # Delete the physical file
    upload_folder = current_app.config['UPLOAD_FOLDER']
    filepath = os.path.join(upload_folder, photo['image_filename'])
    file_deleted = False
    
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            file_deleted = True
            logger.info(f"Deleted file: {filepath}")
        except Exception as e:
            logger.error(f"Failed to delete file {filepath}: {e}")
            return jsonify({'error': f'Failed to delete photo file: {str(e)}'}), 500
    else:
        logger.warning(f"Photo file not found: {filepath}")
        file_deleted = True  # Consider it "deleted" if it doesn't exist

    # Delete from database
    if file_deleted and delete_photo(current_user.id, photo_id):
        logger.info(f"Photo {photo_id} completely deleted by user {current_user.id}")
        return jsonify({'success': True, 'message': 'Photo deleted successfully.'})
    else:
        logger.error(f"Failed to delete photo {photo_id} from database for user {current_user.id}")
        return jsonify({'error': 'Failed to delete photo from database.'}), 500

@main_bp.route('/document/<doc_id>/photo/<photo_id>/remove', methods=['DELETE', 'POST'])
@login_required
def remove_photo_from_document_route(doc_id, photo_id):
    """Remove a photo from a document (but keep the photo in the database)"""
    doc = get_document_by_id(doc_id, current_user.id)
    if not doc:
        return jsonify({'error': 'Document not found or access denied.'}), 404

    # Verify the photo exists and belongs to the user
    photo = get_photo_by_id(photo_id, current_user.id)
    if not photo:
        return jsonify({'error': 'Photo not found or access denied.'}), 404

    # Verify the photo is actually in this document
    if photo_id not in doc.get('photo_ids', []):
        return jsonify({'error': 'Photo is not in this document.'}), 400

    if remove_photo_from_document(current_user.id, doc_id, photo_id):
        # Regenerate combined text for the document
        remaining_photos = []
        updated_doc = get_document_by_id(doc_id, current_user.id)
        
        if updated_doc and updated_doc.get('photo_ids'):
            for pid in updated_doc['photo_ids']:
                remaining_photo = get_photo_by_id(pid, current_user.id)
                if remaining_photo:
                    remaining_photos.append(remaining_photo)
        
        # Update combined text based on remaining photos
        combined_texts = [p.get('edited_text', '') for p in remaining_photos]
        new_combined_text = "\n\n---\n\n".join(combined_texts)
        
        update_document(current_user.id, doc_id, {
            'combined_text': new_combined_text,
            'combined_text_generated_by_user': False
        })
        
        logger.info(f"Photo {photo_id} removed from document {doc_id} by user {current_user.id}")
        return jsonify({'success': True, 'message': 'Photo removed from document successfully.'})
    else:
        logger.error(f"Failed to remove photo {photo_id} from document {doc_id} for user {current_user.id}")
        return jsonify({'error': 'Failed to remove photo from document.'}), 500

@main_bp.route('/photo/<photo_id>/usage', methods=['GET'])
@login_required
def photo_usage(photo_id):
    """Get information about which documents use a specific photo"""
    photo = get_photo_by_id(photo_id, current_user.id)
    if not photo:
        return jsonify({'error': 'Photo not found or access denied.'}), 404

    containing_docs = get_documents_containing_photo(photo_id, current_user.id)
    
    return jsonify({
        'photo_id': photo_id,
        'filename': photo['image_filename'],
        'used_in_documents': [{'id': doc['id'], 'name': doc.get('name', 'Untitled')} for doc in containing_docs],
        'usage_count': len(containing_docs)
    })

# Consider adding a route to delete a specific photo from a document (and optionally from the system if not used elsewhere)
# @main_bp.route('/document/<doc_id>/photo/<photo_id>/remove', methods=['POST'])

# Consider adding a route to delete a photo entirely from the system
# @main_bp.route('/photo/<photo_id>/delete', methods=['POST']) 

@main_bp.route('/camera_autofocus_state', methods=['GET'])
@login_required
def camera_autofocus_state():
    return jsonify(rpi_camera_instance.get_autofocus_state())

@main_bp.route('/camera_set_autofocus', methods=['POST'])
@login_required
def camera_set_autofocus():
    data = request.get_json()
    enabled = data.get('enabled', False)
    success = rpi_camera_instance.set_autofocus(bool(enabled))
    return jsonify({'success': success, 'enabled': enabled})

@main_bp.route('/camera_trigger_autofocus', methods=['POST'])
@login_required
def camera_trigger_autofocus():
    success = rpi_camera_instance.trigger_autofocus()
    return jsonify({'success': success})

# Debug endpoint - test camera without authentication
@main_bp.route('/debug/camera_test')
def debug_camera_test():
    try:
        logger.info("=== DEBUG: Camera test endpoint called ===")
        logger.info(f"Camera instance: {rpi_camera_instance}")
        logger.info(f"Camera type: {type(rpi_camera_instance)}")
        logger.info(f"Camera initialized: {getattr(rpi_camera_instance, '_is_initialized', 'Unknown')}")
        logger.info(f"Camera object: {getattr(rpi_camera_instance, '_camera', 'Unknown')}")
        
        available = rpi_camera_instance.is_available()
        logger.info(f"Camera available: {available}")
        
        return jsonify({
            'camera_available': available,
            'camera_initialized': getattr(rpi_camera_instance, '_is_initialized', False),
            'camera_object_exists': getattr(rpi_camera_instance, '_camera', None) is not None,
            'streaming': getattr(rpi_camera_instance, '_is_streaming', False)
        })
    except Exception as e:
        logger.error(f"Debug camera test error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500