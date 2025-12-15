# gui/fallback_sequence_editor_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
import logging
import copy
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from gui.action_edit_window import ActionEditWindow

try:
    from gui.action_edit_window import ActionEditWindow
    _ActionEditWindowImported = True
except ImportError:
    logger.error("FallbackSequenceEditorDialog: Could not import ActionEditWindow.")
    _ActionEditWindowImported = False
    class ActionEditWindow(tk.Toplevel):
        def __init__(self, master, action_data, save_callback, job_manager, image_storage):
            super().__init__(master)
            self.title("Dummy Action Editor")
            ttk.Label(self, text="ActionEditWindow (Dummy)").pack(padx=20, pady=20)
            dummy_saved_action = {"type": "wait", "params": {"duration": 1.0}}
            self.after(100, lambda: save_callback(dummy_saved_action))
            self.after(200, self.destroy)

try:
    from core.action import create_action, Action 
    _CoreActionImported = True
except ImportError:
    logger.error("FallbackSequenceEditorDialog: Could not import core.action.")
    _CoreActionImported = False
    class Action:
        def __init__(self, type, params, **kwargs): self.type = type; self.params = params
        def __str__(self): return f"DummyAction: {self.type}"
    def create_action(data): return Action(data.get("type", "dummy"), data.get("params", {}))


class FallbackSequenceEditorDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc,
                 initial_fallback_sequence: Optional[List[Dict[str, Any]]],
                 job_manager: Any,
                 image_storage: Any, 
                 parent_action_type: str, 
                 current_fallback_depth: int = 0, 
                 max_fallback_depth: int = 3):  

        super().__init__(master)
        self.transient(master)
        self.grab_set()
        self.title(f"Edit Fallback Sequence (Depth: {current_fallback_depth+1}/{max_fallback_depth})")
        self.resizable(True, False) 

        self.job_manager = job_manager
        self.image_storage = image_storage
        self.parent_action_type = parent_action_type
        self.current_fallback_depth = current_fallback_depth
        self.max_fallback_depth = max_fallback_depth

        self.fallback_sequence: List[Dict[str, Any]] = copy.deepcopy(initial_fallback_sequence or [])
        self.result_sequence: Optional[List[Dict[str, Any]]] = None 

        self._setup_ui()
        self._populate_action_list()
        self._update_buttons_state()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.update_idletasks()
        parent_x = master.winfo_rootx()
        parent_y = master.winfo_rooty()
        parent_w = master.winfo_width()
        parent_h = master.winfo_height()
        win_w = self.winfo_reqwidth()
        win_h = self.winfo_reqheight()
        min_w = max(450, win_w) 
        min_h = max(350, win_h)
        self.minsize(min_w, min_h)

        x = parent_x + (parent_w - min_w) // 2
        y = parent_y + (parent_h - min_h) // 2
        self.geometry(f"{min_w}x{min_h}+{x}+{y}")

        self.action_listbox.focus_set()


    def _setup_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(0, weight=0)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)  


        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="ns")

        self.add_button = ttk.Button(button_frame, text="Add", command=self._add_action, width=10)
        self.add_button.pack(fill=tk.X, pady=2)

        self.edit_button = ttk.Button(button_frame, text="Edit", command=self._edit_selected_action, width=10)
        self.edit_button.pack(fill=tk.X, pady=2)

        self.delete_button = ttk.Button(button_frame, text="Delete", command=self._delete_selected_action, width=10)
        self.delete_button.pack(fill=tk.X, pady=2)

        ttk.Separator(button_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        self.move_up_button = ttk.Button(button_frame, text="Move Up", command=self._move_action_up, width=10)
        self.move_up_button.pack(fill=tk.X, pady=2)

        self.move_down_button = ttk.Button(button_frame, text="Move Down", command=self._move_action_down, width=10)
        self.move_down_button.pack(fill=tk.X, pady=2)

        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=0, column=1, sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        self.action_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, exportselection=False, activestyle="dotbox")
        action_scrollbar_y = ttk.Scrollbar(list_frame, orient="vertical", command=self.action_listbox.yview)
        action_scrollbar_x = ttk.Scrollbar(list_frame, orient="horizontal", command=self.action_listbox.xview)
        self.action_listbox.configure(yscrollcommand=action_scrollbar_y.set, xscrollcommand=action_scrollbar_x.set)

        self.action_listbox.grid(row=0, column=0, sticky="nsew")
        action_scrollbar_y.grid(row=0, column=1, sticky="ns")
        action_scrollbar_x.grid(row=1, column=0, sticky="ew")

        self.action_listbox.bind('<<ListboxSelect>>', self._update_buttons_state)
        self.action_listbox.bind("<Double-1>", lambda e: self._edit_selected_action())

        dialog_button_frame = ttk.Frame(self, padding=(0, 10, 0, 0))
        dialog_button_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.ok_button = ttk.Button(dialog_button_frame, text="OK", command=self._on_ok)
        self.ok_button.pack(side=tk.RIGHT, padx=5)

        self.cancel_button = ttk.Button(dialog_button_frame, text="Cancel", command=self._on_cancel)
        self.cancel_button.pack(side=tk.RIGHT, padx=5)

    def _get_action_summary(self, action_data: Dict[str, Any], index: int) -> str:
        if not _CoreActionImported:
            return f"{index + 1}. Type: {action_data.get('type', 'N/A')}"
        try:
            temp_action_data = copy.deepcopy(action_data)
            temp_action_data.pop('fallback_action_sequence', None)
            action_obj = create_action(temp_action_data)

            summary_parts = []
            action_type_display = action_obj.type.replace("_", " ").title()
            summary = f"{index + 1}. {action_type_display}"

            params = action_obj.params if isinstance(action_obj.params, dict) else {}

            if action_obj.type == 'click':
                summary_parts.extend([f"X:{params.get('x','?')},Y:{params.get('y','?')}", f"{str(params.get('button','left')).capitalize()}", f"{params.get('click_type','single')}"])
            elif action_obj.type == 'wait':
                summary_parts.append(f"{params.get('duration','1.0')}s")

            if summary_parts:
                summary += f" ({', '.join(p for p in summary_parts if p)})"

            if action_obj.condition_id and self.job_manager:
                 cond_obj = self.job_manager.get_shared_condition_by_id(action_obj.condition_id)
                 if cond_obj:
                     summary += f" [If: {cond_obj.name[:15]}..]"
                 else:
                     summary += f" [If: ID '{action_obj.condition_id[:6]}..' (Not Found)]"

            if action_data.get("fallback_action_sequence") and self.current_fallback_depth + 1 < self.max_fallback_depth:
                summary += " [+Fallback]"

            return summary
        except Exception as e:
            logger.error(f"Error generating summary for action data {action_data}: {e}")
            return f"{index + 1}. Error Displaying Action"

    def _populate_action_list(self):
        self.action_listbox.delete(0, tk.END)
        if not self.fallback_sequence:
            self.action_listbox.insert(tk.END, "(No fallback actions defined)")
            self.action_listbox.itemconfig(0, {'fg': 'grey'})
        else:
            for i, action_data in enumerate(self.fallback_sequence):
                summary = self._get_action_summary(action_data, i)
                self.action_listbox.insert(tk.END, summary)
        self._update_buttons_state()

    def _update_buttons_state(self, event=None):
        selected_indices = self.action_listbox.curselection()
        num_selected = len(selected_indices)
        list_size = self.action_listbox.size()
        has_items = list_size > 0 and self.action_listbox.get(0) != "(No fallback actions defined)"

        can_edit = num_selected == 1 and has_items
        can_delete = num_selected > 0 and has_items
        can_move_up = num_selected == 1 and has_items and selected_indices[0] > 0
        can_move_down = num_selected == 1 and has_items and selected_indices[0] < list_size - 1

        self.edit_button.config(state=tk.NORMAL if can_edit else tk.DISABLED)
        self.delete_button.config(state=tk.NORMAL if can_delete else tk.DISABLED)
        self.move_up_button.config(state=tk.NORMAL if can_move_up else tk.DISABLED)
        self.move_down_button.config(state=tk.NORMAL if can_move_down else tk.DISABLED)
        self.add_button.config(state=tk.NORMAL) 

    def _add_action(self):
        if not _ActionEditWindowImported:
            messagebox.showerror("Error", "Action Editor UI is not available.", parent=self)
            return

        default_action_data = {"type": "click", "params": {}} 
        def on_action_edit_closed(new_action_data: Optional[Dict[str,Any]]):
            if new_action_data:
                self._save_newly_added_action(new_action_data)
            self.lift() 
            self.grab_set() 
            self.action_listbox.focus_set()

        ActionEditWindow(
            self, 
            action_data=default_action_data,
            save_callback=on_action_edit_closed,
            job_manager=self.job_manager,
            image_storage=self.image_storage
        )

    def _save_newly_added_action(self, new_action_data: Dict[str, Any]):
        self.fallback_sequence.append(new_action_data)
        self._populate_action_list()
        if self.action_listbox.size() > 0 and self.action_listbox.get(0) != "(No fallback actions defined)":
            last_index = self.action_listbox.size() - 1
            self.action_listbox.selection_clear(0, tk.END)
            self.action_listbox.selection_set(last_index)
            self.action_listbox.activate(last_index)
            self.action_listbox.see(last_index)
        self._update_buttons_state()

    def _edit_selected_action(self):
        selected_indices = self.action_listbox.curselection()
        if not selected_indices or len(selected_indices) != 1:
            messagebox.showwarning("Selection Error", "Please select exactly one action to edit.", parent=self)
            return
        idx = selected_indices[0]

        if not (0 <= idx < len(self.fallback_sequence)):
            logger.error(f"Edit fallback: Index {idx} out of bounds for sequence of length {len(self.fallback_sequence)}")
            self._populate_action_list() 
            return

        if not _ActionEditWindowImported:
            messagebox.showerror("Error", "Action Editor UI is not available.", parent=self)
            return

        action_data_to_edit = self.fallback_sequence[idx]

        def on_action_edit_closed(updated_action_data: Optional[Dict[str,Any]]):
            if updated_action_data:
                self._save_edited_existing_action(idx, updated_action_data)
            self.lift()
            self.grab_set()
            self.action_listbox.focus_set()

        ActionEditWindow(
            self,
            action_data=action_data_to_edit,
            save_callback=on_action_edit_closed,
            job_manager=self.job_manager,
            image_storage=self.image_storage
        )

    def _save_edited_existing_action(self, index: int, updated_action_data: Dict[str, Any]):
        if 0 <= index < len(self.fallback_sequence):
            self.fallback_sequence[index] = updated_action_data
            self._populate_action_list()
            self.action_listbox.selection_set(index)
            self.action_listbox.activate(index)
            self.action_listbox.see(index)
            self._update_buttons_state()
        else:
            logger.error(f"Save edited fallback: Index {index} out of bounds.")

    def _delete_selected_action(self):
        selected_indices = self.action_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select action(s) to delete.", parent=self)
            return

        indices_to_delete = sorted(selected_indices, reverse=True)

        confirm_msg = f"Delete {len(indices_to_delete)} selected fallback action(s)?"
        if messagebox.askyesno("Confirm Deletion", confirm_msg, icon='warning', parent=self):
            for idx in indices_to_delete:
                if 0 <= idx < len(self.fallback_sequence):
                    del self.fallback_sequence[idx]
            self._populate_action_list()
            if self.fallback_sequence:
                new_selection_idx = min(indices_to_delete[0] if indices_to_delete else 0, len(self.fallback_sequence) - 1)
                if new_selection_idx >= 0:
                    self.action_listbox.selection_set(new_selection_idx)
                    self.action_listbox.activate(new_selection_idx)
            self._update_buttons_state()

    def _move_action_up(self):
        selected_indices = self.action_listbox.curselection()
        if not selected_indices or len(selected_indices) != 1:
            return 
        idx = selected_indices[0]
        if idx > 0 and idx < len(self.fallback_sequence):
            self.fallback_sequence[idx], self.fallback_sequence[idx-1] = self.fallback_sequence[idx-1], self.fallback_sequence[idx]
            self._populate_action_list()
            self.action_listbox.selection_set(idx-1)
            self.action_listbox.activate(idx-1)
            self.action_listbox.see(idx-1)

    def _move_action_down(self):
        selected_indices = self.action_listbox.curselection()
        if not selected_indices or len(selected_indices) != 1:
            return
        idx = selected_indices[0]
        if idx < len(self.fallback_sequence) - 1 and idx >= 0:
            self.fallback_sequence[idx], self.fallback_sequence[idx+1] = self.fallback_sequence[idx+1], self.fallback_sequence[idx]
            self._populate_action_list()
            self.action_listbox.selection_set(idx+1)
            self.action_listbox.activate(idx+1)
            self.action_listbox.see(idx+1)

    def _on_ok(self):
        if self.current_fallback_depth + 1 >= self.max_fallback_depth:
            for action_data in self.fallback_sequence:
                if action_data.get("fallback_action_sequence"):
                    messagebox.showwarning("Depth Limit",
                                           f"One or more actions in this fallback sequence still define their own fallbacks. "
                                           f"These deeper fallbacks will be ignored as the maximum depth ({self.max_fallback_depth}) is reached.",
                                           parent=self)
                    break 

        self.result_sequence = self.fallback_sequence
        self.destroy()

    def _on_cancel(self):
        self.result_sequence = None
        self.destroy()
