# gui/ai_brain_management_tab.py
import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import TYPE_CHECKING, Optional, List, Dict, Any, Callable
import copy # Thêm copy

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.job_manager import JobManager
    from core.condition import Condition, NoneCondition
    from core.trigger import Trigger

_GuiComponentsImported = False
try:
    from gui.select_target_dialog import SelectTargetDialog 
    _GuiComponentsImported = True
except ImportError:
    _GuiComponentsImported = False
    class SelectTargetDialog(tk.Toplevel): # type: ignore
         selected_target: Optional[str]
         def __init__(self, parent: tk.Misc, target_list: List[str], dialog_title:str="", prompt:str=""):
            super().__init__(parent); self.selected_target=None; self.after(10, self.destroy)

_CoreClassesImported = False 
try:
    from core.condition import Condition, NoneCondition 
    from core.trigger import Trigger
    _CoreClassesImported = True
except ImportError:
    _CoreClassesImported = False
    if not TYPE_CHECKING: 
        class Condition: id: str; name: str; type: str; is_monitored_by_ai_brain: bool = False # type: ignore
        class NoneCondition(Condition): TYPE="none" # type: ignore
        class Trigger: name: str; enabled:bool; conditions: List[Condition]; actions: List[Any]; condition_logic: str; is_ai_trigger: bool # type: ignore


