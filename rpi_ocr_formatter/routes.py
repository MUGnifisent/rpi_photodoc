import os
from flask import render_template, Blueprint, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import easyocr
import cv2
from models import User

main_bp = Blueprint('main', __name__)

# Initialize EasyOCR Reader
# This might take a moment the first time it runs as it downloads models
reader = easyocr.Reader(['en']) # Specify English, add other languages if needed

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.upload_page'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.get_by_username(username)
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('main.upload_page'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.upload_page'))
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
            return redirect(url_for('main.upload_page'))
        else:
            flash('An error occurred during registration.', 'error') # Should not happen with in-memory
            
    return render_template('register.html')

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main_bp.route('/upload', methods=['GET'])
@login_required
def upload_page():
    return render_template('upload.html', extracted_text=None)

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
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Perform OCR
        try:
            result = reader.readtext(filepath)
            extracted_text = "\n".join([item[1] for item in result])
            # We can remove the file after processing if not needed anymore
            # os.remove(filepath) 
        except Exception as e:
            flash(f'Error during OCR: {str(e)}', 'error')
            extracted_text = "Error processing image."
            # os.remove(filepath) # Also remove if error

        return render_template('upload.html', extracted_text=extracted_text, filename=filename)
    else:
        flash('File type not allowed', 'error')
        return redirect(url_for('main.upload_page'))

# Placeholder for text management page
@main_bp.route('/manage_text')
@login_required
def manage_text():
    # This will eventually display texts from multiple uploads, allow combining, etc.
    return render_template('manage_text.html') 