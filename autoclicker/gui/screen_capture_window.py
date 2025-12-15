# gui/screen_capture_window.py
import tkinter as tk
from tkinter import messagebox
import logging
from tkinter import ttk
from typing import Callable, Optional, Dict, Any
import numpy as np
import threading 

logger = logging.getLogger(__name__)

# Import OS Interaction Client
try:
    from python_csharp_bridge import os_interaction_client
    _BridgeImported_SCW = True
    logger.debug("ScreenCaptureWindow: OSInteractionClient imported.")
except ImportError:
    logger.error("ScreenCaptureWindow: Could not import os_interaction_client. Region capture will fail.")
    _BridgeImported_SCW = False
    class DummyOSInteractionClient:
        def start_interactive_region_select(self) -> Optional[Dict[str, Any]]:
            logger.error("DummyOSInteractionClient: start_interactive_region_select called.")
            return None
    os_interaction_client = DummyOSInteractionClient()

_CV2Available_SCW = False
try:
    import cv2
    _CV2Available_SCW = True
except ImportError:
    logger.warning("ScreenCaptureWindow: OpenCV (cv2) not available. Python-side image processing might be limited.")


class ScreenCaptureWindow:
    def __init__(self, master: tk.Tk | tk.Toplevel,
                 callback: Callable[[Optional[Dict[str, Any]]], None],
                 useGrayscale_python_hint: bool = False, 
                 useBinarization_python_hint: bool = False,
                 for_color: bool = False 
                ):

        self.master_window = master
        self.callback = callback
        self.pp_useGrayscale_python_hint = useGrayscale_python_hint
        self.pp_useBinarization_python_hint = useBinarization_python_hint

        logger.debug("ScreenCaptureWindow: Initializing (will start C# call in a new thread).")

        self._disable_master_window(True)

        self.capture_thread = threading.Thread(target=self._initiate_csharp_region_select_threaded, daemon=True)
        self.capture_thread.start()

    def _disable_master_window(self, disable: bool):
        try:
            if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                if hasattr(self.master_window, 'attributes'):
                    self.master_window.attributes("-disabled", disable)

        except tk.TclError:
            logger.warning("ScreenCaptureWindow: TclError trying to change master window state (likely already destroyed).")
        except Exception as e:
            logger.error(f"ScreenCaptureWindow: Error changing master window state: {e}")


    def _initiate_csharp_region_select_threaded(self):
        """
        Hàm này chạy trong một thread riêng để gọi C# service mà không làm block GUI.
        """
        captured_data: Optional[Dict[str, Any]] = None
        error_message_for_user: Optional[str] = None 

        if not _BridgeImported_SCW:
            logger.error("ScreenCaptureWindow (Thread): Cannot initiate region selection, bridge not imported.")
            error_message_for_user = "OS Interaction service bridge is not available.\nRegion selection cannot proceed."
        else:
            try:
                logger.info("ScreenCaptureWindow (Thread): Calling C# service for interactive region selection...")
                captured_data = os_interaction_client.start_interactive_region_select()

                if captured_data:
                    log_data = {k: v for k, v in captured_data.items() if k != 'image_np'}
                    if "image_np" in captured_data and captured_data["image_np"] is not None:
                        log_data["image_shape"] = captured_data["image_np"].shape
                    logger.info(f"ScreenCaptureWindow (Thread): Region data received from C#: {log_data}")
                else:
                    logger.info("ScreenCaptureWindow (Thread): Region selection cancelled or no data returned from C#.")

            except TimeoutError as te:
                logger.error(f"ScreenCaptureWindow (Thread): Timeout waiting for C# region selection: {te}")
                error_message_for_user = "Region selection timed out."
            except ConnectionRefusedError as cre:
                logger.error(f"ScreenCaptureWindow (Thread): Connection to C# service refused: {cre}")
                error_message_for_user = "Could not connect to the OS Interaction Service."
            except Exception as e:
                logger.error(f"ScreenCaptureWindow (Thread): Error during C# region selection call: {e}", exc_info=True)
                error_message_for_user = f"An unexpected error occurred during region selection:\n{e}"
        try:
            if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                self.master_window.after(0, self._handle_capture_result_on_main_thread, captured_data, error_message_for_user)
            else:
                logger.warning("ScreenCaptureWindow (Thread): Master window no longer exists. Cannot schedule callback.")
                if captured_data: logger.info(f"  (Discarded capture data: {captured_data.get('x1')}, ...)")
                if error_message_for_user: logger.info(f"  (Discarded error: {error_message_for_user})")

        except Exception as e:
            logger.error(f"ScreenCaptureWindow (Thread): Error scheduling callback to main thread: {e}", exc_info=True)


    def _handle_capture_result_on_main_thread(self, result_data: Optional[Dict[str, Any]], error_msg_for_user: Optional[str]):
        logger.debug(f"ScreenCaptureWindow (MainThread): Handling capture result. Data: {'Yes' if result_data else 'No'}, Error: '{error_msg_for_user or 'None'}'")

        self._disable_master_window(False)
        try:
             if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                  if hasattr(self.master_window, 'lift'): self.master_window.lift()
                  if hasattr(self.master_window, 'focus_force'): self.master_window.focus_force()
        except tk.TclError: pass 

        if error_msg_for_user:
            if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                messagebox.showerror("Capture Error", error_msg_for_user, parent=self.master_window)
            else:
                logger.error(f"Capture Error (master window destroyed, cannot show messagebox): {error_msg_for_user}")

        if self.callback:
            try:
                self.callback(result_data)
            except Exception as e:
                logger.error(f"ScreenCaptureWindow (MainThread): Error executing callback: {e}", exc_info=True)
                if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                    messagebox.showerror("Callback Error", f"Error processing captured region data:\n{e}", parent=self.master_window)

    def _apply_python_preprocessing_example(self, img_np: np.ndarray) -> np.ndarray:
        logger.debug("ScreenCaptureWindow: Python-side preprocessing (example - not currently auto-applied here).")
        return img_np
