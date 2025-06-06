# 📷 RPi OCR Formatter

A comprehensive web application for capturing, processing, and managing documents using Raspberry Pi camera with advanced OCR (Optical Character Recognition) and AI-powered text cleanup capabilities.

![RPi OCR Formatter](static/logo.svg)

## 🌟 Features

### 📸 **Advanced Camera System**
- **Live Camera Preview**: Real-time video streaming from Raspberry Pi camera
- **Smart Capture**: Optimized settings for document photography
- **Portrait Mode**: Automatic 90-degree rotation for portrait documents
- **Manual Focus Control**: Autofocus toggle and one-shot focus trigger
- **Optimal Settings**: Automatic exposure, gain, and white balance optimization

### 🔍 **Intelligent OCR Processing**
- **Multi-Language Support**: Ukrainian, English, German, French, Spanish
- **Dual OCR Modes**: Local processing or remote server integration
- **Quality Settings**: Configurable detail levels and paragraph detection
- **Fallback System**: Automatic failover between local and remote OCR

### 🤖 **AI-Powered Text Enhancement**
- **Smart Cleanup**: AI removes OCR artifacts and formatting issues
- **Custom Prompts**: Configurable AI prompts for different document types
- **Translation Services**: Built-in Ukrainian ↔ English translation
- **Action Items**: Automatic extraction of tasks and action items
- **Number Extraction**: Intelligent extraction of important numbers

### 🖼️ **Advanced Image Enhancement**
- **Noise Reduction**: Multiple algorithms with quality/speed trade-offs
- **Contrast Enhancement**: CLAHE with tone preservation
- **Sharpening**: Unsharp mask with configurable strength
- **Color Correction**: White balance and temperature adjustment
- **Experimental Features**: HDR capture and image stacking

### 📁 **Document Management**
- **Photo Gallery**: Organized view of all captured documents
- **Multi-Page Documents**: Combine multiple photos into single documents
- **Text Editing**: Edit OCR results with live preview
- **Search Functionality**: Full-text search across all documents
- **Export Options**: Multiple format support

### 👥 **User Management**
- **Multi-User Support**: Individual user accounts with separate data
- **Secure Authentication**: Flask-Login with password hashing
- **Personal Settings**: Per-user OCR and enhancement preferences
- **Admin Controls**: System-wide configuration management

## 🛠️ Installation

### Prerequisites

- **Raspberry Pi** (4B recommended) with camera module
- **Python 3.8+**
- **pip** package manager
- **Git** for cloning the repository

### Quick Setup

1. **Download and Run Setup Script**
   ```bash
   curl -fsSL https://raw.githubusercontent.com/MUGnifisent/rpi_photodoc/main/setup.sh | bash
   ```
   Note: The setup script will install system dependencies, clone the repository, and set up the Python environment.

2. **Navigate to Project Directory**
   ```bash
   cd rpi_photodoc
   ```

3. **Start the Application**
   ```bash
   bash run.sh
   ```

### Manual Installation

1. **System Dependencies**
   ```bash
   sudo apt update
   sudo apt install -y python3-pip python3-venv git
   sudo apt install -y libcamera-dev python3-libcamera python3-kms++
   sudo apt install -y python3-opencv tesseract-ocr tesseract-ocr-ukr
   ```

2. **Python Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configuration**
   ```bash
   # Create .env file with your settings if needed
   ```

4. **Database Setup**
   ```bash
   python3 -c "from database import init_db; init_db()"
   ```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=production

# LLM Server (Ollama)
LLM_SERVER_URL=http://localhost:11434/api/generate
LLM_MODEL_NAME=llama3.1:8b

# OCR Configuration
OCR_MODE=local  # or 'remote'
OCR_SERVER_URL=http://localhost:8080/ocr

# Upload Settings
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216  # 16MB
```

### System Settings

The application uses YAML configuration files in the `config/` directory:

#### `config/settings.yaml`
```yaml
llm_server_url: http://localhost:11434/api/generate
llm_model_name: llama3.1:8b
ocr_mode: local
ocr_server_url: http://localhost:8080/ocr
```

### Custom Prompts

Prompts are stored in `config/prompts/` and can be customized:

- `cleanup_ocr.txt` - Basic OCR cleanup
- `translate_en_to_ua.txt` - English to Ukrainian translation
- `translate_ua_to_en.txt` - Ukrainian to English translation
- `action_items.txt` - Extract action items
- `extract_numbers.txt` - Extract important numbers
- `summarize.txt` - Document summarization

## 🚀 Usage

### First Run

1. **Access the Application**
   - Open your browser to `http://localhost:5000`
   - Or `http://[raspberry-pi-ip]:5000` for remote access

2. **Create User Account**
   - Click "Sign up" to create your first account
   - All data is stored locally on the device

