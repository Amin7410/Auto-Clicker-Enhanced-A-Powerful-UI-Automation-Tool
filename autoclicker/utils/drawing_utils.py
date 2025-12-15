# utils/drawing_utils.py
import math
import logging
import json
from typing import List, Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_MOVE_DURATION_PER_PIXEL = 0.002
MIN_MOVE_DURATION = 0.01
DEFAULT_DELAY_AFTER_MOUSE_DOWN_S = 0.03
DEFAULT_DELAY_BETWEEN_STROKES_S = 0.05


def _calculate_distance(p1: Dict[str, int], p2: Dict[str, int]) -> float:
    return math.sqrt((p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2)

def convert_drawing_to_actions(
    strokes: List[List[Dict[str, int]]],
    drawing_parameters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    if not strokes:
        return []

    if drawing_parameters is None:
        drawing_parameters = {}

    speed_factor = 1.0
    try:
        speed_factor_param = drawing_parameters.get("draw_speed_factor", 1.0)
        if isinstance(speed_factor_param, (int, float)):
            speed_factor = float(speed_factor_param)
        elif isinstance(speed_factor_param, str) and speed_factor_param.strip():
            speed_factor = float(speed_factor_param.strip())
        if speed_factor <= 0:
            speed_factor = 1.0
    except (ValueError, TypeError):
        speed_factor = 1.0
    current_move_duration_per_pixel = DEFAULT_MOVE_DURATION_PER_PIXEL / speed_factor

    delay_between_strokes_s = DEFAULT_DELAY_BETWEEN_STROKES_S
    try:
        delay_ms_param = drawing_parameters.get("delay_between_strokes_ms", DEFAULT_DELAY_BETWEEN_STROKES_S * 1000)
        if isinstance(delay_ms_param, (int, float)):
            delay_between_strokes_s = float(delay_ms_param) / 1000.0
        elif isinstance(delay_ms_param, str) and delay_ms_param.strip():
            delay_between_strokes_s = float(delay_ms_param.strip()) / 1000.0
        if delay_between_strokes_s < 0:
            delay_between_strokes_s = DEFAULT_DELAY_BETWEEN_STROKES_S
    except (ValueError, TypeError):
        delay_between_strokes_s = DEFAULT_DELAY_BETWEEN_STROKES_S
        
    mouse_button = str(drawing_parameters.get("mouse_button", "left")).lower()
    if mouse_button not in ["left", "right", "middle"]:
        mouse_button = "left"

    delay_after_mouse_down_s = DEFAULT_DELAY_AFTER_MOUSE_DOWN_S
    try:
        delay_after_param = drawing_parameters.get("delay_after_mouse_down_s", DEFAULT_DELAY_AFTER_MOUSE_DOWN_S)
        if isinstance(delay_after_param, (int, float)):
            delay_after_mouse_down_s = float(delay_after_param)
        elif isinstance(delay_after_param, str) and delay_after_param.strip():
            delay_after_mouse_down_s = float(delay_after_param.strip())
        if delay_after_mouse_down_s < 0:
            delay_after_mouse_down_s = DEFAULT_DELAY_AFTER_MOUSE_DOWN_S
    except (ValueError, TypeError):
        delay_after_mouse_down_s = DEFAULT_DELAY_AFTER_MOUSE_DOWN_S


    actions: List[Dict[str, Any]] = []
    num_strokes = len(strokes)

    for stroke_index, current_stroke_points in enumerate(strokes):
        if not current_stroke_points or not isinstance(current_stroke_points, list) or len(current_stroke_points) < 1:
            continue

        start_point = current_stroke_points[0]
        if not isinstance(start_point, dict) or 'x' not in start_point or 'y' not in start_point:
            continue
        try:
            start_x_val = int(start_point['x'])
            start_y_val = int(start_point['y'])
        except (ValueError, TypeError):
            continue


        actions.append({
            "type": "move_mouse",
            "params": {"x": start_x_val, "y": start_y_val, "duration": MIN_MOVE_DURATION},
            "condition_id": None,
            "next_action_index_if_condition_met": None,
            "next_action_index_if_condition_not_met": None
        })

        actions.append({
            "type": "click",
            "params": {"button": mouse_button, "click_type": "down", "x": start_x_val, "y": start_y_val},
            "condition_id": None,
            "next_action_index_if_condition_met": None,
            "next_action_index_if_condition_not_met": None
        })

        if delay_after_mouse_down_s > 0:
            actions.append({
                "type": "wait",
                "params": {"duration": delay_after_mouse_down_s},
                "condition_id": None,
                "next_action_index_if_condition_met": None,
                "next_action_index_if_condition_not_met": None
            })

        if len(current_stroke_points) > 1:
            previous_point = start_point
            for i in range(1, len(current_stroke_points)):
                next_point = current_stroke_points[i]
                if not isinstance(next_point, dict) or 'x' not in next_point or 'y' not in next_point:
                    continue
                try:
                    next_x_val = int(next_point['x'])
                    next_y_val = int(next_point['y'])
                except (ValueError, TypeError):
                    continue

                distance = _calculate_distance(previous_point, next_point)
                move_duration = max(MIN_MOVE_DURATION, distance * current_move_duration_per_pixel)

                actions.append({
                    "type": "move_mouse",
                    "params": {"x": next_x_val, "y": next_y_val, "duration": round(move_duration, 3)},
                    "condition_id": None,
                    "next_action_index_if_condition_met": None,
                    "next_action_index_if_condition_not_met": None
                })
                previous_point = next_point
        
        end_point_of_stroke = current_stroke_points[-1]
        try:
            end_x_val = int(end_point_of_stroke['x'])
            end_y_val = int(end_point_of_stroke['y'])
        except (ValueError, TypeError, KeyError): 
            end_x_val = start_x_val
            end_y_val = start_y_val


        actions.append({
            "type": "click",
            "params": {"button": mouse_button, "click_type": "up", "x": end_x_val, "y": end_y_val},
            "condition_id": None,
            "next_action_index_if_condition_met": None,
            "next_action_index_if_condition_not_met": None
        })

        if delay_between_strokes_s > 0 and stroke_index < num_strokes - 1:
            actions.append({
                "type": "wait",
                "params": {"duration": delay_between_strokes_s},
                "condition_id": None,
                "next_action_index_if_condition_met": None,
                "next_action_index_if_condition_not_met": None
            })

    return actions

def parse_json_strokes_data(json_string: str) -> Optional[List[List[Dict[str, int]]]]:
    if not isinstance(json_string, str) or not json_string.strip():
        raise ValueError("Input JSON string cannot be empty.")
    try:
        data_from_json = json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")

    if not isinstance(data_from_json, list):
        raise ValueError("JSON data must be a list of strokes.")

    parsed_strokes: List[List[Dict[str, int]]] = []
    for i, stroke_data in enumerate(data_from_json):
        if not isinstance(stroke_data, list):
            raise ValueError(f"Stroke at index {i} must be a list of points.")

        current_parsed_stroke: List[Dict[str, int]] = []
        if not stroke_data :
            raise ValueError(f"Stroke at index {i} cannot be empty.")

        for j, point_data in enumerate(stroke_data):
            if not isinstance(point_data, dict):
                raise ValueError(f"Point at stroke {i}, index {j} must be a dictionary {{'x': int, 'y': int}}.")
            if 'x' not in point_data or 'y' not in point_data:
                raise ValueError(f"Point at stroke {i}, index {j} must contain 'x' and 'y' keys.")
            try:
                x_val = int(point_data['x'])
                y_val = int(point_data['y'])
            except (ValueError, TypeError):
                raise ValueError(f"Coordinates 'x' and 'y' at stroke {i}, index {j} must be integers.")
            current_parsed_stroke.append({"x": x_val, "y": y_val})
        parsed_strokes.append(current_parsed_stroke)
    return parsed_strokes
