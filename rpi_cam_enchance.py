import cv2
import numpy as np
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from datetime import datetime
from picamera2 import Picamera2
import libcamera

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("image_enhancer.log"),
        logging.StreamHandler()
    ]
)

class BaseEnhancer(ABC):
    """
    Abstract base class for all image enhancers.
    
    All enhancer classes inherit from this class and implement
    the enhance method.
    """
    
    def __init__(self):
        """Initialize the enhancer with a class-specific logger."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Initializing {self.__class__.__name__}")
    
    @abstractmethod
    def enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance the provided image.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            np.ndarray: Enhanced image as numpy array
        """
        pass


class OptimalSettingsEnhancer(BaseEnhancer):
    """
    Camera configuration class that optimizes settings for image quality.
    
    This class is not a traditional image enhancer as it doesn't process
    images directly. Instead, it configures camera parameters before capture.
    
    NOTE: Apply this to the camera BEFORE capturing images.
    """
    
    def __init__(self, 
                 exposure_time: int = 20000,
                 analog_gain: float = 1.0,
                 awb_mode: str = 'auto',
                 sharpness: float = 1.5):
        """
        Initialize with specific camera settings.
        
        Args:
            exposure_time: Exposure time in microseconds
            analog_gain: Analog gain (similar to ISO)
            awb_mode: Auto white balance mode ('auto', 'tungsten', 'daylight', etc.)
            sharpness: Sharpness level
        """
        super().__init__()
        self.logger.info(f"Setting exposure={exposure_time}, gain={analog_gain}, "
                         f"awb={awb_mode}, sharpness={sharpness}")
        
        self.exposure_time = exposure_time
        self.analog_gain = analog_gain
        
        # Convert string AWB mode to libcamera enum
        awb_modes = {
            'auto': libcamera.controls.AwbModeEnum.Auto,
            'tungsten': libcamera.controls.AwbModeEnum.Tungsten,
            'daylight': libcamera.controls.AwbModeEnum.Daylight,
            'cloudy': libcamera.controls.AwbModeEnum.Cloudy,
            'indoor': libcamera.controls.AwbModeEnum.Indoor,
        }
        self.awb_mode = awb_modes.get(awb_mode.lower(), libcamera.controls.AwbModeEnum.Auto)
        self.sharpness = sharpness
    
    def enhance(self, image: np.ndarray) -> np.ndarray:
        """
        This method exists only to satisfy the BaseEnhancer interface.
        
        NOTE: This class does not enhance images directly.
        Use apply_to_camera() method instead.
        
        Args:
            image: Input image (unmodified by this enhancer)
            
        Returns:
            np.ndarray: The input image (unchanged)
        """
        self.logger.warning("OptimalSettingsEnhancer does not process images directly. "
                           "Use apply_to_camera() method before capturing.")
        return image
    
    def apply_to_camera(self, camera: Picamera2) -> None:
        """
        Apply settings to a camera object.
        
        Args:
            camera: Picamera2 object to configure
        """
        self.logger.info("Applying optimal settings to camera")
        try:
            camera.set_controls({
                "ExposureTime": self.exposure_time,
                "AnalogueGain": self.analog_gain,
                "AwbMode": self.awb_mode,
                "Sharpness": self.sharpness
            })
            time.sleep(2)  # Allow settings to take effect
            self.logger.info("Camera settings applied successfully")
        except Exception as e:
            self.logger.error(f"Failed to apply camera settings: {str(e)}")
            raise


