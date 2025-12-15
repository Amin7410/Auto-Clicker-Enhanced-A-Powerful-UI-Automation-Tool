# gui/job_run_condition_settings.py
import tkinter as tk
from tkinter import ttk, messagebox 
import logging

logger = logging.getLogger(__name__)

try:
    from core.job_run_condition import (
        JobRunCondition, InfiniteRunCondition, CountRunCondition, TimeRunCondition,
        create_job_run_condition 
    )
    _RunConditionDepsImported = True
except ImportError:
    logger.error("Could not import core.job_run_condition. Job Run Condition settings will be limited.")
    _RunConditionDepsImported = False
    class JobRunCondition:
         def __init__(self, type="dummy", params=None): self.type="dummy"; self.params={}
         def to_dict(self): return {"type": "dummy", "params": {}}
         def check_continue(self, context): return False
    class InfiniteRunCondition(JobRunCondition): TYPE = "infinite"
    class CountRunCondition(JobRunCondition): TYPE = "count"
    class TimeRunCondition(JobRunCondition): TYPE = "time"
    def create_job_run_condition(data):
         logger.warning("Dummy create_job_run_condition called.")
         return JobRunCondition("dummy")


logger = logging.getLogger(__name__)

RUN_CONDITION_SETTINGS = {
    InfiniteRunCondition.TYPE: {
        "display_name": "Run Infinitely",
        "create_params_ui": lambda self: self._create_infinite_params()
    },
    CountRunCondition.TYPE: {
        "display_name": "Run N Times",
        "create_params_ui": lambda self: self._create_count_params()
    },
    TimeRunCondition.TYPE: {
         "display_name": "Run for Duration",
         "create_params_ui": lambda self: self._create_time_params()
    },
}

RUN_CONDITION_TYPES_INTERNAL = list(RUN_CONDITION_SETTINGS.keys())
RUN_CONDITION_TYPES_DISPLAY = [settings["display_name"] for settings in RUN_CONDITION_SETTINGS.values()]
RUN_CONDITION_DISPLAY_TO_INTERNAL_MAP = {settings["display_name"]: type_key for type_key, settings in RUN_CONDITION_SETTINGS.items()}


