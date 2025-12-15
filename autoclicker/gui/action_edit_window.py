# gui/action_edit_window.py
import os
import tkinter as tk
from tkinter import ttk, messagebox
import logging
import copy
from typing import TYPE_CHECKING, Callable, Dict, Optional, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.job_manager import JobManager
    from utils.image_storage import ImageStorage
    from core.condition import Condition 

_SettingsFramesImported = False
try:
    from gui.action_settings import ActionSettings
    from gui.select_target_dialog import SelectTargetDialog
    _SettingsFramesImported = True
except ImportError:
    logger.error("ActionEditWindow: Could not import ActionSettings or SelectTargetDialog.")
    _SettingsFramesImported = False
    class ActionSettings(ttk.Frame):
        def __init__(self,m,a=None): super().__init__(m); ttk.Label(self,text="ActionSettings N/A").pack()
        def get_settings(self): return {"type":"click","params":{}, "condition_id": None, "next_action_index_if_condition_met":None, "next_action_index_if_condition_not_met":None}
        def set_settings(self,d): pass;
        def destroy(self): super().destroy()
    class SelectTargetDialog(tk.Toplevel):
        def __init__(self, parent, target_list, dialog_title, prompt):
            super().__init__(parent); ttk.Label(self, text="SelectTargetDialog N/A").pack()
            self.selected_target = target_list[0] if target_list else None
            self.after(10, self.destroy)

_ImageStorageImported = False
try:
    from utils.image_storage import ImageStorage
    _ImageStorageImported = True
except ImportError:
    ImageStorage = type("ImageStorage", (), {}) 
    _ImageStorageImported = False


