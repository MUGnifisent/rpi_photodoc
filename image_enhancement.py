"""
Image enhancement integration module.
This module integrates the rpi_cam_enchance.py enhancement system 
with the existing camera and OCR processing workflow.
"""

import os
import logging
import cv2
import numpy as np
import yaml
from typing import Optional
from settings_routes import get_image_enhancement_settings
from rpi_cam_enchance import (
    ImageEnhancer,
    OptimalSettingsEnhancer,
    DenoiseEnhancer,
    ContrastEnhancer,
    SharpenEnhancer,
    ColorCorrectionEnhancer,
    HDREnhancer,
    ImageStackingEnhancer
)

logger = logging.getLogger(__name__)

def ensure_ocr_server_config():
    """
    Ensure the OCR server config file exists with default values.
    Creates the file if it doesn't exist.
    """
    try:
        from flask import has_app_context, current_app
        if not has_app_context():
            logger.warning("No Flask app context available, skipping OCR config creation")
            return
            
        config_dir = current_app.config.get('CONFIG_DIR', 'config')
        config_path = os.path.join(config_dir, 'ocr_server_config.yaml')
        
        # Check if file already exists
        if os.path.exists(config_path):
            logger.debug(f"OCR server config already exists: {config_path}")
            return
            
        # Create config directory if it doesn't exist
        os.makedirs(config_dir, exist_ok=True)
        
        # Default OCR server configuration
        default_config = {
            'server': {
                'host': '0.0.0.0',
                'port': 8080,
                'debug': False
            },
            'ocr': {
                'languages': ['uk', 'en'],
                'detail': 0,
                'paragraph': True,
                'workers': 0
            },
            'upload': {
                'max_file_size': 16777216,  # 16MB
                'allowed_extensions': ['png', 'jpg', 'jpeg', 'webp', 'tiff', 'bmp'],
                'temp_cleanup': True
            },
            'cors': {
                'enabled': True,
                'origins': '*'
            },
            'logging': {
                'level': 'INFO',
                'save_requests': False,
                'request_log_dir': './ocr_logs'
            }
        }
        
        # Write the default config file
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write("# OCR Server Configuration\n")
            f.write("# All settings are optional - the server will use sensible defaults\n\n")
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False, indent=2)
            
        logger.info(f"Created default OCR server config: {config_path}")
        
    except Exception as e:
        logger.error(f"Failed to create OCR server config: {e}")

