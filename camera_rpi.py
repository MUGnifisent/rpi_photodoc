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
    portrait_mode = False  # New: portrait mode flag

    def __new__(cls):
        with cls._camera_lock:
            if cls._instance is None:
                cls._instance = super(RPiCamera, cls).__new__(cls)
                try:
                    cls._camera = Picamera2()
                    # Maximal preview (stream) resolution for Camera Module 3: 1920x1080 (practical for streaming)
                    # Maximal still resolution: 4608x2592
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
                    logger.error(f"Critical: Failed to initialize Picamera2: {e}. RPi Camera features will be unavailable. Ensure libcamera is running and camera is connected.")
                    cls._camera = None
                    cls._is_initialized = False
            return cls._instance

    def is_available(self):
        return self._is_initialized and self._camera is not None

    def set_portrait_mode(self, enabled: bool):
        with self._camera_lock:
            self.portrait_mode = enabled
            logger.info(f"Portrait mode set to {enabled}. Restarting stream if active.")
            if self._is_streaming:
                self.stop_streaming()
                self.start_streaming()

    def start_streaming(self):
        if not self.is_available():
            logger.warning("Attempted to start streaming, but camera is not available.")
            return False
        if self._is_streaming:
            logger.info("Streaming is already active.")
            return True
        try:
            with self._camera_lock:
                # Set up transform for portrait mode
                transform = Transform()
                if self.portrait_mode:
                    transform = Transform(rotation=90)
                # Re-create and apply video configuration with the correct transform
                self.video_config = self._camera.create_video_configuration(
                    main={"size": (1920, 1080), "format": "RGB888"},
                    lores={"size": (1280, 720), "format": "YUV420"},
                    transform=transform,
                    controls={"FrameRate": 30}
                )
                self._camera.configure(self.video_config)
                encoder = JpegEncoder(q=70)
                self._camera.start_encoder(encoder, FileOutput(self._streaming_output), name='lores')
                self._camera.start()
                self._is_streaming = True
                logger.info(f"Camera streaming started on lores stream. Portrait mode: {self.portrait_mode}")
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
            logger.warning("get_frame called but camera not available or not streaming.")
            return None
        try:
            with self._streaming_output.condition: # Ensure thread-safe access to frame
                if self._streaming_output.condition.wait(timeout=0.1): # Wait for a new frame with timeout
                    frame = self._streaming_output.frame
                    if frame:
                         logger.info(f"get_frame: Returning a frame of size {len(frame)} bytes.")
                    else:
                         logger.warning("get_frame: Condition met, but frame is None.")
                    return frame
                else:
                    logger.warning("get_frame: Timeout waiting for frame condition, no new frame.") 
                    return None 
        except Exception as e:
            logger.error(f"Error getting frame: {e}", exc_info=True)
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
                    self.stop_streaming()
                logger.info("Configuring for still capture...")
                # Maximal still resolution for Camera Module 3: 4608x2592
                transform = Transform()
                if self.portrait_mode:
                    transform = Transform(rotation=90)
                still_config = self._camera.create_still_configuration(
                    main={"size": (4608, 2592)},
                    transform=transform
                )
                self._camera.switch_mode_and_capture_file(still_config, filepath, wait=True)
                logger.info(f"Image captured and saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to capture image: {e}")
            return False
        finally:
            if was_streaming:
                logger.info("Restarting camera stream after capture.")
                self.start_streaming()

    def set_autofocus(self, enabled: bool):
        if not self.is_available():
            logger.warning("set_autofocus called but camera not available.")
            return False, None
        try:
            with self._camera_lock:
                was_streaming = self._is_streaming
                if enabled:
                    # Reset to manual first, then enable continuous AF
                    self._camera.set_controls({"AfMode": 0})
                    time.sleep(0.1)
                    self._camera.set_controls({"AfMode": 2, "AfTrigger": 0})
                    logger.info("Autofocus enabled (reset to manual, then AfMode: 2/Continuous, AfTrigger: 0/Start)")
                else:
                    self._camera.set_controls({"AfMode": 0})
                    logger.info("Autofocus disabled (AfMode: 0/Manual)")
                # Restart stream if it was running
                if was_streaming:
                    logger.info("Restarting stream to apply AF mode change.")
                    self.stop_streaming()
                    time.sleep(0.2)
                    self.start_streaming()
                # Wait a moment for camera to update state
                time.sleep(0.2)
                # Read and log AF state
                meta = self._camera.capture_metadata()
                af_mode = meta.get('AfMode', None)
                af_state = meta.get('AfState', None)
                af_position = meta.get('LensPosition', None)
                logger.info(f"After set_autofocus: AfMode={af_mode}, AfState={af_state}, LensPosition={af_position}")
                return True, {"af_mode": af_mode, "af_state": af_state, "af_position": af_position}
        except Exception as e:
            logger.error(f"Failed to set autofocus: {e}")
            return False, None

    def trigger_autofocus(self):
        if not self.is_available():
            logger.warning("trigger_autofocus called but camera not available.")
            return False
        try:
            with self._camera_lock:
                self._camera.set_controls({"AfMode": 1})  # 1 = Auto (one-shot, int)
                # AfTrigger expects an int: 0 = Start (see libcamera docs)
                self._camera.set_controls({"AfTrigger": 0})
                logger.info("One-shot autofocus triggered (AfMode: 1, AfTrigger: 0/Start)")
            return True
        except Exception as e:
            logger.error(f"Failed to trigger autofocus: {e}")
            return False

    def get_autofocus_state(self):
        if not self.is_available():
            return {"available": False}
        try:
            # Query current autofocus mode and position
            af_mode = self._camera.capture_metadata().get('AfMode', None)
            af_state = self._camera.capture_metadata().get('AfState', None)
            af_position = self._camera.capture_metadata().get('LensPosition', None)
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