class AIBrainManagementTab(ttk.Frame):
    job_manager: 'JobManager'
    trigger_edit_callback: Optional[Callable[[Optional[str]], None]]
    shared_condition_edit_callback: Optional[Callable[[Optional[str]], None]]

    monitored_conditions_tree: ttk.Treeview
    add_to_monitor_button: ttk.Button
    remove_from_monitor_button: ttk.Button
    edit_monitored_button: ttk.Button

    ai_triggers_tree: ttk.Treeview
    add_ai_trigger_button: ttk.Button
    edit_ai_trigger_button: ttk.Button
    delete_ai_trigger_button: ttk.Button
    enable_ai_trigger_button: ttk.Button

    _periodic_update_id: Optional[str] = None 

    def __init__(self, master: tk.Misc, job_manager: 'JobManager') -> None: # type: ignore
        super().__init__(master)
        self.job_manager = job_manager
        self.trigger_edit_callback = None
        self.shared_condition_edit_callback = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._setup_monitored_conditions_ui()
        self._setup_ai_triggers_ui()
        

    def set_callbacks(self, trigger_edit_cb: Callable[[Optional[str]], None],
                      shared_condition_edit_cb: Callable[[Optional[str]], None]) -> None:
        self.trigger_edit_callback = trigger_edit_cb
        self.shared_condition_edit_callback = shared_condition_edit_cb

    def _setup_monitored_conditions_ui(self) -> None:
        monitored_frame = ttk.LabelFrame(self, text="Monitored Conditions (AI Brain Inputs)", padding=10)
        monitored_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        monitored_frame.grid_rowconfigure(0, weight=1); monitored_frame.grid_columnconfigure(0, weight=1)
        tree_frame = ttk.Frame(monitored_frame); tree_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        tree_frame.grid_rowconfigure(0, weight=1); tree_frame.grid_columnconfigure(0, weight=1)
        cols = ("name", "id", "type", "current_state"); self.monitored_conditions_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="extended")
        self.monitored_conditions_tree.heading("name", text="Condition Name", anchor=tk.W); self.monitored_conditions_tree.heading("id", text="ID", anchor=tk.W)
        self.monitored_conditions_tree.heading("type", text="Type", anchor=tk.W); self.monitored_conditions_tree.heading("current_state", text="Current State (Live)", anchor=tk.CENTER)
        self.monitored_conditions_tree.column("name", width=250, stretch=tk.YES); self.monitored_conditions_tree.column("id", width=220, stretch=tk.NO)
        self.monitored_conditions_tree.column("type", width=150, stretch=tk.NO); self.monitored_conditions_tree.column("current_state", width=120, stretch=tk.NO, anchor=tk.CENTER)
        self.monitored_conditions_tree.grid(row=0, column=0, sticky="nsew"); mc_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.monitored_conditions_tree.yview)
        mc_scrollbar.grid(row=0, column=1, sticky="ns"); self.monitored_conditions_tree.configure(yscrollcommand=mc_scrollbar.set)
        self.monitored_conditions_tree.bind("<<TreeviewSelect>>", self._on_monitored_condition_select)
        self.monitored_conditions_tree.tag_configure('state_true', foreground='green', font=('TkDefaultFont', -12, 'bold')) # Kích thước font mặc định, -12 là size
        self.monitored_conditions_tree.tag_configure('state_false', foreground='red')


        button_frame = ttk.Frame(monitored_frame); button_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(5,0))
        self.add_to_monitor_button = ttk.Button(button_frame, text="Add Condition to Monitor...", command=self._add_condition_to_monitor); self.add_to_monitor_button.pack(side=tk.LEFT, padx=2)
        self.remove_from_monitor_button = ttk.Button(button_frame, text="Remove from Monitor", command=self._remove_selected_from_monitor, state=tk.DISABLED); self.remove_from_monitor_button.pack(side=tk.LEFT, padx=2)
        self.edit_monitored_button = ttk.Button(button_frame, text="Edit Shared Condition...", command=self._edit_selected_monitored_condition, state=tk.DISABLED); self.edit_monitored_button.pack(side=tk.LEFT, padx=2)

    def _setup_ai_triggers_ui(self) -> None:
        ai_triggers_frame = ttk.LabelFrame(self, text="AI Brain Triggers (Decision Logic)", padding=10)
        ai_triggers_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        ai_triggers_frame.grid_rowconfigure(0, weight=1); ai_triggers_frame.grid_columnconfigure(0, weight=1)
        tree_frame = ttk.Frame(ai_triggers_frame); tree_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        tree_frame.grid_rowconfigure(0, weight=1); tree_frame.grid_columnconfigure(0, weight=1)
        cols = ("name", "conditions_summary", "actions_summary", "enabled"); self.ai_triggers_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="extended")
        self.ai_triggers_tree.heading("name", text="AI Trigger Name", anchor=tk.W); self.ai_triggers_tree.heading("conditions_summary", text="Logic (Based on Monitored States)", anchor=tk.W)
        self.ai_triggers_tree.heading("actions_summary", text="Actions to Execute", anchor=tk.W); self.ai_triggers_tree.heading("enabled", text="Enabled", anchor=tk.CENTER)
        self.ai_triggers_tree.column("name", width=200, stretch=tk.YES); self.ai_triggers_tree.column("conditions_summary", width=300, stretch=tk.YES)
        self.ai_triggers_tree.column("actions_summary", width=250, stretch=tk.NO); self.ai_triggers_tree.column("enabled", width=80, stretch=tk.NO, anchor=tk.CENTER)
        self.ai_triggers_tree.tag_configure('disabled', foreground='grey')
        self.ai_triggers_tree.grid(row=0, column=0, sticky="nsew"); ait_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.ai_triggers_tree.yview)
        ait_scrollbar.grid(row=0, column=1, sticky="ns"); self.ai_triggers_tree.configure(yscrollcommand=ait_scrollbar.set)
        self.ai_triggers_tree.bind("<<TreeviewSelect>>", self._on_ai_trigger_select); self.ai_triggers_tree.bind("<Double-1>", lambda e: self._edit_selected_ai_trigger())

        button_frame = ttk.Frame(ai_triggers_frame); button_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(5,0))
        self.add_ai_trigger_button = ttk.Button(button_frame, text="Add AI Trigger", command=self._add_ai_trigger); self.add_ai_trigger_button.pack(side=tk.LEFT, padx=2)
        self.edit_ai_trigger_button = ttk.Button(button_frame, text="Edit AI Trigger", command=self._edit_selected_ai_trigger, state=tk.DISABLED); self.edit_ai_trigger_button.pack(side=tk.LEFT, padx=2)
        self.delete_ai_trigger_button = ttk.Button(button_frame, text="Delete AI Trigger", command=self._delete_selected_ai_trigger, state=tk.DISABLED); self.delete_ai_trigger_button.pack(side=tk.LEFT, padx=2)
        self.enable_ai_trigger_button = ttk.Button(button_frame, text="Enable/Disable", command=self._toggle_enable_selected_ai_trigger, state=tk.DISABLED); self.enable_ai_trigger_button.pack(side=tk.LEFT, padx=2)

    def refresh_ai_brain_view(self) -> None:
        self._populate_monitored_conditions_tree()
        self._populate_ai_triggers_tree()

    def _populate_monitored_conditions_tree(self) -> None:
        try:
            selected_iids = self.monitored_conditions_tree.selection()

            if not self.job_manager or not self.job_manager.condition_manager:
                for item in self.monitored_conditions_tree.get_children():
                    self.monitored_conditions_tree.delete(item)
                return

            condition_manager = self.job_manager.condition_manager
            all_shared: List[Condition] = []
            if hasattr(condition_manager, 'get_all_shared_conditions'):
                all_shared = condition_manager.get_all_shared_conditions()

            monitored_conditions: List[Condition] = []
            world_state: Dict[str, bool] = {}
            if self.job_manager.observer and hasattr(self.job_manager.observer, '_monitored_conditions_map'):
                with self.job_manager.observer.lock:
                    world_state = copy.deepcopy(self.job_manager.observer._monitored_conditions_map)

            for cond in all_shared:
                if hasattr(cond, 'is_monitored_by_ai_brain') and cond.is_monitored_by_ai_brain:
                    monitored_conditions.append(cond)
            
            monitored_conditions.sort(key=lambda c: c.name.lower() if hasattr(c, 'name') and c.name else "")
            
            current_tree_iids = set(self.monitored_conditions_tree.get_children())
            new_data_ids = {cond.id for cond in monitored_conditions if hasattr(cond, 'id')}

            ids_to_add = new_data_ids - current_tree_iids
            ids_to_remove = current_tree_iids - new_data_ids
            ids_to_update = current_tree_iids.intersection(new_data_ids)

            for iid_to_remove in ids_to_remove:
                if self.monitored_conditions_tree.exists(iid_to_remove):
                    self.monitored_conditions_tree.delete(iid_to_remove)

            for cond_obj in monitored_conditions:
                if hasattr(cond_obj, 'id') and cond_obj.id in ids_to_add:
                    current_state_val = world_state.get(cond_obj.id, False)
                    current_state_display = "TRUE" if current_state_val else "FALSE"
                    tag_to_apply = 'state_true' if current_state_val else 'state_false'
                    self.monitored_conditions_tree.insert("", tk.END, iid=cond_obj.id, values=(cond_obj.name, cond_obj.id, cond_obj.type, current_state_display), tags=(tag_to_apply,))

            for cond_obj in monitored_conditions:
                if hasattr(cond_obj, 'id') and cond_obj.id in ids_to_update:
                    current_state_val = world_state.get(cond_obj.id, False)
                    current_state_display = "TRUE" if current_state_val else "FALSE"
                    tag_to_apply = 'state_true' if current_state_val else 'state_false'
                    self.monitored_conditions_tree.set(cond_obj.id, column="current_state", value=current_state_display)
                    self.monitored_conditions_tree.item(cond_obj.id, tags=(tag_to_apply,))
            if selected_iids:
                valid_selection = [iid for iid in selected_iids if self.monitored_conditions_tree.exists(iid)]
                if valid_selection:
                    self.monitored_conditions_tree.selection_set(valid_selection)
            if not self.monitored_conditions_tree.get_children():
                self.monitored_conditions_tree.insert("", tk.END, values=("(No conditions monitored by AI Brain)", "", "", ""), tags=('disabled',))
        except tk.TclError:
            return
        self._update_monitored_conditions_buttons_state()

    def _populate_ai_triggers_tree(self) -> None:
        try:
            selected_iids = self.ai_triggers_tree.selection()

            if not self.job_manager:
                for item in self.ai_triggers_tree.get_children():
                    self.ai_triggers_tree.delete(item)
                return

            ai_triggers_list: List[Trigger] = []
            if self.job_manager.observer and hasattr(self.job_manager.observer, '_ai_triggers'):
                with self.job_manager.observer.lock:
                    ai_triggers_list = sorted([t for t in self.job_manager.observer._ai_triggers if hasattr(t, 'name')], key=lambda t: t.name.lower())
            elif hasattr(self.job_manager, 'triggers'):
                ai_triggers_list = sorted([t for t in self.job_manager.triggers.values() if hasattr(t, 'is_ai_trigger') and t.is_ai_trigger and hasattr(t, 'name')], key=lambda t: t.name.lower())

            current_tree_iids = set(self.ai_triggers_tree.get_children())
            new_data_ids = {trigger.name for trigger in ai_triggers_list if hasattr(trigger, 'name')}

            ids_to_add = new_data_ids - current_tree_iids
            ids_to_remove = current_tree_iids - new_data_ids
            ids_to_update = current_tree_iids.intersection(new_data_ids)

            for iid_to_remove in ids_to_remove:
                if self.ai_triggers_tree.exists(iid_to_remove):
                    self.ai_triggers_tree.delete(iid_to_remove)

            for trigger_obj in ai_triggers_list:
                if hasattr(trigger_obj, 'name') and trigger_obj.name in ids_to_add:
                    cond_summary = self._format_ai_trigger_condition_summary(trigger_obj)
                    action_summary = self._format_trigger_action_summary(trigger_obj)
                    enabled_text = "Yes" if trigger_obj.enabled else "No"
                    tags = [] if trigger_obj.enabled else ['disabled']
                    self.ai_triggers_tree.insert("", tk.END, iid=trigger_obj.name, values=(trigger_obj.name, cond_summary, action_summary, enabled_text), tags=tuple(tags))

            for trigger_obj in ai_triggers_list:
                if hasattr(trigger_obj, 'name') and trigger_obj.name in ids_to_update:
                    cond_summary = self._format_ai_trigger_condition_summary(trigger_obj)
                    action_summary = self._format_trigger_action_summary(trigger_obj)
                    enabled_text = "Yes" if trigger_obj.enabled else "No"
                    tags = [] if trigger_obj.enabled else ['disabled']

                    self.ai_triggers_tree.item(trigger_obj.name, 
                                            values=(trigger_obj.name, cond_summary, action_summary, enabled_text), 
                                            tags=tuple(tags))

            if selected_iids:
                valid_selection = [iid for iid in selected_iids if self.ai_triggers_tree.exists(iid)]
                if valid_selection:
                    self.ai_triggers_tree.selection_set(valid_selection)

            if not self.ai_triggers_tree.get_children():
                self.ai_triggers_tree.insert("", tk.END, values=("(No AI Brain Triggers defined)", "", "", ""), tags=('disabled',))
        except tk.TclError:
            return
        self._update_ai_triggers_buttons_state()

    def _format_ai_trigger_condition_summary(self, trigger: Trigger) -> str: # type: ignore
        if not hasattr(trigger, 'conditions') or not trigger.conditions: return "(Activates if AI Brain is On)"
        summary_parts: List[str] = []
        for cond in trigger.conditions:
            cond_display = "(Unknown Condition Ref)"
            if hasattr(cond, 'name') and hasattr(cond, 'type'):
                cond_disp_val = f"{cond.name} ({cond.type})"
                cond_display = cond_disp_val[:40] + "..." if len(cond_disp_val) > 40 else cond_disp_val
            summary_parts.append(cond_display)
        logic = f" {trigger.condition_logic} " if hasattr(trigger, 'condition_logic') and len(summary_parts) > 1 else ""
        return logic.join(summary_parts)

    def _format_trigger_action_summary(self, trigger: Trigger) -> str: # type: ignore
        if not hasattr(trigger, 'actions') or not trigger.actions: return "(No Action)"
        if len(trigger.actions) == 1: return str(trigger.actions[0])
        return f"{len(trigger.actions)} actions"

    def _on_monitored_condition_select(self, event: Optional[tk.Event] = None) -> None: self._update_monitored_conditions_buttons_state()
    def _update_monitored_conditions_buttons_state(self) -> None:
        selected_count = len(self.monitored_conditions_tree.selection())
        remove_state = tk.NORMAL if selected_count > 0 else tk.DISABLED; edit_state = tk.NORMAL if selected_count == 1 else tk.DISABLED
        if hasattr(self, 'remove_from_monitor_button'): self.remove_from_monitor_button.config(state=remove_state)
        if hasattr(self, 'edit_monitored_button'): self.edit_monitored_button.config(state=edit_state)

    def _add_condition_to_monitor(self) -> None:
        if not self.job_manager or not self.job_manager.condition_manager or not _GuiComponentsImported: return
        all_shared_map = self.job_manager.get_condition_display_map_for_ui()
        available_to_monitor: Dict[str, str] = {}
        for cond_id, display_str in all_shared_map.items():
            cond_obj = self.job_manager.get_shared_condition_by_id(cond_id)
            if cond_obj and hasattr(cond_obj, 'type') and cond_obj.type != getattr(NoneCondition, 'TYPE', 'none') and hasattr(cond_obj, 'is_monitored_by_ai_brain') and not cond_obj.is_monitored_by_ai_brain:
                available_to_monitor[cond_id] = display_str
        if not available_to_monitor: messagebox.showinfo("No Conditions", "All suitable Shared Conditions are already monitored or none exist.", parent=self); return
        sorted_display_names = sorted(list(available_to_monitor.values()), key=lambda s: s.lower())
        dialog = SelectTargetDialog(self.winfo_toplevel(), sorted_display_names, "Select Shared Condition to Monitor", "Choose condition:"); self.winfo_toplevel().wait_window(dialog) # type: ignore
        if dialog.selected_target:
            selected_display = dialog.selected_target; selected_id: Optional[str] = None
            for id_val, disp_name in available_to_monitor.items():
                if disp_name == selected_display: selected_id = id_val; break
            if selected_id:
                cond_to_update = self.job_manager.get_shared_condition_by_id(selected_id)
                if cond_to_update and hasattr(cond_to_update, 'is_monitored_by_ai_brain'):
                    cond_to_update.is_monitored_by_ai_brain = True
                    updated_data = cond_to_update.to_dict(); self.job_manager.update_shared_condition(selected_id, updated_data)
                    self.refresh_ai_brain_view()
                    if self.job_manager.observer and hasattr(self.job_manager.observer, '_refresh_monitored_conditions_list'): self.job_manager.observer._refresh_monitored_conditions_list()

    def _remove_selected_from_monitor(self) -> None:
        selected_ids = self.monitored_conditions_tree.selection()
        if not selected_ids: messagebox.showwarning("No Selection", "Please select condition(s) to remove from monitoring.", parent=self); return
        if not self.job_manager: return
        confirm_msg = f"Stop monitoring {len(selected_ids)} condition(s) with AI Brain?\n(Shared Conditions remain, only AI monitoring is removed)."
        if messagebox.askyesno("Confirm Remove Monitoring", confirm_msg, parent=self):
            for cond_id in selected_ids:
                cond_to_update = self.job_manager.get_shared_condition_by_id(cond_id)
                if cond_to_update and hasattr(cond_to_update, 'is_monitored_by_ai_brain') and cond_to_update.is_monitored_by_ai_brain:
                    cond_to_update.is_monitored_by_ai_brain = False
                    updated_data = cond_to_update.to_dict(); self.job_manager.update_shared_condition(cond_id, updated_data)
            self.refresh_ai_brain_view()
            if self.job_manager.observer and hasattr(self.job_manager.observer, '_refresh_monitored_conditions_list'): self.job_manager.observer._refresh_monitored_conditions_list()

    def _edit_selected_monitored_condition(self) -> None:
        selected_ids = self.monitored_conditions_tree.selection()
        if len(selected_ids) != 1: messagebox.showwarning("Selection Error", "Select one monitored condition to edit its definition.", parent=self); return
        condition_id_to_edit = selected_ids[0]
        if self.shared_condition_edit_callback: self.shared_condition_edit_callback(condition_id_to_edit)

    def _on_ai_trigger_select(self, event: Optional[tk.Event] = None) -> None: self._update_ai_triggers_buttons_state()
    def _update_ai_triggers_buttons_state(self) -> None:
        selected_count = len(self.ai_triggers_tree.selection()); edit_state = tk.NORMAL if selected_count == 1 else tk.DISABLED; delete_state = tk.NORMAL if selected_count > 0 else tk.DISABLED; enable_state = tk.NORMAL if selected_count > 0 else tk.DISABLED
        if hasattr(self, 'edit_ai_trigger_button'): self.edit_ai_trigger_button.config(state=edit_state)
        if hasattr(self, 'delete_ai_trigger_button'): self.delete_ai_trigger_button.config(state=delete_state)
        if hasattr(self, 'enable_ai_trigger_button'): self.enable_ai_trigger_button.config(state=enable_state)

    def _add_ai_trigger(self) -> None:
        if self.trigger_edit_callback: self.trigger_edit_callback(None) # TriggerEdit sẽ cần có logic để set is_ai_trigger=True mặc định
    def _edit_selected_ai_trigger(self) -> None:
        selected_names = self.ai_triggers_tree.selection()
        if len(selected_names) != 1: messagebox.showwarning("Selection Error", "Select one AI Trigger to edit.", parent=self); return
        if self.trigger_edit_callback: self.trigger_edit_callback(selected_names[0])
    def _delete_selected_ai_trigger(self) -> None:
        selected_names = self.ai_triggers_tree.selection()
        if not selected_names: messagebox.showwarning("No Selection", "Select AI Trigger(s) to delete.", parent=self); return
        if not self.job_manager: return
        confirm_msg = f"Delete {len(selected_names)} selected AI Trigger(s)?"
        if messagebox.askyesno("Confirm Delete", confirm_msg, icon='warning', parent=self):
            for trigger_name in selected_names:
                try: self.job_manager.delete_trigger(trigger_name)
                except Exception as e: messagebox.showerror("Delete Error", f"Could not delete AI Trigger '{trigger_name}': {e}", parent=self)
            self.refresh_ai_brain_view()
    def _toggle_enable_selected_ai_trigger(self) -> None:
        selected_names = self.ai_triggers_tree.selection()
        if not selected_names: messagebox.showwarning("No Selection", "Select AI Trigger(s) to enable/disable.", parent=self); return
        if not self.job_manager: return
        target_enable_state = True; all_currently_enabled = True
        for name in selected_names:
            trigger = self.job_manager.get_trigger(name)
            if trigger and hasattr(trigger, 'enabled') and not trigger.enabled: all_currently_enabled = False; break
        if all_currently_enabled: target_enable_state = False
        for trigger_name in selected_names:
            try: self.job_manager.enable_trigger(trigger_name, target_enable_state)
            except Exception as e: messagebox.showerror("Error", f"Could not toggle AI Trigger '{trigger_name}': {e}", parent=self)
        self.refresh_ai_brain_view()

    def _start_periodic_update(self) -> None:
        self.refresh_ai_brain_view() 
        if self.winfo_exists() and self.winfo_viewable(): 
             self._periodic_update_id = self.after(1000, self._start_periodic_update) 

    def _stop_periodic_update(self) -> None:
        if self._periodic_update_id:
            self.after_cancel(self._periodic_update_id)
            self._periodic_update_id = None

    def destroy(self) -> None:
        self._stop_periodic_update()
        super().destroy()
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
