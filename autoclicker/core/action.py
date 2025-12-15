# core/action.py
import time
import logging
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List # Thêm List

logger = logging.getLogger(__name__)

_BridgeImported = False
try:
    from python_csharp_bridge import os_interaction_client
    _BridgeImported = True
except ImportError:
    logger.error("Could not import os_interaction_client from python_csharp_bridge.py. Action execution will fail.")
    class DummyOSInteractionClient:
         def simulate_click(self, *args: Any, **kwargs: Any) -> None: logger.error("DummyOSInteractionClient: simulate_click called, bridge not imported.")
         def simulate_move_mouse(self, *args: Any, **kwargs: Any) -> None: logger.error("DummyOSInteractionClient: simulate_move_mouse called, bridge not imported.")
         def simulate_key_press(self, *args: Any, **kwargs: Any) -> None: logger.error("DummyOSInteractionClient: simulate_key_press called, bridge not imported.")
         def simulate_key_down(self, *args: Any, **kwargs: Any) -> None: logger.error("DummyOSInteractionClient: simulate_key_down called, bridge not imported.")
         def simulate_key_up(self, *args: Any, **kwargs: Any) -> None: logger.error("DummyOSInteractionClient: simulate_key_up called, bridge not imported.")
         def simulate_text_entry(self, *args: Any, **kwargs: Any) -> None: logger.error("DummyOSInteractionClient: simulate_text_entry called, bridge not imported.")
         def simulate_modified_key_stroke(self, *args: Any, **kwargs: Any) -> None: logger.error("DummyOSInteractionClient: simulate_modified_key_stroke called, bridge not imported.")
         def simulate_drag(self, *args: Any, **kwargs: Any) -> None: logger.error("DummyOSInteractionClient: simulate_drag called, bridge not imported.")
    os_interaction_client = DummyOSInteractionClient()

_ConditionClassImported = False
try:
    from core.condition import Condition
    _ConditionClassImported = True
except ImportError:
     logger.error("Could not import Condition class from core/condition.py. Action initialization might be limited.")
     class Condition:
          id: Optional[str]
          name: Optional[str]
          type: str
          params: Dict[str, Any]
          def __init__(self, type: str ="unknown_dummy", params: Optional[Dict[str,Any]] = None, id: Optional[str] = None, name: Optional[str] = None, **kwargs: Any) -> None:
              self.type="unknown_dummy"; self.params={}; self.id=None; self.name="DummyCond"
          def check(self, **context: Any) -> bool: return False
     _ConditionClassImported = False


