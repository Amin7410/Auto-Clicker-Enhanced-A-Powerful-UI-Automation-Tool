# gui/drawing_capture_window.py
import tkinter as tk
from tkinter import messagebox, ttk 
import logging
from typing import List, Tuple, Callable, Optional, Dict, Any
import threading

logger = logging.getLogger(__name__)


try:
    from python_csharp_bridge import os_interaction_client
    _BridgeImported_DCW = True
    logger.debug("DrawingCaptureWindow: OSInteractionClient imported.")
except ImportError:
    logger.error("DrawingCaptureWindow: Could not import os_interaction_client. Drawing capture will fail.")
    _BridgeImported_DCW = False
    class DummyOSInteractionClient:
        def start_interactive_drawing_capture(self) -> Optional[List[List[Dict[str, int]]]]:
            logger.error("DummyOSInteractionClient: start_interactive_drawing_capture called.")
            return None
    os_interaction_client = DummyOSInteractionClient()


class DrawingCaptureWindow: 
    def __init__(self, master: tk.Tk | tk.Toplevel,
                 callback: Callable[[Optional[List[List[Dict[str, int]]]]], None]):

        self.master_window = master
        self.callback = callback

        logger.debug("DrawingCaptureWindow: Initializing (will start C# call in a new thread).")

        self._disable_master_window(True)

        self.capture_thread = threading.Thread(target=self._initiate_csharp_drawing_capture_threaded, daemon=True)
        self.capture_thread.start()

    def _disable_master_window(self, disable: bool):
        try:
            if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                if hasattr(self.master_window, 'attributes'):
                    self.master_window.attributes("-disabled", disable)
        except tk.TclError:
            logger.warning("DrawingCaptureWindow: TclError trying to change master window state.")
        except Exception as e:
            logger.error(f"DrawingCaptureWindow: Error changing master window state: {e}")

    def _initiate_csharp_drawing_capture_threaded(self):
        captured_strokes_list: Optional[List[List[Dict[str, int]]]] = None
        error_message_for_user: Optional[str] = None

        if not _BridgeImported_DCW:
            logger.error("DrawingCaptureWindow (Thread): Cannot initiate drawing capture, bridge not imported.")
            error_message_for_user = "OS Interaction service bridge is not available.\nDrawing capture cannot proceed."
        else:
            try:
                logger.info("DrawingCaptureWindow (Thread): Calling C# service for interactive drawing capture...")
                captured_strokes_list = os_interaction_client.start_interactive_drawing_capture()

                if captured_strokes_list is not None: 
                    logger.info(f"DrawingCaptureWindow (Thread): Drawing data received from C# ({len(captured_strokes_list)} strokes).")
                else:
                    logger.info("DrawingCaptureWindow (Thread): Drawing capture cancelled or no data returned from C#.")

            except TimeoutError as te:
                logger.error(f"DrawingCaptureWindow (Thread): Timeout: {te}")
                error_message_for_user = "The drawing capture timed out."
            except ConnectionRefusedError as cre:
                logger.error(f"DrawingCaptureWindow (Thread): Connection refused: {cre}")
                error_message_for_user = "Could not connect to the OS Interaction Service."
            except Exception as e:
                logger.error(f"DrawingCaptureWindow (Thread): Error during C# call: {e}", exc_info=True)
                error_message_for_user = f"An unexpected error occurred: {e}"

        try:
            if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                self.master_window.after(0, self._handle_capture_result_on_main_thread, captured_strokes_list, error_message_for_user)
            else:
                logger.warning("DrawingCaptureWindow (Thread): Master window no longer exists. Cannot schedule callback.")
                if captured_strokes_list: logger.info(f"  (Discarded drawing data: {len(captured_strokes_list)} strokes)")
                if error_message_for_user: logger.info(f"  (Discarded error: {error_message_for_user})")
        except Exception as e:
            logger.error(f"DrawingCaptureWindow (Thread): Error scheduling callback to main thread: {e}", exc_info=True)

    def _handle_capture_result_on_main_thread(self, result_data: Optional[List[List[Dict[str, int]]]], error_msg_for_user: Optional[str]):
        logger.debug(f"DrawingCaptureWindow (MainThread): Handling capture result. Data: {'Yes' if result_data is not None else 'Cancelled/Error'}, Error: '{error_msg_for_user or 'None'}'")

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
                logger.error(f"DrawingCaptureWindow (MainThread): Error executing callback: {e}", exc_info=True)
                if hasattr(self.master_window, 'winfo_exists') and self.master_window.winfo_exists():
                     messagebox.showerror("Callback Error", f"Error processing captured drawing data:\n{e}", parent=self.master_window)