class DenoiseEnhancer(BaseEnhancer):
    """
    Enhancer that applies noise reduction to the image.
    
    Uses OpenCV's denoising algorithms with optimizations for performance.
    """
    
    def __init__(self, 
                 h_luminance: int = 5, 
                 h_color: int = 5,
                 template_window_size: int = 7,
                 search_window_size: int = 21,
                 preserve_colors: bool = True,
                 fast_mode: bool = False,
                 downscale_factor: int = 1):
        """
        Initialize denoising parameters.
        
        Args:
            h_luminance: Filter strength for luminance component (lower = more detail)
            h_color: Filter strength for color components (lower = more accurate color)
            template_window_size: Size of template patch
            search_window_size: Size of window for weighted average calculation
            preserve_colors: Whether to use YCrCb color space to better preserve colors
            fast_mode: Use faster but lower quality denoising algorithm
            downscale_factor: Downscale image by this factor before denoising (1 = no downscaling)
        """
        super().__init__()
        self.logger.info(f"Setting h_luminance={h_luminance}, h_color={h_color}, "
                         f"preserve_colors={preserve_colors}, fast_mode={fast_mode}, "
                         f"downscale_factor={downscale_factor}")
        
        self.h_luminance = h_luminance
        self.h_color = h_color
        self.template_window_size = template_window_size
        self.search_window_size = search_window_size
        self.preserve_colors = preserve_colors
        self.fast_mode = fast_mode
        self.downscale_factor = max(1, downscale_factor)  # Ensure minimum of 1
    
    def enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Apply noise reduction to the image.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            np.ndarray: Denoised image as numpy array
        """
        self.logger.info("Applying denoising")
        start_time = time.time()
        
        try:
            # Downscale for faster processing if requested
            original_size = None
            if self.downscale_factor > 1:
                original_size = image.shape[:2]
                self.logger.info(f"Downscaling by factor of {self.downscale_factor} for faster processing")
                new_size = (image.shape[1] // self.downscale_factor, 
                           image.shape[0] // self.downscale_factor)
                image = cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)
            
            # Choose denoising method
            if self.fast_mode:
                denoised_image = self._apply_fast_denoising(image)
            elif self.preserve_colors:
                denoised_image = self._apply_channel_denoising(image)
            else:
                denoised_image = self._apply_standard_denoising(image)
            
            # Upscale back to original size if needed
            if original_size is not None:
                self.logger.info("Upscaling back to original size")
                denoised_image = cv2.resize(denoised_image, 
                                          (original_size[1], original_size[0]), 
                                          interpolation=cv2.INTER_LINEAR)
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"Denoising completed in {elapsed_time:.2f} seconds")
            return denoised_image
            
        except Exception as e:
            self.logger.error(f"Denoising failed: {str(e)}")
            raise
    
    def _apply_channel_denoising(self, image: np.ndarray) -> np.ndarray:
        """Apply non-local means denoising to each channel separately."""
        # Convert to YCrCb color space for better color preservation
        ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        y, cr, cb = cv2.split(ycrcb)
        
        # Apply denoising only to luminance channel
        self.logger.info("Applying NLMeans denoising to luminance channel")
        y_denoised = cv2.fastNlMeansDenoising(
            y, None, self.h_luminance, 
            self.template_window_size, 
            self.search_window_size
        )
        
        # Only apply lighter denoising to color channels
        self.logger.info("Applying lighter denoising to chrominance channels")
        cr_denoised = cv2.fastNlMeansDenoising(
            cr, None, self.h_color, 
            self.template_window_size, 
            self.search_window_size
        )
        
        cb_denoised = cv2.fastNlMeansDenoising(
            cb, None, self.h_color, 
            self.template_window_size, 
            self.search_window_size
        )
        
        # Merge channels and convert back to BGR
        denoised_ycrcb = cv2.merge([y_denoised, cr_denoised, cb_denoised])
        return cv2.cvtColor(denoised_ycrcb, cv2.COLOR_YCrCb2BGR)
    
    def _apply_standard_denoising(self, image: np.ndarray) -> np.ndarray:
        """Apply standard colored non-local means denoising."""
        self.logger.info("Applying standard NLMeans denoising")
        return cv2.fastNlMeansDenoisingColored(
            image, None, self.h_luminance, self.h_color, 
            self.template_window_size, self.search_window_size
        )
    
    def _apply_fast_denoising(self, image: np.ndarray) -> np.ndarray:
        """Apply faster denoising using bilateral filter."""
        self.logger.info("Applying fast bilateral filter denoising")
        
        # Convert to YCrCb color space for better color preservation
        if self.preserve_colors:
            ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
            y, cr, cb = cv2.split(ycrcb)
            
            # Apply bilateral filter to luminance channel only
            y_denoised = cv2.bilateralFilter(
                y, d=9, sigmaColor=self.h_luminance*2, sigmaSpace=self.h_luminance
            )
            
            # Merge channels and convert back to BGR
            denoised_ycrcb = cv2.merge([y_denoised, cr, cb])
            return cv2.cvtColor(denoised_ycrcb, cv2.COLOR_YCrCb2BGR)
        else:
            # Apply bilateral filter to full color image
            return cv2.bilateralFilter(
                image, d=9, sigmaColor=self.h_luminance*2, sigmaSpace=self.h_luminance
            )


class ContrastEnhancer(BaseEnhancer):
    """
    Enhancer that improves image contrast using CLAHE.
    
    Applies Contrast Limited Adaptive Histogram Equalization to improve
    local contrast while limiting noise amplification and preserving colors.
    """
    
    def __init__(self, 
                 clip_limit: float = 2.0, 
                 tile_grid_size: Tuple[int, int] = (8, 8), 
                 color_space: str = 'YCRCB',
                 preserve_tone: bool = True):
        """
        Initialize contrast enhancement parameters.
        
        Args:
            clip_limit: Threshold for contrast limiting
            tile_grid_size: Size of grid for histogram equalization
            color_space: Color space to use for enhancement ('LAB' or 'YCRCB')
            preserve_tone: Apply tone preservation to avoid color shifts
        """
        super().__init__()
        self.logger.info(f"Setting clip_limit={clip_limit}, color_space={color_space}, "
                         f"preserve_tone={preserve_tone}")
        
        self.clip_limit = clip_limit
        self.tile_grid_size = tile_grid_size
        self.color_space = color_space.upper()
        self.preserve_tone = preserve_tone
        
        if self.color_space not in ['LAB', 'YCRCB']:
            self.logger.warning(f"Unsupported color space: {color_space}. Defaulting to YCRCB.")
            self.color_space = 'YCRCB'
    
    def enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance contrast using CLAHE with color preservation.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            np.ndarray: Contrast-enhanced image as numpy array
        """
        self.logger.info(f"Applying contrast enhancement using {self.color_space} color space")
        start_time = time.time()
        
        try:
            # Store original image for tone preservation
            original = image.copy() if self.preserve_tone else None
            
            # Convert to appropriate color space
            if self.color_space == 'LAB':
                converted = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            else:
                converted = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
            
            # Split channels - in both cases, first channel is luminance/lightness
            channels = list(cv2.split(converted))  # Convert tuple to list so we can modify it
            
            # Apply CLAHE to luminance/lightness channel only
            clahe = cv2.createCLAHE(
                clipLimit=self.clip_limit, 
                tileGridSize=self.tile_grid_size
            )
            channels[0] = clahe.apply(channels[0])
            
            # Merge channels
            enhanced_converted = cv2.merge(channels)
            
            # Convert back to BGR
            if self.color_space == 'LAB':
                enhanced_image = cv2.cvtColor(enhanced_converted, cv2.COLOR_LAB2BGR)
            else:
                enhanced_image = cv2.cvtColor(enhanced_converted, cv2.COLOR_YCrCb2BGR)
            
            # Apply tone preservation if requested
            if self.preserve_tone:
                # Calculate luminance of original and enhanced images
                original_luminance = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY).astype(np.float32)
                enhanced_luminance = cv2.cvtColor(enhanced_image, cv2.COLOR_BGR2GRAY).astype(np.float32)
                
                # Avoid division by zero
                original_luminance = np.maximum(original_luminance, 0.01)
                
                # Calculate luminance ratio
                ratio = enhanced_luminance / original_luminance
                
                # Apply the ratio to each channel to preserve colors
                enhanced_image = original.copy().astype(np.float32)
                for c in range(3):  # For each BGR channel
                    enhanced_image[:,:,c] = np.clip(enhanced_image[:,:,c] * ratio, 0, 255)
                
                enhanced_image = enhanced_image.astype(np.uint8)
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"Contrast enhancement completed in {elapsed_time:.2f} seconds")
            return enhanced_image
            
        except Exception as e:
            self.logger.error(f"Contrast enhancement failed: {str(e)}")
            raise


