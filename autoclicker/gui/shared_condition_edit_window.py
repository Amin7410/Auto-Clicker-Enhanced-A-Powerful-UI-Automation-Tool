# gui/shared_condition_edit_window.py
import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import TYPE_CHECKING, Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)

_GuiComponentsImported = False
try:
    from gui.condition_settings import ConditionSettings
    _GuiComponentsImported = True
except ImportError as e:
    _GuiComponentsImported = False
    class ConditionSettings(ttk.Frame):
        def __init__(self,m: tk.Misc ,condition_data:Optional[Dict[str,Any]]=None,image_storage:Any=None, exclude_types:Optional[list[str]]=None):super().__init__(m)
        def get_settings(self) -> Dict[str,Any]:return {"type":"none","params":{}}
        def set_settings(self,d: Dict[str,Any]) -> None: pass
        def destroy(self) -> None: super().destroy()

_CoreImported = False
try:
    from core.condition import create_condition, Condition, NoneCondition 
    _CoreImported = True
except ImportError:
    _CoreImported = False
    class Condition:
        id:Optional[str]; name:Optional[str]; type:str; params:Dict[str,Any]; is_monitored_by_ai_brain:bool
        def __init__(self, type:str, params:Dict[str,Any], id:Optional[str]=None, name:Optional[str]=None, is_monitored_by_ai_brain:bool=False): self.id=id; self.name=name; self.type=type; self.params=params; self.is_monitored_by_ai_brain=is_monitored_by_ai_brain
        def to_dict(self) -> Dict[str,Any]: return {"id":self.id, "name":self.name, "type":self.type, "params":self.params, "is_monitored_by_ai_brain":self.is_monitored_by_ai_brain}
    class NoneCondition(Condition): TYPE="none" # type: ignore
    def create_condition(data:Dict[str,Any]) -> Condition: return Condition(str(data.get("type")), data.get("params",{}), data.get("id"), data.get("name"), bool(data.get("is_monitored_by_ai_brain",False)))


if TYPE_CHECKING:
    from core.job_manager import JobManager
    from utils.image_storage import ImageStorage