class Action(ABC):
    def __init__(self, type: str, params: Optional[Dict[str, Any]] = None,
                 condition_id: Optional[str] = None,
                 next_action_index_if_condition_met: Optional[int] = None,
                 next_action_index_if_condition_not_met: Optional[int] = None,
                 is_absolute: bool = False,
                 fallback_action_sequence: Optional[List[Dict[str, Any]]] = None): # Thêm fallback_action_sequence
        if not isinstance(type, str) or not type:
             raise ValueError("Action type must be a non-empty string.")
        self.type: str = type
        if params is None:
            self.params: Dict[str, Any] = {}
        elif isinstance(params, dict):
            self.params = params
        else:
            logger.warning(f"Params for action type '{self.type}' is not a dict ({type(params)}). Using empty dict.")
            self.params = {}
        self.condition_id: Optional[str] = None
        if isinstance(condition_id, str) and condition_id.strip():
            self.condition_id = condition_id.strip()
        self._condition_instance_cache: Optional[Condition] = None
        self.next_action_index_if_condition_met: Optional[int] = None
        try:
            next_if_met_str = str(next_action_index_if_condition_met) if next_action_index_if_condition_met is not None else ""
            next_if_met = int(next_if_met_str) if next_if_met_str.strip() else None
            if isinstance(next_if_met, int):
                self.next_action_index_if_condition_met = max(0, next_if_met)
        except (ValueError, TypeError):
            logger.warning(f"Invalid data for next_action_index_if_condition_met: '{next_action_index_if_condition_met}'. Using None.")
            self.next_action_index_if_condition_met = None
        self.next_action_index_if_condition_not_met: Optional[int] = None
        try:
            next_if_not_met_str = str(next_action_index_if_condition_not_met) if next_action_index_if_condition_not_met is not None else ""
            next_if_not_met = int(next_if_not_met_str) if next_if_not_met_str.strip() else None
            if isinstance(next_if_not_met, int):
                self.next_action_index_if_condition_not_met = max(0, next_if_not_met)
        except (ValueError, TypeError):
            logger.warning(f"Invalid data for next_action_index_if_condition_not_met: '{next_action_index_if_condition_not_met}'. Using None.")
            self.next_action_index_if_condition_not_met = None
        self.is_absolute: bool = bool(is_absolute)
        self.fallback_action_sequence: Optional[List[Dict[str, Any]]] = None
        if isinstance(fallback_action_sequence, list):
            valid_fallback_actions = []
            for i, action_data in enumerate(fallback_action_sequence):
                if isinstance(action_data, dict) and action_data.get("type"):
                    valid_fallback_actions.append(action_data)
                else:
                    logger.warning(f"Invalid fallback action data at index {i} for action type '{self.type}'. Skipping.")
            if valid_fallback_actions:
                self.fallback_action_sequence = valid_fallback_actions
        elif fallback_action_sequence is not None:
            logger.warning(f"fallback_action_sequence for action type '{self.type}' is not a list. Using None.")
        self._is_valid: bool = True
        self._validation_error: Optional[str] = None

    def execute(self, job_stop_event: Optional[threading.Event] = None,
                condition_manager: Optional[Any] = None, **context: Any) -> bool:
        condition_result: bool = True

        if self.condition_id:
            if not condition_manager or not hasattr(condition_manager, 'get_shared_condition_by_id'):
                logger.error(f"Action '{self.type}' has condition_id '{self.condition_id}' but no valid condition_manager provided. Skipping condition check, assuming NOT met.")
                condition_result = False
            else:
                actual_condition_to_check: Optional[Condition] = None
                if self._condition_instance_cache and self._condition_instance_cache.id == self.condition_id:
                    actual_condition_to_check = self._condition_instance_cache
                else:
                    actual_condition_to_check = condition_manager.get_shared_condition_by_id(self.condition_id)
                    self._condition_instance_cache = actual_condition_to_check
                if actual_condition_to_check:
                    if not _ConditionClassImported or not isinstance(actual_condition_to_check, Condition):
                        logger.error(f"Condition manager returned non-Condition object for ID '{self.condition_id}'. Type: {type(actual_condition_to_check)}. Assuming condition NOT met.")
                        condition_result = False
                    else:
                        try:
                            logger.debug(f"Action '{self.type}' checking shared condition '{actual_condition_to_check.name}' (ID: {self.condition_id}, Type: {actual_condition_to_check.type}).")
                            condition_result = actual_condition_to_check.check(**context)
                            logger.debug(f"Condition '{actual_condition_to_check.name}' result: {condition_result}")
                        except Exception as e:
                            logger.error(f"Error checking shared condition '{actual_condition_to_check.name}' (ID: {self.condition_id}) for action '{self.type}': {e}", exc_info=True)
                            condition_result = False
                else:
                    logger.warning(f"Action '{self.type}' has condition_id '{self.condition_id}', but condition was not found by manager. Assuming condition NOT met.")
                    condition_result = False
        else:
            pass
        if not condition_result:
            logger.debug(f"Action '{self.type}' core logic SKIPPED: Condition (ID: {self.condition_id or 'N/A'}) not met or error in check.")
            return condition_result 
        if job_stop_event and job_stop_event.is_set():
            logger.info(f"Action '{self.type}' aborted before core execution: Job stop event set.")
            return condition_result 
        logger.debug(f"Action '{self.type}' executing core logic with params: {self.params}")
        try:
             self._execute_core_logic(job_stop_event, **context)
        except Exception as e:
             logger.error(f"Error executing core logic for action '{self.type}': {e}", exc_info=True)
             raise e
        if job_stop_event and job_stop_event.is_set():
             logger.info(f"Action '{self.type}' core logic completed, but Job stop event was set during execution.")
        return condition_result

    @abstractmethod
    def _execute_core_logic(self, job_stop_event: Optional[threading.Event] = None, **context: Any) -> None:
        if not self._is_valid:
             raise ValueError(f"Action '{self.type}' is invalid: {self._validation_error or 'Unknown validation error'}")
        if not _BridgeImported:
             raise RuntimeError("OS Interaction Bridge not imported, cannot execute action.")

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "type": self.type,
            "params": self.params,
            "condition_id": self.condition_id,
            "next_action_index_if_condition_met": self.next_action_index_if_condition_met,
            "next_action_index_if_condition_not_met": self.next_action_index_if_condition_not_met,
            "is_absolute": self.is_absolute,
            "fallback_action_sequence": self.fallback_action_sequence 
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Action':
        if not isinstance(data, dict):
            raise ValueError("Action data for from_dict must be a dictionary.")

        action_type = data.get("type")
        params = data.get("params", {})
        condition_id_data = data.get("condition_id")
        next_if_met_data = data.get("next_action_index_if_condition_met")
        next_if_not_met_data = data.get("next_action_index_if_condition_not_met")
        is_absolute_data = data.get("is_absolute", False)
        fallback_action_sequence_data = data.get("fallback_action_sequence") 

        if not isinstance(action_type, str) or not action_type:
             raise ValueError("Action data must contain a non-empty 'type' string.")
        if not isinstance(params, dict):
             params = {}

        condition_id_str: Optional[str] = None
        if isinstance(condition_id_data, str) and condition_id_data.strip():
            condition_id_str = condition_id_data.strip()

        def safe_int_or_none(value: Any) -> Optional[int]:
             try:
                  val_str = str(value) if value is not None else ""
                  int_val = int(val_str) if val_str.strip() else None
                  return max(0, int_val) if isinstance(int_val, int) else None
             except (ValueError, TypeError):
                 return None

        next_if_met = safe_int_or_none(next_if_met_data)
        next_if_not_met = safe_int_or_none(next_if_not_met_data)

        actual_fallback_sequence: Optional[List[Dict[str, Any]]] = None
        if isinstance(fallback_action_sequence_data, list):
            valid_fallbacks = []
            for item_data in fallback_action_sequence_data:
                if isinstance(item_data, dict):
                    valid_fallbacks.append(item_data)
            if valid_fallbacks:
                actual_fallback_sequence = valid_fallbacks
        elif fallback_action_sequence_data is not None:
             logger.warning(f"Fallback sequence for action type '{action_type}' is not a list. Ignoring.")


        action_class_map: Dict[str, type['Action']] = {
            ClickAction.TYPE: ClickAction,
            PressKeyAction.TYPE: PressKeyAction,
            MoveMouseAction.TYPE: MoveMouseAction,
            DragAction.TYPE: DragAction,
            WaitAction.TYPE: WaitAction,
            KeyDownAction.TYPE: KeyDownAction,
            KeyUpAction.TYPE: KeyUpAction,
            TextEntryAction.TYPE: TextEntryAction,
            ModifiedKeyStrokeAction.TYPE: ModifiedKeyStrokeAction
        }

        action_class = action_class_map.get(action_type)

        if action_class:
            try:
                return action_class(
                    params=params,
                    condition_id=condition_id_str,
                    next_action_index_if_condition_met=next_if_met,
                    next_action_index_if_condition_not_met=next_if_not_met,
                    is_absolute=is_absolute_data,
                    fallback_action_sequence=actual_fallback_sequence 
                )
            except ValueError as ve:
                raise ve
            except Exception as e:
                raise ValueError(f"Could not create Action '{action_type}' from dictionary data.") from e
        else:
            logger.warning(f"Unknown Action type '{action_type}' encountered during deserialization. Using base Action (will not execute specific logic).")
            return Action(
                type=action_type,
                params=params,
                condition_id=condition_id_str,
                next_action_index_if_condition_met=next_if_met,
                next_action_index_if_condition_not_met=next_if_not_met,
                is_absolute=is_absolute_data,
                fallback_action_sequence=actual_fallback_sequence 
            )

    def _interruptible_sleep(self, duration: float, stop_event: Optional[threading.Event] = None) -> bool:
        if duration <= 0:
             return False
        if stop_event:
             was_interrupted = stop_event.wait(timeout=duration)
             return was_interrupted
        else:
             time.sleep(duration)
             return False

