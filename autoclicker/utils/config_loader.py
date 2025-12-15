# utils/config_loader.py
import copy
import json
import os
import logging
import glob
import shutil 
from typing import List, Dict, Any, Optional 

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_NAME = "default"
PROFILE_EXTENSION = ".profile.json"

class ConfigLoader:
    profile_dir: str
    general_config_file: str

    def __init__(self, profile_dir: str = "profiles", general_config_file: str = "config.json") -> None:
        if not isinstance(profile_dir, str) or not profile_dir.strip():
            raise ValueError("Profile directory path cannot be empty.")
        self.profile_dir = profile_dir.strip()
        self.general_config_file = general_config_file
        self._ensure_profile_dir_exists()

    def _ensure_profile_dir_exists(self) -> None:
        try:
            os.makedirs(self.profile_dir, exist_ok=True)
        except Exception as e:
            pass


    def _get_profile_path(self, profile_name: str) -> Optional[str]:
        if not isinstance(profile_name, str) or not profile_name.strip():
            return None
        sanitized_name = "".join(c for c in profile_name if c.isalnum() or c in ('_', '-')).strip()
        if not sanitized_name:
             return None
        filename = f"{sanitized_name}{PROFILE_EXTENSION}"
        return os.path.join(self.profile_dir, filename)

    def profile_exists(self, profile_name: str) -> bool:
        profile_path = self._get_profile_path(profile_name)
        return profile_path is not None and os.path.exists(profile_path)

    def list_profiles(self) -> List[str]:
        profile_names: List[str] = []
        try:
            self._ensure_profile_dir_exists()
            search_pattern = os.path.join(self.profile_dir, f"*{PROFILE_EXTENSION}")
            for filepath in glob.glob(search_pattern):
                if os.path.isfile(filepath):
                    filename = os.path.basename(filepath)
                    if filename.endswith(PROFILE_EXTENSION):
                        profile_name = filename[:-len(PROFILE_EXTENSION)]
                        profile_names.append(profile_name)
        except Exception:
            pass
        return sorted(profile_names)

    def load_profile(self, profile_name: str) -> Dict[str, Any]:
        profile_path = self._get_profile_path(profile_name)
        default_empty_profile: Dict[str, Any] = {
            "jobs": {}, "triggers": {}, "shape_templates": {}, "shared_conditions": []
        }
        if profile_path is None:
            return copy.deepcopy(default_empty_profile)
        try:
            if not os.path.exists(profile_path):
                return copy.deepcopy(default_empty_profile)
            with open(profile_path, "r", encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return copy.deepcopy(default_empty_profile)
                profile_data_loaded = json.loads(content)
                if not isinstance(profile_data_loaded, dict):
                    return copy.deepcopy(default_empty_profile)

                profile_data_to_return: Dict[str, Any] = {}
                profile_data_to_return["jobs"] = profile_data_loaded.get("jobs", {})
                if not isinstance(profile_data_to_return["jobs"], dict): profile_data_to_return["jobs"] = {}
                profile_data_to_return["triggers"] = profile_data_loaded.get("triggers", {})
                if not isinstance(profile_data_to_return["triggers"], dict): profile_data_to_return["triggers"] = {}
                profile_data_to_return["shape_templates"] = profile_data_loaded.get("shape_templates", {})
                if not isinstance(profile_data_to_return["shape_templates"], dict): profile_data_to_return["shape_templates"] = {}
                profile_data_to_return["shared_conditions"] = profile_data_loaded.get("shared_conditions", [])
                if not isinstance(profile_data_to_return["shared_conditions"], list): profile_data_to_return["shared_conditions"] = []

                return profile_data_to_return
        except json.JSONDecodeError:
            return copy.deepcopy(default_empty_profile)
        except Exception:
            return copy.deepcopy(default_empty_profile)

    def save_profile(self, profile_name: str, profile_data: Dict[str, Any]) -> None:
        profile_path = self._get_profile_path(profile_name)
        if profile_path is None:
            raise ValueError(f"Cannot save profile: Invalid name '{profile_name}'.")
        if not isinstance(profile_data, dict):
            raise ValueError("Profile data to save must be a dictionary.")

        data_to_save: Dict[str, Any] = {
            "jobs": profile_data.get("jobs", {}),
            "triggers": profile_data.get("triggers", {}),
            "shape_templates": profile_data.get("shape_templates", {}),
            "shared_conditions": profile_data.get("shared_conditions", [])
        }

        self._ensure_profile_dir_exists()
        try:
            with open(profile_path, "w", encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)
        except TypeError as e:
            raise ValueError(f"Data for profile '{profile_name}' is not JSON serializable.") from e
        except Exception as e:
            raise IOError(f"Error saving profile '{profile_name}': {e}") from e

    def delete_profile(self, profile_name: str) -> bool:
        if profile_name == DEFAULT_PROFILE_NAME: return False
        profile_path = self._get_profile_path(profile_name)
        if profile_path is None or not os.path.exists(profile_path): return False
        try:
            os.remove(profile_path)
            return True
        except Exception:
            return False

    def load_general_config(self, key: Optional[str] = None) -> Any:
        config_data: Dict[str, Any] = {}
        try:
            if not os.path.exists(self.general_config_file): return config_data.get(key) if key else config_data
            with open(self.general_config_file, "r", encoding='utf-8') as f:
                content = f.read().strip();
                if not content: return config_data.get(key) if key else config_data
                config_data = json.loads(content)
                if not isinstance(config_data, dict): config_data = {}
        except Exception: config_data = {}
        return config_data.get(key) if key else config_data

    def save_general_config(self, key: str, data: Any) -> None:
        if not isinstance(key, str) or not key.strip(): raise ValueError("Config key empty")
        current_config = self.load_general_config()
        if not isinstance(current_config, dict): current_config = {}
        current_config[key] = data
        try:
            config_dir = os.path.dirname(self.general_config_file)
            if config_dir: os.makedirs(config_dir, exist_ok=True)
            with open(self.general_config_file, "w", encoding='utf-8') as f:
                 json.dump(current_config, f, indent=4)
        except Exception as e: raise IOError(f"Error saving general config: {e}") from e