3. **Configure Settings**
   - Go to Settings → System Settings (for admin users)
   - Configure LLM server and OCR preferences
   - Set up personal enhancement preferences

### Taking Photos

1. **Camera Setup**
   - Navigate to "Upload New"
   - Camera preview will appear automatically
   - Adjust focus and orientation as needed

2. **Capture Process**
   - Click "Start Camera" to begin live preview
   - Use "Portrait Mode" for vertical documents
   - Click "Capture Photo" when ready
   - Processing happens automatically

3. **Review Results**
   - View original and cleaned text
   - Edit results if needed
   - Save to your document gallery

### Document Management

1. **Gallery View**
   - Browse all captured photos
   - Search by text content
   - Sort by date or name

2. **Multi-Page Documents**
   - Select multiple photos
   - Click "Create Document"
   - Combine pages in logical order
   - Generate unified text output

3. **Text Processing**
   - Choose from various AI prompts
   - Translate between languages
   - Extract specific information
   - Export in multiple formats

## 🏗️ Architecture

### System Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │◄──►│  Flask Server   │◄──►│  RPi Camera     │
│   (Frontend)    │    │   (Backend)     │    │   (Hardware)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │    Database     │
                    │   (SQLite)      │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  External APIs  │
                    │  (LLM, OCR)     │
                    └─────────────────┘