class ImageEnhancementManager:
    """
    Manages image enhancement for the OCR system.
    Integrates the enhancement pipeline with the existing workflow.
    
    IMPORTANT: This class reuses the Flask app's camera instance and 
    does NOT initialize its own camera to prevent conflicts.
    """
    
    def __init__(self):
        self.enhancer = None
        self.settings = None
        self._initialized = False
        # Ensure OCR server config exists
        ensure_ocr_server_config()
    
    def _initialize_enhancer(self):
        """Initialize the image enhancer based on current settings"""
        try:
            # Import here to avoid Flask context issues
            from flask import has_app_context
            if not has_app_context():
                logger.warning("No Flask app context available, skipping enhancement initialization")
                return
                
            self.settings = get_image_enhancement_settings()
            logger.info(f"Initializing image enhancer with settings: {self.settings}")
            
            if not self.settings or not self.settings.get('enabled', False):
                logger.info("Image enhancement is disabled or settings not available")
                self.enhancer = None
                return
            
            # Build enhancement pipeline based on settings
            enhancers = []
            
            # Color correction (usually first for better subsequent processing)
            if self.settings.get('color_correction_enabled', False):
                color_enhancer = ColorCorrectionEnhancer(
                    white_balance=self.settings.get('color_white_balance', True),
                    saturation_factor=self.settings.get('color_saturation_factor', 1.1),
                    temperature_adjustment=self.settings.get('color_temperature_adjustment', 0.0)
                )
                enhancers.append(color_enhancer)
                logger.info("Added color correction enhancer")
            
            # Noise reduction (before sharpening to avoid amplifying noise)
            if self.settings.get('denoise_enabled', False):
                denoise_enhancer = DenoiseEnhancer(
                    h_luminance=self.settings.get('denoise_strength', 5),
                    h_color=self.settings.get('denoise_strength', 5),
                    preserve_colors=True,
                    fast_mode=self.settings.get('denoise_fast_mode', True),
                    downscale_factor=2 if self.settings.get('denoise_fast_mode', True) else 1
                )
                enhancers.append(denoise_enhancer)
                logger.info("Added denoising enhancer")
            
            # Contrast enhancement
            if self.settings.get('contrast_enabled', False):
                contrast_enhancer = ContrastEnhancer(
                    clip_limit=self.settings.get('contrast_clip_limit', 2.0),
                    tile_grid_size=(8, 8),
                    color_space='YCRCB',
                    preserve_tone=self.settings.get('contrast_preserve_tone', True)
                )
                enhancers.append(contrast_enhancer)
                logger.info("Added contrast enhancer")
            
            # Sharpening (usually last to avoid amplifying noise)
            if self.settings.get('sharpen_enabled', False):
                sharpen_enhancer = SharpenEnhancer(
                    strength=self.settings.get('sharpen_strength', 0.8)
                )
                enhancers.append(sharpen_enhancer)
                logger.info("Added sharpening enhancer")
            
            if enhancers:
                # Use BGR format for OpenCV processing
                # IMPORTANT: Do NOT call initialize_camera() on this enhancer
                # to avoid conflicts with the Flask app's camera instance
                self.enhancer = ImageEnhancer(enhancers, input_format='BGR')
                logger.info(f"Image enhancer initialized with {len(enhancers)} enhancers")
                logger.info("WARNING: ImageEnhancer camera initialization disabled to prevent conflicts")
            else:
                logger.info("No enhancers enabled, image enhancement disabled")
                self.enhancer = None
                
            self._initialized = True
                
        except Exception as e:
            logger.error(f"Failed to initialize image enhancer: {e}")
            self.enhancer = None
            self._initialized = True
    
    def apply_camera_settings(self, camera):
        """
        Apply optimal camera settings before capture if enabled.
        
        Args:
            camera: Picamera2 camera object
        """
        try:
            if not self._initialized:
                self._initialize_enhancer()
                
            if not self.settings or not self.settings.get('enabled', False):
                return
            
            if not self.settings.get('camera_optimal_settings', False):
                return
            
            optimal_settings = OptimalSettingsEnhancer(
                exposure_time=self.settings.get('camera_exposure_time', 20000),
                analog_gain=self.settings.get('camera_analog_gain', 1.0),
                awb_mode=self.settings.get('camera_awb_mode', 'auto'),
                sharpness=self.settings.get('camera_sharpness', 1.5)
            )
            
            optimal_settings.apply_to_camera(camera)
            logger.info("Applied optimal camera settings")
            
        except Exception as e:
            logger.error(f"Failed to apply camera settings: {e}")
    
    def apply_experimental_capture(self, camera, output_path: str) -> Optional[str]:
        """
        Apply experimental camera-based enhancers that capture their own images.
        
        Args:
            camera: Picamera2 camera object
            output_path: Path where to save the final image
            
        Returns:
            str: Path to enhanced image if successful, None if failed or not enabled
        """
        try:
            if not self._initialized:
                self._initialize_enhancer()
                
            if not self.settings or not self.settings.get('enabled', False):
                logger.debug("Image enhancement disabled, skipping experimental capture")
                return None
            
            # Check if any experimental features are enabled
            hdr_enabled = self.settings.get('experimental_hdr_enabled', False)
            stacking_enabled = self.settings.get('experimental_stacking_enabled', False)
            
            if not (hdr_enabled or stacking_enabled):
                logger.debug("No experimental features enabled")
                return None
                
            enhanced_image = None
            
            # Apply HDR if enabled (has priority over stacking)
            if hdr_enabled:
                logger.info("Applying experimental HDR enhancement")
                try:
                    hdr_enhancer = HDREnhancer(
                        exposure_times=self.settings.get('experimental_hdr_exposure_times', [5000, 20000, 50000]),
                        camera=camera,
                        gamma=self.settings.get('experimental_hdr_gamma', 2.2),
                        color_input_format='RGB'  # Camera native format
                    )
                    # HDR enhancer captures and processes its own images
                    enhanced_image = hdr_enhancer.enhance(None)  # Input image ignored
                    logger.info("HDR enhancement completed")
                except Exception as e:
                    logger.error(f"HDR enhancement failed: {e}")
                    return None
                    
            # Apply Image Stacking if enabled and HDR not used
            elif stacking_enabled:
                logger.info("Applying experimental image stacking enhancement")
                try:
                    stacking_enhancer = ImageStackingEnhancer(
                        num_images=self.settings.get('experimental_stacking_num_images', 5),
                        camera=camera,
                        alignment_threshold=self.settings.get('experimental_stacking_alignment_threshold', 0.7),
                        color_input_format='RGB'  # Camera native format
                    )
                    # Stacking enhancer captures and processes its own images
                    enhanced_image = stacking_enhancer.enhance(None)  # Input image ignored
                    logger.info("Image stacking enhancement completed")
                except Exception as e:
                    logger.error(f"Image stacking enhancement failed: {e}")
                    return None
            
            if enhanced_image is not None:
                # Convert from RGB (camera format) to BGR (OpenCV format) for saving
                enhanced_image_bgr = cv2.cvtColor(enhanced_image, cv2.COLOR_RGB2BGR)
                
                # Save the enhanced image
                success = cv2.imwrite(output_path, enhanced_image_bgr)
                if success:
                    logger.info(f"Experimental enhancement saved to {output_path}")
                    return output_path
                else:
                    logger.error(f"Failed to save experimental enhancement to {output_path}")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error in experimental capture enhancement: {e}")
            return None

    def enhance_image(self, image_path: str) -> bool:
        """
        Enhance an image file in place.
        
        Args:
            image_path: Path to the image file to enhance
            
        Returns:
            bool: True if enhancement was applied successfully, False otherwise
        """
        try:
            if not self._initialized:
                self._initialize_enhancer()
                
            # Check if enhancement is enabled
            if not self.settings or not self.settings.get('enabled', False):
                logger.debug("Image enhancement is disabled, skipping enhancement")
                return True
            
            if not self.enhancer:
                logger.debug("No enhancer available, skipping enhancement")
                return True
            
            if not os.path.exists(image_path):
                logger.error(f"Image file not found: {image_path}")
                return False
            
            logger.info(f"Enhancing image: {image_path}")
            
            # Load image using OpenCV (BGR format)
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return False
            
            # Apply enhancements
            enhanced_image = self.enhancer.enhance_image(image)
            
            # Safety check: Ensure enhanced image is valid
            if enhanced_image is None:
                logger.error("Enhancement returned None, keeping original image")
                return True
            
            # Check if image went completely black (common enhancement failure)
            mean_brightness = np.mean(enhanced_image)
            if mean_brightness < 5:  # Very dark image, likely corrupted
                logger.warning(f"Enhanced image too dark (mean brightness: {mean_brightness:.2f}), keeping original")
                return True
            
            # Check for unusual color artifacts (red/blue spots)
            if len(enhanced_image.shape) == 3:  # Color image
                b_mean, g_mean, r_mean = np.mean(enhanced_image, axis=(0,1))
                color_ratio = max(r_mean, b_mean) / max(g_mean, 1)  # Avoid division by zero
                if color_ratio > 3:  # Excessive red or blue artifacts
                    logger.warning(f"Enhanced image has color artifacts (ratio: {color_ratio:.2f}), keeping original")
                    return True
            
            # Save enhanced image back to the same path
            success = cv2.imwrite(image_path, enhanced_image)
            if success:
                logger.info(f"Successfully enhanced and saved image: {image_path}")
                return True
            else:
                logger.error(f"Failed to save enhanced image: {image_path}")
                return False
            
        except Exception as e:
            logger.error(f"Error enhancing image {image_path}: {e}")
            return False
    
    def refresh_settings(self):
        """Refresh enhancement settings and reinitialize enhancer"""
        logger.info("Refreshing image enhancement settings")
        self._initialized = False
        self._initialize_enhancer()

# Global instance
enhancement_manager = ImageEnhancementManager()