class SharpenEnhancer(BaseEnhancer):
    """
    Enhancer that sharpens the image.
    
    Applies a sharpening kernel to enhance edge details in the image.
    """
    
    def __init__(self, strength: float = 0.8):
        """
        Initialize sharpening parameters.
        
        Args:
            strength: Sharpening strength factor (1.0 is standard sharpening)
        """
        super().__init__()
        self.logger.info(f"Setting sharpening strength={strength}")
        
        # Calculate kernel based on strength
        center_value = 1.0 + 4.0 * strength
        self.kernel = np.array([
            [0, -1 * strength, 0],
            [-1 * strength, center_value, -1 * strength],
            [0, -1 * strength, 0]
        ])
    
    def enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Apply sharpening to the image.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            np.ndarray: Sharpened image as numpy array
        """
        self.logger.info("Applying image sharpening")
        start_time = time.time()
        
        try:
            sharpened = cv2.filter2D(image, -1, self.kernel)
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"Sharpening completed in {elapsed_time:.2f} seconds")
            return sharpened
            
        except Exception as e:
            self.logger.error(f"Sharpening failed: {str(e)}")
            raise


class ColorCorrectionEnhancer(BaseEnhancer):
    """
    Enhancer that applies color correction to improve color accuracy.
    
    This class provides methods for correcting color issues like
    color cast, white balance problems, and color saturation.
    """
    
    def __init__(self, 
                 white_balance: bool = True,
                 saturation_factor: float = 1.1,
                 temperature_adjustment: float = 0.0):
        """
        Initialize color correction parameters.
        
        Args:
            white_balance: Whether to apply automatic white balance correction
            saturation_factor: Factor to adjust color saturation (1.0 = no change)
            temperature_adjustment: Color temperature adjustment (-1.0 = cooler, 1.0 = warmer)
        """
        super().__init__()
        self.logger.info(f"Setting white_balance={white_balance}, "
                         f"saturation_factor={saturation_factor}, "
                         f"temperature_adjustment={temperature_adjustment}")
        
        self.white_balance = white_balance
        self.saturation_factor = saturation_factor
        self.temperature_adjustment = np.clip(temperature_adjustment, -1.0, 1.0)
    
    def enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Apply color correction to the image.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            np.ndarray: Color-corrected image as numpy array
        """
        self.logger.info("Applying color correction")
        start_time = time.time()
        
        try:
            corrected_image = image.copy()
            
            # Apply automatic white balance if requested
            if self.white_balance:
                corrected_image = self._apply_white_balance(corrected_image)
            
            # Apply color temperature adjustment
            if self.temperature_adjustment != 0.0:
                corrected_image = self._adjust_temperature(corrected_image, self.temperature_adjustment)
            
            # Apply saturation adjustment
            if self.saturation_factor != 1.0:
                corrected_image = self._adjust_saturation(corrected_image, self.saturation_factor)
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"Color correction completed in {elapsed_time:.2f} seconds")
            return corrected_image
            
        except Exception as e:
            self.logger.error(f"Color correction failed: {str(e)}")
            raise
    
    def _apply_white_balance(self, image: np.ndarray) -> np.ndarray:
        """
        Apply gray world automatic white balance algorithm.
        
        Args:
            image: Input image
            
        Returns:
            White-balanced image
        """
        # Convert image to float32 for processing
        img_float = image.astype(np.float32)
        
        # Compute average BGR values
        avg_b = np.mean(img_float[:, :, 0])
        avg_g = np.mean(img_float[:, :, 1])
        avg_r = np.mean(img_float[:, :, 2])
        
        # Calculate illumination
        illumination = (avg_b + avg_g + avg_r) / 3
        
        # Compute scaling factors
        if avg_b > 0 and avg_g > 0 and avg_r > 0:
            kb = illumination / avg_b
            kg = illumination / avg_g
            kr = illumination / avg_r
            
            # Apply scaling
            img_float[:, :, 0] = np.clip(img_float[:, :, 0] * kb, 0, 255)
            img_float[:, :, 1] = np.clip(img_float[:, :, 1] * kg, 0, 255)
            img_float[:, :, 2] = np.clip(img_float[:, :, 2] * kr, 0, 255)
        
        return img_float.astype(np.uint8)
    
    def _adjust_saturation(self, image: np.ndarray, factor: float) -> np.ndarray:
        """
        Adjust color saturation.
        
        Args:
            image: Input image
            factor: Saturation adjustment factor
            
        Returns:
            Saturation-adjusted image
        """
        # Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
        
        # Adjust saturation
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * factor, 0, 255)
        
        # Convert back to BGR
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    
    def _adjust_temperature(self, image: np.ndarray, adjustment: float) -> np.ndarray:
        """
        Adjust color temperature (warmer/cooler).
        
        Args:
            image: Input image
            adjustment: Temperature adjustment (-1.0 to 1.0)
            
        Returns:
            Temperature-adjusted image
        """
        if adjustment > 0:  # Warmer
            blue_factor = 1.0 - (0.2 * adjustment)
            red_factor = 1.0 + (0.2 * adjustment)
        else:  # Cooler (adjustment is negative)
            blue_factor = 1.0 - (0.2 * adjustment)
            red_factor = 1.0 + (0.2 * adjustment)
        
        # Apply factors to channels
        result = image.copy().astype(np.float32)
        result[:, :, 0] = np.clip(result[:, :, 0] * blue_factor, 0, 255)  # Blue channel
        result[:, :, 2] = np.clip(result[:, :, 2] * red_factor, 0, 255)   # Red channel
        
        return result.astype(np.uint8)


