# gui/action_settings.py
import tkinter as tk
from tkinter import ttk, messagebox
import logging
import copy
from typing import Any, Dict, Optional, List, Callable 

logger = logging.getLogger(__name__)

try:
    from gui.key_recorder import KeyRecorder
    _KeyRecorderImported = True
except ImportError:
    logger.warning("ActionSettings: Could not import KeyRecorder. Key recording functionality will be limited.")
    _KeyRecorderImported = False
    class KeyRecorder(ttk.Frame):
        def __init__(self, master, initial_key="", on_change_callback=None):
             super().__init__(master)
             self._recorded_key_internal_val = initial_key if initial_key else ""
             self._entry = ttk.Entry(self)
             self._entry.insert(0, self._recorded_key_internal_val if self._recorded_key_internal_val else "None")
             self._entry.config(state="readonly")
             self._entry.pack(fill=tk.X, expand=True)
        def get_key(self): return self._recorded_key_internal_val
        def set_key(self, key_string: str | None):
             self._recorded_key_internal_val = key_string if key_string else ""
             if hasattr(self, '_entry') and self._entry.winfo_exists():
                 current_state = self._entry.cget("state")
                 if current_state == tk.DISABLED: self._entry.config(state=tk.NORMAL)
                 self._entry.delete(0, tk.END)
                 self._entry.insert(0, self._recorded_key_internal_val if self._recorded_key_internal_val else "None")
                 if current_state == tk.DISABLED: self._entry.config(state=tk.DISABLED)
        def destroy(self): super().destroy()


try:
    from gui.coordinate_capture_window import CoordinateCaptureWindow
    _CoordinateCaptureWindowImported = True
except ImportError:
    logger.error("ActionSettings: Could not import CoordinateCaptureWindow. Coordinate picking will be disabled.")
    _CoordinateCaptureWindowImported = False
    class CoordinateCaptureWindow:
         def __init__(self, master: tk.Misc, callback: callable, num_points: int = 1):
            logger.error(f"Dummy CoordinateCaptureWindow called for {num_points} points.")
            if callable(callback):
                if hasattr(master, 'after'):
                    master.after(10, lambda: callback(None))
                else:
                    temp_root_for_after = tk.Tk()
                    temp_root_for_after.withdraw()
                    temp_root_for_after.after(10, lambda: callback(None))
                    temp_root_for_after.after(20, temp_root_for_after.destroy)

try:
    from gui.fallback_sequence_editor_dialog import FallbackSequenceEditorDialog
    _FallbackEditorImported = True
except ImportError:
    logger.error("ActionSettings: Could not import FallbackSequenceEditorDialog.")
    _FallbackEditorImported = False
    class FallbackSequenceEditorDialog(tk.Toplevel):
        result_sequence: Optional[List[Dict[str, Any]]] = None
        def __init__(self, master, initial_fallback_sequence, job_manager, image_storage, parent_action_type, current_fallback_depth, max_fallback_depth):
            super().__init__(master)
            self.title("Dummy Fallback Editor")
            ttk.Label(self, text="FallbackSequenceEditorDialog (Dummy)").pack(padx=20, pady=20)
            self.result_sequence = initial_fallback_sequence 
            self.after(100, self.destroy)


def is_integer_or_empty(value: str) -> bool:
    if value == "":
        return True
    try:
        int(value)
        return True
    except ValueError:
        return False

def is_float_or_empty(value: str) -> bool:
    if value == "":
        return True
    try:
        float(value)
        return True
    except ValueError:
        return False