class ActionEditWindow(tk.Toplevel):
    def __init__(self, master: tk.Tk | tk.Toplevel,
                 action_data: Dict[str, Any],
                 save_callback: Callable[[Dict[str, Any]], None],
                 job_manager: 'JobManager',
                 image_storage: Optional['ImageStorage'] = None): # type: ignore
        super().__init__(master)
        self.title("Edit Action")
        self.transient(master); self.grab_set(); self.resizable(True, False)

        if not _SettingsFramesImported or not job_manager:
            err_msg = "Cannot open Action Editor: "
            if not _SettingsFramesImported: err_msg += "UI components missing. "
            if not job_manager: err_msg += "JobManager not provided."
            messagebox.showerror("Error", err_msg, parent=master)
            self.after(10, self.destroy)
            return

        self.original_action_data = copy.deepcopy(action_data)
        self.save_callback = save_callback
        self.job_manager = job_manager
        self.image_storage = image_storage
        
        self._current_assigned_condition_id: Optional[str] = self.original_action_data.get("condition_id")
        
        logger.debug(f"ActionEditWindow init for type: {self.original_action_data.get('type', 'N/A')}, initial condition_id: {self._current_assigned_condition_id}")

        self.grid_columnconfigure(0, weight=1)

        action_settings_outer_frame = ttk.LabelFrame(self, text="Action Properties", padding="5")
        action_settings_outer_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="new")
        action_settings_outer_frame.grid_columnconfigure(0, weight=1)
        
        self.action_settings = ActionSettings(action_settings_outer_frame, action=self.original_action_data)
        self.action_settings.pack(fill="x", expand=True, padx=5, pady=5)

        condition_management_frame = ttk.LabelFrame(self, text="Action Condition (Optional - Shared)", padding="10")
        condition_management_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        condition_management_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(condition_management_frame, text="Assigned Condition:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.assigned_condition_name_var = tk.StringVar(value="(None)")
        assigned_condition_label = ttk.Label(condition_management_frame, textvariable=self.assigned_condition_name_var, relief="sunken", padding=(5,3), anchor="w")
        assigned_condition_label.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        condition_buttons_frame = ttk.Frame(condition_management_frame)
        condition_buttons_frame.grid(row=0, column=2, padx=(10,0), pady=5, sticky="e")

        self.assign_button = ttk.Button(condition_buttons_frame, text="Assign/Change...", command=self._assign_or_change_condition, width=16)
        self.assign_button.pack(side=tk.LEFT, padx=2)
        
        self.edit_assigned_button = ttk.Button(condition_buttons_frame, text="Edit Assigned...", command=self._edit_assigned_condition, width=15)
        self.edit_assigned_button.pack(side=tk.LEFT, padx=2)

        self.clear_button = ttk.Button(condition_buttons_frame, text="Clear", command=self._clear_assigned_condition, width=8)
        self.clear_button.pack(side=tk.LEFT, padx=2)

        bottom_button_frame = ttk.Frame(self)
        bottom_button_frame.grid(row=2, column=0, padx=10, pady=(10, 10), sticky="e")
        ttk.Button(bottom_button_frame, text="Save Action", command=self._save_action).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_button_frame, text="Cancel", command=self._cancel).pack(side=tk.LEFT, padx=5)

        self.grid_rowconfigure(0, weight=0) 
        self.grid_rowconfigure(1, weight=0) 
        self.grid_rowconfigure(2, weight=0) 

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._update_assigned_condition_display_and_buttons() 
        self.update_idletasks()
        
        min_w = max(self.winfo_reqwidth(), 550) 
        min_h = self.winfo_reqheight() + 20 
        self.minsize(min_w, min_h)
        self.geometry(f"{min_w}x{min_h}") 

        self.update_idletasks()
        parent_x = master.winfo_rootx(); parent_y = master.winfo_rooty()
        parent_w = master.winfo_width(); parent_h = master.winfo_height()
        win_w = self.winfo_width(); win_h = self.winfo_height()
        x = parent_x + (parent_w - win_w) // 2
        y = parent_y + (parent_h - win_h) // 2
        self.geometry(f"+{x}+{y}")

        logger.debug(f"ActionEditWindow UI built. Initial condition ID: {self._current_assigned_condition_id}")

    def _update_assigned_condition_display_and_buttons(self):
        display_text = "(No Condition Assigned)"
        can_edit = False
        if self._current_assigned_condition_id and self.job_manager:
            condition_obj = self.job_manager.get_shared_condition_by_id(self._current_assigned_condition_id)
            if condition_obj and hasattr(condition_obj, 'name') and hasattr(condition_obj, 'type') and hasattr(condition_obj, 'id'):
                display_text = f"{condition_obj.name} (Type: {condition_obj.type})" 
                can_edit = True
            else:
                display_text = f"(Error: Condition ID '{self._current_assigned_condition_id}' not found or invalid!)"
        
        self.assigned_condition_name_var.set(display_text)
        self.edit_assigned_button.config(state=tk.NORMAL if can_edit else tk.DISABLED)
        self.clear_button.config(state=tk.NORMAL if self._current_assigned_condition_id else tk.DISABLED)

    def _assign_or_change_condition(self):
        if not self.job_manager:
            messagebox.showerror("Error", "JobManager is not available to list conditions.", parent=self)
            return

        condition_display_map = self.job_manager.get_condition_display_map_for_ui()
        
        sorted_condition_items = sorted(condition_display_map.items(), key=lambda item: item[1].lower())

        target_list_for_dialog = [display_str for id_str, display_str in sorted_condition_items]

        id_list_for_mapping = [id_str for id_str, display_str in sorted_condition_items]

        special_option_create_display = "[Create New Shared Condition...]"
        special_option_create_id = "_CREATE_NEW_"

        target_list_for_dialog.insert(0, special_option_create_display)
        id_list_for_mapping.insert(0, special_option_create_id)

        dialog = SelectTargetDialog(
            self, 
            target_list=target_list_for_dialog,
            dialog_title="Assign Shared Condition",
            prompt="Select a shared condition:"
        )
        self.wait_window(dialog) 

        if dialog.selected_target: 
            try:
                selected_index = target_list_for_dialog.index(dialog.selected_target)
                selected_id_or_action_key = id_list_for_mapping[selected_index]

                if selected_id_or_action_key == special_option_create_id:
                    self._handle_create_new_shared_condition_flow()
                else: 
                    self._current_assigned_condition_id = selected_id_or_action_key
                    logger.info(f"ActionEditWindow: Assigned shared condition ID: {self._current_assigned_condition_id}")
                
                self._update_assigned_condition_display_and_buttons()
            except ValueError:
                logger.error(f"Selected target '{dialog.selected_target}' not found in dialog list during mapping.")
            except Exception as e:
                logger.error(f"Error processing selection from Assign Condition dialog: {e}", exc_info=True)
                messagebox.showerror("Error", f"Could not process selection: {e}", parent=self)


    def _handle_create_new_shared_condition_flow(self):
        logger.debug("ActionEditWindow: User selected to create a new shared condition.")
        try:
            from gui.shared_condition_edit_window import SharedConditionEditWindow 
        except ImportError:
            messagebox.showerror("Error", "Shared Condition editor UI is not available.", parent=self)
            return

        def assign_newly_created_condition(newly_created_condition: Optional['Condition']): # type: ignore
            if newly_created_condition and hasattr(newly_created_condition, 'id') and newly_created_condition.id:
                self._current_assigned_condition_id = newly_created_condition.id
                logger.info(f"ActionEditWindow: Newly created condition '{newly_created_condition.name}' (ID: {newly_created_condition.id}) assigned.")
            else:
                logger.warning("ActionEditWindow: New shared condition creation was cancelled or failed; no condition assigned.")
            self._update_assigned_condition_display_and_buttons()
            self.lift() 
            self.grab_set() 

        shared_cond_editor = SharedConditionEditWindow(
            self.winfo_toplevel(), 
            job_manager=self.job_manager,
            image_storage=self.image_storage,
            condition_to_edit_id=None,
            save_and_assign_callback=assign_newly_created_condition
        )

    def _edit_assigned_condition(self):
        if not self._current_assigned_condition_id:
            messagebox.showinfo("Info", "No condition is currently assigned to this action.", parent=self)
            return
        
        logger.debug(f"ActionEditWindow: Request to edit assigned condition ID: {self._current_assigned_condition_id}")
        try:
            from gui.shared_condition_edit_window import SharedConditionEditWindow
        except ImportError:
            messagebox.showerror("Error", "Shared Condition editor UI is not available.", parent=self)
            return

        def after_assigned_condition_edited(edited_condition: Optional['Condition']): # type: ignore
            if edited_condition:
                logger.info(f"ActionEditWindow: Assigned condition '{edited_condition.name}' (ID: {edited_condition.id}) was edited.")
            else:
                logger.warning("ActionEditWindow: Edit of assigned condition was cancelled or failed.")
            self._update_assigned_condition_display_and_buttons()
            self.lift()
            self.grab_set()

        shared_cond_editor = SharedConditionEditWindow(
            self.winfo_toplevel(),
            job_manager=self.job_manager,
            image_storage=self.image_storage,
            condition_to_edit_id=self._current_assigned_condition_id,
            save_and_assign_callback=after_assigned_condition_edited 
        )

    def _clear_assigned_condition(self):
        if self._current_assigned_condition_id:
            if messagebox.askyesno("Confirm Clear", "Are you sure you want to remove the assigned condition from this action?\n(The shared condition itself will not be deleted from the library).", parent=self, icon='question'):
                self._current_assigned_condition_id = None
                logger.info("ActionEditWindow: Assigned condition cleared for this action.")
                self._update_assigned_condition_display_and_buttons()
        else:
            messagebox.showinfo("Info", "No condition is currently assigned.", parent=self)

    def _save_action(self):
        logger.debug("ActionEditWindow: Save Action button clicked.")
        if not _SettingsFramesImported:
            messagebox.showerror("Error", "Cannot save: ActionSettings UI N/A.", parent=self); return
        try:
            action_properties_data = self.action_settings.get_settings()
            logger.debug(f"ActionEditWindow: Collected Action Properties: {action_properties_data}")

            final_action_data = copy.deepcopy(action_properties_data) 
            final_action_data["condition_id"] = self._current_assigned_condition_id 

            if "condition" in final_action_data:
                del final_action_data["condition"]

            logger.info(f"ActionEditWindow: Final Action data for save: {final_action_data}")

            if not final_action_data.get("type"):
                raise ValueError("Action type is missing from settings.")

            if self.save_callback:
                 try: self.save_callback(final_action_data)
                 except Exception as cb_ex:
                     logger.error(f"Error in save_callback from ActionEditWindow: {cb_ex}.", exc_info=True)
                     messagebox.showerror("Save Error", f"Error processing save: {cb_ex}", parent=self)
                     return 
            self.destroy()
        except ValueError as e:
            logger.error(f"Input validation failed during ActionEditWindow save: {e}.", exc_info=False)
            messagebox.showerror("Input Error", f"Invalid input: {e}", parent=self)
        except Exception as e:
            logger.error(f"Unexpected error during ActionEditWindow save_action: {e}.", exc_info=True)
            messagebox.showerror("Error", f"Failed to save action: {e}", parent=self)

    def _cancel(self):
        logger.debug("ActionEditWindow: Cancel clicked or window closed.")
        self.destroy()

    def destroy(self):
         logger.debug("ActionEditWindow: Destroying...")
         if hasattr(self, 'action_settings') and self.action_settings.winfo_exists():
              try: self.action_settings.destroy()
              except Exception as e: logger.warning(f"Error destroying action_settings: {e}")
         super().destroy()
