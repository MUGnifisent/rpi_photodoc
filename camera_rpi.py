import time
import io
from threading import Condition, Lock
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from libcamera import Transform
import logging

logger = logging.getLogger(__name__)

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

class RPiCamera:
    _instance = None
    _camera = None
    _streaming_output = None
    _is_streaming = False
    _is_initialized = False
    _camera_lock = Lock()  # Use Lock instead of Condition for cleaner locking
    portrait_mode = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RPiCamera, cls).__new__(cls)
            try:
                cls._camera = Picamera2()
                # Initial configuration
                cls.video_config = cls._camera.create_video_configuration(
                    main={"size": (1920, 1080), "format": "RGB888"},
                    lores={"size": (1280, 720), "format": "YUV420"},
                    controls={"FrameRate": 30}
                )
                cls._camera.configure(cls.video_config)
                cls._streaming_output = StreamingOutput()
                cls._is_initialized = True
                logger.info("RPiCamera initialized successfully.")
            except Exception as e:
                logger.error(f"Critical: Failed to initialize Picamera2: {e}. RPi Camera features will be unavailable.")
                cls._camera = None
                cls._is_initialized = False
        return cls._instance

    def is_available(self):
        return self._is_initialized and self._camera is not None

    def set_portrait_mode(self, enabled: bool):
        with self._camera_lock:
            if self.portrait_mode == enabled:
                logger.info(f"Portrait mode already set to {enabled}")
                return
                
            self.portrait_mode = enabled
            logger.info(f"Portrait mode set to {enabled}. Restarting stream if active.")
            if self._is_streaming:
                self._stop_streaming_internal()
                self._start_streaming_internal()

    def _start_streaming_internal(self):
        """Internal method that assumes lock is already held"""
        if not self.is_available():
            logger.warning("Cannot start streaming, camera not available.")
            return False
        if self._is_streaming:
            logger.info("Streaming is already active.")
            return True
        try:
            # Set up transform for portrait mode
            transform = Transform()
            if self.portrait_mode:
                transform = Transform(rotation=90)
            
            # Create and apply video configuration
            self.video_config = self._camera.create_video_configuration(
                main={"size": (1920, 1080), "format": "RGB888"},
                lores={"size": (1280, 720), "format": "YUV420"},
                transform=transform,
                controls={"FrameRate": 30}
            )
            self._camera.configure(self.video_config)
            
            # Start encoder and camera
            encoder = JpegEncoder(q=70)
            self._camera.start_encoder(encoder, FileOutput(self._streaming_output), name='lores')
            self._camera.start()
            self._is_streaming = True
            logger.info(f"Camera streaming started. Portrait mode: {self.portrait_mode}.")
            return True
        except Exception as e:
            logger.error(f"Could not start camera streaming: {e}")
            self._is_streaming = False
            return False

    def start_streaming(self):
        with self._camera_lock:
            return self._start_streaming_internal()

    def _stop_streaming_internal(self):
        """Internal method that assumes lock is already held"""
        if not self.is_available() or not self._is_streaming:
            return
        try:
            self._camera.stop()
            self._camera.stop_encoder()
            self._is_streaming = False
            logger.info("Camera streaming stopped.")
        except Exception as e:
            logger.error(f"Could not stop camera streaming: {e}")

    def stop_streaming(self):
        with self._camera_lock:
            self._stop_streaming_internal()

    def get_frame(self):
        if not self.is_available() or not self._is_streaming:
            logger.warning("get_frame called but camera not available or not streaming.")
            return None
        try:
            with self._streaming_output.condition:
                if self._streaming_output.condition.wait(timeout=0.1):
                    frame = self._streaming_output.frame
                    if frame:
                        logger.debug(f"get_frame: Returning a frame of size {len(frame)} bytes.")
                    else:
                        logger.warning("get_frame: Condition met, but frame is None.")
                    return frame
                else:
                    logger.debug("get_frame: Timeout waiting for frame condition, no new frame.")
                    return None 
        except Exception as e:
            logger.error(f"Error getting frame: {e}", exc_info=True)
            return None

    def capture_image(self, filepath):
        if not self.is_available():
            logger.error("Camera not initialized or available for capture.")
            raise RuntimeError("Camera not initialized or available.")
        
        with self._camera_lock:
            was_streaming = self._is_streaming
            try:
                # Stop streaming if active
                if was_streaming:
                    logger.info("Stopping stream for high-resolution capture.")
                    self._stop_streaming_internal()
                    # Give camera time to fully stop
                    time.sleep(0.5)
                
                logger.info("Configuring for still capture...")
                
                # Set up transform for portrait mode
                transform = Transform()
                if self.portrait_mode:
                    transform = Transform(rotation=90)
                
                # Create still configuration
                still_config = self._camera.create_still_configuration(
                    main={"size": (4608, 2592)},
                    transform=transform
                )
                
                # Use switch_mode_and_capture_file for atomic operation
                self._camera.switch_mode_and_capture_file(still_config, filepath, wait=True)
                logger.info(f"Image captured and saved to {filepath}")
                
                # Verify file was actually created
                import os
                if not os.path.exists(filepath):
                    logger.error(f"Capture appeared successful but file not found: {filepath}")
                    return False
                
                file_size = os.path.getsize(filepath)
                logger.info(f"Captured image file size: {file_size} bytes")
                
                if file_size < 1000:  # Less than 1KB is probably an error
                    logger.error(f"Captured image file too small: {file_size} bytes")
                    return False
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to capture image: {e}", exc_info=True)
                return False
            finally:
                # Always try to restart streaming if it was active
                if was_streaming:
                    logger.info("Restarting camera stream after capture.")
                    # Give more time before restarting
                    time.sleep(0.5)
                    
                    # Try to restart streaming with retries
                    for attempt in range(3):
                        try:
                            success = self._start_streaming_internal()
                            if success:
                                logger.info(f"Successfully restarted streaming on attempt {attempt + 1}")
                                break
                            else:
                                logger.warning(f"Failed to restart streaming, attempt {attempt + 1}")
                                if attempt < 2:  # Don't sleep on last attempt
                                    time.sleep(1.0)
                        except Exception as e:
                            logger.error(f"Error restarting streaming attempt {attempt + 1}: {e}")
                            if attempt < 2:
                                time.sleep(1.0)
                    else:
                        logger.error("Failed to restart streaming after 3 attempts")

    def set_autofocus(self, enabled: bool):
        if not self.is_available():
            logger.warning("set_autofocus called but camera not available.")
            return False
        try:
            with self._camera_lock:
                if enabled:
                    logger.info("Attempting to enable continuous autofocus...")
                    # Set AfMode to Continuous (2)
                    self._camera.set_controls({"AfMode": 2})
                    time.sleep(0.3)
                    
                    # Verify the mode was set
                    metadata = self._camera.capture_metadata()
                    af_mode = metadata.get('AfMode')
                    logger.info(f"AfMode after setting to Continuous: {af_mode}")
                    
                    if af_mode == 2:
                        # Trigger autofocus
                        self._camera.set_controls({"AfTrigger": 0})
                        time.sleep(0.2)
                        final_metadata = self._camera.capture_metadata()
                        logger.info(f"Continuous Autofocus enabled: AfMode={final_metadata.get('AfMode')}, AfState={final_metadata.get('AfState')}")
                    else:
                        logger.warning(f"Failed to set AfMode to Continuous. Camera reports: {af_mode}")
                        return False
                else:
                    logger.info("Disabling autofocus (set to Manual)...")
                    self._camera.set_controls({"AfMode": 0})
                    time.sleep(0.2)
                    metadata = self._camera.capture_metadata()
                    logger.info(f"Autofocus disabled: AfMode={metadata.get('AfMode')}")
            return True
        except Exception as e:
            logger.error(f"Failed to set autofocus: {e}", exc_info=True)
            return False

    def trigger_autofocus(self):
        if not self.is_available():
            logger.warning("trigger_autofocus called but camera not available.")
            return False
        try:
            with self._camera_lock:
                # Set to Auto (one-shot) mode
                self._camera.set_controls({"AfMode": 1})
                # Trigger autofocus
                self._camera.set_controls({"AfTrigger": 0})
                logger.info("One-shot autofocus triggered (AfMode: 1, AfTrigger: 0)")
            return True
        except Exception as e:
            logger.error(f"Failed to trigger autofocus: {e}")
            return False

    def get_autofocus_state(self):
        if not self.is_available():
            return {"available": False}
        try:
            with self._camera_lock:
                metadata = self._camera.capture_metadata()
                af_mode = metadata.get('AfMode', None)
                af_state = metadata.get('AfState', None)
                af_position = metadata.get('LensPosition', None)
                return {
                    "available": True,
                    "af_mode": af_mode,
                    "af_state": af_state,
                    "af_position": af_position
                }
        except Exception as e:
            logger.error(f"Failed to get autofocus state: {e}")
            return {"available": False, "error": str(e)}

# Global instance for easy access from Flask routes
rpi_camera_instance = RPiCamera()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("Attempting to initialize RPiCamera...")
    cam = rpi_camera_instance

    if cam.is_available():
        print("Camera is available.")
        print("Starting stream test...")
        if cam.start_streaming():
            print("Streaming started. Will try to get frames for 2 seconds.")
            end_time = time.time() + 2
            frame_count = 0
            while time.time() < end_time:
                frame = cam.get_frame()
                if frame:
                    frame_count += 1
                time.sleep(0.03)
            print(f"Got {frame_count} frames in 2 seconds.")

            print("Attempting to capture an image to test_capture.jpg...")
            if cam.capture_image("test_capture.jpg"):
                print("Image captured successfully: test_capture.jpg")
            else:
                print("Failed to capture image.")
            
            if cam._is_streaming:
                print("Streaming is active after capture.")
            else:
                print("Streaming is NOT active after capture, attempting to restart.")
                cam.start_streaming()

            if cam._is_streaming:
                print("Stopping stream.")
                cam.stop_streaming()
                print("Streaming stopped.")
            else:
                print("Stream was not running to stop.")
        else:
            print("Failed to start streaming.")
    else:
        print("Camera not available or failed to initialize. Check logs and ensure RPi environment.")