class ActionSettings(ttk.Frame):
    def __init__(self, master: tk.Misc,
                 action: Optional[Dict[str, Any]] = None,
                 job_manager: Optional[Any] = None, 
                 image_storage: Optional[Any] = None, 
                 current_job_actions_count: int = 0, 
                 is_editing_fallback: bool = False, 
                 current_fallback_depth: int = 0,   
                 max_fallback_depth: int = 3):     

        super().__init__(master)
        self.job_manager = job_manager
        self.image_storage = image_storage
        self.current_job_actions_count = current_job_actions_count
        self.is_editing_fallback = is_editing_fallback
        self.current_fallback_depth = current_fallback_depth
        self.max_fallback_depth = max_fallback_depth

        default_action: Dict[str, Any] = {
            "type": "click",
            "params": {},
            "condition_id": None,
            "next_action_index_if_condition_met": None,
            "next_action_index_if_condition_not_met": None,
            "is_absolute": False,
            "fallback_action_sequence": None
        }
        self.action = copy.deepcopy(action or default_action)
        self.action.setdefault("type", "click")
        self.action.setdefault("params", {})
        self.action.setdefault("condition_id", None)
        self.action.setdefault("next_action_index_if_condition_met", None)
        self.action.setdefault("next_action_index_if_condition_not_met", None)
        self.action.setdefault("is_absolute", False)
        self.action.setdefault("fallback_action_sequence", None)

        self.vcmd_integer = self.register(is_integer_or_empty)
        self.vcmd_float = self.register(is_float_or_empty)

        top_config_frame = ttk.Frame(self)
        top_config_frame.grid(row=0, column=0, columnspan=3, padx=5, pady=(5,0), sticky=tk.EW)
        top_config_frame.grid_columnconfigure(1, weight=1) 

        self.type_label = ttk.Label(top_config_frame, text="Action Type:")
        self.type_label.grid(row=0, column=0, padx=(0,5), pady=5, sticky=tk.W)

        self.type_choices = ["click", "press_key", "move_mouse", "drag", "wait",
                             "key_down", "key_up", "text_entry", "modified_key_stroke"]

        initial_type = self.action.get("type", "click")
        if initial_type not in self.type_choices:
             logger.warning(f"ActionSettings: Invalid initial type '{initial_type}', defaulting to 'click'.")
             initial_type = "click"
             self.action["type"] = initial_type

        self.type_var = tk.StringVar(value=initial_type)
        self.type_combobox = ttk.Combobox(
            top_config_frame, textvariable=self.type_var, values=self.type_choices,
            state="readonly", width=20
        )
        self.type_combobox.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        self.type_combobox.bind("<<ComboboxSelected>>", self.on_type_selected)

        self.is_absolute_var = tk.BooleanVar(value=self.action.get("is_absolute", False))
        self.is_absolute_checkbutton = ttk.Checkbutton(
            top_config_frame, text="Is Absolute (Must Execute)",
            variable=self.is_absolute_var
        )
        self.is_absolute_checkbutton.grid(row=0, column=2, padx=(10,0), pady=5, sticky=tk.W)

        self.param_frame = ttk.Frame(self)
        self.param_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        self.param_frame.grid_columnconfigure(1, weight=1)
        self.param_widgets: Dict[str, Any] = {}
        self._button_var = tk.StringVar() 
        self._click_type_var = tk.StringVar() 

        flow_control_outer_frame = ttk.Frame(self)
        flow_control_outer_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        flow_control_outer_frame.grid_columnconfigure(0, weight=1) 

        self.jump_settings_frame = ttk.LabelFrame(flow_control_outer_frame, text="Flow Control (Next Action Index, 0-based)", padding="5")
        self.jump_settings_frame.pack(fill=tk.X, expand=True, pady=(0,5))
        self.jump_settings_frame.grid_columnconfigure(1, weight=1)
        self.jump_settings_frame.grid_columnconfigure(3, weight=1) 

        self._create_param_entry(
            "next_action_index_if_condition_met", "If Condition Met:",
            row=0, column=0, master=self.jump_settings_frame, width=8, validate_type="integer"
        )
        self._create_param_entry(
            "next_action_index_if_condition_not_met", "If Condition Not Met:",
            row=0, column=2, master=self.jump_settings_frame, width=8, validate_type="integer"
        )

        if self.current_job_actions_count > 0:
            max_idx = self.current_job_actions_count - 1
            ttk.Label(self.jump_settings_frame, text=f"(Current max index: {max_idx})").grid(row=0, column=4, padx=5, sticky=tk.W)

        self.fallback_settings_frame = ttk.LabelFrame(flow_control_outer_frame, text="Fallback Action Sequence", padding="5")
        self.fallback_settings_frame.pack(fill=tk.X, expand=True)
        self.fallback_settings_frame.grid_columnconfigure(0, weight=1)

        self.fallback_summary_var = tk.StringVar(value=self._get_fallback_summary_text())
        fallback_summary_label = ttk.Label(self.fallback_settings_frame, textvariable=self.fallback_summary_var)
        fallback_summary_label.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.manage_fallback_button = ttk.Button(
            self.fallback_settings_frame,
            text="Define/Edit Fallback Sequence...",
            command=self._manage_fallback_sequence
        )
        self.manage_fallback_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        if self.is_editing_fallback and self.current_fallback_depth + 1 >= self.max_fallback_depth:
            self.manage_fallback_button.grid_remove()
            fallback_summary_label.grid_configure(columnspan=2)
            ttk.Label(self.fallback_settings_frame, text="(Max fallback depth reached)").grid(row=1, column=0, columnspan=2, padx=5, sticky="w", pady=(0,5))


        self.on_type_selected(from_init=True) 
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)    

    def _get_fallback_summary_text(self) -> str:
        sequence = self.action.get("fallback_action_sequence")
        if isinstance(sequence, list) and sequence:
            return f"{len(sequence)} fallback action(s) defined."
        return "(No fallback actions defined)"

    def _update_fallback_summary_display(self):
        self.fallback_summary_var.set(self._get_fallback_summary_text())

    def _manage_fallback_sequence(self):
        if not _FallbackEditorImported:
            messagebox.showerror("Error", "Fallback Sequence Editor UI is not available.", parent=self)
            return
        if not self.job_manager or not self.image_storage:
            messagebox.showerror("Error", "JobManager or ImageStorage not available for Fallback Editor.", parent=self)
            return

        current_sequence_data = self.action.get("fallback_action_sequence")

        dialog = FallbackSequenceEditorDialog(
            self.winfo_toplevel(), 
            initial_fallback_sequence=current_sequence_data,
            job_manager=self.job_manager,
            image_storage=self.image_storage,
            parent_action_type=self.action.get("type", "unknown"),
            current_fallback_depth=self.current_fallback_depth, 
            max_fallback_depth=self.max_fallback_depth
        )

        if dialog.result_sequence is not None:
            self.action["fallback_action_sequence"] = dialog.result_sequence
        self._update_fallback_summary_display()


    def on_type_selected(self, event: Optional[tk.Event] = None, from_init: bool = False) -> None:
        selected_type_from_var = self.type_var.get()
        logger.debug(f"ActionSettings.on_type_selected: Triggered. Var: '{selected_type_from_var}'. Current self.action type: '{self.action.get('type')}'. From init: {from_init}")

        if not from_init and self.action.get("type") != selected_type_from_var:
            logger.info(f"ActionSettings: User changed type to '{selected_type_from_var}'. Resetting params.")
            self.action["type"] = selected_type_from_var
            self.action["params"] = {}
        elif from_init and self.action.get("type") != selected_type_from_var :
            logger.warning(f"ActionSettings: Init type mismatch. Var: '{selected_type_from_var}', Action: '{self.action.get('type')}'. Forcing var to action type.")
            self.type_var.set(self.action.get("type", "click"))
            selected_type_from_var = self.type_var.get()


        if hasattr(self, 'param_frame') and self.param_frame.winfo_exists():
            for widget in list(self.param_frame.winfo_children()):
                if widget not in [getattr(self, 'jump_settings_frame', None), getattr(self, 'fallback_settings_frame', None)]:
                    try:
                        if widget.winfo_exists(): widget.destroy()
                    except tk.TclError: pass
                    except Exception: pass
            self.param_widgets = {} 
        else:
            self.param_frame = ttk.Frame(self)
            self.param_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
            self.param_frame.grid_columnconfigure(1, weight=1)

        param_creation_func = getattr(self, f'_create_{selected_type_from_var}_params', None)
        if callable(param_creation_func):
             param_creation_func()
        else:
            if self.param_frame.winfo_exists():
                no_param_label = ttk.Label(self.param_frame, text="(No specific parameters for this type)")
                no_param_label.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
                self.param_widgets["_no_param_label_"] = [no_param_label]

        self._populate_widgets_from_current_action_state() 

        if self.param_frame.winfo_exists():
            self.param_frame.update_idletasks()

    def _populate_widgets_from_current_action_state(self) -> None:
        action_type = self.action.get("type", "click")
        params = self.action.get("params", {})
        if not isinstance(params, dict): params = {}

        logger.debug(f"ActionSettings._populate_widgets: Populating for type '{action_type}' with params {params}")

        default_params_for_type = self._get_default_params_for_type(action_type)

        if action_type == "click":
            self._update_widget_value("x", params.get("x", default_params_for_type.get("x",0)))
            self._update_widget_value("y", params.get("y", default_params_for_type.get("y",0)))
            self._update_widget_value("delay_before", params.get("delay_before", default_params_for_type.get("delay_before",0.0)))
            self._button_var.set(params.get("button", default_params_for_type.get("button","left")))
            self._click_type_var.set(params.get("click_type", default_params_for_type.get("click_type","single")))
            self._update_widget_value("hold_duration", params.get("hold_duration", default_params_for_type.get("hold_duration",0.0)))
        elif action_type == "press_key":
            self._update_widget_value("key", params.get("key", default_params_for_type.get("key","")))
            self._update_widget_value("delay_before", params.get("delay_before", default_params_for_type.get("delay_before",0.0)))
        elif action_type == "move_mouse":
            self._update_widget_value("x", params.get("x", default_params_for_type.get("x",0)))
            self._update_widget_value("y", params.get("y", default_params_for_type.get("y",0)))
            self._update_widget_value("duration", params.get("duration", default_params_for_type.get("duration",0.1)))
            self._update_widget_value("delay_before", params.get("delay_before", default_params_for_type.get("delay_before",0.0)))
        elif action_type == "drag":
            self._update_widget_value("x", params.get("x", default_params_for_type.get("x",0)))
            self._update_widget_value("y", params.get("y", default_params_for_type.get("y",0)))
            self._update_widget_value("swipe_x", params.get("swipe_x", default_params_for_type.get("swipe_x",0)))
            self._update_widget_value("swipe_y", params.get("swipe_y", default_params_for_type.get("swipe_y",0)))
            self._update_widget_value("duration", params.get("duration", default_params_for_type.get("duration",1.0)))
            self._update_widget_value("delay_before", params.get("delay_before", default_params_for_type.get("delay_before",0.0)))
            self._button_var.set(params.get("button", default_params_for_type.get("button","left")))
        elif action_type == "wait":
            self._update_widget_value("duration", params.get("duration", default_params_for_type.get("duration",1.0)))
            self._update_widget_value("delay_before", params.get("delay_before", default_params_for_type.get("delay_before",0.0)))
        elif action_type == "key_down":
            self._update_widget_value("key", params.get("key", default_params_for_type.get("key","")))
            self._update_widget_value("delay_before", params.get("delay_before", default_params_for_type.get("delay_before",0.0)))
        elif action_type == "key_up":
            self._update_widget_value("key", params.get("key", default_params_for_type.get("key","")))
            self._update_widget_value("delay_before", params.get("delay_before", default_params_for_type.get("delay_before",0.0)))
        elif action_type == "text_entry":
            self._update_widget_value("text", params.get("text", default_params_for_type.get("text","")))
            self._update_widget_value("delay_before", params.get("delay_before", default_params_for_type.get("delay_before",0.0)))
        elif action_type == "modified_key_stroke":
            self._update_widget_value("modifier", params.get("modifier", default_params_for_type.get("modifier","")))
            self._update_widget_value("main_key", params.get("main_key", default_params_for_type.get("main_key","")))
            self._update_widget_value("delay_before", params.get("delay_before", default_params_for_type.get("delay_before",0.0)))

        self._update_widget_value("next_action_index_if_condition_met", self.action.get("next_action_index_if_condition_met"))
        self._update_widget_value("next_action_index_if_condition_not_met", self.action.get("next_action_index_if_condition_not_met"))
        self.is_absolute_var.set(bool(self.action.get("is_absolute", False)))
        self._update_fallback_summary_display()


    def _get_default_params_for_type(self, action_type_str: str) -> Dict[str, Any]:
        if action_type_str == "click": return {"x":0, "y":0, "delay_before":0.0, "button":"left", "click_type":"single", "hold_duration":0.0}
        if action_type_str == "press_key": return {"key":"", "delay_before":0.0}
        if action_type_str == "move_mouse": return {"x":0, "y":0, "duration":0.1, "delay_before":0.0}
        if action_type_str == "drag": return {"x":0, "y":0, "swipe_x":0, "swipe_y":0, "duration":1.0, "delay_before":0.0, "button":"left"}
        if action_type_str == "wait": return {"duration":1.0, "delay_before":0.0}
        if action_type_str == "key_down": return {"key":"", "delay_before":0.0}
        if action_type_str == "key_up": return {"key":"", "delay_before":0.0}
        if action_type_str == "text_entry": return {"text":"", "delay_before":0.0}
        if action_type_str == "modified_key_stroke": return {"modifier":"", "main_key":"", "delay_before":0.0}
        return {}


    def _create_param_entry(self, key: str, text: str, row: int, column: int = 0, columnspan: int = 2,
                            sticky: str = tk.EW, padx: int = 5, pady: int = 2, width: Optional[int] = None,
                            master: Optional[tk.Widget] = None, validate_type: Optional[str] = None) -> ttk.Entry:
        parent_frame = master if master else self.param_frame
        label = ttk.Label(parent_frame, text=text)
        label.grid(row=row, column=column, padx=padx, pady=pady, sticky=tk.W)

        entry_width = width if width is not None else 20
        entry = ttk.Entry(parent_frame, width=entry_width)
        if validate_type == "integer":
            entry.config(validate="key", validatecommand=(self.vcmd_integer, "%P"))
        elif validate_type == "float":
            entry.config(validate="key", validatecommand=(self.vcmd_float, "%P"))

        entry_column = column + 1
        entry_columnspan = columnspan -1 if columnspan > 1 else 1
        if columnspan == 1: entry_columnspan = 1


        entry.grid(row=row, column=entry_column, columnspan=entry_columnspan, padx=padx, pady=pady, sticky=sticky)
        self.param_widgets[key] = entry
        return entry

    def _update_widget_value(self, key: str, value: Any, default: Any = "") -> None:
        widget = self.param_widgets.get(key)
        actual_value_to_set = str(value) if value is not None else str(default)

        if isinstance(widget, ttk.Entry):
            try:
                if widget.winfo_exists():
                    current_state = widget.cget("state")
                    if current_state == tk.DISABLED: widget.config(state=tk.NORMAL)
                    widget.delete(0, tk.END)
                    widget.insert(0, actual_value_to_set)
                    if current_state == tk.DISABLED: widget.config(state=tk.DISABLED)
            except tk.TclError: pass
            except Exception as e: logger.error(f"Error updating widget {key}: {e}")
        elif isinstance(widget, KeyRecorder) and hasattr(widget, 'set_key'):
             try:
                 if widget.winfo_exists():
                     widget.set_key(str(actual_value_to_set))
             except tk.TclError: pass
             except Exception as e: logger.error(f"Error updating KeyRecorder {key}: {e}")


    def _add_coordinate_entries_and_button(self, row: int, x_key: str, y_key: str, x_text: str, y_text: str,
                                           pick_button_text: str, num_points_to_pick: int) -> None:
        self.param_frame.grid_columnconfigure(1, weight=0)
        self.param_frame.grid_columnconfigure(3, weight=0)
        self.param_frame.grid_columnconfigure(4, weight=0)

        self._create_param_entry(x_key, x_text, row, column=0, columnspan=1, sticky=tk.W, width=8, validate_type="integer")
        self._create_param_entry(y_key, y_text, row, column=2, columnspan=1, sticky=tk.W, width=8, validate_type="integer")

        if _CoordinateCaptureWindowImported:
            pick_button = ttk.Button(
                self.param_frame, text=pick_button_text, width=12,
                command=lambda np=num_points_to_pick, xk=x_key, yk=y_key: self._pick_coordinates_action(np, x_entry_key=xk, y_entry_key=yk)
            )
            pick_button.grid(row=row, column=4, padx=5, pady=2, sticky="e")
        else:
            ttk.Label(self.param_frame, text="(Pick N/A)").grid(row=row, column=4, padx=5, pady=2, sticky="w")


    def _create_click_params(self) -> None:
        current_row = 0
        self._add_coordinate_entries_and_button(
            row=current_row, x_key="x", y_key="y",
            x_text="X:", y_text="Y:",
            pick_button_text="Pick Point", num_points_to_pick=1
        )
        current_row += 1
        self._create_param_entry("delay_before", "Delay Before (s):", current_row, width=8, validate_type="float", columnspan=4); current_row += 1

        button_frame = ttk.Frame(self.param_frame)
        button_frame.grid(row=current_row, column=0, columnspan=5, padx=0, pady=2, sticky=tk.W)
        ttk.Label(button_frame, text="Button:").pack(side=tk.LEFT, padx=(5,2))
        ttk.Radiobutton(button_frame, text="Left", variable=self._button_var, value="left").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(button_frame, text="Right", variable=self._button_var, value="right").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(button_frame, text="Middle", variable=self._button_var, value="middle").pack(side=tk.LEFT, padx=2)
        current_row += 1

        click_type_frame = ttk.Frame(self.param_frame)
        click_type_frame.grid(row=current_row, column=0, columnspan=5, padx=0, pady=2, sticky=tk.W)
        ttk.Label(click_type_frame, text="Click Type:").pack(side=tk.LEFT, padx=(5,2))
        ttk.Radiobutton(click_type_frame, text="Single", variable=self._click_type_var, value="single").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(click_type_frame, text="Double", variable=self._click_type_var, value="double").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(click_type_frame, text="Down", variable=self._click_type_var, value="down").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(click_type_frame, text="Up", variable=self._click_type_var, value="up").pack(side=tk.LEFT, padx=2)
        current_row += 1

        self._create_param_entry("hold_duration", "Hold Duration (s):", current_row, width=8, validate_type="float", columnspan=4); current_row += 1
        self.param_frame.grid_columnconfigure(1, weight=1)


    def _create_press_key_params(self) -> None:
        current_row = 0
        key_label = ttk.Label(self.param_frame, text="Key:")
        key_label.grid(row=current_row, column=0, padx=5, pady=2, sticky=tk.W)
        if _KeyRecorderImported:
            key_recorder_widget = KeyRecorder(self.param_frame)
            key_recorder_widget.grid(row=current_row, column=1, padx=5, pady=2, sticky=tk.EW)
            self.param_widgets["key"] = key_recorder_widget
        else:
            fallback_entry = ttk.Entry(self.param_frame)
            fallback_entry.grid(row=current_row, column=1, padx=5, pady=2, sticky=tk.EW)
            self.param_widgets["key"] = fallback_entry
            ttk.Label(self.param_frame, text="(KeyRecorder N/A)").grid(row=current_row, column=2, padx=5, pady=2, sticky=tk.W)
        current_row += 1
        self._create_param_entry("delay_before", "Delay Before (s):", current_row, width=8, validate_type="float"); current_row += 1
        self.param_frame.grid_columnconfigure(1, weight=1)
        self.param_frame.grid_columnconfigure(2, weight=0)

    def _create_move_mouse_params(self) -> None:
        current_row = 0
        self._add_coordinate_entries_and_button(
            row=current_row, x_key="x", y_key="y",
            x_text="Target X:", y_text="Target Y:",
            pick_button_text="Pick Point", num_points_to_pick=1
        )
        current_row += 1
        self._create_param_entry("duration", "Duration (s):", current_row, width=8, validate_type="float", columnspan=4); current_row += 1
        self._create_param_entry("delay_before", "Delay Before (s):", current_row, width=8, validate_type="float", columnspan=4); current_row += 1
        self.param_frame.grid_columnconfigure(1, weight=1)

    def _create_drag_params(self) -> None:
        current_row = 0
        self._create_param_entry("x", "Start X:", current_row, column=0, columnspan=1, sticky=tk.W, width=8, validate_type="integer")
        self._create_param_entry("y", "Start Y:", current_row, column=2, columnspan=1, sticky=tk.W, width=8, validate_type="integer"); current_row += 1
        self._create_param_entry("swipe_x", "End X:", current_row, column=0, columnspan=1, sticky=tk.W, width=8, validate_type="integer")
        self._create_param_entry("swipe_y", "End Y:", current_row, column=2, columnspan=1, sticky=tk.W, width=8, validate_type="integer"); current_row += 1
        if _CoordinateCaptureWindowImported:
            pick_button = ttk.Button(
                self.param_frame, text="Pick Start/End", width=12,
                command=lambda: self._pick_coordinates_action(2, x_entry_key="x", y_entry_key="y", x2_entry_key="swipe_x", y2_entry_key="swipe_y")
            )
            pick_button.grid(row=current_row, column=0, columnspan=5, padx=5, pady=5, sticky="w"); current_row += 1
        else:
            ttk.Label(self.param_frame, text="(Pick N/A)").grid(row=current_row, column=0, columnspan=5, padx=5, pady=5, sticky="w"); current_row += 1

        self._create_param_entry("duration", "Duration (s):", current_row, width=8, validate_type="float", columnspan=4); current_row += 1
        self._create_param_entry("delay_before", "Delay Before (s):", current_row, width=8, validate_type="float", columnspan=4); current_row += 1
        button_frame = ttk.Frame(self.param_frame)
        button_frame.grid(row=current_row, column=0, columnspan=5, padx=0, pady=2, sticky=tk.W)
        ttk.Label(button_frame, text="Button:").pack(side=tk.LEFT, padx=(5,2))
        ttk.Radiobutton(button_frame, text="Left", variable=self._button_var, value="left").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(button_frame, text="Right", variable=self._button_var, value="right").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(button_frame, text="Middle", variable=self._button_var, value="middle").pack(side=tk.LEFT, padx=2)
        current_row += 1
        self.param_frame.grid_columnconfigure(1, weight=1)


    def _create_wait_params(self) -> None:
        current_row = 0
        self._create_param_entry("duration", "Duration (s):", current_row, width=8, validate_type="float"); current_row += 1
        self._create_param_entry("delay_before", "Delay Before (s):", current_row, width=8, validate_type="float"); current_row += 1
        self.param_frame.grid_columnconfigure(1, weight=1)

    def _create_key_down_params(self) -> None:
        self._create_press_key_params()

    def _create_key_up_params(self) -> None:
        self._create_press_key_params()

    def _create_text_entry_params(self) -> None:
        current_row = 0
        self._create_param_entry("text", "Text to Type:", current_row, columnspan=2, sticky=tk.EW); current_row += 1
        self._create_param_entry("delay_before", "Delay Before (s):", current_row, width=8, validate_type="float"); current_row += 1
        self.param_frame.grid_columnconfigure(1, weight=1)

    def _create_modified_key_stroke_params(self) -> None:
        current_row = 0
        modifier_label = ttk.Label(self.param_frame, text="Modifier Key:")
        modifier_label.grid(row=current_row, column=0, padx=5, pady=2, sticky=tk.W)
        if _KeyRecorderImported:
            modifier_recorder = KeyRecorder(self.param_frame)
            modifier_recorder.grid(row=current_row, column=1, padx=5, pady=2, sticky=tk.EW)
            self.param_widgets["modifier"] = modifier_recorder
        else:
            fallback_entry_mod = ttk.Entry(self.param_frame)
            fallback_entry_mod.grid(row=current_row, column=1, padx=5, pady=2, sticky=tk.EW)
            self.param_widgets["modifier"] = fallback_entry_mod
        ttk.Label(self.param_frame, text="(e.g. ctrl, shift, alt, win)").grid(row=current_row, column=2, padx=5, pady=2, sticky=tk.W)
        current_row += 1

        main_key_label = ttk.Label(self.param_frame, text="Main Key:")
        main_key_label.grid(row=current_row, column=0, padx=5, pady=2, sticky=tk.W)
        if _KeyRecorderImported:
            main_key_recorder = KeyRecorder(self.param_frame)
            main_key_recorder.grid(row=current_row, column=1, padx=5, pady=2, sticky=tk.EW)
            self.param_widgets["main_key"] = main_key_recorder
        else:
            fallback_entry_main = ttk.Entry(self.param_frame)
            fallback_entry_main.grid(row=current_row, column=1, padx=5, pady=2, sticky=tk.EW)
            self.param_widgets["main_key"] = fallback_entry_main
        current_row += 1

        self._create_param_entry("delay_before", "Delay Before (s):", current_row, width=8, validate_type="float"); current_row += 1
        self.param_frame.grid_columnconfigure(1, weight=1)
        self.param_frame.grid_columnconfigure(2, weight=0)

    def _pick_coordinates_action(self, num_points: int, x_entry_key: str, y_entry_key: str,
                                x2_entry_key: Optional[str] = None, y2_entry_key: Optional[str] = None) -> None:
        if not _CoordinateCaptureWindowImported:
            messagebox.showerror("Error", "Coordinate capture feature is not available.", parent=self.winfo_toplevel())
            return
        try:
            CoordinateCaptureWindow(
                self.winfo_toplevel(),
                callback=lambda result_data: self._on_coordinates_picked_action(result_data, num_points, x_entry_key, y_entry_key, x2_entry_key, y2_entry_key),
                num_points=num_points
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start coordinate capture: {e}", parent=self.winfo_toplevel())
            logger.error(f"Error starting coordinate capture for action: {e}", exc_info=True)


    def _on_coordinates_picked_action(self, result_data: Optional[Any], expected_points: int, x_entry_key: str, y_entry_key: str,
                                      x2_entry_key: Optional[str] = None, y2_entry_key: Optional[str] = None) -> None:
        if result_data is None:
            logger.info("Coordinate pick for action cancelled or failed.")
            return

        try:
            if expected_points == 1 and isinstance(result_data, tuple) and len(result_data) == 2 and isinstance(result_data[0], int):
                x, y = result_data
                self._update_widget_value(x_entry_key, x)
                self._update_widget_value(y_entry_key, y)
            elif expected_points == 2 and isinstance(result_data, tuple) and len(result_data) == 2 and \
                 isinstance(result_data[0], tuple) and len(result_data[0]) == 2 and \
                 isinstance(result_data[1], tuple) and len(result_data[1]) == 2:
                (startX, startY), (endX, endY) = result_data
                self._update_widget_value(x_entry_key, startX)
                self._update_widget_value(y_entry_key, startY)
                if x2_entry_key and y2_entry_key:
                    self._update_widget_value(x2_entry_key, endX)
                    self._update_widget_value(y2_entry_key, endY)
            else:
                logger.warning(f"Received unexpected data format from CoordinateCaptureWindow for action: {result_data}")
        except Exception as e:
            logger.error(f"Error processing picked coordinates for action: {e}", exc_info=True)

    def get_settings(self) -> Dict[str, Any]:
        action_type = self.type_var.get()
        params: Dict[str, Any] = {}
        is_absolute = self.is_absolute_var.get()
        fallback_sequence_to_save = self.action.get("fallback_action_sequence")


        def get_entry_value(key: str) -> Optional[str]:
            widget = self.param_widgets.get(key)
            if isinstance(widget, ttk.Entry):
                return widget.get()
            return None

        def get_key_recorder_value(key: str) -> str:
            widget = self.param_widgets.get(key)
            if isinstance(widget, KeyRecorder) and hasattr(widget, 'get_key'):
                return widget.get_key()
            elif isinstance(widget, ttk.Entry):
                 return widget.get().strip()
            return ""

        def get_int_param(key: str, default: int = 0) -> int:
            value_str = get_entry_value(key)
            if value_str == "" or value_str is None: return default
            try: return int(value_str)
            except ValueError: raise ValueError(f"Invalid integer for '{key}': '{value_str}'")

        def get_float_param(key: str, default: float = 0.0) -> float:
            value_str = get_entry_value(key)
            if value_str == "" or value_str is None: return default
            try: return float(value_str)
            except ValueError: raise ValueError(f"Invalid number for '{key}': '{value_str}'")

        def get_int_or_none_from_entry(key: str) -> Optional[int]:
             value_str = get_entry_value(key)
             if value_str == "" or value_str is None: return None
             try: return int(value_str)
             except ValueError: raise ValueError(f"Invalid integer for '{key}': '{value_str}'")

        try:
            if action_type == "click":
                params = {"x": get_int_param("x"), "y": get_int_param("y"),
                          "delay_before": max(0.0, get_float_param("delay_before")),
                          "button": self._button_var.get() or "left",
                          "click_type": self._click_type_var.get() or "single",
                          "hold_duration": max(0.0, get_float_param("hold_duration"))}
            elif action_type == "press_key":
                key_val = get_key_recorder_value("key")
                if not key_val: raise ValueError("Key for Press Key cannot be empty.")
                params = {"key": key_val, "delay_before": max(0.0, get_float_param("delay_before"))}
            elif action_type == "move_mouse":
                params = {"x": get_int_param("x"), "y": get_int_param("y"),
                          "duration": max(0.0, get_float_param("duration", 0.1)),
                          "delay_before": max(0.0, get_float_param("delay_before"))}
            elif action_type == "drag":
                params = {"x": get_int_param("x"), "y": get_int_param("y"),
                          "swipe_x": get_int_param("swipe_x"), "swipe_y": get_int_param("swipe_y"),
                          "duration": max(0.0, get_float_param("duration", 1.0)),
                          "delay_before": max(0.0, get_float_param("delay_before")),
                          "button": self._button_var.get() or "left"}
            elif action_type == "wait":
                duration_val = get_float_param("duration", 1.0)
                if duration_val <= 0: raise ValueError("Wait duration must be positive.")
                params = {"duration": duration_val, "delay_before": max(0.0, get_float_param("delay_before"))}
            elif action_type == "key_down":
                key_val = get_key_recorder_value("key")
                if not key_val: raise ValueError("Key for Key Down cannot be empty.")
                params = {"key": key_val, "delay_before": max(0.0, get_float_param("delay_before"))}
            elif action_type == "key_up":
                key_val = get_key_recorder_value("key")
                if not key_val: raise ValueError("Key for Key Up cannot be empty.")
                params = {"key": key_val, "delay_before": max(0.0, get_float_param("delay_before"))}
            elif action_type == "text_entry":
                 params = {"text": get_entry_value("text") or "",
                           "delay_before": max(0.0, get_float_param("delay_before"))}
            elif action_type == "modified_key_stroke":
                 mod_key = get_key_recorder_value("modifier")
                 main_k = get_key_recorder_value("main_key")
                 if not mod_key: raise ValueError("Modifier key cannot be empty.")
                 if not main_k: raise ValueError("Main key cannot be empty.")
                 params = {"modifier": mod_key, "main_key": main_k,
                           "delay_before": max(0.0, get_float_param("delay_before"))}

            final_next_met_index = get_int_or_none_from_entry("next_action_index_if_condition_met")
            final_next_not_met_index = get_int_or_none_from_entry("next_action_index_if_condition_not_met")
            if final_next_met_index is not None and final_next_met_index < 0: raise ValueError("Next Action Index (Met) cannot be negative.")
            if final_next_not_met_index is not None and final_next_not_met_index < 0: raise ValueError("Next Action Index (Not Met) cannot be negative.")

        except ValueError as e:
            raise e
        except Exception as e:
             logger.error(f"Unexpected error collecting settings in ActionSettings: {e}", exc_info=True)
             raise ValueError(f"Unexpected error collecting settings: {e}")

        return {
            "type": action_type, "params": params,
            "next_action_index_if_condition_met": final_next_met_index,
            "next_action_index_if_condition_not_met": final_next_not_met_index,
            "is_absolute": is_absolute,
            "fallback_action_sequence": fallback_sequence_to_save # Thêm vào kết quả
        }

    def set_settings(self, settings_data: Dict[str, Any]) -> None:
        if not isinstance(settings_data, dict):
            logger.warning(f"ActionSettings.set_settings: Invalid data type: {type(settings_data)}")
            return

        self.action = copy.deepcopy(settings_data)
        self.action.setdefault("type", "click")
        self.action.setdefault("params", {})
        self.action.setdefault("next_action_index_if_condition_met", None)
        self.action.setdefault("next_action_index_if_condition_not_met", None)
        self.action.setdefault("is_absolute", False)
        self.action.setdefault("fallback_action_sequence", None)


        action_type_from_data = self.action.get("type", "click")
        if action_type_from_data not in self.type_choices:
            logger.warning(f"ActionSettings.set_settings: Invalid action type '{action_type_from_data}' in data. Defaulting to 'click'.")
            action_type_from_data = "click"
            self.action["type"] = action_type_from_data

        force_rebuild_ui = not bool(self.param_widgets)

        if self.type_var.get() != action_type_from_data or force_rebuild_ui:
            self.type_var.set(action_type_from_data) 
        else:
            self._populate_widgets_from_current_action_state()


    def destroy(self) -> None:
        if hasattr(self, 'param_widgets'):
            for key, widget_or_list in list(self.param_widgets.items()):
                if isinstance(widget_or_list, list):
                    for item_widget in widget_or_list:
                        if isinstance(item_widget, tk.Widget) and item_widget.winfo_exists():
                            try: item_widget.destroy()
                            except: pass
                elif isinstance(widget_or_list, tk.Widget) and widget_or_list.winfo_exists():
                    try: widget_or_list.destroy()
                    except: pass
        super().destroy()