# Multi-frame enhancers - These require direct camera access
class HDREnhancer(BaseEnhancer):
    """
    Enhancer that creates HDR images from multiple exposures.
    
    NOTE: This enhancer requires direct access to the camera and captures
    multiple images at different exposures.
    """
    
    def __init__(self, 
                 exposure_times: List[int] = None,
                 camera: Optional[Picamera2] = None,
                 gamma: float = 2.2,
                 color_input_format: str = 'RGB'):
        """
        Initialize HDR parameters.
        
        Args:
            exposure_times: List of exposure times in microseconds
            camera: Picamera2 object for capturing
            gamma: Gamma correction factor for tone mapping
            color_input_format: Color format of input images ('BGR' or 'RGB')
        """
        super().__init__()
        self.exposure_times = exposure_times or [5000, 20000, 50000]
        self.camera = camera
        self.gamma = gamma
        self.color_input_format = color_input_format.upper()
        
        if self.color_input_format not in ['BGR', 'RGB']:
            self.logger.warning(f"Unsupported input format: {color_input_format}. Defaulting to RGB.")
            self.color_input_format = 'RGB'
        
        self.logger.info(f"Setting exposure_times={self.exposure_times}, gamma={gamma}, "
                         f"color_input_format={self.color_input_format}")
    
    def enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Apply HDR processing using multiple camera exposures.
        
        NOTE: This method ignores the input image if a camera is provided
        and captures a new HDR sequence.
        
        Args:
            image: Input image (ignored if camera is provided)
            
        Returns:
            np.ndarray: HDR processed image as numpy array
        """
        self.logger.info("HDR processing starting")
        
        if self.camera is None:
            self.logger.warning("No camera provided to HDREnhancer. Returning input image unchanged.")
            return image
        
        try:
            # Capture multiple exposures
            self.logger.info(f"Capturing {len(self.exposure_times)} exposures")
            images = []
            
            for exp in self.exposure_times:
                self.logger.info(f"Setting exposure time to {exp} µs")
                self.camera.set_controls({"ExposureTime": exp})
                time.sleep(1)  # Allow exposure to settle
                raw_img = self.camera.capture_array()
                
                # Convert from RGB (camera native) to BGR (OpenCV native) if needed
                if self.color_input_format == 'RGB':
                    img = cv2.cvtColor(raw_img, cv2.COLOR_RGB2BGR)
                else:
                    img = raw_img
                    
                images.append(img)
            
            # Convert to 8-bit images for OpenCV HDR
            imgs_8bit = [cv2.convertScaleAbs(img) for img in images]
            
            # Normalize exposure times to seconds for OpenCV
            exp_times_sec = np.array(self.exposure_times, dtype=np.float32) / 1000000.0
            
            # Merge to HDR
            merge_debevec = cv2.createMergeDebevec()
            hdr = merge_debevec.process(imgs_8bit, times=exp_times_sec)
            
            # Tone mapping
            tonemap = cv2.createTonemap(gamma=self.gamma)
            ldr = tonemap.process(hdr)
            final_img = cv2.convertScaleAbs(ldr, alpha=255)
            
            self.logger.info("HDR processing completed successfully")
            return final_img
            
        except Exception as e:
            self.logger.error(f"HDR processing failed: {str(e)}")
            raise


class ImageStackingEnhancer(BaseEnhancer):
    """
    Enhancer that reduces noise by stacking multiple images.
    
    NOTE: This enhancer requires direct access to the camera and captures
    multiple images to align and average them.
    """
    
    def __init__(self, 
                 num_images: int = 5,
                 camera: Optional[Picamera2] = None,
                 alignment_threshold: float = 0.7,
                 color_input_format: str = 'RGB'):
        """
        Initialize image stacking parameters.
        
        Args:
            num_images: Number of images to stack
            camera: Picamera2 object for capturing
            alignment_threshold: Threshold for feature matching (0.0-1.0)
            color_input_format: Color format of input images ('BGR' or 'RGB')
        """
        super().__init__()
        self.num_images = num_images
        self.camera = camera
        self.alignment_threshold = alignment_threshold
        self.color_input_format = color_input_format.upper()
        
        if self.color_input_format not in ['BGR', 'RGB']:
            self.logger.warning(f"Unsupported input format: {color_input_format}. Defaulting to RGB.")
            self.color_input_format = 'RGB'
        
        self.logger.info(f"Setting num_images={num_images}, alignment_threshold={alignment_threshold}, "
                        f"color_input_format={self.color_input_format}")
    
    def enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Apply image stacking for noise reduction.
        
        NOTE: This method ignores the input image if a camera is provided
        and captures a new image sequence.
        
        Args:
            image: Input image (ignored if camera is provided)
            
        Returns:
            np.ndarray: Stacked image as numpy array
        """
        self.logger.info(f"Starting image stacking with {self.num_images} images")
        
        if self.camera is None:
            self.logger.warning("No camera provided to ImageStackingEnhancer. Returning input image unchanged.")
            return image
        
        try:
            # Capture multiple images
            self.logger.info(f"Capturing {self.num_images} images")
            images = []
            for i in range(self.num_images):
                self.logger.info(f"Capturing image {i+1}/{self.num_images}")
                raw_img = self.camera.capture_array()
                
                # Convert from RGB (camera native) to BGR (OpenCV native) if needed
                if self.color_input_format == 'RGB':
                    img = cv2.cvtColor(raw_img, cv2.COLOR_RGB2BGR)
                else:
                    img = raw_img
                    
                images.append(img)
                time.sleep(0.5)
            
            # Convert first image to float32 for processing
            self.logger.info("Aligning and stacking images")
            aligned_images = [np.float32(images[0])]
            
            # Align and stack images
            for i in range(1, len(images)):
                # Convert images to grayscale for alignment
                gray1 = cv2.cvtColor(images[0], cv2.COLOR_BGR2GRAY)
                gray2 = cv2.cvtColor(images[i], cv2.COLOR_BGR2GRAY)
                
                # Find features
                orb = cv2.ORB_create()
                kp1, des1 = orb.detectAndCompute(gray1, None)
                kp2, des2 = orb.detectAndCompute(gray2, None)
                
                if des1 is None or des2 is None or len(des1) < 4 or len(des2) < 4:
                    self.logger.warning(f"Not enough features in image {i+1}. Skipping.")
                    continue
                
                # Match features
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = bf.match(des1, des2)
                matches = sorted(matches, key=lambda x: x.distance)
                
                # Extract location of good matches
                threshold = int(len(matches) * self.alignment_threshold)
                good_matches = matches[:max(4, threshold)]  # Need at least 4 points for homography
                
                if len(good_matches) < 4:
                    self.logger.warning(f"Not enough good matches in image {i+1}. Skipping.")
                    continue
                
                src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                
                # Find homography
                M, _ = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
                
                if M is not None:
                    aligned = cv2.warpPerspective(images[i], M, (images[0].shape[1], images[0].shape[0]))
                    aligned_images.append(np.float32(aligned))
                else:
                    self.logger.warning(f"Could not find homography for image {i+1}. Skipping.")
            
            # Average the images
            self.logger.info(f"Averaging {len(aligned_images)} aligned images")
            result = np.mean(aligned_images, axis=0)
            result = cv2.convertScaleAbs(result)
            
            self.logger.info("Image stacking completed successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"Image stacking failed: {str(e)}")
            raise


class ImageEnhancer:
    """
    Main class for enhancing images from Raspberry Pi camera.
    
    This class initializes the camera, captures images, and applies a sequence of
    enhancement techniques in the order they are provided.
    """
    
    def __init__(self, enhancers: List[BaseEnhancer] = None, input_format: str = 'RGB'):
        """
        Initialize the ImageEnhancer with optional list of enhancers.
        
        Args:
            enhancers: List of BaseEnhancer objects to apply in sequence
            input_format: Color format of input images ('BGR' or 'RGB')
        """
        self.logger = logging.getLogger('ImageEnhancer')
        self.logger.info("Initializing ImageEnhancer")
        
        self.enhancers = enhancers or []
        self.camera = None
        self.input_format = input_format.upper()
        
        if self.input_format not in ['BGR', 'RGB']:
            self.logger.warning(f"Unsupported input format: {input_format}. Defaulting to RGB.")
            self.input_format = 'RGB'
        
        self.logger.info(f"Input format set to {self.input_format}")
    
    def initialize_camera(self, resolution: Tuple[int, int] = (3280, 2464)) -> None:
        """
        Initialize the Raspberry Pi camera with specified resolution.
        
        Args:
            resolution: Tuple containing width and height in pixels
        """
        self.logger.info(f"Initializing camera with resolution {resolution}")
        
        try:
            self.camera = Picamera2()
            config = self.camera.create_still_configuration(
                main={"size": resolution},
                buffer_count=1
            )
            self.camera.start(config)
            
            # Allow camera to warm up
            time.sleep(2)
            self.logger.info("Camera initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize camera: {str(e)}")
            raise
    
    def capture_image(self, filename: str = None) -> np.ndarray:
        """
        Capture an image from the camera.
        
        Args:
            filename: Optional filename to save the captured image
            
        Returns:
            np.ndarray: The captured image as a numpy array in the expected format
        """
        if self.camera is None:
            self.logger.error("Camera not initialized. Call initialize_camera() first")
            raise RuntimeError("Camera not initialized. Call initialize_camera() first")
        
        self.logger.info("Capturing image")
        try:
            # PiCamera2 returns images in RGB format by default
            raw_image = self.camera.capture_array()
            self.logger.info(f"Captured raw image with shape {raw_image.shape}")
            
            # Convert to BGR for OpenCV processing if our input format is BGR
            if self.input_format == 'BGR':
                self.logger.info("Converting from RGB (camera native) to BGR (OpenCV native)")
                image = cv2.cvtColor(raw_image, cv2.COLOR_RGB2BGR)
            else:
                # Keep as RGB if that's our chosen format
                image = raw_image
            
            if filename:
                # Always save in BGR format for cv2.imwrite
                save_image = image if self.input_format == 'BGR' else cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                cv2.imwrite(filename, save_image)
                self.logger.info(f"Image saved to {filename}")
            
            return image
        except Exception as e:
            self.logger.error(f"Failed to capture image: {str(e)}")
            raise
    
    def add_enhancer(self, enhancer: BaseEnhancer) -> None:
        """
        Add an enhancer to the enhancement pipeline.
        
        Args:
            enhancer: A BaseEnhancer object to add to the pipeline
        """
        self.logger.info(f"Adding enhancer: {enhancer.__class__.__name__}")
        self.enhancers.append(enhancer)
    
    def enhance_image(self, image: np.ndarray, output_path: str = None) -> np.ndarray:
        """
        Apply all enhancers to the image in sequence.
        
        Args:
            image: The input image as a numpy array
            output_path: Optional path to save the final enhanced image
            
        Returns:
            np.ndarray: The enhanced image as a numpy array
        """
        self.logger.info(f"Starting enhancement pipeline with {len(self.enhancers)} enhancers")
        
        # Ensure correct color format for OpenCV processing
        if self.input_format == 'RGB':
            self.logger.info("Converting input from RGB to BGR for OpenCV processing")
            working_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            working_image = image.copy()
        
        # Save the original for comparison if saving output
        if output_path:
            original_path = output_path.replace('.', '_original.')
            self.logger.info(f"Saving original image to {original_path}")
            cv2.imwrite(original_path, working_image)
        
        # Apply each enhancer in sequence
        for i, enhancer in enumerate(self.enhancers):
            self.logger.info(f"Applying enhancer {i+1}/{len(self.enhancers)}: {enhancer.__class__.__name__}")
            try:
                # Use the enhancer
                working_image = enhancer.enhance(working_image)
                
                # Save intermediate result if debugging is enabled
                if logging.getLogger().level <= logging.DEBUG and output_path:
                    debug_path = output_path.replace('.', f'_step{i+1}_{enhancer.__class__.__name__}.')
                    self.logger.debug(f"Saving intermediate result to {debug_path}")
                    cv2.imwrite(debug_path, working_image)
                    
            except Exception as e:
                self.logger.error(f"Error in enhancer {enhancer.__class__.__name__}: {str(e)}")
                raise
        
        # Convert back to original format if needed
        if self.input_format == 'RGB':
            self.logger.info("Converting result from BGR back to RGB")
            working_image = cv2.cvtColor(working_image, cv2.COLOR_BGR2RGB)
        
        # Save final output
        if output_path:
            self.logger.info(f"Saving enhanced image to {output_path}")
            # Note: cv2.imwrite expects BGR format
            output_image = working_image if self.input_format == 'BGR' else cv2.cvtColor(working_image, cv2.COLOR_RGB2BGR)
            cv2.imwrite(output_path, output_image)
        
        self.logger.info("Enhancement pipeline completed successfully")
        return working_image
    
    def capture_and_enhance(self, output_path: str = None) -> np.ndarray:
        """
        Capture an image and enhance it with all configured enhancers.
        
        Args:
            output_path: Optional path to save the final enhanced image
            
        Returns:
            np.ndarray: The enhanced image as a numpy array
        """
        self.logger.info("Capturing and enhancing image")
        
        if self.camera is None:
            self.logger.info("Camera not initialized, initializing now")
            self.initialize_camera()
        
        image = self.capture_image()
        return self.enhance_image(image, output_path)
    
    def close(self) -> None:
        """Close the camera and release resources."""
        if self.camera:
            self.logger.info("Closing camera")
            self.camera.close()


if __name__ == "__main__":
    denoise = DenoiseEnhancer(h_luminance=5, h_color=5, preserve_colors=True, fast_mode=True)
    color_correction = ColorCorrectionEnhancer(white_balance=True, saturation_factor=1.1)
    contrast = ContrastEnhancer(clip_limit=2.0, tile_grid_size=(8, 8), color_space='YCRCB')
    sharpen = SharpenEnhancer(strength=0.8)
    
    enhancer = ImageEnhancer([color_correction, denoise, contrast, sharpen], input_format='RGB')
    
    try:
        enhancer.initialize_camera(resolution=(3280, 2464))
        optimal_settings = OptimalSettingsEnhancer(exposure_time=20000, analog_gain=1.0, awb_mode='auto', sharpness=1.5)
        optimal_settings.apply_to_camera(enhancer.camera)
        time.sleep(2)
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = f"enhanced_{timestamp}.jpg"
        enhanced_image = enhancer.capture_and_enhance(output_path=output_path)
        print(f"Enhanced image saved to {output_path}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        enhancer.close()