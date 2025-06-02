import time
import io
from threading import Condition, Lock, Event # Import Condition, Lock, Event
from picamera2 import Picamera2
# from picamera2.encoders import H264Encoder # If MJPEGEncoder is preferred for streaming
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from libcamera import Transform # For potential flipping
from libcamera import controls as LibcameraControls # Added import
import logging
import threading # Added import

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
    # _camera = None # This will be an instance variable
    # _streaming_output = None # This will be an instance variable
    # _is_streaming = False # This will be an instance variable
    # _is_initialized = False # This will be an instance variable
    # _camera_lock = Condition() # This will be an instance variable, and should be a Lock
    # portrait_mode = False  # This will be an instance variable
    # _af_enabled = False # This will be an instance variable

    def __new__(cls, *args, **kwargs): # Modified to accept args and kwargs
        # Using a simpler singleton pattern, actual initialization in __init__
        if cls._instance is None:
            cls._instance = super(RPiCamera, cls).__new__(cls)
        return cls._instance

    def __init__(self, camera_num=0):
        # Ensure __init__ is called only once for the singleton
        if hasattr(self, '_initialized_singleton') and self._initialized_singleton:
            return
        
        self.picam2 = None
        self.camera_num = camera_num
        self.is_streaming = False # Renamed from _is_streaming
        self._camera_lock = Lock() # Changed from Condition
        self._frame_lock = Lock() 
        self._frame_event = Event()
        self._latest_frame_bytes = None
        self._portrait_mode = False  # Default to landscape
        self._stop_stream_request = Event()
        self.streaming_thread = None
        self.encoder = None 
        self._af_enabled = False # Initialize autofocus state
        self._streaming_output = StreamingOutput() # Initialize streaming output here

        try:
            self.picam2 = Picamera2(camera_num=self.camera_num)
            # Maximal preview (stream) resolution for Camera Module 3: 1920x1080
            # Maximal still resolution: 4608x2592
            self.video_config = self.picam2.create_video_configuration(
                main={"size": (1920, 1080), "format": "RGB888"},
                lores={"size": (1280, 720), "format": "YUV420"},
                controls={"FrameRate": 30}
            )
            self.picam2.configure(self.video_config)
            self._is_initialized = True # Moved from __new__
            logger.info(f"RPiCamera initialized successfully for camera {self.camera_num}.")
        except Exception as e:
            logger.error(f"Critical: Failed to initialize Picamera2 for camera {self.camera_num}: {e}. RPi Camera features will be unavailable. Ensure libcamera is running and camera is connected.")
            self.picam2 = None
            self._is_initialized = False # Moved from __new__
        
        self._initialized_singleton = True


    def is_available(self):
        return self._is_initialized and self.picam2 is not None

    def set_portrait_mode(self, enabled: bool):
        with self._camera_lock:
            self._portrait_mode = enabled
            logger.info(f"Portrait mode set to {enabled}. Restarting stream if active.")
            if self.is_streaming: # use renamed variable
                self.stop_streaming()
                self.start_streaming()

    def start_streaming(self):
        if not self.is_available():
            logger.warning("Attempted to start streaming, but camera is not available.")
            return False
        if self.is_streaming: # use renamed variable
            logger.info("Streaming is already active.")
            return True
        try:
            with self._camera_lock:
                transform = Transform()
                if self._portrait_mode: # use instance variable
                    transform = Transform(rotation=90)
                
                # Ensure AfMode is set to Manual (0) initially when stream starts
                # Continuous AF (2) can be enabled via UI later if desired.
                current_controls = {"FrameRate": 30, "AfMode": LibcameraControls.AfModeEnum.Manual}

                self.video_config = self.picam2.create_video_configuration(
                    main={"size": (1920, 1080), "format": "RGB888"},
                    lores={"size": (1280, 720), "format": "YUV420"},
                    transform=transform,
                    controls=current_controls
                )
                self.picam2.configure(self.video_config)
                
                # Use JpegEncoder for streaming output
                self.encoder = JpegEncoder(q=70) # Assign to self.encoder
                self.picam2.start_encoder(self.encoder, FileOutput(self._streaming_output), name='lores') # Use self.encoder
                self.picam2.start()
                self.is_streaming = True # use renamed variable
                logger.info(f"Camera streaming started on lores stream. Portrait mode: {self._portrait_mode}. Initial AfMode: {current_controls['AfMode']}.")
            return True
        except Exception as e:
            logger.error(f"Could not start camera streaming: {e}", exc_info=True)
            self.is_streaming = False # use renamed variable
            return False

    def stop_streaming(self):
        if not self.is_available() or not self.is_streaming: # use renamed variable
            return
        try:
            with self._camera_lock:
                self.picam2.stop()
                if self.encoder is not None: # Check if encoder was started
                     self.picam2.stop_encoder()
                self.is_streaming = False # use renamed variable
                logger.info("Camera streaming stopped.")
        except Exception as e:
            logger.error(f"Could not stop camera streaming: {e}", exc_info=True)

    def get_frame(self):
        if not self.is_available() or not self.is_streaming: # use renamed variable
            logger.warning("get_frame called but camera not available or not streaming.")
            return None
        try:
            with self._streaming_output.condition: 
                if self._streaming_output.condition.wait(timeout=0.5): # Increased timeout
                    frame = self._streaming_output.frame
                    if frame:
                         # logger.debug(f"get_frame: Returning a frame of size {len(frame)} bytes.") # DEBUG level
                         pass
                    else:
                         logger.warning("get_frame: Condition met, but frame is None.")
                    return frame
                else:
                    # This is a common case if the client disconnects or the browser is not actively fetching
                    logger.debug("get_frame: Timeout waiting for frame condition, no new frame. This can be normal.") 
                    return None 
        except Exception as e:
            logger.error(f"Error getting frame: {e}", exc_info=True)
            return None

    def capture_image(self, filepath):
        if not self.is_available():
            logger.error("Camera not initialized or available for capture.")
            raise RuntimeError("Camera not initialized or available.")
        was_streaming = self.is_streaming # use renamed variable
        try:
            with self._camera_lock:
                if was_streaming:
                    logger.info("Stopping stream for high-resolution capture.")
                    self.stop_streaming()
                
                logger.info("Configuring for still capture...")
                transform = Transform()
                if self._portrait_mode: # use instance variable
                    transform = Transform(rotation=90)

                # Get current AF settings to re-apply if needed, or decide to trigger AF
                current_af_mode = self.picam2.capture_metadata().get('AfMode', LibcameraControls.AfModeEnum.Manual.value)
                
                still_config = self.picam2.create_still_configuration(
                    main={"size": (4608, 2592)}, # Max resolution for IMX708
                    transform=transform,
                    # Preserve current AF mode for the capture if it's not Manual.
                    # If it was Manual, perhaps trigger a one-shot AF? For now, let's keep it simple.
                    controls={"AfMode": current_af_mode} 
                )
                # If autofocus is currently enabled (continuous), let it adjust.
                # If manual, the user should have focused or used one-shot AF.
                # Optionally, could add a small delay here if AF was continuous.
                # time.sleep(0.5) # if self._af_enabled

                self.picam2.switch_mode_and_capture_file(still_config, filepath, wait=True)
                logger.info(f"Image captured and saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to capture image: {e}", exc_info=True)
            return False
        finally:
            if was_streaming:
                logger.info("Restarting camera stream after capture.")
                self.start_streaming()

    def set_autofocus(self, enabled: bool):
        if not self.is_available():
            logger.warning("set_autofocus called but camera not available.")
            self._af_enabled = False
            return False
        try:
            with self._camera_lock:
                if enabled:
                    logger.info("Attempting to enable continuous autofocus...")
                    self.picam2.set_controls({"AfMode": LibcameraControls.AfModeEnum.Continuous})
                    logger.info("Set AfMode: Continuous.")
                    time.sleep(0.3)
                    metadata_after_afmode = self.picam2.capture_metadata()
                    logger.info(f"Metadata after setting AfMode=Continuous: AfMode={metadata_after_afmode.get('AfMode')}, AfState={metadata_after_afmode.get('AfState')}")

                    if metadata_after_afmode.get('AfMode') == LibcameraControls.AfModeEnum.Continuous.value:
                        self.picam2.set_controls({"AfTrigger": LibcameraControls.AfTriggerEnum.Start})
                        logger.info("Set AfTrigger: Start.")
                        time.sleep(0.2)
                        metadata_after_trigger = self.picam2.capture_metadata()
                        current_af_mode = metadata_after_trigger.get('AfMode')
                        current_af_state = metadata_after_trigger.get('AfState')
                        logger.info(f"Continuous Autofocus enabled: Final reported state - AfMode: {current_af_mode}, AfState: {current_af_state}")
                        if current_af_mode == LibcameraControls.AfModeEnum.Continuous.value:
                            self._af_enabled = True
                        else:
                            logger.warning(f"AfMode changed from Continuous after AfTrigger. Now: {current_af_mode}")
                            self._af_enabled = False
                    else:
                        logger.warning(f"Failed to set AfMode to Continuous. Camera reports: {metadata_after_afmode.get('AfMode')}. AfTrigger will not be sent.")
                        self._af_enabled = False
                else:
                    logger.info("Attempting to disable autofocus (set to Manual)...")
                    self.picam2.set_controls({"AfMode": LibcameraControls.AfModeEnum.Manual})
                    logger.info("Set AfMode: Manual.")
                    time.sleep(0.2)
                    metadata_after_disable = self.picam2.capture_metadata()
                    current_af_mode = metadata_after_disable.get('AfMode')
                    current_af_state = metadata_after_disable.get('AfState')
                    logger.info(f"Autofocus disabled: AfMode reported by camera: {current_af_mode}, AfState: {current_af_state}")
                    self._af_enabled = False
            return True
        except Exception as e:
            logger.error(f"Failed to set autofocus: {e}", exc_info=True)
            self._af_enabled = False
            return False

    def trigger_autofocus(self):
        if not self.is_available():
            logger.warning("trigger_autofocus called but camera not available.")
            return False
        try:
            with self._camera_lock:
                logger.info("Triggering one-shot autofocus (AfMode: Auto, AfTrigger: Start)")
                self.picam2.set_controls({"AfMode": LibcameraControls.AfModeEnum.Auto})
                time.sleep(0.05) # Short delay between mode set and trigger
                self.picam2.set_controls({"AfTrigger": LibcameraControls.AfTriggerEnum.Start})
                logger.info("One-shot autofocus triggered.")
                # UI will typically re-query get_autofocus_state after a delay.
                # The internal _af_enabled state should remain as it was (e.g. if continuous was on, it stays on)
                # unless the one-shot AF action implicitly changes the underlying AfMode to something other than Continuous.
                # For now, we don't change _af_enabled here, assuming one-shot doesn't permanently disable continuous.
            return True
        except Exception as e:
            logger.error(f"Failed to trigger autofocus: {e}", exc_info=True)
            return False

    def get_autofocus_state(self):
        # Returns the locally stored AF state.
        is_cam_available = self.is_available()
        # If camera is available, and we think AF is enabled, we can optionally verify with camera.
        # However, the user explicitly asked to store state locally and not rely on reading.
        # So, we will trust our local _af_enabled state.
        # For future enhancement, we could add:
        # if is_cam_available and self._af_enabled:
        #     try:
        #        metadata = self.picam2.capture_metadata()
        #        actual_af_mode = metadata.get('AfMode')
        #        if actual_af_mode != LibcameraControls.AfModeEnum.Continuous.value:
        #            logger.warning(f"Local AF state is enabled, but camera reports AfMode {actual_af_mode}. Correcting local state.")
        #            self._af_enabled = False # Or handle appropriately
        #     except Exception as e:
        #        logger.error(f"Error trying to verify AF state from camera: {e}")
        return {
            "available": is_cam_available,
            "enabled": self._af_enabled if is_cam_available else False # Only true if camera is available
        }
    
    def get_camera_metadata(self): # Added method to get general metadata
        if not self.is_available():
            return None
        try:
            return self.picam2.capture_metadata()
        except Exception as e:
            logger.error(f"Failed to get camera metadata: {e}")
            return None

    def shutdown(self):
        logger.info("RPiCamera shutdown sequence initiated.")
        with self._camera_lock: # Ensure thread-safe operations during shutdown
            if self.is_streaming:
                logger.info("Stopping camera stream as part of shutdown...")
                self.stop_streaming() # This already handles stopping encoder and stream

            if self.picam2 is not None:
                logger.info("Closing Picamera2 instance...")
                try:
                    self.picam2.close()
                    logger.info("Picamera2 instance closed.")
                except Exception as e:
                    logger.error(f"Error closing Picamera2 instance: {e}", exc_info=True)
                self.picam2 = None
            
            self._is_initialized = False
            self.is_streaming = False # Explicitly set, though stop_streaming should do it
            logger.info("RPiCamera shutdown sequence completed.")

# Global instance
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
            if cam.is_streaming:
                print("Streaming is active after capture.")
            else:
                print("Streaming is NOT active after capture, attempting to restart.")
                cam.start_streaming()

            if cam.is_streaming:
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