class ClickAction(Action):
    TYPE = "click"
    def __init__(self, params: Optional[Dict[str, Any]] = None,
                 condition_id: Optional[str] = None,
                 next_action_index_if_condition_met: Optional[int] = None,
                 next_action_index_if_condition_not_met: Optional[int] = None,
                 is_absolute: bool = False,
                 fallback_action_sequence: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(type=self.TYPE, params=params, condition_id=condition_id,
                         next_action_index_if_condition_met=next_action_index_if_condition_met,
                         next_action_index_if_condition_not_met=next_action_index_if_condition_not_met,
                         is_absolute=is_absolute, fallback_action_sequence=fallback_action_sequence)
        try:
            self.x = int(self.params.get("x", 0))
            self.y = int(self.params.get("y", 0))
            self.button = str(self.params.get("button", "left")).lower()
            if self.button not in ["left", "right", "middle"]:
                 self.button = "left"; self.params["button"] = "left"
            self.click_type = str(self.params.get("click_type", "single")).lower()
            if self.click_type not in ["single", "double", "down", "up"]:
                 self.click_type = "single"; self.params["click_type"] = "single"
            self.delay_before = float(self.params.get("delay_before", 0.0))
            self.delay_before = max(0.0, self.delay_before); self.params["delay_before"] = self.delay_before
            self.hold_duration = float(self.params.get("hold_duration", 0.0))
            self.hold_duration = max(0.0, self.hold_duration); self.params["hold_duration"] = self.hold_duration
        except (ValueError, TypeError) as e:
             self._is_valid = False; self._validation_error = str(e)
        else: self._is_valid = True

    def _execute_core_logic(self, job_stop_event: Optional[threading.Event] = None, **context: Any) -> None:
        super()._execute_core_logic(job_stop_event, **context)
        if self.delay_before > 0:
            if self._interruptible_sleep(self.delay_before, job_stop_event):
                return
        os_interaction_client.simulate_click(self.x, self.y, self.button, self.click_type, self.hold_duration)

class PressKeyAction(Action):
    TYPE = "press_key"
    def __init__(self, params: Optional[Dict[str, Any]] = None, condition_id: Optional[str] = None,
                 next_action_index_if_condition_met: Optional[int] = None,
                 next_action_index_if_condition_not_met: Optional[int] = None,
                 is_absolute: bool = False,
                 fallback_action_sequence: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(type=self.TYPE, params=params, condition_id=condition_id,
                         next_action_index_if_condition_met=next_action_index_if_condition_met,
                         next_action_index_if_condition_not_met=next_action_index_if_condition_not_met,
                         is_absolute=is_absolute, fallback_action_sequence=fallback_action_sequence)
        try:
            self.key_name = str(self.params.get("key", ""))
            if not self.key_name: self._is_valid = False; self._validation_error = "key_name parameter is empty."; return
            self.delay_before = float(self.params.get("delay_before", 0.0))
            self.delay_before = max(0.0, self.delay_before); self.params["delay_before"] = self.delay_before
        except Exception as e: self._is_valid = False; self._validation_error = str(e); return
        else: self._is_valid = True

    def _execute_core_logic(self, job_stop_event: Optional[threading.Event] = None, **context: Any) -> None:
        super()._execute_core_logic(job_stop_event, **context)
        if self.delay_before > 0:
            if self._interruptible_sleep(self.delay_before, job_stop_event): return
        os_interaction_client.simulate_key_press(self.key_name)

class MoveMouseAction(Action):
    TYPE = "move_mouse"
    def __init__(self, params: Optional[Dict[str, Any]] = None, condition_id: Optional[str] = None,
                 next_action_index_if_condition_met: Optional[int] = None,
                 next_action_index_if_condition_not_met: Optional[int] = None,
                 is_absolute: bool = False,
                 fallback_action_sequence: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(type=self.TYPE, params=params, condition_id=condition_id,
                         next_action_index_if_condition_met=next_action_index_if_condition_met,
                         next_action_index_if_condition_not_met=next_action_index_if_condition_not_met,
                         is_absolute=is_absolute, fallback_action_sequence=fallback_action_sequence)
        try:
            self.x = int(self.params.get("x", 0)); self.y = int(self.params.get("y", 0))
            self.duration = float(self.params.get("duration", 0.1)); self.duration = max(0.0, self.duration); self.params["duration"] = self.duration
            self.delay_before = float(self.params.get("delay_before", 0.0)); self.delay_before = max(0.0, self.delay_before); self.params["delay_before"] = self.delay_before
        except (ValueError, TypeError) as e: self._is_valid = False; self._validation_error = str(e)
        else: self._is_valid = True

    def _execute_core_logic(self, job_stop_event: Optional[threading.Event] = None, **context: Any) -> None:
        super()._execute_core_logic(job_stop_event, **context)
        if self.delay_before > 0:
            if self._interruptible_sleep(self.delay_before, job_stop_event): return
        os_interaction_client.simulate_move_mouse(self.x, self.y, self.duration)

class DragAction(Action):
    TYPE = "drag"
    def __init__(self, params: Optional[Dict[str, Any]] = None, condition_id: Optional[str] = None,
                 next_action_index_if_condition_met: Optional[int] = None,
                 next_action_index_if_condition_not_met: Optional[int] = None,
                 is_absolute: bool = False,
                 fallback_action_sequence: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(type=self.TYPE, params=params, condition_id=condition_id,
                         next_action_index_if_condition_met=next_action_index_if_condition_met,
                         next_action_index_if_condition_not_met=next_action_index_if_condition_not_met,
                         is_absolute=is_absolute, fallback_action_sequence=fallback_action_sequence)
        try:
            self.start_x = int(self.params.get("x", 0)); self.start_y = int(self.params.get("y", 0))
            self.end_x = int(self.params.get("swipe_x", 0)); self.end_y = int(self.params.get("swipe_y", 0))
            self.button = str(self.params.get("button", "left")).lower()
            if self.button not in ["left", "right", "middle"]: self.button = "left"; self.params["button"] = "left"
            self.duration = float(self.params.get("duration", 1.0)); self.duration = max(0.0, self.duration); self.params["duration"] = self.duration
            self.delay_before = float(self.params.get("delay_before", 0.0)); self.delay_before = max(0.0, self.delay_before); self.params["delay_before"] = self.delay_before
        except (ValueError, TypeError) as e: self._is_valid = False; self._validation_error = str(e)
        else: self._is_valid = True

    def _execute_core_logic(self, job_stop_event: Optional[threading.Event] = None, **context: Any) -> None:
        super()._execute_core_logic(job_stop_event, **context)
        if self.delay_before > 0:
            if self._interruptible_sleep(self.delay_before, job_stop_event): return
        if _BridgeImported:
            try: os_interaction_client.simulate_move_mouse(self.start_x, self.start_y, duration=0.05)
            except Exception: pass
        if job_stop_event and job_stop_event.is_set(): return
        if _BridgeImported: os_interaction_client.simulate_drag(self.end_x, self.end_y, self.button, self.duration)
        else: raise RuntimeError("OS Interaction Bridge not imported for DragAction.")

class WaitAction(Action):
    TYPE = "wait"
    def __init__(self, params: Optional[Dict[str, Any]] = None, condition_id: Optional[str] = None,
                 next_action_index_if_condition_met: Optional[int] = None,
                 next_action_index_if_condition_not_met: Optional[int] = None,
                 is_absolute: bool = False,
                 fallback_action_sequence: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(type=self.TYPE, params=params, condition_id=condition_id,
                         next_action_index_if_condition_met=next_action_index_if_condition_met,
                         next_action_index_if_condition_not_met=next_action_index_if_condition_not_met,
                         is_absolute=is_absolute, fallback_action_sequence=fallback_action_sequence)
        try:
            self.duration = float(self.params.get("duration", 1.0)); self.duration = max(0.0, self.duration); self.params["duration"] = self.duration
            self.delay_before = float(self.params.get("delay_before", 0.0)); self.delay_before = max(0.0, self.delay_before); self.params["delay_before"] = self.delay_before
        except (ValueError, TypeError) as e: self._is_valid = False; self._validation_error = str(e)
        else: self._is_valid = True

    def _execute_core_logic(self, job_stop_event: Optional[threading.Event] = None, **context: Any) -> None:
        if not self._is_valid:
             raise ValueError(f"WaitAction is invalid: {self._validation_error}")
        if self.delay_before > 0:
            if self._interruptible_sleep(self.delay_before, job_stop_event): return
        if self.duration <= 0: return
        if self._interruptible_sleep(self.duration, job_stop_event): pass

class KeyDownAction(Action):
    TYPE = "key_down"
    def __init__(self, params: Optional[Dict[str, Any]] = None, condition_id: Optional[str] = None,
                 next_action_index_if_condition_met: Optional[int] = None,
                 next_action_index_if_condition_not_met: Optional[int] = None,
                 is_absolute: bool = False,
                 fallback_action_sequence: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(type=self.TYPE, params=params, condition_id=condition_id,
                         next_action_index_if_condition_met=next_action_index_if_condition_met,
                         next_action_index_if_condition_not_met=next_action_index_if_condition_not_met,
                         is_absolute=is_absolute, fallback_action_sequence=fallback_action_sequence)
        try:
            self.key_name = str(self.params.get("key", ""))
            if not self.key_name: self._is_valid = False; self._validation_error = "key_name parameter is empty."; return
            self.delay_before = float(self.params.get("delay_before", 0.0)); self.delay_before = max(0.0, self.delay_before); self.params["delay_before"] = self.delay_before
        except Exception as e: self._is_valid = False; self._validation_error = str(e); return
        else: self._is_valid = True

    def _execute_core_logic(self, job_stop_event: Optional[threading.Event] = None, **context: Any) -> None:
        super()._execute_core_logic(job_stop_event, **context)
        if self.delay_before > 0:
            if self._interruptible_sleep(self.delay_before, job_stop_event): return
        os_interaction_client.simulate_key_down(self.key_name)

class KeyUpAction(Action):
    TYPE = "key_up"
    def __init__(self, params: Optional[Dict[str, Any]] = None, condition_id: Optional[str] = None,
                 next_action_index_if_condition_met: Optional[int] = None,
                 next_action_index_if_condition_not_met: Optional[int] = None,
                 is_absolute: bool = False,
                 fallback_action_sequence: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(type=self.TYPE, params=params, condition_id=condition_id,
                         next_action_index_if_condition_met=next_action_index_if_condition_met,
                         next_action_index_if_condition_not_met=next_action_index_if_condition_not_met,
                         is_absolute=is_absolute, fallback_action_sequence=fallback_action_sequence)
        try:
            self.key_name = str(self.params.get("key", ""))
            if not self.key_name: self._is_valid = False; self._validation_error = "key_name parameter is empty."; return
            self.delay_before = float(self.params.get("delay_before", 0.0)); self.delay_before = max(0.0, self.delay_before); self.params["delay_before"] = self.delay_before
        except Exception as e: self._is_valid = False; self._validation_error = str(e); return
        else: self._is_valid = True

    def _execute_core_logic(self, job_stop_event: Optional[threading.Event] = None, **context: Any) -> None:
        super()._execute_core_logic(job_stop_event, **context)
        if self.delay_before > 0:
            if self._interruptible_sleep(self.delay_before, job_stop_event): return
        os_interaction_client.simulate_key_up(self.key_name)

class TextEntryAction(Action):
    TYPE = "text_entry"
    def __init__(self, params: Optional[Dict[str, Any]] = None, condition_id: Optional[str] = None,
                 next_action_index_if_condition_met: Optional[int] = None,
                 next_action_index_if_condition_not_met: Optional[int] = None,
                 is_absolute: bool = False,
                 fallback_action_sequence: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(type=self.TYPE, params=params, condition_id=condition_id,
                         next_action_index_if_condition_met=next_action_index_if_condition_met,
                         next_action_index_if_condition_not_met=next_action_index_if_condition_not_met,
                         is_absolute=is_absolute, fallback_action_sequence=fallback_action_sequence)
        try:
            self.text_to_entry = str(self.params.get("text", ""))
            self.delay_before = float(self.params.get("delay_before", 0.0)); self.delay_before = max(0.0, self.delay_before); self.params["delay_before"] = self.delay_before
        except Exception as e: self._is_valid = False; self._validation_error = str(e); return
        else: self._is_valid = True

    def _execute_core_logic(self, job_stop_event: Optional[threading.Event] = None, **context: Any) -> None:
        super()._execute_core_logic(job_stop_event, **context)
        if self.delay_before > 0:
            if self._interruptible_sleep(self.delay_before, job_stop_event): return
        os_interaction_client.simulate_text_entry(self.text_to_entry)

class ModifiedKeyStrokeAction(Action):
    TYPE = "modified_key_stroke"
    def __init__(self, params: Optional[Dict[str, Any]] = None, condition_id: Optional[str] = None,
                 next_action_index_if_condition_met: Optional[int] = None,
                 next_action_index_if_condition_not_met: Optional[int] = None,
                 is_absolute: bool = False,
                 fallback_action_sequence: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(type=self.TYPE, params=params, condition_id=condition_id,
                         next_action_index_if_condition_met=next_action_index_if_condition_met,
                         next_action_index_if_condition_not_met=next_action_index_if_condition_not_met,
                         is_absolute=is_absolute, fallback_action_sequence=fallback_action_sequence)
        try:
            self.modifier_key = str(self.params.get("modifier", ""))
            self.main_key = str(self.params.get("main_key", ""))
            if not self.modifier_key or not self.main_key: self._is_valid = False; self._validation_error = "modifier or main_key parameter is empty."; return
            self.delay_before = float(self.params.get("delay_before", 0.0)); self.delay_before = max(0.0, self.delay_before); self.params["delay_before"] = self.delay_before
        except Exception as e: self._is_valid = False; self._validation_error = str(e); return
        else: self._is_valid = True

    def _execute_core_logic(self, job_stop_event: Optional[threading.Event] = None, **context: Any) -> None:
        super()._execute_core_logic(job_stop_event, **context)
        if self.delay_before > 0:
            if self._interruptible_sleep(self.delay_before, job_stop_event): return
        os_interaction_client.simulate_modified_key_stroke(self.modifier_key, self.main_key)

def create_action(data: Optional[Dict[str, Any]]) -> Action:
     if not isinstance(data, dict):
         return Action(type="invalid_data_type_for_factory",
                       params=data if isinstance(data, dict) else {},
                       is_absolute=False,
                       fallback_action_sequence=None)
     try:
         return Action.from_dict(data)
     except ValueError as ve:
         return Action(type=f"error_creating_{data.get('type', 'unknown')}",
                       params=data.get('params',{}),
                       condition_id=data.get('condition_id'),
                       is_absolute=data.get('is_absolute', False),
                       fallback_action_sequence=data.get('fallback_action_sequence') if isinstance(data.get('fallback_action_sequence'), list) else None)
     except Exception as e:
         return Action(type=f"unexpected_error_creating_{data.get('type', 'unknown')}",
                       params=data.get('params',{}),
                       condition_id=data.get('condition_id'),
                       is_absolute=data.get('is_absolute', False),
                       fallback_action_sequence=data.get('fallback_action_sequence') if isinstance(data.get('fallback_action_sequence'), list) else None)

if not hasattr(Action, 'safe_int_or_none'):
    @staticmethod
    def _action_safe_int_or_none_helper(value: Any) -> Optional[int]:
         try:
              val_str = str(value) if value is not None else ""
              int_val = int(val_str) if val_str.strip() else None
              return max(0, int_val) if isinstance(int_val, int) else None
         except (ValueError, TypeError):
             return None
    Action.safe_int_or_none = _action_safe_int_or_none_helper
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
