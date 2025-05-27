import time
import io
from threading import Condition # Import Condition
from picamera2 import Picamera2
# from picamera2.encoders import H264Encoder # If MJPEGEncoder is preferred for streaming
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from libcamera import Transform # For potential flipping
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
    _camera_lock = Condition() # For thread-safe access to camera operations if needed

    def __new__(cls):
        with cls._camera_lock:
            if cls._instance is None:
                cls._instance = super(RPiCamera, cls).__new__(cls)
                try:
                    cls._camera = Picamera2()
                    # Keep main high for capture, lores for streaming
                    cls.video_config = cls._camera.create_video_configuration(
                        main={"size": (1280, 720), "format": "RGB888"}, # Preview stream
                        lores={"size": (640, 480), "format": "YUV420"},   # Low-res for MJPEG encoder
                        controls={"FrameRate": 30} # Specify framerate
                    )
                    cls._camera.configure(cls.video_config)
                    cls._streaming_output = StreamingOutput()
                    cls._is_initialized = True
                    logger.info("RPiCamera initialized successfully.")
                except Exception as e: # Broad exception for RPi-specific import/init errors
                    logger.error(f"Critical: Failed to initialize Picamera2: {e}. RPi Camera features will be unavailable. Ensure libcamera is running and camera is connected.")
                    cls._camera = None
                    cls._is_initialized = False
            return cls._instance

    def is_available(self):
        return self._is_initialized and self._camera is not None

    def start_streaming(self):
        if not self.is_available():
            logger.warning("Attempted to start streaming, but camera is not available.")
            return False
        if self._is_streaming:
            logger.info("Streaming is already active.")
            return True
        try:
            with self._camera_lock:
                # Use lores stream for JPEG encoding for the feed
                encoder = JpegEncoder(q=70)
                # Output to our custom streaming output, using the lores stream
                self._camera.start_encoder(encoder, FileOutput(self._streaming_output), name='lores')
                self._camera.start()
                self._is_streaming = True
                logger.info("Camera streaming started on lores stream.")
            return True
        except Exception as e:
            logger.error(f"Could not start camera streaming: {e}")
            self._is_streaming = False
            return False

    def stop_streaming(self):
        if not self.is_available() or not self._is_streaming:
            return
        try:
            with self._camera_lock:
                self._camera.stop()
                self._camera.stop_encoder()
                self._is_streaming = False
                logger.info("Camera streaming stopped.")
        except Exception as e:
            logger.error(f"Could not stop camera streaming: {e}")

    def get_frame(self):
        if not self.is_available() or not self._is_streaming:
            return None
        try:
            with self._streaming_output.condition: # Ensure thread-safe access to frame
                if self._streaming_output.condition.wait(timeout=0.1): # Wait for a new frame with timeout
                    return self._streaming_output.frame
                else:
                    # logger.debug("Timeout waiting for frame, none available.") # Can be noisy
                    return None 
        except Exception as e:
            logger.error(f"Error getting frame: {e}")
            return None

    def capture_image(self, filepath):
        if not self.is_available():
            logger.error("Camera not initialized or available for capture.")
            raise RuntimeError("Camera not initialized or available.")
        
        was_streaming = self._is_streaming
        try:
            with self._camera_lock:
                if was_streaming:
                    logger.info("Stopping stream for high-resolution capture.")
                    self.stop_streaming() # Stop lores streaming for a high-res capture
                
                # Create a higher-resolution configuration for capture if needed, or use main stream of video_config
                # For simplicity, Picamera2 can capture from the main stream directly if it's high enough res
                # Or, switch to a dedicated still mode:
                logger.info("Configuring for still capture...")
                still_config = self._camera.create_still_configuration(
                    main={"size": (1920, 1080)}, # Capture resolution
                    # transform=Transform(hflip=1, vflip=1) # if camera is upside down
                )
                # self._camera.configure(still_config) # Configure for still capture
                # job = self._camera.capture_file(filepath, wait=False) # Capture without wait if app needs to be responsive
                # self._camera.wait(job) # Wait for capture to complete
                self._camera.switch_mode_and_capture_file(still_config, filepath, wait=True)
                logger.info(f"Image captured and saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to capture image: {e}")
            return False
        finally:
            if was_streaming:
                logger.info("Restarting camera stream after capture.")
                # Reconfigure back to video mode before restarting encoder if mode was switched
                # self._camera.configure(self.video_config) 
                self.start_streaming()

# Global instance for easy access from Flask routes
# This is generally okay for Picamera2 as it manages its own singleton internally for the camera hardware.
# However, ensure methods are thread-safe if accessed concurrently.
rpi_camera_instance = RPiCamera()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("Attempting to initialize RPiCamera...")
    cam = rpi_camera_instance # Use the global instance

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
                    # print(f"Got a frame of size: {len(frame)} bytes") # Too verbose for quick test
                time.sleep(0.03) # Approx 30fps
            print(f"Got {frame_count} frames in 2 seconds.")

            print("Attempting to capture an image to test_capture.jpg...")
            if cam.capture_image("test_capture.jpg"):
                print("Image captured successfully: test_capture.jpg")
            else:
                print("Failed to capture image.")
            
            # Stream should have restarted if it was active
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

# Ensure a clean shutdown if the script is interrupted (though web server handles this differently)
# def cleanup_camera():
#    camera_instance = RPiCamera()
#    if camera_instance.is_available() and camera_instance._is_streaming:
#        camera_instance.stop_streaming()
#    if camera_instance.is_available() and camera_instance._camera:
#        camera_instance._camera.close() # Properly close the camera
#        logger.info("Picamera2 instance closed.")
# atexit.register(cleanup_camera) # Might be useful for standalone scripts, less so for Flask apps 