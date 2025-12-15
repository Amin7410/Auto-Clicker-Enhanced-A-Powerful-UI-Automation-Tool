# gui/key_recorder.py
import tkinter as tk
from tkinter import ttk
from typing import Callable
import keyboard 
import threading
import logging
import time 

logger = logging.getLogger(__name__)

class GlobalKeyboardHookManager:
    _instance = None
    _active_recorder = None
    _hook_handle = None  
    _lock = threading.Lock()
    _hook_state_listeners: list[Callable[[bool], None]] = [] 

    def __new__(cls):
        with cls._lock: 
            if cls._instance is None:
                cls._instance = super(GlobalKeyboardHookManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def add_hook_state_listener(cls, listener: Callable[[bool], None]):
        with cls._lock:
            if listener not in cls._hook_state_listeners:
                cls._hook_state_listeners.append(listener)
                logger.debug(f"GHKM: Added hook state listener: {listener}")

    @classmethod
    def remove_hook_state_listener(cls, listener: Callable[[bool], None]):
        with cls._lock:
            try:
                cls._hook_state_listeners.remove(listener)
                logger.debug(f"GHKM: Removed hook state listener: {listener}")
            except ValueError:
                pass

    def _notify_hook_state_change(self, is_hook_being_taken_by_recorder: bool):

        logger.debug(f"GHKM: Notifying hook state change. Is hook being taken: {is_hook_being_taken_by_recorder}")

        listeners_copy = list(self._hook_state_listeners)
        for listener in listeners_copy:
            try:

                listener(is_hook_being_taken_by_recorder)
            except Exception as e:
                logger.error(f"GHKM: Error in hook state listener {listener}: {e}", exc_info=True)

    def request_hook(self, recorder_instance: 'KeyRecorder', callback: Callable):
        with self._lock:
            logger.debug(f"GHKM: Hook requested by {recorder_instance}. Current active: {self._active_recorder}")

            if self._active_recorder is not None and self._active_recorder != recorder_instance:
                logger.debug(f"GHKM: Another recorder {self._active_recorder} is active. Requesting it to stop.")
                try:

                    if hasattr(self._active_recorder, 'stop_recording') and \
                       hasattr(self._active_recorder, 'master') and \
                       self._active_recorder.master and \
                       hasattr(self._active_recorder.master, 'after') and \
                       callable(self._active_recorder.master.after):

                        self._active_recorder.master.after(0, self._active_recorder.stop_recording, True) 
                    else:
                        logger.warning(f"GHKM: Could not properly request stop for previous recorder {self._active_recorder} (missing attributes/methods or master). Manually clearing active recorder.")

                        if self._hook_handle: #
                            try: keyboard.unhook(self._hook_handle)
                            except: pass
                        self._hook_handle = None
                        self._active_recorder = None 

                except Exception as e:
                    logger.warning(f"GHKM: Error requesting stop for previous recorder: {e}")
            if self._hook_handle:
                logger.debug("GHKM: Existing hook_handle found, attempting to unhook before setting new one.")
                try: keyboard.unhook(self._hook_handle)
                except: pass
                self._hook_handle = None

            was_hook_globally_free = (self._active_recorder is None)

            try:
                self._hook_handle = keyboard.hook(callback, suppress=True)

                self._active_recorder = recorder_instance 
                logger.debug(f"GHKM: Hook successfully installed for {recorder_instance} (suppress=True).")

                if was_hook_globally_free: 
                    self._notify_hook_state_change(True) 
                return True
            except Exception as e:
                logger.error(f"GHKM: Failed to install hook for {recorder_instance}: {e}", exc_info=True)
                if self._active_recorder == recorder_instance: 
                    self._active_recorder = None

                if was_hook_globally_free:
                    self._notify_hook_state_change(False) 
                return False

    def release_hook(self, recorder_instance: 'KeyRecorder'):
        with self._lock:
            logger.debug(f"GHKM: Hook release requested by {recorder_instance}. Current active: {self._active_recorder}")
            if self._active_recorder == recorder_instance:
                if self._hook_handle:
                    try:
                        keyboard.unhook(self._hook_handle)
                        logger.debug(f"GHKM: Hook unhooked by {recorder_instance}.")
                    except Exception as e:
                        logger.warning(f"GHKM: Error unhooking: {e}")
                    self._hook_handle = None
                
                self._active_recorder = None
                logger.debug(f"GHKM: Active recorder cleared.")
                self._notify_hook_state_change(False) 
            else:
                logger.warning(f"GHKM: {recorder_instance} tried to release hook, but {self._active_recorder} was active (or None).")


    def is_hook_active_by(self, recorder_instance: 'KeyRecorder'):
        with self._lock:
            return self._active_recorder == recorder_instance and self._hook_handle is not None
    
    

class KeyRecorder(ttk.Frame):
    def __init__(self, master, initial_key="", on_change_callback=None):
        super().__init__(master)
        self._recorded_key_internal = initial_key if initial_key and initial_key.strip() else ""
        self._display_key_var = tk.StringVar(value=self._format_display_key(self._recorded_key_internal))
        self._is_recording_local_state = False 
        self.on_change_callback = on_change_callback
        self._hook_manager = GlobalKeyboardHookManager()

        self.key_display_label = ttk.Label(self, textvariable=self._display_key_var, width=25, relief="sunken", anchor="w", padding=(5,2))
        self.key_display_label.pack(side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)

        self.record_button = ttk.Button(self, text="Record", command=self.toggle_recording, width=8)
        self.record_button.pack(side=tk.LEFT)

    def get_key(self) -> str:
        return self._recorded_key_internal

    def set_key(self, key_string: str | None):
        self._recorded_key_internal = key_string if key_string and key_string.strip() else ""
        self._display_key_var.set(self._format_display_key(self._recorded_key_internal))
        if self.on_change_callback:
            if hasattr(self, 'master') and self.master and hasattr(self.master, 'after') and callable(self.master.after):
                 self.master.after(0, self.on_change_callback, self._recorded_key_internal)
            else: 
                 try: self.on_change_callback(self._recorded_key_internal)
                 except Exception as e: logger.error(f"KeyRecorder: Error in on_change_callback (no master.after): {e}")


    def _format_display_key(self, key_str: str) -> str:
        return key_str if key_str else "None (Click Record)"

    def toggle_recording(self):
        if self._is_recording_local_state:
            self.stop_recording(cancelled=True)
        else:
            self.start_recording()

    def start_recording(self):
        if self._is_recording_local_state:
            return

        if self._hook_manager.request_hook(self, self._key_event_handler):
            self._is_recording_local_state = True
            self.record_button.config(text="Recording...", state=tk.DISABLED)
            self._display_key_var.set("Press key(s)... (Esc to cancel)")
            logger.debug(f"KeyRecorder ({id(self)}): Started recording.")
        else:
            logger.error(f"KeyRecorder ({id(self)}): Failed to acquire hook from manager.")
            self._display_key_var.set("Error: Hook busy")

    def stop_recording(self, cancelled: bool = False):
        if not self._is_recording_local_state:
            return

        self._is_recording_local_state = False 
        self._hook_manager.release_hook(self) 
        
        if self.winfo_exists():
            self.master.after(0, self._finalize_stop_recording_ui, cancelled)
        logger.debug(f"KeyRecorder ({id(self)}): Stopped recording. Cancelled: {cancelled}")


    def _finalize_stop_recording_ui(self, cancelled: bool):
        if not self.winfo_exists():
            return

        self.record_button.config(text="Record", state=tk.NORMAL)
        current_display_value = ""
        if cancelled:
            current_display_value = self._format_display_key(self._recorded_key_internal)
        elif self._recorded_key_internal: 
            current_display_value = self._format_display_key(self._recorded_key_internal)
        else: 
            current_display_value = self._format_display_key("") 
        
        self._display_key_var.set(current_display_value)


    def _key_event_handler(self, event: keyboard.KeyboardEvent):

        standard_modifiers = {
            "left ctrl": "ctrl", "right ctrl": "ctrl", "ctrl": "ctrl",
            "left shift": "shift", "right shift": "shift", "shift": "shift",
            "left alt": "alt", "right alt": "alt", "altgr": "alt", "alt": "alt",
            "left windows": "win", "right windows": "win", "win": "win",
            "left cmd": "win", "right cmd": "win", "cmd": "win", 
            "left meta": "win", "right meta": "win", "meta": "win",
        }
        standard_keys = {
            "space": "space", "enter": "enter", "return": "enter", "tab": "tab",
            "backspace": "backspace", "delete": "delete", "insert": "insert",
            "home": "home", "end": "end", "page up": "pageup", "page down": "pagedown",
            "up": "up", "down": "down", "left": "left", "right": "right",
            **{f"f{i}": f"f{i}" for i in range(1, 13)},
            **{f"num{i}":f"num{i}" for i in range(10)},
            "decimal": "decimal", "add": "add", "subtract":"subtract", "multiply":"multiply", "divide":"divide"
        }
        robust_win_key_names = {"win", "left windows", "right windows"}

        if not self._is_recording_local_state or not self._hook_manager.is_hook_active_by(self):
            return True

        if event.name == 'esc':
            logger.debug(f"KeyRecorder ({id(self)}): Recording cancelled by ESC key.")
            if self.winfo_exists() and self.master and hasattr(self.master, 'after'):
                self.master.after(0, self.stop_recording, True)
            return False

        if event.event_type == keyboard.KEY_DOWN:
            processed_key_str = ""
            try:
                active_modifier_set = set()
                if keyboard.is_pressed("ctrl") or keyboard.is_pressed("left ctrl") or keyboard.is_pressed("right ctrl"):
                    active_modifier_set.add("ctrl")
                if keyboard.is_pressed("shift") or keyboard.is_pressed("left shift") or keyboard.is_pressed("right shift"):
                    active_modifier_set.add("shift")
                if keyboard.is_pressed("alt") or keyboard.is_pressed("left alt") or keyboard.is_pressed("right alt") or keyboard.is_pressed("altgr"):
                    active_modifier_set.add("alt")

                for wk_name in robust_win_key_names:
                    try:
                        if keyboard.is_pressed(wk_name):
                            active_modifier_set.add("win")
                            break 
                    except ValueError: 
                        pass
                
                final_key_parts = sorted(list(active_modifier_set))
                current_event_name = event.name.lower() if event.name else "unknown"
                main_event_key = None

                if current_event_name in standard_modifiers:
                 
                    pass
                elif current_event_name in standard_keys:
                    main_event_key = standard_keys[current_event_name]
                elif len(current_event_name) == 1 and current_event_name.isalnum():
                    main_event_key = current_event_name
                
                if main_event_key:
                    if main_event_key not in final_key_parts:
                        final_key_parts.append(main_event_key)
                    processed_key_str = "+".join(final_key_parts)
                else: 
                    if final_key_parts:
                        self._display_key_var.set(f"Recording: { '+'.join(final_key_parts) } + ...")
                    else: 
                        self._display_key_var.set("Press key(s)... (Esc to cancel)")
                    return True 

                if processed_key_str:
                    logger.debug(f"KeyRecorder ({id(self)}): Key to record: '{processed_key_str}'")
                    if self.winfo_exists() and self.master and hasattr(self.master, 'after'):
                        def schedule_update(key_to_set):
                            if not self.winfo_exists(): return
                            self._recorded_key_internal = key_to_set
                            self._display_key_var.set(self._format_display_key(key_to_set))
                            if self.on_change_callback:
                                self.on_change_callback(key_to_set)
                            self.stop_recording(cancelled=False)
                        self.master.after(0, lambda k=processed_key_str: schedule_update(k))
                    return False
                else:
                    return True

            except ValueError as ve:
                 logger.error(f"KeyRecorder ({id(self)}): ValueError in _key_event_handler (likely from is_pressed for an unmapped key like 'os'): {ve}")
                 return True
            except Exception as e:
                logger.error(f"KeyRecorder ({id(self)}): Error in _key_event_handler (KEY_DOWN): {e}", exc_info=True)
                if self.winfo_exists() and self.master and hasattr(self.master, 'after'):
                     self.master.after(0, self.stop_recording, True)
                return True

        elif event.event_type == keyboard.KEY_UP:
            current_event_name = event.name.lower() if event.name else "unknown"

            normalized_released_modifier = standard_modifiers.get(current_event_name)

            if normalized_released_modifier:
             
                def check_and_record_modifier_on_release(released_mod_name):
                    if not self._is_recording_local_state: return 
                    other_mods_pressed = set()
                    if keyboard.is_pressed("ctrl") or keyboard.is_pressed("left ctrl") or keyboard.is_pressed("right ctrl"): other_mods_pressed.add("ctrl")
                    if keyboard.is_pressed("shift") or keyboard.is_pressed("left shift") or keyboard.is_pressed("right shift"): other_mods_pressed.add("shift")
                    if keyboard.is_pressed("alt") or keyboard.is_pressed("left alt") or keyboard.is_pressed("right alt") or keyboard.is_pressed("altgr"): other_mods_pressed.add("alt")
                    for wk_name in robust_win_key_names:
                        try:
                            if keyboard.is_pressed(wk_name): other_mods_pressed.add("win"); break
                        except ValueError: pass

                    if not self._recorded_key_internal and not other_mods_pressed:
                        key_to_set = released_mod_name 
                        logger.debug(f"KeyRecorder ({id(self)}): Modifier '{key_to_set}' released alone, recording it.")

                        if self.winfo_exists() and self.master and hasattr(self.master, 'after'):
                            def schedule_update_final(k_final_set):
                                if not self.winfo_exists(): return
                                self._recorded_key_internal = k_final_set
                                self._display_key_var.set(self._format_display_key(k_final_set))
                                if self.on_change_callback:
                                    self.on_change_callback(k_final_set)
                                self.stop_recording(cancelled=False)
                            self.master.after(0, lambda k_s=key_to_set: schedule_update_final(k_s))

                if self.winfo_exists() and self.master and hasattr(self.master, 'after'):
                    self.master.after(20, lambda mod_name=normalized_released_modifier: check_and_record_modifier_on_release(mod_name)) 
            return True 
        
        return True

    def destroy(self):
        logger.debug(f"KeyRecorder ({id(self)}): Destroying. Internal key: '{self._recorded_key_internal}'")
        if self._is_recording_local_state:
             self._hook_manager.release_hook(self)
             self._is_recording_local_state = False
        super().destroy()