```

### Core Components

#### **Flask Application** (`app.py`)
- Main application entry point
- Configuration management
- User session handling
- Blueprint registration

#### **Routes** (`routes.py`)
- HTTP endpoint definitions
- Camera streaming logic
- File upload handling
- OCR processing coordination

#### **Camera System** (`camera_rpi.py`)
- Raspberry Pi camera interface
- Video streaming management
- Thread-safe operations
- Hardware abstraction

#### **Image Enhancement** (`image_enhancement.py`, `rpi_cam_enchance.py`)
- Advanced image processing pipeline
- Multiple enhancement algorithms
- User-configurable settings
- Experimental features (HDR, stacking)

#### **Data Management**
- `models.py` - User data models
- `database.py` - SQLite database operations
- `photo_manager.py` - Photo metadata handling
- `document_manager.py` - Multi-page document logic

#### **Settings System**
- `settings_routes.py` - Configuration endpoints
- `user_settings.py` - Per-user preferences
- YAML-based system configuration

### Database Schema

#### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Photos Table
```sql
CREATE TABLE photos (
    id TEXT PRIMARY KEY,
    user_id INTEGER,
    image_filename TEXT NOT NULL,
    original_ocr_text TEXT,
    ai_cleaned_text TEXT,
    edited_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
```

#### Documents Table
```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    user_id INTEGER,
    name TEXT NOT NULL,
    combined_text TEXT,
    combined_text_generated_by_user BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
```

#### User Settings Table
```sql
CREATE TABLE user_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    category TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    setting_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
```

## 🔧 Advanced Configuration

### Image Enhancement Settings

#### Noise Reduction
```python
# User configurable settings
denoise_enabled: bool = False
denoise_strength: int = 3  # 1-10 scale
denoise_fast_mode: bool = True
```

#### Contrast Enhancement
```python
contrast_enabled: bool = False
contrast_clip_limit: float = 1.5  # 0.5-4.0 range
contrast_preserve_tone: bool = True
```

#### Sharpening
```python
sharpen_enabled: bool = False
sharpen_strength: float = 0.3  # 0.1-1.0 range
```

#### Color Correction
```python
color_correction_enabled: bool = False
color_white_balance: bool = False
color_saturation_factor: float = 1.0  # 0.5-2.0 range
color_temperature_adjustment: float = 0.0  # -1.0 to 1.0
```

#### Camera Settings
```python
camera_optimal_settings: bool = False
camera_exposure_time: int = 33000  # microseconds
camera_analog_gain: float = 1.0  # ISO sensitivity
camera_awb_mode: str = 'auto'  # Auto white balance mode
camera_sharpness: float = 1.0  # 0.0-2.0 range
```

#### Experimental Features
```python
# HDR (High Dynamic Range)
experimental_hdr_enabled: bool = False
experimental_hdr_exposure_times: list = [5000, 20000, 50000]
experimental_hdr_gamma: float = 2.2

# Image Stacking
experimental_stacking_enabled: bool = False
experimental_stacking_num_images: int = 5
experimental_stacking_alignment_threshold: float = 0.7
```

### OCR Configuration

#### Local OCR (EasyOCR)
```python
languages: list = ['uk', 'en']  # Language codes
detail_level: int = 0  # 0=text only, 1=with coordinates, 2=with confidence
paragraph_mode: bool = True
```

#### Remote OCR Server
Configure the standalone OCR server in `ocr_server/`:

```yaml
# ocr_server_config.yaml
server:
  host: '0.0.0.0'
  port: 8080
  debug: false

ocr:
  languages: ['uk', 'en']
  detail: 0
  paragraph: true
  workers: 0  # 0 = auto-detect CPU cores

upload:
  max_file_size: 16777216  # 16MB
  allowed_extensions: ['png', 'jpg', 'jpeg', 'webp', 'tiff', 'bmp']
  temp_cleanup: true

cors:
  enabled: true
  origins: '*'

logging:
  level: 'INFO'
  save_requests: false
  request_log_dir: './ocr_logs'
```

### LLM Integration

The application integrates with Ollama for AI text processing:

1. **Install Ollama**
   ```bash
   curl -fsSL https://ollama.ai/install.sh | sh
   ```

2. **Download Models**
   ```bash
   ollama pull llama3.1:8b
   # or other compatible models
   ```

3. **Configure Endpoint**
   ```yaml
   llm_server_url: http://localhost:11434/api/generate
   llm_model_name: llama3.1:8b
   ```

## 🧪 Development

### Project Structure

```
cursor_test/
├── app.py                 # Main Flask application
├── routes.py             # HTTP routes and endpoints
├── camera_rpi.py         # Raspberry Pi camera interface
├── image_enhancement.py  # Enhancement integration
├── rpi_cam_enchance.py   # Advanced image processing
├── models.py            # User data models
├── database.py          # Database operations
├── photo_manager.py     # Photo metadata management
├── document_manager.py  # Document operations
├── settings_routes.py   # Configuration endpoints
├── user_settings.py     # User preferences
├── config/
│   ├── settings.yaml    # System configuration
│   └── prompts/         # AI prompt templates
├── static/
│   ├── *.css           # Stylesheets
│   ├── *.js            # Frontend JavaScript
│   └── logo.svg        # Application logo
├── templates/
│   └── *.html          # Jinja2 templates
├── ocr_server/
│   ├── ocr_server.py   # Standalone OCR service
│   └── README.MD       # OCR server documentation
├── uploads/            # User uploaded files
├── venv/              # Python virtual environment
├── requirements.txt   # Python dependencies
├── setup.sh          # Installation script
├── run.sh           # Application launcher
├── update.sh        # Update script
└── README.md        # This file
```

### Adding New Features

#### 1. Image Enhancement Algorithms

Create a new enhancer class in `rpi_cam_enchance.py`:

```python
class CustomEnhancer:
    def __init__(self, parameter1=1.0, parameter2=True):
        self.parameter1 = parameter1
        self.parameter2 = parameter2
    
    def enhance(self, image):
        # Your enhancement logic here
        enhanced = process_image(image, self.parameter1, self.parameter2)
        return enhanced
```

#### 2. AI Prompts

Add new prompt files to `config/prompts/`:

```text
# config/prompts/custom_task.txt
Please process the following text according to these rules:
1. Rule one
2. Rule two
3. Rule three

Text to process:
{text}

Please provide the processed result:
```

#### 3. User Settings

Extend the default settings in `user_settings.py`:

```python
DEFAULT_USER_SETTINGS = {
    'custom_category': {
        'setting_name': default_value,
        'another_setting': another_default,
    }
}
```

### Testing


#### Camera Testing
```bash
# Test camera availability
python3 -c "from camera_rpi import RPiCamera; cam = RPiCamera(); print(f'Camera available: {cam.is_available()}')"

# Test image capture
curl -X POST http://localhost:5000/capture_rpi_photo
```

#### OCR Testing
```bash
# Test local OCR
python3 -c "from routes import perform_ocr_local; result = perform_ocr_local('test_image.jpg', {}); print(result)"

# Test remote OCR server
curl -X POST -F "file=@test_image.jpg" http://localhost:8080/ocr
```

### Performance Optimization

#### Image Processing
- Use `fast_mode=True` for noise reduction in production
- Adjust `downscale_factor` for faster processing on slower hardware
- Enable experimental features only when needed

#### Database
- Regular VACUUM operations for SQLite optimization
- Index frequently queried columns
- Implement pagination for large datasets

#### Caching
- Browser caching for static assets
- Image thumbnail generation
- OCR result caching

## 🐛 Troubleshooting

### Common Issues

#### Camera Not Available
```bash
# Check camera connection
vcgencmd get_camera

# Verify permissions
sudo usermod -a -G video $USER

# Restart device if needed
sudo reboot
```

#### OCR Errors
```bash
# Check Tesseract installation
tesseract --version

# Verify language packs
tesseract --list-langs

# Test basic OCR
tesseract test_image.jpg output.txt -l eng
```

#### LLM Connection Issues
```bash
# Check Ollama status
ollama list

# Test API endpoint
curl http://localhost:11434/api/generate -d '{"model":"llama3.1:8b","prompt":"Hello"}'

# Check if Ollama is running
ps aux | grep ollama
```

#### Performance Issues
- **Slow processing**: Enable fast mode in enhancement settings
- **High memory usage**: Reduce image resolution or enable downscaling
- **Network timeouts**: Increase timeout values in configuration

#### Database Issues
```bash
# Check database integrity
sqlite3 app.db "PRAGMA integrity_check;"

# Backup database
cp app.db app_backup_$(date +%Y%m%d).db

# Reset database (WARNING: loses all data)
rm app.db && python3 -c "from database import init_db; init_db()"
```

### Log Files

Application logs are available in:
- Console output (when running with `./run.sh`)
- OCR server output (when running the OCR server separately)

### Debug Mode

Enable debug mode for development:

```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
python3 app.py
```

## 🔒 Security

### Authentication
- Passwords are hashed using Werkzeug's PBKDF2 with salt
- Session management via Flask-Login
- CSRF protection on all forms

### File Handling
- Filename sanitization with secure_filename()
- File type validation
- Size limits enforced
- Upload directory isolation

### Network Security
- CORS configuration for API endpoints
- Input validation and sanitization
- SQL injection prevention with parameterized queries

### Production Deployment

For production use:

1. **Change Default Settings**
   ```bash
   # Generate secure secret key
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Use HTTPS**
   ```bash
   # Install SSL certificate
   sudo apt install certbot
   sudo certbot --nginx
   ```

3. **Firewall Configuration**
   ```bash
   sudo ufw enable
   sudo ufw allow 80
   sudo ufw allow 443
   sudo ufw allow 22  # SSH
   ```

4. **Regular Updates**
   ```bash
   ./update.sh
   ```

## 📋 API Reference

### Camera Endpoints

#### GET `/camera/status`
Check camera availability and streaming status.

**Response:**
```json
{
  "available": true,
  "streaming": false,
  "message": "Camera ready"
}
```

#### POST `/camera/start_stream`
Start camera video streaming.

**Response:**
```json
{
  "success": true,
  "message": "Camera stream started"
}
```

#### POST `/camera/stop_stream`
Stop camera video streaming.

#### GET `/camera/feed`
Get live video stream (MJPEG format).

#### POST `/capture_rpi_photo`
Capture photo from RPi camera with full processing pipeline.

**Response:**
```json
{
  "success": true,
  "message": "Photo captured and processed",
  "photo_id": "uuid-here",
  "filename": "rpi_capture_2024-12-06_14-30-22.jpg",
  "redirect_url": "/gallery"
}
```

### Camera Control Endpoints

#### POST `/camera/set_autofocus`
Toggle autofocus on/off.

**Request:**
```json
{
  "enabled": true
}
```

#### POST `/camera/trigger_autofocus`
Trigger one-shot autofocus.

#### POST `/camera/toggle_orientation`
Toggle portrait mode orientation.

**Request:**
```json
{
  "enabled": true
}
```

### Document Management

#### GET `/gallery`
Display photo gallery with pagination and search.

#### POST `/create_document`
Create multi-page document from selected photos.

**Request:**
```json
{
  "photo_ids": ["uuid1", "uuid2", "uuid3"],
  "document_name": "My Document"
}
```

#### GET `/document/<doc_id>`
View document with all pages and combined text.

#### POST `/document/<doc_id>/update_text`
Update document's combined text.

#### POST `/document/<doc_id>/reorder`
Reorder pages within document.

### Settings API

#### GET `/settings`
Display settings page with current configuration.

#### POST `/settings/user`
Update user-specific settings.

**Request:**
```json
{
  "category": "image_enhancement",
  "settings": {
    "enabled": true,
    "denoise_enabled": true,
    "denoise_strength": 5
  }
}
```

#### POST `/settings/system`
Update system-wide settings (admin only).

**Request:**
```json
{
  "llm_server_url": "http://localhost:11434/api/generate",
  "llm_model_name": "llama3.1:8b",
  "ocr_mode": "local"
}
```

## 🤝 Contributing

### Development Setup

1. **Make Changes** to the codebase
2. **Test Thoroughly** with the application
3. **Update Documentation** as needed

### Code Standards

- **Python**: Follow PEP 8 style guide
- **JavaScript**: Use ES6+ features
- **HTML/CSS**: Semantic markup, mobile-first design
- **Documentation**: Update README for new features



## 🙏 Acknowledgments

- **EasyOCR** - Robust OCR library
- **OpenCV** - Computer vision and image processing
- **Flask** - Web framework
- **Ollama** - Local LLM serving
- **Picamera2** - Raspberry Pi camera interface
- **Bulma** - CSS framework for responsive design

## 📞 Support

### Support
For support, refer to this documentation and the troubleshooting section.

---

**Built with ❤️ for the Raspberry Pi community**

*Last updated: June 2025*