class JobRunConditionSettings(ttk.Frame):
    """
    A frame containing widgets to configure the settings (parameters)
    for a Job's Run Condition type. The displayed widgets are dynamic.
    """
    def __init__(self, master, initial_condition_data: dict = None):
        """
        Initializes the JobRunConditionSettings frame.

        Args:
            master: The parent widget.
            initial_condition_data (dict, optional): A dictionary representing the initial condition
                                                   settings (e.g., from job.run_condition.to_dict()).
                                                   Should contain 'type' and 'params'.
                                                   Defaults to data for an InfiniteRunCondition.
        """
        super().__init__(master)
        self.initial_condition_data = initial_condition_data 
        self._current_condition_obj: JobRunCondition = create_job_run_condition(initial_condition_data) 

        logger.debug(f"Initializing JobRunConditionSettings with type: {self._current_condition_obj.type}")

        self.type_label = ttk.Label(self, text="Job Run Condition:")
        self.type_label.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)

        initial_display_type = next(
            (settings["display_name"] for type_key, settings in RUN_CONDITION_SETTINGS.items()
             if type_key == self._current_condition_obj.type),
             RUN_CONDITION_TYPES_DISPLAY[0] 
        )
        self.type_var = tk.StringVar(value=initial_display_type)

        self.type_combobox = ttk.Combobox(
            self,
            textvariable=self.type_var,
            values=RUN_CONDITION_TYPES_DISPLAY,
            state="readonly",
            width=30
        )
        self.type_combobox.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        self.type_combobox.bind("<<ComboboxSelected>>", self._on_type_selected)

        self.param_frame = ttk.Frame(self)

        self.param_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

        self.param_frame.grid_columnconfigure(1, weight=1) 

        self.param_widgets = {}

        self._on_type_selected() 

        self.grid_columnconfigure(1, weight=1) 
        self.grid_rowconfigure(1, weight=1) 


    def _on_type_selected(self, event=None):
        """
        Called when the condition type is changed in the combobox or on initial load.
        Destroys old parameter widgets and creates new ones based on the selected type,
        then attempts to populate them with data from the *initial* condition data
        if the selected type matches, otherwise uses defaults for the new type.
        """
        selected_display_key = self.type_var.get()
        selected_internal_type = RUN_CONDITION_DISPLAY_TO_INTERNAL_MAP.get(selected_display_key, RUN_CONDITION_TYPES_INTERNAL[0])
        logger.debug(f"Job Run Condition type selected: '{selected_display_key}' (internal: '{selected_internal_type}')")

        if hasattr(self, 'param_frame') and self.param_frame.winfo_exists():
             for widget in self.param_frame.winfo_children():
                 widget.destroy()

        self.param_widgets = {} 
        self.param_frame.grid_columnconfigure(0, weight=0) 
        self.param_frame.grid_columnconfigure(1, weight=0)

        create_func = RUN_CONDITION_SETTINGS.get(selected_internal_type, {}).get("create_params_ui")

        if create_func:
            logger.debug(f"Creating widgets for type: {selected_internal_type}")
            try:
                 create_func(self) 
            except Exception as e:
                 logger.error(f"Error creating parameter UI for type '{selected_internal_type}': {e}.", exc_info=True)
                 error_label = ttk.Label(self.param_frame, text=f"Error loading settings UI: {selected_internal_type}", foreground="red")
                 error_label.grid(row=0, column=0, columnspan=2, sticky=tk.W)
                 self.param_widgets["error_label"] = [error_label]

        else:
             logger.warning(f"No parameter creation function defined for type: {selected_internal_type}")
             no_param_label = ttk.Label(self.param_frame, text="(No parameters required)")
             no_param_label.grid(row=0, column=0, columnspan=2, sticky=tk.W)
             self.param_widgets["no_param_label"] = [no_param_label]

        self.param_frame.grid_columnconfigure(1, weight=1) 

        initial_params_to_populate = {}
        if self.initial_condition_data and isinstance(self.initial_condition_data, dict) and \
           self.initial_condition_data.get("type") == selected_internal_type:
             initial_params_to_populate = self.initial_condition_data.get("params", {})


        logger.debug(f"Populating widgets for type: {selected_internal_type} with params: {initial_params_to_populate}")
        self._populate_params(initial_params_to_populate)

        self.update_idletasks() 


    def _populate_params(self, params_data: dict):
        """
        Populates the current parameter widgets with values from a params dictionary.

        Args:
            params_data (dict): Dictionary containing parameter values.
        """
        if not isinstance(params_data, dict):
             logger.warning(f"Invalid params_data type passed to _populate_params: {type(params_data)}. Using empty dict.")
             params_data = {}

        def set_entry(key: str, default_value=""):
            widget_info = self.param_widgets.get(key)

            if isinstance(widget_info, list) and len(widget_info) > 1 and isinstance(widget_info[1], ttk.Entry):
                entry_widget = widget_info[1]
                entry_widget.delete(0, tk.END)
                value_to_set = params_data.get(key, default_value)
               
                entry_widget.insert(0, str(value_to_set if value_to_set is not None else default_value))

        selected_display_key = self.type_var.get()
        selected_internal_type = RUN_CONDITION_DISPLAY_TO_INTERNAL_MAP.get(selected_display_key, RUN_CONDITION_TYPES_INTERNAL[0])

        if selected_internal_type == CountRunCondition.TYPE:
             set_entry("count", "1") 

        elif selected_internal_type == TimeRunCondition.TYPE:
             set_entry("duration", "60.0") 
        else: 
             pass


    def _add_param_entry(self, key: str, text: str, row: int, column: int = 0, columnspan: int = 2, sticky=tk.W, padx: int = 5, pady: int = 2):
        """Helper to create a label and entry, add to grid, and store."""
        label = ttk.Label(self.param_frame, text=text)
        label.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
        entry = ttk.Entry(self.param_frame, width=10) 
        entry.grid(row=row, column=column + 1, columnspan=columnspan - 1, padx=padx, pady=pady, sticky=tk.W) 
        self.param_widgets[key] = [label, entry]
        return entry

    def _create_infinite_params(self):
        """No parameters for InfiniteRunCondition."""
        logger.debug("Creating infinite run condition params UI (none).")
        no_param_label = ttk.Label(self.param_frame, text="(Runs until stopped manually)")
        no_param_label.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        self.param_widgets["no_param_label"] = [no_param_label]


    def _create_count_params(self):
        """Creates widgets for the 'count' run condition parameters."""
        logger.debug("Creating count run condition params UI.")
        self._add_param_entry("count", "Number of runs:", 0) 
        self.param_frame.grid_columnconfigure(1, weight=1) 


    def _create_time_params(self):
        """Creates widgets for the 'time' run condition parameters."""
        logger.debug("Creating time run condition params UI.")
        self._add_param_entry("duration", "Run duration (seconds):", 0) 
        self.param_frame.grid_columnconfigure(1, weight=1) 

    def get_settings(self) -> dict:
        """
        Collects the current run condition settings (type and parameters)
        from the displayed widgets and internal variables. Performs validation.

        Returns:
            dict: A dictionary representing the configured run condition settings,
                  suitable for create_job_run_condition(). Contains 'type' and 'params'.

        Raises:
            ValueError: If any input value is invalid (e.g., non-numeric, missing required).
        """
        selected_display_key = self.type_var.get()
        condition_type = RUN_CONDITION_DISPLAY_TO_INTERNAL_MAP.get(selected_display_key, RUN_CONDITION_TYPES_INTERNAL[0])

        params = {}

        def get_entry_value(key: str) -> str | None:
            widget_info = self.param_widgets.get(key)
            if isinstance(widget_info, list) and len(widget_info) > 1 and isinstance(widget_info[1], ttk.Entry):
                return widget_info[1].get()
            return None 


        try:
            if condition_type == InfiniteRunCondition.TYPE:
                pass  

            elif condition_type == CountRunCondition.TYPE:
                count_str = get_entry_value("count")
                try:
                     count_value = int(count_str) if count_str else 1 
                     params["count"] = max(1, count_value)
                except ValueError:
                     raise ValueError("Number of runs must be an integer.")

            elif condition_type == TimeRunCondition.TYPE:
                 duration_str = get_entry_value("duration")
                 try:
                     duration_value = float(duration_str) if duration_str else 0.0 
                     params["duration"] = max(0.1, duration_value) 
                 except ValueError:
                      raise ValueError("Run duration must be a number.")

            else: 
                 logger.warning(f"Unknown run condition type '{condition_type}' encountered in get_settings. Returning empty params.")
                 pass 


        except ValueError as e: 
             logger.error(f"Run condition settings validation failed for type '{condition_type}': {e}.")
             raise e
        except Exception as e: 
             logger.error(f"Unexpected error getting run condition settings for type '{condition_type}': {e}.", exc_info=True)
             raise ValueError(f"Unexpected error collecting settings: {e}")

        return {"type": condition_type, "params": params}


    def set_settings(self, condition_data: dict):
        """
        Updates the widgets in the frame to reflect the provided run condition settings data.
        Sets the combobox which triggers widget recreation and population,
        or manually repopulates if the type doesn't change.

        Args:
            condition_data (dict): A dictionary representing the run condition settings data
                                   (should contain 'type' and 'params').
        """
        if not isinstance(condition_data, dict):
            logger.error(f"Invalid condition_data format passed to JobRunConditionSettings.set_settings: {type(condition_data)}. Expected dict.")
            return 

        self.initial_condition_data = condition_data

        self._current_condition_obj = create_job_run_condition(condition_data)


        new_internal_type = self._current_condition_obj.type
        new_display_key = next((settings["display_name"] for type_key, settings in RUN_CONDITION_SETTINGS.items() if type_key == new_internal_type), RUN_CONDITION_TYPES_DISPLAY[0])


        current_display_key = self.type_var.get()

        if new_display_key != current_display_key:
             
             self.type_var.set(new_display_key)
        else:
             
             self._on_type_selected() 
