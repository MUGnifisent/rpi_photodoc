#!/usr/bin/env python3
"""
Standalone OCR Server
A simple HTTP server that accepts image uploads and returns OCR text results.

Usage:
    python ocr_server.py

Optional configuration file: ocr_server_config.yaml
"""

import os
import json
import logging
import tempfile
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import easyocr
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OCRServer:
    def __init__(self, config_file='./config/ocr_server_config.yaml'):
        self.app = Flask(__name__)
        self.config_file = config_file
        self.config = self.load_config()
        self.setup_app()
        self.setup_cors()
        self.setup_routes()
        self.reader = None
        self.initialize_ocr()

    def load_config(self):
        """Load configuration from file or use defaults"""
        default_config = {
            'server': {
                'host': '0.0.0.0',
                'port': 8080,
                'debug': False
            },
            'ocr': {
                'languages': ['uk', 'en'],  # Ukrainian and English
                'detail': 0,  # 0 = text only, 1 = with coordinates
                'paragraph': True,
                'workers': 0  # 0 = auto, or specify number of workers
            },
            'upload': {
                'max_file_size': 16 * 1024 * 1024,  # 16MB
                'allowed_extensions': ['png', 'jpg', 'jpeg', 'webp', 'tiff', 'bmp'],
                'temp_cleanup': True
            },
            'cors': {
                'enabled': True,
                'origins': '*'  # In production, specify allowed origins
            },
            'logging': {
                'level': 'INFO',
                'save_requests': False,  # Save processed images for debugging
                'request_log_dir': './ocr_logs'
            }
        }

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    file_config = yaml.safe_load(f) or {}
                logger.info(f"Loaded configuration from {self.config_file}")
                
                # Merge configs (file config overrides defaults)
                def merge_dict(default, override):
                    result = default.copy()
                    for key, value in override.items():
                        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                            result[key] = merge_dict(result[key], value)
                        else:
                            result[key] = value
                    return result
                
                return merge_dict(default_config, file_config)
            except Exception as e:
                logger.warning(f"Error loading config file {self.config_file}: {e}")
                logger.info("Using default configuration")
        else:
            logger.info(f"Config file {self.config_file} not found, using defaults")
            # Create example config file
            self.create_example_config(default_config)

        return default_config

    def create_example_config(self, config):
        """Create an example configuration file"""
        try:
            example_file = './config/ocr_server_config.yaml'
            with open(example_file, 'w') as f:
                yaml.dump(config, f, indent=2, default_flow_style=False)
            logger.info(f"Created example configuration file: {example_file}")
        except Exception as e:
            logger.warning(f"Could not create example config: {e}")

    def setup_app(self):
        """Configure Flask app"""
        self.app.config['MAX_CONTENT_LENGTH'] = self.config['upload']['max_file_size']
        
        # Set logging level
        log_level = self.config['logging']['level'].upper()
        if hasattr(logging, log_level):
            logging.getLogger().setLevel(getattr(logging, log_level))

    def setup_cors(self):
        """Setup CORS if enabled"""
        if self.config['cors']['enabled']:
            CORS(self.app, origins=self.config['cors']['origins'])
            logger.info("CORS enabled")

    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'ocr_ready': self.reader is not None
            })

        @self.app.route('/info', methods=['GET'])
        def server_info():
            """Server information endpoint"""
            return jsonify({
                'server': 'OCR Server',
                'version': '1.0.0',
                'supported_languages': self.config['ocr']['languages'],
                'max_file_size': self.config['upload']['max_file_size'],
                'allowed_extensions': self.config['upload']['allowed_extensions']
            })

        @self.app.route('/ocr', methods=['POST'])
        def process_ocr():
            """Main OCR processing endpoint"""
            try:
                # Check if OCR is initialized
                if self.reader is None:
                    return jsonify({
                        'success': False,
                        'error': 'OCR engine not initialized'
                    }), 500

                # Check if file is present
                if 'image' not in request.files:
                    return jsonify({
                        'success': False,
                        'error': 'No image file provided'
                    }), 400

                file = request.files['image']
                if file.filename == '':
                    return jsonify({
                        'success': False,
                        'error': 'No file selected'
                    }), 400

                # Validate file extension
                if not self.is_allowed_file(file.filename):
                    return jsonify({
                        'success': False,
                        'error': f'File type not allowed. Supported: {self.config["upload"]["allowed_extensions"]}'
                    }), 400

                # Process the image
                result = self.process_image(file)
                return jsonify(result)

            except Exception as e:
                logger.error(f"Error processing OCR request: {e}", exc_info=True)
                return jsonify({
                    'success': False,
                    'error': f'Internal server error: {str(e)}'
                }), 500

        @self.app.errorhandler(413)
        def file_too_large(e):
            return jsonify({
                'success': False,
                'error': f'File too large. Maximum size: {self.config["upload"]["max_file_size"]} bytes'
            }), 413

    def is_allowed_file(self, filename):
        """Check if file extension is allowed"""
        if not filename:
            return False
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.config['upload']['allowed_extensions']

    def initialize_ocr(self):
        """Initialize EasyOCR reader"""
        try:
            logger.info("Initializing EasyOCR...")
            languages = self.config['ocr']['languages']
            logger.info(f"Loading languages: {languages}")
            
            self.reader = easyocr.Reader(
                languages,
                gpu=False  # Set to True if you have GPU support
            )
            logger.info("EasyOCR initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            logger.error("OCR functionality will not be available")

    def process_image(self, file):
        """Process uploaded image with OCR"""
        temp_file = None
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                file.save(temp_file.name)
                temp_file_path = temp_file.name

            logger.info(f"Processing image: {file.filename}")
            
            # Perform OCR
            ocr_config = self.config['ocr']
            result = self.reader.readtext(
                temp_file_path,
                detail=ocr_config['detail'],
                paragraph=ocr_config['paragraph'],
                workers=ocr_config['workers']
            )

            # Extract text
            if ocr_config['detail'] == 0:
                # Text only
                text = "\n".join(result) if result else ""
            else:
                # With coordinates - extract just the text
                text = "\n".join([item[1] for item in result]) if result else ""

            # Save request for debugging if enabled
            if self.config['logging']['save_requests']:
                self.save_request_log(file.filename, text)

            logger.info(f"OCR completed. Text length: {len(text)}")
            
            return {
                'success': True,
                'text': text,
                'length': len(text),
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error processing image {file.filename}: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'OCR processing failed: {str(e)}'
            }
        
        finally:
            # Cleanup temporary file
            if temp_file and self.config['upload']['temp_cleanup']:
                try:
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file: {e}")

    def save_request_log(self, filename, text):
        """Save request log for debugging"""
        try:
            log_dir = self.config['logging']['request_log_dir']
            os.makedirs(log_dir, exist_ok=True)
            
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'filename': filename,
                'text': text,
                'text_length': len(text)
            }
            
            log_file = os.path.join(log_dir, f"ocr_request_{uuid.uuid4().hex[:8]}.json")
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_entry, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.warning(f"Failed to save request log: {e}")

    def run(self):
        """Start the OCR server"""
        server_config = self.config['server']
        
        logger.info("="*50)
        logger.info("OCR Server Starting")
        logger.info("="*50)
        logger.info(f"Host: {server_config['host']}")
        logger.info(f"Port: {server_config['port']}")
        logger.info(f"Debug: {server_config['debug']}")
        logger.info(f"OCR Languages: {self.config['ocr']['languages']}")
        logger.info(f"Max file size: {self.config['upload']['max_file_size']} bytes")
        logger.info(f"Allowed extensions: {self.config['upload']['allowed_extensions']}")
        logger.info("="*50)
        logger.info("Endpoints:")
        logger.info("  GET  /health - Health check")
        logger.info("  GET  /info   - Server information")
        logger.info("  POST /ocr    - OCR processing")
        logger.info("="*50)
        
        if self.reader is None:
            logger.warning("WARNING: OCR engine not initialized! Server will accept requests but OCR will fail.")
        
        try:
            self.app.run(
                host=server_config['host'],
                port=server_config['port'],
                debug=server_config['debug'],
                threaded=True  # Allow multiple concurrent requests
            )
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}")

def main():
    """Main entry point"""
    print("Starting OCR Server...")
    
    # Check for required dependencies
    try:
        import easyocr
        import flask
        import yaml
    except ImportError as e:
        print(f"Missing required dependency: {e}")
        print("Please install required packages:")
        print("pip install flask flask-cors easyocr pyyaml")
        return 1
    
    # Start server
    server = OCRServer()
    server.run()
    return 0

if __name__ == '__main__':
    exit(main())