class SharedConditionEditWindow(tk.Toplevel):
    job_manager: 'JobManager'
    image_storage: Optional['ImageStorage']
    condition_to_edit_id: Optional[str]
    on_close_callback: Optional[Callable[[], None]]
    save_and_assign_callback: Optional[Callable[[Optional[Condition]], None]]
    initial_condition_data: Dict[str, Any]
    _current_condition_name: str
    name_entry: ttk.Entry
    is_monitored_var: tk.BooleanVar 
    condition_settings: ConditionSettings
    save_button: ttk.Button; cancel_button: ttk.Button

    def __init__(self, master: tk.Tk | tk.Toplevel,
                 job_manager: 'JobManager', # type: ignore
                 image_storage: Optional['ImageStorage'], # type: ignore
                 condition_to_edit_id: Optional[str] = None,
                 on_close_callback: Optional[Callable[[], None]] = None,
                 save_and_assign_callback: Optional[Callable[[Optional[Condition]], None]] = None) -> None:
        super().__init__(master)

        if not _GuiComponentsImported or not _CoreImported or not job_manager:
            if hasattr(self, 'after'): self.after(10, self.destroy)
            return

        self.job_manager = job_manager; self.image_storage = image_storage
        self.condition_to_edit_id = condition_to_edit_id
        self.on_close_callback = on_close_callback; self.save_and_assign_callback = save_and_assign_callback
        self.initial_condition_data = {"type": "none", "params": {}, "name": "", "is_monitored_by_ai_brain": False}
        self._current_condition_name = ""

        if self.condition_to_edit_id:
            condition_obj = self.job_manager.get_shared_condition_by_id(self.condition_to_edit_id)
            if condition_obj and hasattr(condition_obj, 'to_dict'):
                self.initial_condition_data = condition_obj.to_dict()
                self._current_condition_name = condition_obj.name if hasattr(condition_obj,'name') else ""
                self.title(f"Edit Shared Condition: {self._current_condition_name}")
            else:
                messagebox.showerror("Error", f"Could not find Shared Condition with ID: {self.condition_to_edit_id}", parent=master)
                if hasattr(self, 'after'): self.after(10, self.destroy)
                return
        else:
            self.title("Create New Shared Condition")
        
        self.transient(master); self.grab_set(); self.resizable(True, True); self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._setup_ui()

        self.condition_settings.set_settings(self.initial_condition_data)
        self.name_entry.delete(0, tk.END) 
        self.name_entry.insert(0, self._current_condition_name if self._current_condition_name else self.initial_condition_data.get("name", ""))
        self.is_monitored_var.set(bool(self.initial_condition_data.get("is_monitored_by_ai_brain", False)))


        self.update_idletasks(); min_w = max(self.winfo_reqwidth(), 550); min_h = max(self.winfo_reqheight(), 600); self.minsize(min_w, min_h)
        if hasattr(master, 'winfo_exists') and master.winfo_exists():
            master.update_idletasks(); master_x = master.winfo_rootx(); master_y = master.winfo_rooty(); master_w = master.winfo_width(); master_h = master.winfo_height()
            win_w = self.winfo_width(); win_h = self.winfo_height(); x = master_x + (master_w - win_w) // 2; y = master_y + (master_h - win_h) // 2; self.geometry(f"+{x}+{y}")
        if hasattr(self, 'name_entry'): self.name_entry.focus_set()


    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        name_frame = ttk.LabelFrame(self, text="Condition Identification", padding="10"); name_frame.grid(row=0, column=0, padx=10, pady=(10,5), sticky="ew"); name_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(name_frame, text="Condition Name:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.name_entry = ttk.Entry(name_frame, width=50); self.name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        if self.condition_to_edit_id:
            ttk.Label(name_frame, text="ID (fixed):").grid(row=1, column=0, padx=5, pady=2, sticky="w")
            id_label = ttk.Label(name_frame, text=self.condition_to_edit_id); id_label.grid(row=1, column=1, padx=5, pady=2, sticky="w")

        self.is_monitored_var = tk.BooleanVar(value=bool(self.initial_condition_data.get("is_monitored_by_ai_brain", False)))
        is_monitored_check = ttk.Checkbutton(name_frame, text="Monitor this condition with AI Brain", variable=self.is_monitored_var)
    
        checkbox_row = 2 if self.condition_to_edit_id else 1
        is_monitored_check.grid(row=checkbox_row, column=0, columnspan=2, padx=5, pady=(5,0), sticky="w")

        self.condition_settings = ConditionSettings(self, condition_data=self.initial_condition_data, image_storage=self.image_storage, exclude_types=[NoneCondition.TYPE]) # type: ignore
        self.condition_settings.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        button_frame = ttk.Frame(self); button_frame.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="e")
        save_text = "Save Condition"
        if self.save_and_assign_callback and not self.condition_to_edit_id: save_text = "Create & Assign Condition"
        elif self.save_and_assign_callback and self.condition_to_edit_id: save_text = "Save & Update Assignment"
        self.save_button = ttk.Button(button_frame, text=save_text, command=self._on_save); self.save_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self._on_cancel); self.cancel_button.pack(side=tk.LEFT, padx=5)

    def _on_save(self) -> None:
        entered_name = self.name_entry.get().strip()
        if not entered_name:
            messagebox.showerror("Input Error", "Condition Name cannot be empty.", parent=self)
            if hasattr(self, 'name_entry'): self.name_entry.focus_set()
            return
        try:
            condition_type_and_params = self.condition_settings.get_settings()
            if not condition_type_and_params or "type" not in condition_type_and_params:
                raise ValueError("Could not retrieve valid settings from ConditionSettings.")

            final_condition_data: Dict[str, Any] = {
                "id": self.condition_to_edit_id, "name": entered_name,
                "type": condition_type_and_params["type"],
                "params": condition_type_and_params.get("params", {}),
                "is_monitored_by_ai_brain": self.is_monitored_var.get() 
            }
            
            saved_condition_obj: Optional[Condition] = None

            if self.condition_to_edit_id:
                if self.job_manager.update_shared_condition(self.condition_to_edit_id, final_condition_data): # type: ignore
                    saved_condition_obj = self.job_manager.get_shared_condition_by_id(self.condition_to_edit_id) # type: ignore
                else:
                    messagebox.showerror("Save Error", "Failed to update shared condition. Check logs.", parent=self)
                    return
            else:
                new_condition_obj = create_condition(final_condition_data)
                if not new_condition_obj: raise ValueError("Failed to create new Condition object from data.")
                if self.job_manager.add_shared_condition(new_condition_obj): # type: ignore
                    saved_condition_obj = new_condition_obj
                else:
                    messagebox.showerror("Save Error", "Failed to add new shared condition. Check logs.", parent=self)
                    return
            
            if self.save_and_assign_callback: self.save_and_assign_callback(saved_condition_obj)
            elif self.on_close_callback: self.on_close_callback()
            self.destroy()
        except ValueError as ve:
            messagebox.showerror("Input Error", str(ve), parent=self); self.lift()
        except Exception as e:
            messagebox.showerror("Save Error", f"An unexpected error occurred: {e}", parent=self); self.lift()

    def _on_cancel(self) -> None:
        if self.save_and_assign_callback: self.save_and_assign_callback(None)
        elif self.on_close_callback: self.on_close_callback()
        self.destroy()

    def destroy(self) -> None:
        name_for_log = "N/A"
        if hasattr(self, 'name_entry') and self.name_entry.winfo_exists(): name_for_log = self.name_entry.get()
        
        if hasattr(self, 'condition_settings') and self.condition_settings.winfo_exists():
            try: self.condition_settings.destroy()
            except Exception: pass
        super().destroy()
