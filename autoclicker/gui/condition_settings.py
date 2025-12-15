# gui/condition_settings.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from PIL import Image, ImageTk
import cv2
import os
import numpy as np
import re
import copy
from typing import Callable, Optional, List, Dict, Any, Tuple

from utils.parsing_utils import parse_tuple_str

logger = logging.getLogger(__name__)

_UtilsSuccessfullyImported = False
try:
    from utils.parsing_utils import parse_tuple_str
    from utils.color_utils import hex_to_rgb, rgb_to_hex
    from utils.image_analysis import analyze_region_colors, get_top_n_colors_histogram_peaks, get_top_n_colors_kmeans
    _UtilsSuccessfullyImported = True
except ImportError as e_utils:
    _UtilsSuccessfullyImported = False
    logger_cs_utils_fallback = logging.getLogger(__name__)
    logger_cs_utils_fallback.error(f"ConditionSettings: Critical utils import failed: {e_utils}. Some functionalities will be broken.")
    if 'parse_tuple_str' not in globals():
        def parse_tuple_str(s,l,t): return None # type: ignore
    if 'hex_to_rgb' not in globals():
        def hex_to_rgb(h): return (0,0,0) # type: ignore
    if 'rgb_to_hex' not in globals():
        def rgb_to_hex(r): return "#000000" # type: ignore
    if 'analyze_region_colors' not in globals():
        def analyze_region_colors(i, t, s): # type: ignore
            logger_cs_utils_fallback.warning("Using dummy analyze_region_colors")
            return {}
    if 'get_top_n_colors_histogram_peaks' not in globals():
        def get_top_n_colors_histogram_peaks(i,n,b,s,p): # type: ignore
            logger_cs_utils_fallback.warning("Using dummy get_top_n_colors_histogram_peaks")
            return []
    if 'get_top_n_colors_kmeans' not in globals():
        def get_top_n_colors_kmeans(i,n,s): # type: ignore
            logger_cs_utils_fallback.warning("Using dummy get_top_n_colors_kmeans")
            return []

_BridgeImported = False
try:
    from python_csharp_bridge import os_interaction_client
    _BridgeImported = True
except ImportError:
    logger.error("ConditionSettings: Could not import os_interaction_client.")
    class DummyOSInteractionClient:
         def capture_region(self, *args, **kwargs): return {"image_np": None, "x1": 0, "y1": 0, "x2": 0, "y2": 0}
         def get_pixel_color(self, *args, **kwargs): return "#000000"
         def get_screen_size(self): return (1920, 1080)
    os_interaction_client = DummyOSInteractionClient()

_CaptureDepsImported = False
try:
     from gui.screen_capture_window import ScreenCaptureWindow
     from gui.coordinate_capture_window import CoordinateCaptureWindow
     from utils.image_storage import ImageStorage
     _CaptureDepsImported = True
except ImportError:
     logger.warning("ConditionSettings: Could not import screen_capture_window, coordinate_capture_window or image_storage. Capture features disabled.")
     class ScreenCaptureWindow:
          def __init__(self, master: tk.Misc, callback: Callable[[Optional[Dict[str, Any]]], None], **kwargs):
            if callable(callback):
                if hasattr(master, 'after'): master.after(10, lambda: callback(None))
                else: callback(None)
     class CoordinateCaptureWindow:
         def __init__(self, master: tk.Misc, callback: Callable[[Optional[Any]], None], num_points: int = 1):
            if callable(callback):
                if hasattr(master, 'after'): master.after(10, lambda: callback(None))
                else: callback(None)
     class ImageStorage:
        def __init__(self, storage_dir: str = "dummy_images"): self.storage_dir = storage_dir
        def get_full_path(self, p): return os.path.abspath(os.path.join(self.storage_dir, p))
        def file_exists(self, p): return False
        def save_image(self, img, base): return f"dummy_images/{base}.png"

_ColorUtilsImported = False
try:
     from utils.color_utils import hex_to_rgb, rgb_to_hex
     _ColorUtilsImported = True
except ImportError:
     logger.warning("ConditionSettings: Could not import color_utils.")
     def hex_to_rgb(hex_color): raise ImportError("color_utils not imported") # type: ignore
     def rgb_to_hex(rgb_color): raise ImportError("color_utils not imported") # type: ignore

_ConditionCoreImported = False
logger.info("CONDITION_SETTINGS.PY: Attempting to import core.condition...")
print("CONDITION_SETTINGS.PY: Attempting to import core.condition...")
try:
    from core.condition import (
        Condition, create_condition, NoneCondition,
        ColorAtPositionCondition, ImageOnScreenCondition,
        TextOnScreenCondition, WindowExistsCondition, ProcessExistsCondition,
        TextInRelativeRegionCondition, RegionColorCondition, MultiImageCondition,
        CONDITION_TYPE_SETTINGS as CORE_CONDITION_TYPE_SETTINGS,
        ACTION_CONDITION_TYPES_DISPLAY as CORE_ACTION_CONDITION_TYPES_DISPLAY,
        ACTION_CONDITION_DISPLAY_TO_INTERNAL_MAP as CORE_ACTION_CONDITION_DISPLAY_TO_INTERNAL_MAP
    )
    _ConditionCoreImported = True
    logger.info("CONDITION_SETTINGS.PY: Successfully imported from core.condition.")
    print("CONDITION_SETTINGS.PY: Successfully imported from core.condition.")
except ImportError as e_core_cond_import:
    logger.critical(f"CONDITION_SETTINGS.PY: IMPORT FAILED for core.condition: {e_core_cond_import}", exc_info=True)
    print(f"CONDITION_SETTINGS.PY: IMPORT FAILED for core.condition: {e_core_cond_import}")
    _ConditionCoreImported = False
    class Condition: pass
    class NoneCondition(Condition): TYPE="none"
    class ColorAtPositionCondition(Condition): TYPE="color_at_position"
    class ImageOnScreenCondition(Condition): TYPE="image_on_screen"
    class TextOnScreenCondition(Condition): TYPE="text_on_screen"
    class WindowExistsCondition(Condition): TYPE="window_exists"
    class ProcessExistsCondition(Condition): TYPE="process_exists"
    class TextInRelativeRegionCondition(Condition): TYPE="text_in_relative_region"
    class RegionColorCondition(Condition): TYPE="region_color"
    class MultiImageCondition(Condition): TYPE="multi_image_on_screen"

    def create_condition(data): return type("DummyCond", (), {"type":NoneCondition.TYPE, "params":{}, "id": data.get("id"), "name": data.get("name")})() # type: ignore
    CORE_CONDITION_TYPE_SETTINGS = {
         NoneCondition.TYPE: {"display_name": "Always True", "create_params_ui": lambda s: s._create_none_params(), "show_preview": False },
         ColorAtPositionCondition.TYPE: {"display_name": "Color at Position", "create_params_ui": lambda s: s._create_color_at_position_params(), "show_preview": False },
         ImageOnScreenCondition.TYPE: {"display_name": "Image on Screen", "create_params_ui": lambda s: s._create_image_on_screen_params(), "show_preview": True },
         TextOnScreenCondition.TYPE: {"display_name": "Text on Screen", "create_params_ui": lambda s: s._create_text_on_screen_params(), "show_preview": True },
         WindowExistsCondition.TYPE: {"display_name": "Window Exists", "create_params_ui": lambda s: s._create_window_exists_params(), "show_preview": False },
         ProcessExistsCondition.TYPE: {"display_name": "Process Exists", "create_params_ui": lambda s: s._create_process_exists_params(), "show_preview": False },
         TextInRelativeRegionCondition.TYPE: {"display_name": "Text near Anchor", "create_params_ui": lambda s: s._create_text_in_relative_region_params(), "show_preview": True},
         RegionColorCondition.TYPE: {"display_name": "Color in Region (%)", "create_params_ui": lambda s: s._create_region_color_params(), "show_preview": True},
         MultiImageCondition.TYPE: {"display_name": "Multiple Images Pattern", "create_params_ui": lambda s: s._create_multi_image_params_ui(), "show_preview": True},
    }
    CORE_ACTION_CONDITION_TYPES_DISPLAY = [s["display_name"] for s in CORE_CONDITION_TYPE_SETTINGS.values()]
    CORE_ACTION_CONDITION_DISPLAY_TO_INTERNAL_MAP = {s["display_name"]: t for t, s in CORE_CONDITION_TYPE_SETTINGS.items()}


_ImageProcessingAvailable_UI = False
try:
    from utils.image_processing import preprocess_for_image_matching, preprocess_for_ocr
    _ImageProcessingAvailable_UI = True
except ImportError:
    logger.error("ConditionSettings: Could not import image processing utils. Previews will not work.")
    def preprocess_for_image_matching(img, params): return img # type: ignore
    def preprocess_for_ocr(img, params): return img # type: ignore

_PytesseractAvailable_UI = False

if _ConditionCoreImported:
    try:
        import pytesseract
        if hasattr(pytesseract.pytesseract, 'tesseract_cmd') and pytesseract.pytesseract.tesseract_cmd and os.path.exists(pytesseract.pytesseract.tesseract_cmd):
            _PytesseractAvailable_UI = True
            try: pytesseract.get_tesseract_version()
            except pytesseract.TesseractNotFoundError: _PytesseractAvailable_UI = False
            except Exception: pass
        else:
            common_paths = [r'C:\Program Files\Tesseract-OCR\tesseract.exe', r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']
            found_path = next((p for p in common_paths if os.path.exists(p)), None)
            if found_path: pytesseract.pytesseract.tesseract_cmd = found_path
            try: pytesseract.get_tesseract_version(); _PytesseractAvailable_UI = True
            except pytesseract.TesseractNotFoundError: logger.warning("ConditionSettings: Tesseract OCR not found or not configured.")
            except Exception: pass
    except ImportError: logger.warning("ConditionSettings: Pytesseract library not found.")
    except Exception as e: logger.error(f"ConditionSettings: Error initializing Pytesseract: {e}")


def is_integer_or_empty(value: str) -> bool:
    if value == "": return True
    try: int(value); return True
    except ValueError: return False

def is_float_or_empty(value: str) -> bool:
    if value == "": return True
    try: float(value); return True
    except ValueError: return False

def is_comma_sep_ints(value: str, expected_len: int) -> bool:
    if value == "": return True
    parts = value.split(',')
    if len(parts) != expected_len: return False
    try: [int(p.strip()) for p in parts]; return True
    except ValueError: return False


class ConditionSettings(ttk.Frame):
    def __init__(self, master, condition_data: Optional[Dict[str, Any]] = None,
                 image_storage: Optional[ImageStorage] = None, # type: ignore
                 exclude_types: Optional[List[str]] = None):
        super().__init__(master)
        self.exclude_types = exclude_types if isinstance(exclude_types, list) else []

        self.canvas: Optional[tk.Canvas] = None
        self.param_frame: Optional[ttk.Frame] = None
        self._param_frame_window_id: Optional[int] = None 
        self._filtered_action_condition_types_display: List[str] = []
        self._filtered_action_condition_display_to_internal_map: Dict[str, str] = {}
        self.param_widgets: Dict[str, List[Any]] = {}

        self.grid_rowconfigure(0, weight=0) 
        self.grid_rowconfigure(1, weight=1) 
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1) 
        self.grid_columnconfigure(2, weight=0) 

        if not _ConditionCoreImported or not _UtilsSuccessfullyImported :
            error_msg = "ConditionSettings Error: Missing critical dependencies.\n"
            if not _ConditionCoreImported: error_msg += "- Core condition classes failed to import.\n"
            if not _UtilsSuccessfullyImported: error_msg += "- Utility functions (parsing, color, image_analysis) failed to import.\n"
            error_label = ttk.Label(self, text=error_msg, foreground="red", wraplength=400)
            error_label.grid(row=0, column=0, columnspan=3, padx=10, pady=10, sticky="nsew") # columnspan=3 để chiếm cả 3 cột đã định nghĩa
            logger.critical(error_msg)

        self.vcmd_integer = self.register(is_integer_or_empty)
        self.vcmd_float = self.register(is_float_or_empty)
        self.vcmd_int_tuple2 = self.register(lambda P: is_comma_sep_ints(P, 2))

        self.initial_condition_data = copy.deepcopy(condition_data or {"type": NoneCondition.TYPE, "params": {}, "name": "", "id": None})
        if _ConditionCoreImported:
            self._current_condition_obj: Condition = create_condition(self.initial_condition_data)
        else:
            self._current_condition_obj: Condition = type("DummyCondFull", (object,), {"type":NoneCondition.TYPE, "params":{}, "id": self.initial_condition_data.get("id"), "name": self.initial_condition_data.get("name"), "is_monitored_by_ai_brain": False, "to_dict": lambda: self.initial_condition_data})() # type: ignore

        self.image_storage = image_storage if isinstance(image_storage, ImageStorage) else None # type: ignore
        if not self.image_storage and _CaptureDepsImported:
             logger.warning("ConditionSettings initialized without a valid ImageStorage instance.")

        self._current_preview_image_pil: Optional[Image.Image] = None
        self._current_preview_image_tk: Optional[ImageTk.PhotoImage] = None
        self._last_captured_region_np: Optional[np.ndarray] = None
        self._recognized_text_var = tk.StringVar(value="Recognized text preview...")

        self._grayscale_var = tk.BooleanVar()
        self._binarization_var = tk.BooleanVar()
        self._adaptive_threshold_var = tk.BooleanVar()
        self._clahe_var = tk.BooleanVar()
        self._gaussian_blur_var = tk.BooleanVar()
        self._median_blur_var = tk.BooleanVar()
        self._bilateral_filter_var = tk.BooleanVar()
        self._canny_edges_var = tk.BooleanVar()

        self._anchor_pp_grayscale_var = tk.BooleanVar()
        self._anchor_pp_binarization_var = tk.BooleanVar()
        self._anchor_pp_gaussian_blur_var = tk.BooleanVar()
        self._anchor_pp_median_blur_var = tk.BooleanVar()

        self._ocr_pp_grayscale_var = tk.BooleanVar()
        self._ocr_pp_adaptive_threshold_var = tk.BooleanVar()
        self._ocr_pp_median_blur_var = tk.BooleanVar()

        self.target_color_swatch_images: List[ImageTk.PhotoImage] = []
        self.analysis_swatch_images: List[ImageTk.PhotoImage] = []

        self.multi_image_anchor_preview_image_pil: Optional[Image.Image] = None
        self.multi_image_anchor_preview_image_tk: Optional[ImageTk.PhotoImage] = None
        self.multi_image_sub_images_data: List[Dict[str, Any]] = []

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        ttk.Label(self, text="Condition Type:").grid(row=0, column=0, padx=5, pady=(5,0), sticky=tk.W)

        self._filtered_condition_type_settings: Dict[str, Any] = {
            k: v for k, v in CORE_CONDITION_TYPE_SETTINGS.items() if k not in self.exclude_types
        }
        self._filtered_action_condition_types_display: List[str] = [
            settings["display_name"] for settings in self._filtered_condition_type_settings.values()
        ]
        self._filtered_action_condition_display_to_internal_map: Dict[str, str] = {
            settings["display_name"]: type_key for type_key, settings in self._filtered_condition_type_settings.items()
        }

        initial_display_type = self._filtered_action_condition_types_display[0] if self._filtered_action_condition_types_display else "Error: No Types"
        if self._current_condition_obj and hasattr(self._current_condition_obj, 'type') and self._current_condition_obj.type in self._filtered_condition_type_settings:
            initial_display_type = self._filtered_condition_type_settings[self._current_condition_obj.type]["display_name"]

        self.type_var = tk.StringVar(value=initial_display_type)
        self.type_combobox = ttk.Combobox(self, textvariable=self.type_var,
                                          values=self._filtered_action_condition_types_display,
                                          state="readonly", width=30)
        self.type_combobox.grid(row=0, column=1, padx=5, pady=(5,0), sticky=tk.EW)
        self.type_combobox.bind("<<ComboboxSelected>>", self._on_type_selected)

        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.param_frame = ttk.Frame(self.canvas) 
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=1, column=0, columnspan=2, padx=(5,0), pady=(5,5), sticky="nsew")
        self.scrollbar.grid(row=1, column=2, padx=(0,5), pady=(5,5), sticky="ns")
        self._param_frame_window_id = self.canvas.create_window((0, 0), window=self.param_frame, anchor="nw")

        self.param_frame.bind("<Configure>", self._on_param_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_mouse_wheel(self.canvas)
        self._bind_mouse_wheel(self.param_frame)

        if _ConditionCoreImported and _UtilsSuccessfullyImported:
            self._on_type_selected()

    def _on_param_frame_configure(self, event: Optional[tk.Event] = None) -> None:
        if self.canvas and self.canvas.winfo_exists(): 
            self.canvas.after_idle(self._update_scroll_region)

    def _on_canvas_configure(self, event: Optional[tk.Event] = None) -> None:
        if not (self.canvas and self.canvas.winfo_exists()): return 
        canvas_width = self.canvas.winfo_width()
        if hasattr(self,'_param_frame_window_id') and self._param_frame_window_id:
             if canvas_width > 1 :
                self.canvas.itemconfigure(self._param_frame_window_id, width=canvas_width)
        self.canvas.after_idle(self._update_scroll_region)

    def _update_scroll_region(self) -> None:
        if hasattr(self,'canvas') and self.canvas and self.canvas.winfo_exists() and \
           hasattr(self,'param_frame') and self.param_frame and self.param_frame.winfo_exists():
            self.param_frame.update_idletasks()
            content_height = self.param_frame.winfo_reqheight()
            canvas_width = self.canvas.winfo_width()
            self.canvas.configure(scrollregion=(0, 0, canvas_width, max(1, content_height)))

    def _bind_mouse_wheel(self, widget: tk.Widget) -> None:
        if widget and widget.winfo_exists():
            try:
                widget.bind("<MouseWheel>", self._on_mousewheel, add='+');
                widget.bind("<Button-4>", self._on_mousewheel, add='+');
                widget.bind("<Button-5>", self._on_mousewheel, add='+')
            except tk.TclError: pass

    def _unbind_mouse_wheel(self, widget: tk.Widget) -> None:
         if widget and widget.winfo_exists():
            try:
                widget.unbind("<MouseWheel>");
                widget.unbind("<Button-4>");
                widget.unbind("<Button-5>")
            except tk.TclError: pass

    def _on_mousewheel(self, event: tk.Event) -> Optional[str]:
        delta = 0
        if event.num == 5 or event.delta < 0: delta = 1
        elif event.num == 4 or event.delta > 0: delta = -1
        if delta != 0 and hasattr(self,'canvas') and self.canvas and self.canvas.winfo_exists():
            try:
                self.canvas.yview_scroll(delta, "units");
                return "break"
            except tk.TclError: pass
        return None

    def _add_swatch_to_tree(self, tree_widget: ttk.Treeview, image_list_ref: list, hex_color: str, values_tuple: tuple) -> None:
        if not (tree_widget and tree_widget.winfo_exists()):
            logger.warning("_add_swatch_to_tree: Tree widget does not exist.")
            return
        try:
            r, g, b = hex_to_rgb(hex_color)
            swatch_img_pil = Image.new("RGB", (16, 12), (r, g, b))
            photo = ImageTk.PhotoImage(swatch_img_pil)
            image_list_ref.append(photo)
            tree_widget.insert("", tk.END, image=photo, values=values_tuple)
        except Exception as e:
            logger.error(f"Error creating/adding swatch for {hex_color}: {e}", exc_info=True)
            tree_widget.insert("", tk.END, text="ERR", values=values_tuple)

    def _update_color_analysis_display(self, image_for_analysis_np_rgb: Optional[np.ndarray],
                                      colors_to_analyze_defs: Optional[List[Dict[str,Any]]] = None,
                                      analyze_top_n: Optional[int] = None):
        logger.debug(f"Updating color analysis display. Image present: {image_for_analysis_np_rgb is not None}, Targets: {colors_to_analyze_defs is not None}, TopN: {analyze_top_n}")
        if not (hasattr(self, 'color_analysis_tree') and self.color_analysis_tree and self.color_analysis_tree.winfo_exists()): # Thêm kiểm tra self.color_analysis_tree
            logger.debug("Color analysis tree not found or not visible, skipping update.")
            return

        for item in self.color_analysis_tree.get_children():
            self.color_analysis_tree.delete(item)
        self.analysis_swatch_images.clear()

        if image_for_analysis_np_rgb is None:
            if analyze_top_n is not None or colors_to_analyze_defs is not None:
                self._add_swatch_to_tree(self.color_analysis_tree, self.analysis_swatch_images, "#808080", ("N/A", "No image in preview"))
            return

        analysis_results_tuples: List[Tuple[Tuple[int,int,int], float]] = []
        try:
            sampling_str = self._get_widget_value("sampling_step", "1")
            sampling = int(sampling_str) if sampling_str and sampling_str.isdigit() else 1
            sampling = max(1, sampling)

            if colors_to_analyze_defs is not None:
                logger.debug(f"Analyzing target colors: {colors_to_analyze_defs}")
                targets_for_func: List[Tuple[Tuple[int,int,int], int]] = []
                for color_def in colors_to_analyze_defs:
                    try:
                        rgb_tuple_val = color_def.get("rgb")
                        if not (isinstance(rgb_tuple_val, tuple) and len(rgb_tuple_val) == 3):
                            rgb_tuple_val = hex_to_rgb(str(color_def.get("hex")))

                        tol = int(color_def.get("tolerance", 10))
                        targets_for_func.append((rgb_tuple_val, tol))
                    except (ValueError, TypeError) as e_conv:
                        logger.warning(f"Skipping invalid target color definition for analysis: {color_def}, error: {e_conv}")
                        continue

                if targets_for_func:
                    percentages_dict = analyze_region_colors(image_for_analysis_np_rgb, targets_for_func, sampling)
                    for color_def in colors_to_analyze_defs:
                        hex_key = str(color_def.get("hex"))
                        rgb_val = color_def.get("rgb")
                        if not rgb_val:
                            try: rgb_val = hex_to_rgb(hex_key)
                            except: continue
                        analysis_results_tuples.append((rgb_val, percentages_dict.get(hex_key, 0.0)))
                else:
                    logger.debug("No valid target colors provided to analyze_region_colors function.")

            elif analyze_top_n is not None and analyze_top_n > 0:
                logger.debug(f"Analyzing Top {analyze_top_n} colors.")
                bins_p_channel = 16
                peak_dist_f = 1.0
                analysis_results_tuples = get_top_n_colors_histogram_peaks(image_for_analysis_np_rgb, analyze_top_n, bins_p_channel, sampling, peak_dist_f)

            if not analysis_results_tuples:
                logger.debug("No analysis results to display (empty list from analysis function).")
                self._add_swatch_to_tree(self.color_analysis_tree, self.analysis_swatch_images, "#808080", ("N/A", "No dominant colors or error."))
            else:
                logger.debug(f"Displaying {len(analysis_results_tuples)} analysis results in tree.")
                for (r,g,b), percentage in analysis_results_tuples:
                    hex_color = rgb_to_hex((r,g,b))
                    self._add_swatch_to_tree(self.color_analysis_tree, self.analysis_swatch_images, hex_color, (hex_color, f"{percentage:.2f}%"))
        except Exception as e:
            logger.error(f"Error during color analysis display update logic: {e}", exc_info=True)
            self._add_swatch_to_tree(self.color_analysis_tree, self.analysis_swatch_images, "#FF0000", ("Error", "Analysis failed"))


    def _on_type_selected(self, event: Optional[tk.Event] = None) -> None:
        if not hasattr(self, '_filtered_action_condition_display_to_internal_map') or \
           not self._filtered_action_condition_display_to_internal_map:
            logger.error("ConditionSettings._on_type_selected: Filtered type map not initialized. Cannot proceed.")
            if self.param_frame and self.param_frame.winfo_exists():
                for widget in list(self.param_frame.winfo_children()): widget.destroy()
                ttk.Label(self.param_frame, text="Error: Condition types not loaded.", foreground="red").pack()
            return

        selected_display_key = self.type_var.get()
        selected_internal_type = self._filtered_action_condition_display_to_internal_map.get(selected_display_key, NoneCondition.TYPE)
        logger.debug(f"ConditionSettings: Type selected: '{selected_display_key}' (Internal: '{selected_internal_type}')")

        if hasattr(self, 'param_frame') and self.param_frame and self.param_frame.winfo_exists():
            for widget in list(self.param_frame.winfo_children()):
                self._unbind_mouse_wheel(widget)
                try:
                    widget.destroy()
                except tk.TclError: pass
                except Exception as e: logger.warning(f"Error destroying old param widget {widget}: {e}")
        else:
            if self.canvas and self.canvas.winfo_exists():
                self.param_frame = ttk.Frame(self.canvas)
                if hasattr(self, '_param_frame_window_id') and self._param_frame_window_id:
                    self.canvas.itemconfigure(self._param_frame_window_id, window=self.param_frame)
                else:
                    ttk.Label(self, text="UI Error: Cannot load settings area for parameters.").grid(row=1, column=0, columnspan=2)
                    logger.critical("param_frame or its canvas window item could not be ensured in _on_type_selected.")
                    return
            else:
                 logger.critical("Canvas not available in _on_type_selected.")
                 return


        self.param_widgets = {}
        self.target_color_swatch_images.clear()
        self.analysis_swatch_images.clear()
        self.multi_image_sub_images_data.clear()
        self.multi_image_anchor_preview_image_pil = None
        self.multi_image_anchor_preview_image_tk = None


        if hasattr(self, 'param_frame') and self.param_frame and self.param_frame.winfo_exists():
            cols, rows = self.param_frame.grid_size()
            for i in range(cols): self.param_frame.grid_columnconfigure(i, weight=0)
            for i in range(rows): self.param_frame.grid_rowconfigure(i, weight=0)


        create_func = self._filtered_condition_type_settings.get(selected_internal_type, {}).get("create_params_ui")
        last_param_row_index = 0

        if create_func and callable(create_func):
            try:
                create_func(self)
                if hasattr(self, 'param_frame') and self.param_frame and self.param_frame.winfo_exists():
                    self.param_frame.update_idletasks()
                    last_param_row_index = self.param_frame.grid_size()[1]
            except Exception as e:
                 logger.error(f"Error creating UI for condition type '{selected_internal_type}': {e}.", exc_info=True)
                 if hasattr(self, 'param_frame') and self.param_frame and self.param_frame.winfo_exists():
                     ttk.Label(self.param_frame, text=f"Error building UI for {selected_display_key}:\n{str(e)[:100]}", foreground="red").grid(row=0, column=0, columnspan=4, sticky="ew")
                 last_param_row_index = 1
        else:
             if hasattr(self, 'param_frame') and self.param_frame and self.param_frame.winfo_exists():
                 no_param_label = ttk.Label(self.param_frame, text="(No parameters required for this type)")
                 no_param_label.grid(row=0, column=0, columnspan=4, sticky="w", padx=5, pady=5)
                 self.param_widgets["_no_params_label_"] = [no_param_label]
             last_param_row_index = 1

        show_preview_area = self._filtered_condition_type_settings.get(selected_internal_type, {}).get("show_preview", False)

        if not (hasattr(self, '_preview_container_frame') and self._preview_container_frame and self._preview_container_frame.winfo_exists()):
            self._create_preview_area_widgets()

        if not (hasattr(self, '_color_analysis_frame_container') and self._color_analysis_frame_container and self._color_analysis_frame_container.winfo_exists()):
            self._create_color_analysis_area_widgets()

        if show_preview_area:
            if hasattr(self, '_preview_container_frame') and self._preview_container_frame:
                self._preview_container_frame.grid(row=last_param_row_index, column=0, columnspan=4, padx=5, pady=10, sticky="nsew")
                last_param_row_index += 1
            
            if selected_internal_type == TextOnScreenCondition.TYPE or selected_internal_type == TextInRelativeRegionCondition.TYPE:
                if hasattr(self, 'recognized_text_label') and self.recognized_text_label.winfo_exists():
                     self.recognized_text_label.grid()
                self._recognized_text_var.set("Recognized text preview...")
            else:
                if hasattr(self, 'recognized_text_label') and self.recognized_text_label.winfo_exists():
                     self.recognized_text_label.grid_remove()
                self._recognized_text_var.set("")
            self._clear_preview()
        elif hasattr(self, '_preview_container_frame') and self._preview_container_frame: 
            self._preview_container_frame.grid_remove()
            self._clear_preview()
            self._recognized_text_var.set("")

        if selected_internal_type == RegionColorCondition.TYPE and show_preview_area:
            if hasattr(self, '_color_analysis_frame_container') and self._color_analysis_frame_container: 
                self._color_analysis_frame_container.grid(row=last_param_row_index, column=0, columnspan=4, padx=5, pady=5, sticky="ew")
            self.after_idle(lambda: self._update_color_analysis_display(None))
        elif hasattr(self, '_color_analysis_frame_container') and self._color_analysis_frame_container: 
            self._color_analysis_frame_container.grid_remove()
            self.after_idle(lambda: self._update_color_analysis_display(None))

        params_to_populate = {}
        if self._current_condition_obj and hasattr(self._current_condition_obj, 'type') and self._current_condition_obj.type == selected_internal_type:
             params_to_populate = self._current_condition_obj.params
        else:
            existing_id = self._current_condition_obj.id if self._current_condition_obj and hasattr(self._current_condition_obj, 'id') else None
            existing_name = self._current_condition_obj.name if self._current_condition_obj and hasattr(self._current_condition_obj, 'name') else None
            existing_is_monitored = self._current_condition_obj.is_monitored_by_ai_brain if self._current_condition_obj and hasattr(self._current_condition_obj, 'is_monitored_by_ai_brain') else False

            temp_default_cond_data = {
                "type": selected_internal_type, "params": {}, "id": existing_id, "name": existing_name,
                "is_monitored_by_ai_brain": existing_is_monitored
            }
            default_cond_for_new_type = create_condition(temp_default_cond_data) # type: ignore
            params_to_populate = default_cond_for_new_type.params if default_cond_for_new_type and hasattr(default_cond_for_new_type, 'params') else {}
            if not (self.initial_condition_data and self.initial_condition_data.get("type") == selected_internal_type):
                 self._current_condition_obj = default_cond_for_new_type # type: ignore


        self._populate_params(params_to_populate)

        if hasattr(self, 'canvas') and self.canvas and self.canvas.winfo_exists(): 
            self.canvas.after_idle(self._update_scroll_region)

    def _create_preview_area_widgets(self):
        if not (self.param_frame and self.param_frame.winfo_exists()): return
        self._preview_container_frame = ttk.Frame(self.param_frame)
        self._preview_container_frame.grid_columnconfigure(0, weight=1)
        preview_width, preview_height = 250, 180
        self.preview_label = ttk.Label(self._preview_container_frame, text="Preview Area", anchor="center", relief="sunken", borderwidth=1, justify=tk.CENTER)
        self.preview_label.grid(row=0, column=0, rowspan=2, padx=(0,5), pady=0, sticky="nsew")
        self.preview_label.config(width=int(preview_width / 7.5))
        self.preview_label.grid_propagate(False)
        self.preview_button = ttk.Button(self._preview_container_frame, text="Preview Processing", command=self._trigger_preview_preprocessing)
        self.preview_button.grid(row=0, column=1, padx=(5, 0), pady=(0,2), sticky="ne")
        self.recognized_text_label = ttk.Label(self._preview_container_frame, textvariable=self._recognized_text_var, anchor="nw", wraplength=preview_width-10, justify=tk.LEFT, relief="sunken", borderwidth=1)
        self.recognized_text_label.grid(row=2, column=0, columnspan=2, padx=0, pady=(5,0), sticky="nsew")
        self.param_widgets["_preview_label_widget_"] = [self.preview_label]
        self.param_widgets["_preview_button_widget_"] = [self.preview_button]
        self.param_widgets["_recognized_text_label_widget_"] = [self.recognized_text_label]

    def _analyze_top_n_colors_in_preview(self):
        if not (hasattr(self, '_current_preview_image_pil') and self._current_preview_image_pil):
            messagebox.showinfo("Info", "No image in preview to analyze. Please capture or load an image first.", parent=self)
            return
        if not (hasattr(self, 'top_n_entry') and self.top_n_entry and self.top_n_entry.winfo_exists()): # Thêm kiểm tra self.top_n_entry
            logger.error("ConditionSettings: Top N entry widget not found for analysis.")
            messagebox.showerror("UI Error", "Top N input field is missing.", parent=self)
            return

        try:
            n_colors_str = self.top_n_entry.get()
            n_colors = int(n_colors_str) if n_colors_str and n_colors_str.isdigit() else 5
            if n_colors <= 0:
                messagebox.showerror("Input Error", "Number of colors (N) for Top N analysis must be a positive integer.", parent=self)
                if hasattr(self, 'top_n_entry') and self.top_n_entry.winfo_exists(): self.top_n_entry.focus_set()
                return
        except ValueError:
            messagebox.showerror("Input Error", "Invalid number entered for N (Top N colors).", parent=self)
            if hasattr(self, 'top_n_entry') and self.top_n_entry.winfo_exists(): self.top_n_entry.focus_set()
            return
        except Exception as e_get_n:
            logger.error(f"Error getting N for Top N analysis: {e_get_n}", exc_info=True)
            messagebox.showerror("Error", f"Could not get N value: {e_get_n}", parent=self)
            return

        try:
            image_np_rgb = np.array(self._current_preview_image_pil.convert("RGB"))
        except Exception as e_conv:
            logger.error(f"Error converting preview PIL image to NumPy for Top N analysis: {e_conv}")
            messagebox.showerror("Image Error", "Could not process preview image for color analysis.", parent=self)
            return

        self.after_idle(lambda: self._update_color_analysis_display(image_np_rgb, analyze_top_n=n_colors))

    def _analyze_target_colors_in_preview(self):
        if not (hasattr(self, '_current_preview_image_pil') and self._current_preview_image_pil):
            messagebox.showinfo("Info", "No image in preview to analyze. Please capture or load an image first.", parent=self)
            return

        target_colors_from_params = []
        if self._current_condition_obj and hasattr(self._current_condition_obj, 'params') and isinstance(self._current_condition_obj.params, dict):
             target_colors_from_params = self._current_condition_obj.params.get("target_colors", [])

        if not target_colors_from_params or not isinstance(target_colors_from_params, list):
            messagebox.showinfo("Info", "No target colors are currently defined for this condition. Add some target colors first.", parent=self)
            self.after_idle(lambda: self._update_color_analysis_display(None))
            return

        try:
            image_np_rgb = np.array(self._current_preview_image_pil.convert("RGB"))
        except Exception as e_conv:
            logger.error(f"Error converting preview PIL image to NumPy for target color analysis: {e_conv}")
            messagebox.showerror("Image Error", "Could not process preview image for color analysis.", parent=self)
            return

        self.after_idle(lambda: self._update_color_analysis_display(image_np_rgb, colors_to_analyze_defs=target_colors_from_params))

    def _create_color_analysis_area_widgets(self):
        if not (self.param_frame and self.param_frame.winfo_exists()): return
        self._color_analysis_frame_container = ttk.Frame(self.param_frame)
        self._color_analysis_frame = ttk.LabelFrame(self._color_analysis_frame_container, text="Color Analysis of Preview")
        self._color_analysis_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.color_analysis_tree = ttk.Treeview(self._color_analysis_frame, columns=("hex", "percentage"), show="headings", height=5)
        self.color_analysis_tree.heading("#0", text="Color"); self.color_analysis_tree.column("#0", width=40, anchor="center", stretch=False)
        self.color_analysis_tree.heading("hex", text="HEX"); self.color_analysis_tree.column("hex", width=80, anchor="w")
        self.color_analysis_tree.heading("percentage", text="% Preview"); self.color_analysis_tree.column("percentage", width=100, anchor="e")
        self.color_analysis_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0), pady=5)
        ca_scrollbar = ttk.Scrollbar(self._color_analysis_frame, orient="vertical", command=self.color_analysis_tree.yview)
        ca_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,5), pady=5)
        self.color_analysis_tree.configure(yscrollcommand=ca_scrollbar.set)

        top_n_frame = ttk.Frame(self._color_analysis_frame)
        top_n_frame.pack(fill=tk.X, pady=5, padx=5)
        ttk.Label(top_n_frame, text="N:").pack(side=tk.LEFT, padx=(0,2))
        self.top_n_entry = ttk.Entry(top_n_frame, width=4, validate="key", validatecommand=(self.vcmd_integer, "%P"))
        self.top_n_entry.insert(0, "5")
        self.top_n_entry.pack(side=tk.LEFT, padx=2)
        self.analyze_top_n_button = ttk.Button(top_n_frame, text="Find Top N", command=self._analyze_top_n_colors_in_preview)
        self.analyze_top_n_button.pack(side=tk.LEFT, padx=5)
        self.analyze_targets_button = ttk.Button(top_n_frame, text="Analyze Targets", command=self._analyze_target_colors_in_preview)
        self.analyze_targets_button.pack(side=tk.LEFT, padx=5)

    def _add_param_entry(self, key: str, text: str, row: int, col: int = 0, master: Optional[ttk.Frame] = None, **kwargs: Any) -> ttk.Entry:
        parent = master if master and master.winfo_exists() else self.param_frame 
        if not (parent and parent.winfo_exists()):
            logger.error(f"_add_param_entry: Parent widget for key '{key}' does not exist.")
            return ttk.Entry(self) 

        label = ttk.Label(parent, text=text)
        label.grid(row=row, column=col, padx=kwargs.get("padx", 5), pady=kwargs.get("pady", 2), sticky=tk.W)
        entry = ttk.Entry(parent, width=kwargs.get("width", 15))
        validate = kwargs.get("validate", None)
        if validate == "integer": entry.config(validate="key", validatecommand=(self.vcmd_integer, "%P"))
        elif validate == "float": entry.config(validate="key", validatecommand=(self.vcmd_float, "%P"))
        elif validate == "int_tuple2": entry.config(validate="key", validatecommand=(self.vcmd_int_tuple2, "%P"))
        entry.grid(row=row, column=col + 1, padx=kwargs.get("padx", 5), pady=kwargs.get("pady", 2), sticky=kwargs.get("sticky", tk.EW))
        self.param_widgets[key] = [label, entry]
        self._bind_mouse_wheel(entry); self._bind_mouse_wheel(label)
        return entry

    def _add_param_checkbox(self, key: str, text: str, row: int, col: int = 0, master: Optional[ttk.Frame] = None, variable: Optional[tk.BooleanVar] = None, **kwargs: Any) -> Tuple[ttk.Checkbutton, tk.BooleanVar]:
        parent = master if master and master.winfo_exists() else self.param_frame
        if not (parent and parent.winfo_exists()):
            logger.error(f"_add_param_checkbox: Parent widget for key '{key}' does not exist.")
            dummy_var = tk.BooleanVar()
            return ttk.Checkbutton(self, variable=dummy_var), dummy_var

        if variable is None: variable = tk.BooleanVar()
        checkbox = ttk.Checkbutton(parent, text=text, variable=variable, command=kwargs.get("command", None))
        checkbox.grid(row=row, column=col, columnspan=kwargs.get("columnspan", 1), padx=kwargs.get("padx", 5), pady=kwargs.get("pady", 1), sticky=kwargs.get("sticky", tk.W))
        self.param_widgets[key] = [checkbox, variable]
        self._bind_mouse_wheel(checkbox)
        return checkbox, variable

    def _add_param_combobox(self, key: str, text: str, row: int, col: int = 0, master: Optional[ttk.Frame] = None, values: Optional[list] = None, variable: Optional[tk.StringVar] = None, **kwargs: Any) -> Tuple[ttk.Combobox, tk.StringVar]:
         parent = master if master and master.winfo_exists() else self.param_frame
         if not (parent and parent.winfo_exists()):
            logger.error(f"_add_param_combobox: Parent widget for key '{key}' does not exist.")
            dummy_var = tk.StringVar()
            return ttk.Combobox(self, textvariable=dummy_var), dummy_var

         label = ttk.Label(parent, text=text)
         label.grid(row=row, column=col, padx=kwargs.get("padx", 5), pady=kwargs.get("pady", 2), sticky=tk.W)
         if variable is None: variable = tk.StringVar()
         combobox = ttk.Combobox(parent, textvariable=variable, values=values or [], state=kwargs.get("state", "readonly"), width=kwargs.get("width", 18))
         combobox.grid(row=row, column=col + 1, padx=kwargs.get("padx", 5), pady=kwargs.get("pady", 2), sticky=kwargs.get("sticky", tk.EW))
         self.param_widgets[key] = [label, combobox, variable]
         self._bind_mouse_wheel(combobox); self._bind_mouse_wheel(label)
         return combobox, variable

    def _add_param_button(self, key: str, text: str, row: int, col: int = 0, master: Optional[ttk.Frame] = None, command: Optional[Callable] = None, **kwargs: Any) -> ttk.Button:
        parent = master if master and master.winfo_exists() else self.param_frame
        if not (parent and parent.winfo_exists()):
            logger.error(f"_add_param_button: Parent widget for key '{key}' does not exist.")
            return ttk.Button(self)

        button = ttk.Button(parent, text=text, command=command, width=kwargs.get("width", 15))
        button.grid(row=row, column=col, columnspan=kwargs.get("columnspan", 1), padx=kwargs.get("padx", 5), pady=kwargs.get("pady", 5), sticky=kwargs.get("sticky", tk.EW))
        self.param_widgets[key] = [button]
        self._bind_mouse_wheel(button)
        return button

    def _add_param_separator(self, row: int, col: int = 0, columnspan: int = 4, master: Optional[ttk.Frame] = None) -> None:
        parent = master if master and master.winfo_exists() else self.param_frame
        if not (parent and parent.winfo_exists()): return
        sep = ttk.Separator(parent, orient=tk.HORIZONTAL)
        sep.grid(row=row, column=col, columnspan=columnspan, padx=5, pady=5, sticky=tk.EW)

    def _create_none_params(self) -> None:
        if not (self.param_frame and self.param_frame.winfo_exists()): return
        ttk.Label(self.param_frame, text="(Condition is always true)").grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

    def _create_color_at_position_params(self) -> None:
        if not (self.param_frame and self.param_frame.winfo_exists()): return
        frame = self.param_frame
        frame.grid_columnconfigure(1, weight=0); frame.grid_columnconfigure(2, weight=0)
        row = 0
        self._add_param_entry("abs_color_x", "X Coordinate (Abs):", row, col=0, master=frame, validate="integer", width=7)
        self._add_param_entry("abs_color_y", "Y Coordinate (Abs):", row, col=2, master=frame, validate="integer", width=7); row += 1
        hex_entry = self._add_param_entry("color_hex", "Target Color (Hex):", row, col=0, master=frame, width=9)
        self.color_swatch = tk.Label(frame, text="    ", bg="#000000", relief="sunken", borderwidth=1)
        self.color_swatch.grid(row=row, column=2, padx=(0,5), pady=2, sticky="w")
        if hex_entry: hex_entry.bind("<KeyRelease>", self._update_color_swatch); hex_entry.bind("<FocusOut>", self._update_color_swatch); row += 1
        self._add_param_entry("tolerance", "Tolerance (0-765):", row, col=0, master=frame, validate="integer", width=7); row += 1
        if _CaptureDepsImported:
             self._add_param_button("capture_button", "Pick Color Point", row=row, col=0, master=frame, columnspan=3, command=lambda: self._start_coordinate_capture(num_points=1))

    def _update_color_swatch(self, event: Optional[tk.Event] = None) -> None:
        hex_widget_info = self.param_widgets.get("color_hex")
        hex_entry = self._find_widget_in_list(hex_widget_info, ttk.Entry)
        if hex_entry and hasattr(self, 'color_swatch') and self.color_swatch.winfo_exists():
            hex_value = hex_entry.get().strip()
            try:
                if not hex_value.startswith('#'): hex_value = '#' + hex_value
                if len(hex_value) == 4: hex_value = '#' + ''.join([c*2 for c in hex_value[1:]])
                if re.fullmatch(r'#[0-9a-fA-F]{6}', hex_value): self.color_swatch.config(bg=hex_value)
                else: self.color_swatch.config(bg="SystemButtonFace")
            except tk.TclError: self.color_swatch.config(bg="SystemButtonFace")

    def _create_image_on_screen_params(self) -> None:
        if not (self.param_frame and self.param_frame.winfo_exists()): return
        parent = self.param_frame; parent.grid_columnconfigure(1, weight=1); current_row = 0
        region_frame = ttk.LabelFrame(parent, text="Search Region", padding=5)
        region_frame.grid(row=current_row, column=0, columnspan=4, padx=5, pady=5, sticky="ew"); current_row += 1
        region_frame.grid_columnconfigure(1, weight=0); region_frame.grid_columnconfigure(3, weight=0); region_frame.grid_columnconfigure(4, weight=0)
        self._add_param_entry("region_x1", "X1:", 0, col=0, master=region_frame, validate="integer", width=6)
        self._add_param_entry("region_y1", "Y1:", 1, col=0, master=region_frame, validate="integer", width=6)
        self._add_param_entry("region_x2", "X2:", 0, col=2, master=region_frame, validate="integer", width=6)
        self._add_param_entry("region_y2", "Y2:", 1, col=2, master=region_frame, validate="integer", width=6)
        if _CaptureDepsImported: self._add_param_button("capture_region_btn", "Select Region", row=0, col=4, rowspan=2, master=region_frame, width=12, sticky="ns", command=lambda: self._start_region_capture(for_color=False))

        img_frame = ttk.LabelFrame(parent, text="Template Image", padding=5)
        img_frame.grid(row=current_row, column=0, columnspan=4, padx=5, pady=5, sticky="ew"); current_row += 1
        img_frame.grid_columnconfigure(1, weight=1)
        self._add_param_entry("image_path", "Path:", 0, col=0, master=img_frame, width=40)
        self._add_param_button("browse_btn", "Browse...", row=0, col=2, master=img_frame, width=10, command=self._browse_image_path)
        if _CaptureDepsImported and self.image_storage: self._add_param_button("capture_save_btn", "Capture New", row=0, col=3, master=img_frame, width=12, command=lambda: self._start_region_capture(for_color=False, save_new_image=True))

        match_frame = ttk.LabelFrame(parent, text="Matching & Selection", padding=5)
        match_frame.grid(row=current_row, column=0, columnspan=4, padx=5, pady=5, sticky="ew"); current_row += 1
        match_frame.grid_columnconfigure(1, weight=1); match_frame.grid_columnconfigure(3, weight=1); match_row = 0
        self._add_param_combobox("matching_method", "Method:", match_row, col=0, master=match_frame, values=["Template", "Feature"], width=10)
        self._add_param_entry("threshold", "Threshold:", match_row, col=2, master=match_frame, validate="float", width=6); match_row += 1
        self._add_param_combobox("template_matching_method", "Template Alg:", match_row, col=0, master=match_frame, values=["TM_CCOEFF_NORMED", "TM_CCORR_NORMED", "TM_SQDIFF_NORMED"], width=18)
        
        self._add_param_combobox("selection_strategy", "Selection Strategy:", match_row, col=2, master=match_frame,
                                 values=["first_found", "top_most", "bottom_most", "left_most", "right_most",
                                         "closest_to_center_search_region", "closest_to_last_click", "closest_to_point"],
                                 width=20)
        match_row += 1
        self.ref_point_x_entry = self._add_param_entry("reference_point_x", "Ref X (for closest_to_point):", match_row, col=0, master=match_frame, validate="integer", width=6)
        self.ref_point_y_entry = self._add_param_entry("reference_point_y", "Ref Y:", match_row, col=2, master=match_frame, validate="integer", width=6)
        self._toggle_ref_point_visibility()
        if self.param_widgets.get("selection_strategy"):
            combo_widget = self._find_widget_in_list(self.param_widgets["selection_strategy"], ttk.Combobox)
            if combo_widget: combo_widget.bind("<<ComboboxSelected>>", self._toggle_ref_point_visibility)

        match_row += 1
        self._add_param_separator(match_row, columnspan=4, master=match_frame); match_row += 1
        self._add_param_entry("orb_nfeatures", "ORB Features:", match_row, col=0, master=match_frame, validate="integer", width=8)
        self._add_param_entry("min_feature_matches", "Min Matches:", match_row, col=2, master=match_frame, validate="integer", width=6); match_row += 1
        self._add_param_entry("homography_inlier_ratio", "Inlier Ratio:", match_row, col=0, master=match_frame, validate="float", width=8); match_row += 1


        proc_frame = ttk.LabelFrame(parent, text="Preprocessing Options", padding=5)
        proc_frame.grid(row=current_row, column=0, columnspan=4, padx=5, pady=5, sticky="nsew"); current_row += 1
        proc_frame.grid_columnconfigure(1, weight=0); proc_frame.grid_columnconfigure(3, weight=0); proc_row = 0
        self._add_param_checkbox("grayscale", "Grayscale", proc_row, col=0, master=proc_frame, variable=self._grayscale_var, columnspan=1);
        self._add_param_checkbox("binarization", "Binarization (Otsu)", proc_row, col=2, master=proc_frame, variable=self._binarization_var, columnspan=1); proc_row+=1
        self._add_param_checkbox("gaussian_blur", "Gaussian Blur", proc_row, col=0, master=proc_frame, variable=self._gaussian_blur_var, columnspan=1);
        self._add_param_entry("gaussian_blur_kernel", "Kernel(w,h):", proc_row, col=1, master=proc_frame, validate="int_tuple2", width=6, sticky=tk.W);
        self._add_param_checkbox("median_blur", "Median Blur", proc_row, col=2, master=proc_frame, variable=self._median_blur_var, columnspan=1);
        self._add_param_entry("median_blur_kernel", "Kernel(k):", proc_row, col=3, master=proc_frame, validate="integer", width=6, sticky=tk.W); proc_row+=1
        self._add_param_checkbox("clahe", "CLAHE", proc_row, col=0, master=proc_frame, variable=self._clahe_var, columnspan=1);
        self._add_param_entry("clahe_clip_limit", "Clip Limit:", proc_row, col=1, master=proc_frame, validate="float", width=6, sticky=tk.W);
        self._add_param_entry("clahe_tile_grid_size", "Tile(w,h):", proc_row, col=3, master=proc_frame, validate="int_tuple2", width=6, sticky=tk.W); proc_row+=1
        self._add_param_checkbox("bilateral_filter", "Bilateral Filter", proc_row, col=0, master=proc_frame, variable=self._bilateral_filter_var, columnspan=1);
        self._add_param_entry("bilateral_d", "Diameter(d):", proc_row, col=1, master=proc_frame, validate="integer", width=6, sticky=tk.W); proc_row+=1
        self._add_param_entry("bilateral_sigma_color", "Sigma Color:", proc_row, col=1, master=proc_frame, validate="float", width=6, sticky=tk.W);
        self._add_param_entry("bilateral_sigma_space", "Sigma Space:", proc_row, col=3, master=proc_frame, validate="float", width=6, sticky=tk.W); proc_row+=1
        self._add_param_checkbox("canny_edges", "Canny Edges", proc_row, col=0, master=proc_frame, variable=self._canny_edges_var, columnspan=1);
        self._add_param_entry("canny_threshold1", "Threshold 1:", proc_row, col=1, master=proc_frame, validate="float", width=6, sticky=tk.W);
        self._add_param_entry("canny_threshold2", "Threshold 2:", proc_row, col=3, master=proc_frame, validate="float", width=6, sticky=tk.W); proc_row+=1
        self._bind_recursive_mousewheel(parent)

    def _toggle_ref_point_visibility(self, event=None):
        strategy = self._get_widget_value("selection_strategy", "first_found")
        show_ref_point = (strategy == "closest_to_point")

        ref_x_widgets = self.param_widgets.get("reference_point_x")
        ref_y_widgets = self.param_widgets.get("reference_point_y")

        if ref_x_widgets and isinstance(ref_x_widgets, list):
            for widget in ref_x_widgets:
                if widget.winfo_exists():
                    if show_ref_point: widget.grid()
                    else: widget.grid_remove()
        if ref_y_widgets and isinstance(ref_y_widgets, list):
            for widget in ref_y_widgets:
                if widget.winfo_exists():
                    if show_ref_point: widget.grid()
                    else: widget.grid_remove()
        if self.param_frame and self.param_frame.winfo_exists(): 
             self.param_frame.update_idletasks()
             if self.canvas and self.canvas.winfo_exists():
                 self.canvas.after_idle(self._update_scroll_region)


    def _browse_image_path(self) -> None:
        if not self.image_storage: messagebox.showwarning("Warning", "Image storage location not configured.", parent=self); return
        initial_dir = os.path.abspath(self.image_storage.storage_dir)
        filetypes = [("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All Files", "*.*")]
        filepath = filedialog.askopenfilename(title="Select Template Image", initialdir=initial_dir, filetypes=filetypes, parent=self)
        if filepath:
            try:
                base_path = os.path.abspath(".")
                rel_path = os.path.relpath(filepath, base_path)
                rel_path_normalized = rel_path.replace('\\', '/')
                self._set_widget_value("image_path", rel_path_normalized)
            except ValueError:
                self._set_widget_value("image_path", filepath)
            except Exception as e: messagebox.showerror("Error", f"Could not process image path: {e}", parent=self)

    def _browse_user_words_file_path(self) -> None:
        initial_dir_text = os.path.abspath(".")
        if self.image_storage:
            initial_dir_text = os.path.abspath(self.image_storage.storage_dir)

        filepath = filedialog.askopenfilename(
            title="Select User Words File for OCR",
            initialdir=initial_dir_text,
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            parent=self
        )
        if filepath:
            try:
                base_path = os.path.abspath(".")
                rel_path = os.path.relpath(filepath, base_path)
                rel_path_normalized = rel_path.replace('\\', '/')
                self._set_widget_value("user_words_file_path", rel_path_normalized)
            except ValueError:
                self._set_widget_value("user_words_file_path", filepath)
            except Exception as e:
                messagebox.showerror("Error", f"Could not process user words file path: {e}", parent=self)


    def _create_text_on_screen_params(self) -> None:
        if not (self.param_frame and self.param_frame.winfo_exists()): return
        parent = self.param_frame; parent.grid_columnconfigure(1, weight=1); current_row = 0
        region_frame = ttk.LabelFrame(parent, text="Search Region", padding=5)
        region_frame.grid(row=current_row, column=0, columnspan=4, padx=5, pady=5, sticky="ew"); current_row += 1
        region_frame.grid_columnconfigure(1, weight=0); region_frame.grid_columnconfigure(3, weight=0); region_frame.grid_columnconfigure(4, weight=0)
        self._add_param_entry("region_x1", "X1:", 0, col=0, master=region_frame, validate="integer", width=6)
        self._add_param_entry("region_y1", "Y1:", 1, col=0, master=region_frame, validate="integer", width=6)
        self._add_param_entry("region_x2", "X2:", 0, col=2, master=region_frame, validate="integer", width=6)
        self._add_param_entry("region_y2", "Y2:", 1, col=2, master=region_frame, validate="integer", width=6)
        if _CaptureDepsImported: self._add_param_button("capture_ocr_btn", "Select & OCR", row=0, col=4, rowspan=2, master=region_frame, width=12, sticky="ns", command=lambda: self._start_region_capture(for_color=False))

        text_frame = ttk.LabelFrame(parent, text="Text & OCR Options", padding=5)
        text_frame.grid(row=current_row, column=0, columnspan=4, padx=5, pady=5, sticky="ew"); current_row += 1
        text_frame.grid_columnconfigure(1, weight=1); text_frame.grid_columnconfigure(3, weight=0); text_frame.grid_columnconfigure(5, weight=1); ocr_row = 0
        self._add_param_entry("target_text", "Target Text / Regex:", ocr_row, col=0, master=text_frame, width=30);
        self._add_param_checkbox("case_sensitive", "Case Sensitive", ocr_row, col=2, master=text_frame, columnspan=1, sticky=tk.W);
        self._add_param_checkbox("use_regex", "Use Regex", ocr_row, col=3, master=text_frame, columnspan=1, sticky=tk.W); ocr_row+=1
        self._add_param_entry("ocr_language", "Lang (e.g., eng, vie):", ocr_row, col=0, master=text_frame, width=8, sticky=tk.W);
        self._add_param_entry("ocr_psm", "PSM (0-13):", ocr_row, col=2, master=text_frame, validate="integer", width=6, sticky=tk.W);
        self._add_param_entry("ocr_char_whitelist", "Whitelist Chars:", ocr_row, col=4, master=text_frame, width=15, sticky=tk.EW); ocr_row+=1
        self._add_param_entry("user_words_file_path", "User Words File (txt):", ocr_row, col=0, master=text_frame, width=30, sticky=tk.EW)
        self._add_param_button("browse_user_words_btn", "Browse...", ocr_row, col=2, master=text_frame, width=10, command=self._browse_user_words_file_path, sticky=tk.W); ocr_row+=1


        proc_frame = ttk.LabelFrame(parent, text="OCR Preprocessing Options", padding=5)
        proc_frame.grid(row=current_row, column=0, columnspan=4, padx=5, pady=5, sticky="nsew"); current_row += 1
        proc_frame.grid_columnconfigure(1, weight=0); proc_frame.grid_columnconfigure(3, weight=0); proc_row = 0
        self._add_param_checkbox("grayscale", "Grayscale", proc_row, col=0, master=proc_frame, variable=self._grayscale_var, columnspan=1);
        self._add_param_checkbox("adaptive_threshold", "Adaptive Threshold", proc_row, col=2, master=proc_frame, variable=self._adaptive_threshold_var, columnspan=1); proc_row+=1
        self._add_param_entry("ocr_upscale_factor", "Upscale Factor:", proc_row, col=0, master=proc_frame, validate="float", width=6, sticky=tk.W);
        self._add_param_checkbox("median_blur", "Median Blur", proc_row, col=2, master=proc_frame, variable=self._median_blur_var, columnspan=1);
        self._add_param_entry("median_blur_kernel", "Kernel(k):", proc_row, col=3, master=proc_frame, validate="integer", width=6, sticky=tk.W); proc_row+=1
        self._add_param_checkbox("gaussian_blur", "Gaussian Blur", proc_row, col=0, master=proc_frame, variable=self._gaussian_blur_var, columnspan=1);
        self._add_param_entry("gaussian_blur_kernel", "Kernel(w,h):", proc_row, col=1, master=proc_frame, validate="int_tuple2", width=6, sticky=tk.W);
        self._add_param_checkbox("clahe", "CLAHE", proc_row, col=2, master=proc_frame, variable=self._clahe_var, columnspan=1);
        self._add_param_entry("clahe_clip_limit", "Clip Limit:", proc_row, col=3, master=proc_frame, validate="float", width=6, sticky=tk.W); proc_row+=1
        self._add_param_entry("clahe_tile_grid_size", "CLAHE Tile(w,h):", proc_row, col=1, master=proc_frame, validate="int_tuple2", width=6, sticky=tk.W); proc_row+=1
        self._bind_recursive_mousewheel(parent)

    def _create_window_exists_params(self) -> None:
        if not (self.param_frame and self.param_frame.winfo_exists()): return
        parent = self.param_frame; parent.grid_columnconfigure(1, weight=1)
        frame = ttk.LabelFrame(parent, text="Window Identification", padding=5)
        frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew"); frame.grid_columnconfigure(1, weight=1); row=0
        self._add_param_entry("window_title", "Window Title (contains):", row, master=frame, width=40); row += 1
        self._add_param_entry("window_class", "Window Class (exact):", row, master=frame, width=40); row += 1
        ttk.Label(frame, text="(Leave blank to ignore property)").grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)

    def _create_process_exists_params(self) -> None:
        if not (self.param_frame and self.param_frame.winfo_exists()): return
        parent = self.param_frame; parent.grid_columnconfigure(1, weight=1)
        frame = ttk.LabelFrame(parent, text="Process Identification", padding=5)
        frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew"); frame.grid_columnconfigure(1, weight=1); row=0
        self._add_param_entry("process_name", "Process Name (e.g., notepad.exe):", row, master=frame, width=40); row += 1

    def _create_text_in_relative_region_params(self) -> None:
        if not (self.param_frame and self.param_frame.winfo_exists()): return
        parent = self.param_frame
        parent.grid_columnconfigure(1, weight=1)
        current_main_row = 0

        overall_region_frame = ttk.LabelFrame(parent, text="Overall Search Region (for Anchor Image)", padding=5)
        overall_region_frame.grid(row=current_main_row, column=0, columnspan=4, padx=5, pady=5, sticky="ew"); current_main_row += 1
        overall_region_frame.grid_columnconfigure(1, weight=0); overall_region_frame.grid_columnconfigure(3, weight=0); overall_region_frame.grid_columnconfigure(4, weight=0)
        self._add_param_entry("region_x1", "X1:", 0, col=0, master=overall_region_frame, validate="integer", width=6)
        self._add_param_entry("region_y1", "Y1:", 1, col=0, master=overall_region_frame, validate="integer", width=6)
        self._add_param_entry("region_x2", "X2:", 0, col=2, master=overall_region_frame, validate="integer", width=6, sticky="w")
        self._add_param_entry("region_y2", "Y2:", 1, col=2, master=overall_region_frame, validate="integer", width=6, sticky="w")
        if _CaptureDepsImported:
            self._add_param_button("capture_overall_region_btn", "Select Overall Region",
                                   row=0, col=4, rowspan=2, master=overall_region_frame, width=18, sticky="ns",
                                   command=lambda: self._start_region_capture(for_color=False, region_keys_prefix=""))

        anchor_frame = ttk.LabelFrame(parent, text="Anchor Image", padding=5)
        anchor_frame.grid(row=current_main_row, column=0, columnspan=4, padx=5, pady=5, sticky="ew"); current_main_row += 1
        anchor_frame.grid_columnconfigure(1, weight=1); anchor_row = 0
        self._add_param_entry("anchor_image_path", "Path:", anchor_row, col=0, master=anchor_frame, width=40)
        self._add_param_button("browse_anchor_btn", "Browse...", anchor_row, col=2, master=anchor_frame, width=10, command=lambda: self._browse_specific_image_path("anchor_image_path"))
        if _CaptureDepsImported and self.image_storage:
            self._add_param_button("capture_anchor_btn", "Capture Anchor", anchor_row, col=3, master=anchor_frame, width=14, command=lambda: self._start_region_capture(for_color=False, save_new_image=True, image_path_key="anchor_image_path"))
        anchor_row += 1
        self._add_param_combobox("anchor_matching_method", "Match Method:", anchor_row, col=0, master=anchor_frame, values=["Template", "Feature"], width=10)
        self._add_param_entry("anchor_threshold", "Threshold:", anchor_row, col=2, master=anchor_frame, validate="float", width=6); anchor_row += 1


        relative_frame = ttk.LabelFrame(parent, text="Relative OCR Region (from Anchor)", padding=5)
        relative_frame.grid(row=current_main_row, column=0, columnspan=4, padx=5, pady=5, sticky="ew"); current_main_row += 1
        relative_frame.grid_columnconfigure(1, weight=0); relative_frame.grid_columnconfigure(3, weight=0); rel_row = 0
        self._add_param_entry("relative_x_offset", "X Offset:", rel_row, col=0, master=relative_frame, validate="integer", width=6)
        self._add_param_entry("relative_y_offset", "Y Offset:", rel_row, col=2, master=relative_frame, validate="integer", width=6); rel_row += 1
        self._add_param_entry("relative_width", "Width:", rel_row, col=0, master=relative_frame, validate="integer", width=6)
        self._add_param_entry("relative_height", "Height:", rel_row, col=2, master=relative_frame, validate="integer", width=6); rel_row += 1
        self._add_param_combobox("relative_to_corner", "Offset From Corner:", rel_row, col=0, master=relative_frame, values=["top_left", "top_right", "bottom_left", "bottom_right", "center"], width=15); rel_row += 1

        ocr_text_frame = ttk.LabelFrame(parent, text="Text to Find & OCR Options (for Relative Region)", padding=5)
        ocr_text_frame.grid(row=current_main_row, column=0, columnspan=4, padx=5, pady=5, sticky="ew"); current_main_row += 1
        ocr_text_frame.grid_columnconfigure(1, weight=1); ocr_row_rel = 0
        self._add_param_entry("text_to_find", "Target Text/Regex:", ocr_row_rel, col=0, master=ocr_text_frame, width=30)
        self._add_param_checkbox("ocr_case_sensitive", "Case Sensitive", ocr_row_rel, col=2, master=ocr_text_frame)
        self._add_param_checkbox("ocr_use_regex", "Use Regex", ocr_row_rel, col=3, master=ocr_text_frame); ocr_row_rel += 1
        self._add_param_entry("ocr_language", "Lang:", ocr_row_rel, col=0, master=ocr_text_frame, width=8)
        self._add_param_entry("ocr_psm", "PSM:", ocr_row_rel, col=2, master=ocr_text_frame, validate="integer", width=6)
        self._add_param_entry("ocr_char_whitelist", "Whitelist:", ocr_row_rel, col=4, master=ocr_text_frame, width=15, sticky="ew"); ocr_row_rel+=1
        self._add_param_entry("ocr_user_words_file_path", "User Words File:", ocr_row_rel, col=0, master=ocr_text_frame, width=30, sticky=tk.EW)
        self._add_param_button("browse_ocr_user_words_btn", "Browse...", ocr_row_rel, col=2, master=ocr_text_frame, width=10, command=lambda: self._browse_specific_text_file("ocr_user_words_file_path"), sticky=tk.W)

        self._bind_recursive_mousewheel(parent)

    def _create_region_color_params(self) -> None:
        if not (self.param_frame and self.param_frame.winfo_exists()): return
        parent = self.param_frame
        parent.grid_columnconfigure(1, weight=1)
        current_row = 0

        region_frame = ttk.LabelFrame(parent, text="Region to Analyze", padding=5)
        region_frame.grid(row=current_row, column=0, columnspan=4, padx=5, pady=5, sticky="ew"); current_row += 1
        region_frame.grid_columnconfigure(1, weight=0); region_frame.grid_columnconfigure(3, weight=0); region_frame.grid_columnconfigure(4, weight=0)
        self._add_param_entry("region_x1", "X1:", 0, col=0, master=region_frame, validate="integer", width=6)
        self._add_param_entry("region_y1", "Y1:", 1, col=0, master=region_frame, validate="integer", width=6)
        self._add_param_entry("region_x2", "X2:", 0, col=2, master=region_frame, validate="integer", width=6, sticky="w")
        self._add_param_entry("region_y2", "Y2:", 1, col=2, master=region_frame, validate="integer", width=6, sticky="w")
        if _CaptureDepsImported:
            self._add_param_button("capture_color_region_btn", "Select Region",
                                   row=0, col=4, rowspan=2, master=region_frame, width=12, sticky="ns",
                                   command=lambda: self._start_region_capture(for_color=True, region_keys_prefix=""))

        target_colors_frame = ttk.LabelFrame(parent, text="Target Colors", padding=5)
        target_colors_frame.grid(row=current_row, column=0, columnspan=4, padx=5, pady=5, sticky="ew"); current_row += 1
        target_colors_frame.grid_rowconfigure(0, weight=1); target_colors_frame.grid_columnconfigure(0, weight=1)

        tc_list_frame = ttk.Frame(target_colors_frame)
        tc_list_frame.grid(row=0, column=0, sticky="nsew", padx=(0,5))
        tc_list_frame.grid_rowconfigure(0, weight=1); tc_list_frame.grid_columnconfigure(0, weight=1)

        self.target_colors_tree = ttk.Treeview(tc_list_frame, columns=("label", "hex", "tolerance", "threshold_pct"), show="headings", height=4, selectmode="browse")
        self.target_colors_tree.heading("#0", text="Swatch"); self.target_colors_tree.column("#0", width=40, stretch=False, anchor="center")
        self.target_colors_tree.heading("label", text="Label"); self.target_colors_tree.column("label", width=120)
        self.target_colors_tree.heading("hex", text="HEX"); self.target_colors_tree.column("hex", width=80, anchor="center")
        self.target_colors_tree.heading("tolerance", text="Tolerance"); self.target_colors_tree.column("tolerance", width=80, anchor="center")
        self.target_colors_tree.heading("threshold_pct", text="% Threshold"); self.target_colors_tree.column("threshold_pct", width=100, anchor="e")
        self.target_colors_tree.grid(row=0, column=0, sticky="nsew")
        tc_scroll = ttk.Scrollbar(tc_list_frame, orient="vertical", command=self.target_colors_tree.yview)
        tc_scroll.grid(row=0, column=1, sticky="ns")
        self.target_colors_tree.configure(yscrollcommand=tc_scroll.set)
        self.target_colors_tree.bind("<<TreeviewSelect>>", self._on_target_color_select)

        tc_button_frame = ttk.Frame(target_colors_frame)
        tc_button_frame.grid(row=0, column=1, sticky="ns", padx=(5,0))
        self.add_target_color_button = ttk.Button(tc_button_frame, text="Add", command=self._add_target_color_dialog, width=8)
        self.add_target_color_button.pack(pady=2, fill=tk.X)
        self.edit_target_color_button = ttk.Button(tc_button_frame, text="Edit", command=self._edit_target_color_dialog, width=8, state=tk.DISABLED)
        self.edit_target_color_button.pack(pady=2, fill=tk.X)
        self.remove_target_color_button = ttk.Button(tc_button_frame, text="Del", command=self._remove_target_color, width=8, state=tk.DISABLED)
        self.remove_target_color_button.pack(pady=2, fill=tk.X)

        logic_params_frame = ttk.LabelFrame(parent, text="Logic & General Thresholds", padding=5)
        logic_params_frame.grid(row=current_row, column=0, columnspan=4, padx=5, pady=5, sticky="ew"); current_row += 1
        lpf_row = 0
        self._add_param_combobox("condition_logic", "Condition Logic:", lpf_row, col=0, master=logic_params_frame,
                                 values=["ANY_TARGET_MET_THRESHOLD", "ALL_TARGETS_MET_THRESHOLD", "TOTAL_PERCENTAGE_ABOVE_THRESHOLD"], width=30); lpf_row += 1
        self._add_param_entry("match_percentage_threshold", "Total Match Threshold (%):", lpf_row, col=0, master=logic_params_frame, validate="float", width=7); lpf_row += 1
        self._add_param_entry("sampling_step", "Sampling Step (px):", lpf_row, col=0, master=logic_params_frame, validate="integer", width=7); lpf_row += 1

        self._populate_target_colors_treeview()
        self._bind_recursive_mousewheel(parent)

    def _create_multi_image_params_ui(self) -> None:
        if not (self.param_frame and self.param_frame.winfo_exists()): return
        parent = self.param_frame
        parent.grid_columnconfigure(0, weight=1); parent.grid_columnconfigure(1, weight=0) 
        current_row = 0

        overall_region_frame = ttk.LabelFrame(parent, text="Overall Search Region (for Anchor Image - Optional)", padding=5)
        overall_region_frame.grid(row=current_row, column=0, columnspan=2, padx=5, pady=5, sticky="ew"); current_row += 1
        overall_region_frame.grid_columnconfigure(1, weight=0); overall_region_frame.grid_columnconfigure(3, weight=0); overall_region_frame.grid_columnconfigure(4, weight=0)
        self._add_param_entry("region_x1", "X1:", 0, col=0, master=overall_region_frame, validate="integer", width=6)
        self._add_param_entry("region_y1", "Y1:", 1, col=0, master=overall_region_frame, validate="integer", width=6)
        self._add_param_entry("region_x2", "X2 (-1 for full):", 0, col=2, master=overall_region_frame, validate="integer", width=10, sticky="w")
        self._add_param_entry("region_y2", "Y2 (-1 for full):", 1, col=2, master=overall_region_frame, validate="integer", width=10, sticky="w")
        if _CaptureDepsImported:
            self._add_param_button("capture_multi_overall_region_btn", "Select Overall Region",
                                   row=0, col=4, rowspan=2, master=overall_region_frame, width=18, sticky="ns",
                                   command=lambda: self._start_region_capture(for_color=False, region_keys_prefix="", is_multi_image_overall=True))


        canvas_frame = ttk.LabelFrame(parent, text="Define Image Pattern", padding=5)
        canvas_frame.grid(row=current_row, column=0, columnspan=2, padx=5, pady=5, sticky="nsew"); current_row += 1
        parent.grid_rowconfigure(current_row -1, weight=1) 
        canvas_frame.grid_columnconfigure(0, weight=1); canvas_frame.grid_rowconfigure(0, weight=1)

        self.multi_image_canvas = tk.Canvas(canvas_frame, bg="lightgrey", width=400, height=300, relief="sunken", borderwidth=1)
        self.multi_image_canvas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        mi_controls_frame = ttk.Frame(canvas_frame)
        mi_controls_frame.grid(row=0, column=1, rowspan=2, sticky="ns", padx=(5,0)) 
        self._add_param_button("multi_image_add_anchor_btn", "Set/Change Anchor Image", row=0, col=0, master=mi_controls_frame, command=self._multi_image_set_anchor_image, width=20)
        self._add_param_button("multi_image_add_sub_btn", "Add Sub-Image", row=1, col=0, master=mi_controls_frame, command=self._multi_image_add_sub_image, width=20)
        self.multi_image_clear_button = ttk.Button(mi_controls_frame, text="Clear Canvas", command=self._multi_image_clear_canvas, width=20)
        self.multi_image_clear_button.grid(row=2, column=0, padx=5, pady=5, sticky=tk.EW)

        mi_details_frame = ttk.LabelFrame(parent, text="Image Details & Parameters", padding=5)
        mi_details_frame.grid(row=current_row, column=0, columnspan=2, padx=5, pady=5, sticky="ew"); current_row += 1
        mi_details_frame.grid_columnconfigure(1, weight=1)
        
        anchor_params_frame = ttk.LabelFrame(mi_details_frame, text="Anchor Image Parameters", padding=3)
        anchor_params_frame.pack(fill=tk.X, expand=True, pady=(0,5))
        ap_row = 0
        self._add_param_entry("multi_anchor_image_path", "Anchor Path:", ap_row, col=0, master=anchor_params_frame, width=30, sticky="ew")
        self._add_param_entry("multi_anchor_threshold", "Anchor Threshold:", ap_row, col=2, master=anchor_params_frame, validate="float", width=6); ap_row+=1
        self._add_param_combobox("multi_anchor_match_method", "Anchor Match Method:", ap_row, col=0, master=anchor_params_frame, values=["Template", "Feature"], width=15)

        sub_params_frame = ttk.LabelFrame(mi_details_frame, text="Sub-Images Common Parameters", padding=3)
        sub_params_frame.pack(fill=tk.X, expand=True)
        sp_row = 0
        self._add_param_entry("multi_sub_image_threshold", "Sub-Images Threshold:", sp_row, col=0, master=sub_params_frame, validate="float", width=6)
        self._add_param_combobox("multi_sub_image_match_method", "Sub-Images Match Method:", sp_row, col=2, master=sub_params_frame, values=["Template", "Feature"], width=15); sp_row+=1
        pos_tolerance_frame = ttk.LabelFrame(mi_details_frame, text="Relative Position Tolerance (Pixels)", padding=3)
        pos_tolerance_frame.pack(fill=tk.X, expand=True, pady=(5,0))
        pt_row=0
        self._add_param_entry("multi_pos_tolerance_x", "X Tolerance:", pt_row, col=0, master=pos_tolerance_frame, validate="integer", width=6)
        self._add_param_entry("multi_pos_tolerance_y", "Y Tolerance:", pt_row, col=2, master=pos_tolerance_frame, validate="integer", width=6)


        self._multi_image_canvas_setup_bindings()
        self._bind_recursive_mousewheel(parent)

    def _multi_image_canvas_setup_bindings(self):
        if hasattr(self, 'multi_image_canvas') and self.multi_image_canvas.winfo_exists():

            pass

    def _multi_image_set_anchor_image(self):
        if not self.image_storage: messagebox.showwarning("Setup", "Image storage not configured.", parent=self); return
        filepath = filedialog.askopenfilename(title="Select Anchor Image for Pattern",
                                            initialdir=os.path.abspath(self.image_storage.storage_dir),
                                            filetypes=[("Image Files", "*.png *.jpg *.bmp"), ("All Files", "*.*")],
                                            parent=self)
        if filepath:
            try:
                rel_path = os.path.relpath(filepath, os.path.abspath("."))
                self._set_widget_value("multi_anchor_image_path", rel_path.replace('\\', '/'))
                self.multi_image_anchor_preview_image_pil = Image.open(filepath)
                self._multi_image_redraw_canvas()
            except Exception as e:
                messagebox.showerror("Error", f"Could not load anchor image: {e}", parent=self)
                self.multi_image_anchor_preview_image_pil = None
                self._multi_image_redraw_canvas()


    def _multi_image_add_sub_image(self):
        if not self.image_storage: messagebox.showwarning("Setup", "Image storage not configured.", parent=self); return
        if not self.multi_image_anchor_preview_image_pil:
             messagebox.showwarning("Anchor Needed", "Please set an Anchor Image first before adding sub-images.", parent=self)
             return

        filepath = filedialog.askopenfilename(title="Select Sub-Image for Pattern",
                                            initialdir=os.path.abspath(self.image_storage.storage_dir),
                                            filetypes=[("Image Files", "*.png *.jpg *.bmp"), ("All Files", "*.*")],
                                            parent=self)
        if filepath:
            try:
                rel_path = os.path.relpath(filepath, os.path.abspath("."))
                normalized_path = rel_path.replace('\\', '/')

                new_sub_image_pil = Image.open(filepath)

                self.multi_image_sub_images_data.append({
                    "path": normalized_path,
                    "pil_image": new_sub_image_pil, 
                    "offset_x_from_anchor": 0, 
                    "offset_y_from_anchor": 0, 
                    "canvas_item_id": None, 
                    "current_canvas_x": 10, 
                    "current_canvas_y": 10  
                    
                })
                self._multi_image_redraw_canvas()
            except Exception as e:
                messagebox.showerror("Error", f"Could not load sub-image: {e}", parent=self)


    def _multi_image_clear_canvas(self):
        self.multi_image_anchor_preview_image_pil = None
        self._set_widget_value("multi_anchor_image_path", "")
        self.multi_image_sub_images_data.clear()
        self._multi_image_redraw_canvas()

    def _multi_image_redraw_canvas(self):
        if not (hasattr(self, 'multi_image_canvas') and self.multi_image_canvas.winfo_exists()):
            return
        
        self.multi_image_canvas.delete("all") 
        self.multi_image_anchor_preview_image_tk = None 

        canvas_width = self.multi_image_canvas.winfo_width()
        canvas_height = self.multi_image_canvas.winfo_height()
        if canvas_width <=1 or canvas_height <=1 :
             self.multi_image_canvas.after(100, self._multi_image_redraw_canvas) 
             return

        if self.multi_image_anchor_preview_image_pil:
            try:
                img_copy = self.multi_image_anchor_preview_image_pil.copy()
                max_dim = min(canvas_width // 2, canvas_height // 2, 150)
                img_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                self.multi_image_anchor_preview_image_tk = ImageTk.PhotoImage(img_copy)
                anchor_canvas_x = 20 
                anchor_canvas_y = 20
                self.multi_image_canvas.create_image(anchor_canvas_x, anchor_canvas_y,
                                                     anchor=tk.NW,
                                                     image=self.multi_image_anchor_preview_image_tk,
                                                     tags=("anchor_image",))
                self.multi_image_anchor_canvas_pos = (anchor_canvas_x, anchor_canvas_y)
            except Exception as e:
                logger.error(f"Error displaying anchor image on canvas: {e}")
                self.multi_image_canvas.create_text(10,10, text="Error: Anchor Preview", anchor=tk.NW, fill="red")

        current_y_offset_display = (self.multi_image_anchor_preview_image_tk.height() + 30) if hasattr(self, 'multi_image_anchor_preview_image_tk') and self.multi_image_anchor_preview_image_tk else 20


        for i, sub_data in enumerate(self.multi_image_sub_images_data):
            pil_img = sub_data.get("pil_image")
            if pil_img:
                try:
                    img_copy = pil_img.copy()
                    img_copy.thumbnail((80,80), Image.Resampling.LANCZOS) 
                    photo_img = ImageTk.PhotoImage(img_copy)
                    sub_data["_tk_image_ref"] = photo_img

                    sub_canvas_x = self.multi_image_anchor_canvas_pos[0] + sub_data.get("offset_x_from_anchor", 0) if hasattr(self, "multi_image_anchor_canvas_pos") else 20
                    sub_canvas_y = self.multi_image_anchor_canvas_pos[1] + sub_data.get("offset_y_from_anchor", 0) if hasattr(self, "multi_image_anchor_canvas_pos") else current_y_offset_display

                    sub_data["current_canvas_x"] = sub_canvas_x 
                    sub_data["current_canvas_y"] = sub_canvas_y

                    canvas_item_id = self.multi_image_canvas.create_image(
                        sub_canvas_x, sub_canvas_y,
                        anchor=tk.NW,
                        image=photo_img,
                        tags=(f"sub_image_{i}", "sub_image") 
                    )
                    sub_data["canvas_item_id"] = canvas_item_id
                    current_y_offset_display += 30
                except Exception as e:
                    logger.error(f"Error displaying sub-image {sub_data.get('path')} on canvas: {e}")

        if self.canvas and self.canvas.winfo_exists():
            self.canvas.after_idle(self._update_scroll_region)

    def _on_target_color_select(self, event=None):
        if not (hasattr(self, 'target_colors_tree') and self.target_colors_tree.winfo_exists()): return
        selected_ids = self.target_colors_tree.selection()
        can_edit_remove = tk.NORMAL if selected_ids else tk.DISABLED
        if hasattr(self, 'edit_target_color_button'): self.edit_target_color_button.config(state=can_edit_remove)
        if hasattr(self, 'remove_target_color_button'): self.remove_target_color_button.config(state=can_edit_remove)

    def _populate_target_colors_treeview(self):
        if not (hasattr(self, 'target_colors_tree') and self.target_colors_tree.winfo_exists()): return
        for item in self.target_colors_tree.get_children(): self.target_colors_tree.delete(item)
        self.target_color_swatch_images.clear()

        target_colors_data = []
        if self._current_condition_obj and hasattr(self._current_condition_obj, 'params') and isinstance(self._current_condition_obj.params, dict):
            target_colors_data = self._current_condition_obj.params.get("target_colors", [])
        
        if not target_colors_data:
            self.target_colors_tree.insert("", tk.END, values=("(No target colors defined)", "", "", ""))
        else:
            for color_def in target_colors_data:
                label = color_def.get("label", "N/A")
                hex_val = color_def.get("hex", "#000000")
                tolerance = color_def.get("tolerance", 10)
                threshold_pct = color_def.get("threshold", 75.0)
                self._add_swatch_to_tree(self.target_colors_tree, self.target_color_swatch_images, hex_val, (label, hex_val, tolerance, f"{threshold_pct:.1f}%"))
        self._on_target_color_select()

    def _add_target_color_dialog(self, existing_color_data: Optional[Dict[str, Any]] = None, edit_index: Optional[int] = None):
        dialog_title = "Edit Target Color" if existing_color_data else "Add Target Color"
        color_dialog = tk.Toplevel(self)
        color_dialog.title(dialog_title)
        color_dialog.transient(self); color_dialog.grab_set(); color_dialog.resizable(False, False)
        
        main_frame = ttk.Frame(color_dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(1, weight=1)
        row = 0

        ttk.Label(main_frame, text="Label:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        default_label = f"Color {len(self.target_color_swatch_images) + 1}"
        label_val = existing_color_data.get("label", default_label) if existing_color_data else default_label
        label_var = tk.StringVar(value=label_val)
        label_entry = ttk.Entry(main_frame, textvariable=label_var, width=30)
        label_entry.grid(row=row, column=1, columnspan=2, sticky="ew", padx=5, pady=2); row+=1

        ttk.Label(main_frame, text="HEX Color:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        hex_val_init = existing_color_data.get("hex", "#FFFFFF") if existing_color_data else "#FFFFFF"
        hex_var = tk.StringVar(value=hex_val_init)
        hex_entry_cd = ttk.Entry(main_frame, textvariable=hex_var, width=10)
        hex_entry_cd.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        
        color_dialog_swatch = tk.Label(main_frame, text="    ", bg=hex_var.get(), relief="sunken", borderwidth=1)
        color_dialog_swatch.grid(row=row, column=2, sticky="w", padx=5, pady=2)
        hex_var.trace_add("write", lambda *args: self._update_specific_color_swatch(None, hex_entry_cd, color_dialog_swatch))
        row+=1
        
        ttk.Label(main_frame, text="Tolerance (0-255):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        tolerance_val_init = str(existing_color_data.get("tolerance", 10)) if existing_color_data else "10"
        tolerance_var = tk.StringVar(value=tolerance_val_init)
        tolerance_entry = ttk.Entry(main_frame, textvariable=tolerance_var, width=7, validate="key", validatecommand=(self.vcmd_integer, "%P"))
        tolerance_entry.grid(row=row, column=1, sticky="w", padx=5, pady=2); row+=1

        ttk.Label(main_frame, text="Min % for Match (0-100):").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        threshold_val_init = f"{existing_color_data.get('threshold', 75.0):.1f}" if existing_color_data else "75.0"
        threshold_var = tk.StringVar(value=threshold_val_init)
        threshold_entry = ttk.Entry(main_frame, textvariable=threshold_var, width=7, validate="key", validatecommand=(self.vcmd_float, "%P"))
        threshold_entry.grid(row=row, column=1, sticky="w", padx=5, pady=2); row+=1

        button_f = ttk.Frame(main_frame)
        button_f.grid(row=row, column=0, columnspan=3, pady=(10,0), sticky="e")
        
        def on_save_color():
            try:
                new_hex = hex_var.get().strip()
                if not new_hex.startswith("#"): new_hex = "#" + new_hex
                new_rgb = hex_to_rgb(new_hex)
                new_tolerance = int(tolerance_var.get())
                if not (0 <= new_tolerance <= 255): raise ValueError("Tolerance must be 0-255")
                new_threshold = float(threshold_var.get())
                if not (0.0 <= new_threshold <= 100.0): raise ValueError("Threshold % must be 0-100")
                new_label = label_var.get().strip() or f"Color_RGB_{new_rgb[0]}_{new_rgb[1]}_{new_rgb[2]}"

                color_data_entry = {
                    "label": new_label, "hex": new_hex, "rgb": new_rgb,
                    "tolerance": new_tolerance, "threshold": new_threshold
                }
                if self._current_condition_obj and hasattr(self._current_condition_obj, 'params') and isinstance(self._current_condition_obj.params, dict):
                    if "target_colors" not in self._current_condition_obj.params or not isinstance(self._current_condition_obj.params["target_colors"], list):
                         self._current_condition_obj.params["target_colors"] = []
                    
                    if edit_index is not None and 0 <= edit_index < len(self._current_condition_obj.params["target_colors"]):
                        self._current_condition_obj.params["target_colors"][edit_index] = color_data_entry
                    else:
                        self._current_condition_obj.params["target_colors"].append(color_data_entry)
                    
                    self._populate_target_colors_treeview()
                    pil_image_for_analysis = None
                    if hasattr(self, '_last_captured_region_np') and self._last_captured_region_np is not None:
                        pil_image_for_analysis = self._numpy_to_pil(self._last_captured_region_np)

                    self.after_idle(lambda: self._update_color_analysis_display(
                        pil_image_for_analysis, 
                        colors_to_analyze_defs=self._current_condition_obj.params["target_colors"]
                    ))
                    color_dialog.destroy()
                else: messagebox.showerror("Error", "Parent condition object not found or invalid.", parent=color_dialog)

            except ValueError as ve: messagebox.showerror("Input Error", str(ve), parent=color_dialog)
            except Exception as ex: messagebox.showerror("Error", f"Could not save color: {ex}", parent=color_dialog)


        ttk.Button(button_f, text="Save Color", command=on_save_color).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_f, text="Cancel", command=color_dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        color_dialog.update_idletasks()
        cd_w = color_dialog.winfo_reqwidth(); cd_h = color_dialog.winfo_reqheight()
        self.update_idletasks()
        parent_x = self.winfo_rootx(); parent_y = self.winfo_rooty(); parent_w = self.winfo_width(); parent_h = self.winfo_height()
        x = parent_x + (parent_w // 2) - (cd_w // 2); y = parent_y + (parent_h // 2) - (cd_h // 2)
        color_dialog.geometry(f"+{x}+{y}")
        label_entry.focus_set()

    def _edit_target_color_dialog(self):
        if not (hasattr(self, 'target_colors_tree') and self.target_colors_tree.winfo_exists()): return
        selected_items = self.target_colors_tree.selection()
        if not selected_items: return
        selected_iid = selected_items[0]
        
        edit_idx = -1
        target_colors_data = self._current_condition_obj.params.get("target_colors", []) if self._current_condition_obj and hasattr(self._current_condition_obj, 'params') else []
        try:
            item_values = self.target_colors_tree.item(selected_iid, "values")
            selected_hex_from_tree = item_values[1] 
            for i, color_def in enumerate(target_colors_data):
                if color_def.get("hex") == selected_hex_from_tree:
                    edit_idx = i
                    break
        except tk.TclError:
             pass
        
        if edit_idx == -1: 
            try:
                tree_item = self.target_colors_tree.item(selected_iid)
                if tree_item: 
                    item_values = self.target_colors_tree.item(selected_iid, "values")
                    if item_values:
                        selected_hex_from_tree = item_values[1]
                        for i, color_def in enumerate(target_colors_data):
                            if color_def.get("hex") == selected_hex_from_tree and color_def.get("label") == item_values[0]:
                                edit_idx = i
                                break
            except Exception as e:
                logger.warning(f"Error trying to get index for editing target color: {e}")


        if edit_idx != -1 and 0 <= edit_idx < len(target_colors_data):
             self._add_target_color_dialog(existing_color_data=target_colors_data[edit_idx], edit_index=edit_idx)
        else:
            logger.warning(f"Could not find target color with IID '{selected_iid}' or derived values in data for editing.")


    def _remove_target_color(self):
        if not (hasattr(self, 'target_colors_tree') and self.target_colors_tree.winfo_exists()): return
        selected_items_iids = self.target_colors_tree.selection() 
        if not selected_items_iids: return
        
        if self._current_condition_obj and hasattr(self._current_condition_obj, 'params') and isinstance(self._current_condition_obj.params, dict):
            target_colors_list = self._current_condition_obj.params.get("target_colors", [])
            if not isinstance(target_colors_list, list): return

            hex_values_to_remove = set()
            for iid in selected_items_iids:
                try:
                    item_values = self.target_colors_tree.item(iid, "values")
                    if item_values and len(item_values) > 1:
                        hex_values_to_remove.add(item_values[1]) 
                except tk.TclError:
                    continue

            if not hex_values_to_remove: return

            new_target_colors = [
                color_def for color_def in target_colors_list
                if color_def.get("hex") not in hex_values_to_remove
            ]
            
            if len(new_target_colors) < len(target_colors_list):
                self._current_condition_obj.params["target_colors"] = new_target_colors
                self._populate_target_colors_treeview()
                self.after_idle(lambda: self._update_color_analysis_display(self._numpy_to_pil(self._last_captured_region_np), colors_to_analyze_defs=new_target_colors))
        self._on_target_color_select()


    def _update_specific_color_swatch(self, event: Optional[tk.Event], hex_entry_widget: ttk.Entry, swatch_label_widget: tk.Label) -> None:
        if hex_entry_widget and swatch_label_widget and hex_entry_widget.winfo_exists() and swatch_label_widget.winfo_exists():
            hex_value = hex_entry_widget.get().strip()
            try:
                if not hex_value.startswith('#'): hex_value = '#' + hex_value
                if len(hex_value) == 4: hex_value = '#' + ''.join([c*2 for c in hex_value[1:]])
                if re.fullmatch(r'#[0-9a-fA-F]{6}', hex_value): swatch_label_widget.config(bg=hex_value)
                else: swatch_label_widget.config(bg="SystemButtonFace")
            except tk.TclError: swatch_label_widget.config(bg="SystemButtonFace")

    def _browse_specific_image_path(self, param_key: str) -> None:
        if not self.image_storage: messagebox.showwarning("Warning", "Image storage not configured.", parent=self); return
        initial_dir = os.path.abspath(self.image_storage.storage_dir)
        filepath = filedialog.askopenfilename(title=f"Select Image for {param_key}", initialdir=initial_dir, filetypes=[("Image Files", "*.png *.jpg *.bmp"), ("All Files", "*.*")], parent=self)
        if filepath:
            try:
                rel_path = os.path.relpath(filepath, os.path.abspath("."))
                self._set_widget_value(param_key, rel_path.replace('\\', '/'))
            except ValueError: self._set_widget_value(param_key, filepath)
            except Exception as e: messagebox.showerror("Error", f"Could not process path: {e}", parent=self)

    def _browse_specific_text_file(self, param_key: str) -> None:
        initial_dir = os.path.abspath(".")
        if self.image_storage : initial_dir = os.path.abspath(self.image_storage.storage_dir)
        filepath = filedialog.askopenfilename(title=f"Select Text File for {param_key}", initialdir=initial_dir, filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")], parent=self)
        if filepath:
            try:
                rel_path = os.path.relpath(filepath, os.path.abspath("."))
                self._set_widget_value(param_key, rel_path.replace('\\', '/'))
            except ValueError: self._set_widget_value(param_key, filepath)
            except Exception as e: messagebox.showerror("Error", f"Could not process path: {e}", parent=self)


    def _bind_recursive_mousewheel(self, parent_widget: tk.Widget) -> None:
        self._bind_mouse_wheel(parent_widget)
        for child in parent_widget.winfo_children(): self._bind_recursive_mousewheel(child)

    def _start_coordinate_capture(self, num_points: int) -> None:
        if not _CaptureDepsImported:
            messagebox.showerror("Error", "Coordinate capture feature is not available.", parent=self.winfo_toplevel())
            return
        try:
            CoordinateCaptureWindow(self.winfo_toplevel(), self._on_coordinates_picked, num_points=num_points)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start coordinate capture: {e}", parent=self.winfo_toplevel())
            logger.error(f"Error starting coordinate capture: {e}", exc_info=True)


    def _on_coordinates_picked(self, result_data: Optional[Any]) -> None:
        if result_data is None:
            logger.info("Coordinate pick cancelled or failed.")
            return

        if isinstance(result_data, tuple) and len(result_data) == 2 and isinstance(result_data[0], int):
             abs_x, abs_y = result_data
             self._set_widget_value("abs_color_x", abs_x)
             self._set_widget_value("abs_color_y", abs_y)
             try:
                 if _BridgeImported:
                     hex_color = os_interaction_client.get_pixel_color(abs_x, abs_y)
                     self._set_widget_value("color_hex", hex_color)
                     self.after_idle(self._update_color_swatch)
             except Exception as e:
                 logger.warning(f"Could not get/set color after picking point: {e}")
        else:
            logger.warning(f"Received unexpected data format from CoordinateCaptureWindow: {result_data}")

    def _start_region_capture(self, for_color: bool, save_new_image: bool = False, image_path_key: str = "image_path", region_keys_prefix: str = "", is_multi_image_overall: bool = False) -> None:
        if not _CaptureDepsImported:
            messagebox.showerror("Error", "Screen capture feature is not available.", parent=self.winfo_toplevel())
            return
        try:
            ScreenCaptureWindow(
                self.winfo_toplevel(),
                lambda result: self._on_region_captured(result, save_new_image=save_new_image, image_path_key_to_set=image_path_key, region_keys_prefix_to_set=region_keys_prefix, is_multi_image_overall_capture=is_multi_image_overall)
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start region capture: {e}", parent=self.winfo_toplevel())
            logger.error(f"Error starting region capture: {e}", exc_info=True)


    def _on_region_captured(self, result_data: Optional[Dict[str, Any]], save_new_image: bool = False, image_path_key_to_set: str = "image_path", region_keys_prefix_to_set: str = "", is_multi_image_overall_capture: bool = False) -> None:
        if result_data is None:
            logger.info("Region capture cancelled or failed.")
            return

        self._set_widget_value(f"{region_keys_prefix_to_set}region_x1", result_data.get("x1"))
        self._set_widget_value(f"{region_keys_prefix_to_set}region_y1", result_data.get("y1"))
        self._set_widget_value(f"{region_keys_prefix_to_set}region_x2", result_data.get("x2"))
        self._set_widget_value(f"{region_keys_prefix_to_set}region_y2", result_data.get("y2"))

        img_np_captured = result_data.get("image_np")
        if img_np_captured is None:
            self._clear_preview();
            if hasattr(self, '_recognized_text_var'): self._recognized_text_var.set("Preview Error: No image data from capture.")
            return

        self._last_captured_region_np = img_np_captured.copy()
        current_type = self._filtered_action_condition_display_to_internal_map.get(self.type_var.get(), NoneCondition.TYPE)
        show_preview_area = self._filtered_condition_type_settings.get(current_type, {}).get("show_preview", False)

        if show_preview_area and not is_multi_image_overall_capture : # Only update general preview if not for multi-image overall
            self._display_pil_image(self._numpy_to_pil(img_np_captured))

        if save_new_image and self.image_storage:
            if (current_type == ImageOnScreenCondition.TYPE and image_path_key_to_set == "image_path") or \
               (current_type == TextInRelativeRegionCondition.TYPE and image_path_key_to_set == "anchor_image_path") or \
               (current_type == MultiImageCondition.TYPE and image_path_key_to_set.startswith("multi_")): # Handle multi-image paths
                try:
                    base_name = os.path.splitext(os.path.basename(image_path_key_to_set))[0] or "captured"
                    saved_relative_path = self.image_storage.save_image(img_np_captured, base_name)
                    self._set_widget_value(image_path_key_to_set, saved_relative_path)
                    if image_path_key_to_set == "multi_anchor_image_path": # If it was for the anchor of multi-image
                        self.multi_image_anchor_preview_image_pil = Image.open(self.image_storage.get_full_path(saved_relative_path))
                        self._multi_image_redraw_canvas()

                except Exception as e:
                    messagebox.showerror("Save Error", f"Failed to save captured image: {e}", parent=self)
                    logger.error(f"Error saving captured image: {e}", exc_info=True)
        elif save_new_image and not self.image_storage:
             messagebox.showwarning("Save Error", "Image storage is not available to save captured image.", parent=self)


        if current_type == TextOnScreenCondition.TYPE or (current_type == TextInRelativeRegionCondition.TYPE and region_keys_prefix_to_set == ""):
            self._perform_ocr_preview(img_np_captured)

    def _trigger_preview_preprocessing(self) -> None:
        current_type = self._filtered_action_condition_display_to_internal_map.get(self.type_var.get(), NoneCondition.TYPE)
        if not _ImageProcessingAvailable_UI: messagebox.showerror("Error", "Image processing library (OpenCV) missing.", parent=self); return
        source_image_np: Optional[np.ndarray] = None
        
        if current_type == ImageOnScreenCondition.TYPE:
            image_path = self._get_widget_value("image_path", "")
            if not image_path: messagebox.showwarning("Input Missing", "Please specify the template image path first.", parent=self); return
            if not self.image_storage: messagebox.showerror("Error", "Image storage unavailable.", parent=self); return
            full_path = self.image_storage.get_full_path(image_path)
            if not self.image_storage.file_exists(image_path): messagebox.showerror("Error", f"Image file not found:\n{full_path}", parent=self); return
            try:
                source_image_np = cv2.imread(full_path, cv2.IMREAD_UNCHANGED)
                if source_image_np is None: raise ValueError("cv2.imread returned None")
            except Exception as e: messagebox.showerror("Error", f"Failed to load image '{image_path}':\n{e}", parent=self); return
        elif current_type == TextOnScreenCondition.TYPE or current_type == RegionColorCondition.TYPE or current_type == TextInRelativeRegionCondition.TYPE :
            if self._last_captured_region_np is None: messagebox.showinfo("Info", "Please use 'Select Region' or 'Select & OCR' first to capture a region for preview.", parent=self); return
            source_image_np = self._last_captured_region_np.copy()
        elif current_type == MultiImageCondition.TYPE:
            # For MultiImage, preview might mean previewing the Anchor's preprocessing
            # Or previewing a selected Sub-Image's preprocessing.
            # This needs more specific UI to select which image to preview processing for.
            # For now, let's assume it previews the anchor if set.
            anchor_path = self._get_widget_value("multi_anchor_image_path", "")
            if anchor_path and self.image_storage and self.image_storage.file_exists(anchor_path):
                full_anchor_path = self.image_storage.get_full_path(anchor_path)
                try: source_image_np = cv2.imread(full_anchor_path, cv2.IMREAD_UNCHANGED)
                except: pass
            if source_image_np is None:
                 messagebox.showinfo("Info", "Set an anchor image for MultiImage to preview its processing.", parent=self); return
        else: return

        if source_image_np is None: self._clear_preview(); self._recognized_text_var.set("Preview Error: No source."); return
        
        current_pp_params = self._get_current_ui_params()
        processed_image_np: Optional[np.ndarray] = None
        try:
            if current_type == ImageOnScreenCondition.TYPE or (current_type == MultiImageCondition.TYPE and source_image_np is not None): # Use image matching for MultiImage anchor/sub
                # For MultiImage, decide if params are anchor-specific or sub-image common
                params_to_use_for_multi = {}
                if current_type == MultiImageCondition.TYPE:
                     # TODO: This needs UI to select if previewing anchor or a sub-image and use respective params
                     # For now, using general params as a placeholder
                     params_to_use_for_multi = {k.replace("multi_anchor_pp_", ""):v for k,v in current_pp_params.items() if k.startswith("multi_anchor_pp_")}
                     if not params_to_use_for_multi: params_to_use_for_multi = current_pp_params # Fallback

                processed_image_np = preprocess_for_image_matching(source_image_np, current_pp_params if current_type != MultiImageCondition.TYPE else params_to_use_for_multi)

            elif current_type == TextOnScreenCondition.TYPE or current_type == TextInRelativeRegionCondition.TYPE:
                ocr_pp_params = {k.replace("ocr_pp_", ""): v for k,v in current_pp_params.items() if k.startswith("ocr_pp_")}
                if not ocr_pp_params:
                    ocr_pp_params = {k:v for k,v in current_pp_params.items() if not k.startswith("anchor_pp_")}
                processed_image_np = preprocess_for_ocr(source_image_np, ocr_pp_params)
            elif current_type == RegionColorCondition.TYPE:
                processed_image_np = source_image_np

            if processed_image_np is None: messagebox.showerror("Processing Error", "Image preprocessing failed. Check logs.", parent=self); self._clear_preview(); self._recognized_text_var.set("Preview Error: Processing failed."); return
            
            self._display_pil_image(self._numpy_to_pil(processed_image_np))
            
            if current_type == TextOnScreenCondition.TYPE or current_type == TextInRelativeRegionCondition.TYPE:
                 self._perform_ocr_preview(processed_image_np)
        except Exception as e: messagebox.showerror("Preview Error", f"Error during preview generation:\n{e}", parent=self); self._clear_preview();
        if hasattr(self, '_recognized_text_var'): self._recognized_text_var.set("Preview Error.")

    def _perform_ocr_preview(self, img_np_processed: Optional[np.ndarray]) -> None:
         if not (_ImageProcessingAvailable_UI and _PytesseractAvailable_UI):
             self._recognized_text_var.set("OCR Preview: Dependencies missing (OpenCV or Tesseract)."); return
         if img_np_processed is None: self._recognized_text_var.set("OCR Preview: No image data."); return
         try:
             img_pil_preview = self._numpy_to_pil(img_np_processed)
             if img_pil_preview:
                  lang = self._get_widget_value("ocr_language", "eng") or "eng"
                  psm = self._get_widget_value("ocr_psm", "6") or "6"
                  whitelist = self._get_widget_value("ocr_char_whitelist", "")
                  user_words_path = self._get_widget_value("ocr_user_words_file_path", "") or self._get_widget_value("user_words_file_path", "")

                  preview_config_parts = [f'--psm {psm}', '--oem 3', f'-l {lang}']
                  if whitelist: preview_config_parts.append(f'-c tessedit_char_whitelist={whitelist}')
                  if user_words_path:
                      full_user_words_path = os.path.abspath(user_words_path)
                      if os.path.exists(full_user_words_path): preview_config_parts.append(f'-c tessedit_user_words_file="{full_user_words_path}"')
                      else: logger.warning(f"OCR Preview: User words file not found: {full_user_words_path}")
                  
                  preview_config_str = " ".join(preview_config_parts)
                  recognized_text = pytesseract.image_to_string(img_pil_preview, config=preview_config_str)
                  self._recognized_text_var.set(f"Preview: '{recognized_text.strip()}'")
             else: self._recognized_text_var.set("OCR Preview: Image conversion failed.")
         except pytesseract.TesseractNotFoundError: self._recognized_text_var.set("OCR Preview: Tesseract not found or not configured.")
         except Exception as e: self._recognized_text_var.set(f"OCR Preview Error: {str(e)[:100]}")


    def _numpy_to_pil(self, img_np: Optional[np.ndarray]) -> Optional[Image.Image]:
        if img_np is None: return None
        try:
            if img_np.ndim == 3:
                if img_np.shape[2] == 4: return Image.fromarray(cv2.cvtColor(img_np, cv2.COLOR_BGRA2RGBA))
                elif img_np.shape[2] == 3: return Image.fromarray(cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB))
            elif img_np.ndim == 2: return Image.fromarray(img_np, 'L')
            return None
        except Exception as e: logger.error(f"Error converting numpy to PIL: {e}"); return None

    def _display_pil_image(self, img_pil: Optional[Image.Image]) -> None:
        if not (hasattr(self, 'preview_label') and self.preview_label.winfo_exists()):
            logger.debug("_display_pil_image: Preview label does not exist.")
            return

        preview_widget = self.preview_label

        if img_pil is None:
            logger.debug("_display_pil_image: Received None for img_pil. Clearing preview.")
            self._clear_preview()
            self._current_preview_image_pil = None 
            self.after_idle(lambda: self._update_color_analysis_display(None))
            return

        try:
            self._current_preview_image_pil = img_pil.copy()

            img_display_thumb = img_pil.copy()
            
            preview_widget.update_idletasks()
            widget_width = preview_widget.winfo_width()
            widget_height = preview_widget.winfo_height()

            if widget_width <= 1 or widget_height <= 1:
                logger.debug(f"_display_pil_image: Preview label too small ({widget_width}x{widget_height}). Retrying display.")
                self.after(50, lambda: self._display_pil_image(img_pil))
                return

            max_preview_size = (max(10, widget_width - 4), max(10, widget_height - 4))
            img_display_thumb.thumbnail(max_preview_size, Image.Resampling.LANCZOS)
            self._current_preview_image_tk = ImageTk.PhotoImage(img_display_thumb)
            preview_widget.config(image=self._current_preview_image_tk, text="")
            logger.debug(f"_display_pil_image: Image displayed. Thumbnail size: {img_display_thumb.size}")


            current_type = self._filtered_action_condition_display_to_internal_map.get(self.type_var.get(), NoneCondition.TYPE)
            if current_type == RegionColorCondition.TYPE:
                if self._current_preview_image_pil:
                    img_np_rgb_for_analysis = np.array(self._current_preview_image_pil.convert("RGB"))
                    target_colors_defs = []
                    if self._current_condition_obj and hasattr(self._current_condition_obj, 'params'):
                         target_colors_defs = self._current_condition_obj.params.get("target_colors", [])
                    
                    logger.debug(f"_display_pil_image: Triggering color analysis for RegionColor with {len(target_colors_defs)} target(s).")
                    self.after_idle(lambda: self._update_color_analysis_display(img_np_rgb_for_analysis, colors_to_analyze_defs=target_colors_defs))
                else: 
                    logger.warning("_display_pil_image: _current_preview_image_pil is None despite img_pil being present. Cannot analyze.")
                    self.after_idle(lambda: self._update_color_analysis_display(None))
    

        except Exception as e:
            preview_widget.config(text="Preview Err", image=''); self._current_preview_image_tk = None
            self._current_preview_image_pil = None
            logger.error(f"Error displaying PIL image: {e}", exc_info=True)
            self.after_idle(lambda: self._update_color_analysis_display(None))

    def _load_preview_image(self, relative_image_path: str) -> None:
        if not hasattr(self, 'preview_label') or not self.preview_label.winfo_exists(): return
        if not self.image_storage: self._display_pil_image(None); return
        if not relative_image_path: self._display_pil_image(None); return
        full_path = self.image_storage.get_full_path(relative_image_path)
        if not self.image_storage.file_exists(relative_image_path):
             self.preview_label.config(text=f"Not Found:\n{os.path.basename(relative_image_path)}", image=''); self._current_preview_image_tk = None
             return
        try:
            img_pil = Image.open(full_path)
            self._current_preview_image_pil = img_pil.copy()
            self._display_pil_image(img_pil)
            img_pil.close()
        except Exception as e:
            self.preview_label.config(text="Preview Err", image=''); self._current_preview_image_tk = None; self._current_preview_image_pil = None
            logger.error(f"Error loading preview image '{relative_image_path}': {e}")

    def _clear_preview(self, keep_text: bool = False) -> None:
        self._current_preview_image_pil = None; self._current_preview_image_tk = None
        if hasattr(self, 'preview_label') and self.preview_label.winfo_exists():
            self.preview_label.config(image='')
            if not keep_text: self.preview_label.config(text='Preview Area')

    def _find_widget_in_list(self, widget_info: Optional[List[Any]], widget_type: type) -> Optional[Any]:
        if isinstance(widget_info, list):
            for w in widget_info:
                if isinstance(w, widget_type): return w
        return None

    def _get_widget_value(self, key: str, default: Any = None) -> Any:
        widget_info = self.param_widgets.get(key)
        if not widget_info: return default
        try:
            variable = self._find_widget_in_list(widget_info, tk.Variable)
            if variable: return variable.get()
            entry = self._find_widget_in_list(widget_info, ttk.Entry)
            if entry: return entry.get()
            combobox = self._find_widget_in_list(widget_info, ttk.Combobox)
            if combobox: return combobox.get()
            return default
        except Exception: return default

    def _set_widget_value(self, key: str, value: Any, default: Any = "") -> None:
         widget_info = self.param_widgets.get(key)
         if not widget_info: return
         val_to_set = value if value is not None else default
         try:
             variable = self._find_widget_in_list(widget_info, tk.Variable)
             if variable:
                 if isinstance(variable, tk.BooleanVar): variable.set(bool(val_to_set))
                 elif isinstance(variable, tk.StringVar): variable.set(str(val_to_set) if val_to_set is not None else "")
                 else:
                     try: variable.set(val_to_set)
                     except: pass
                 if key == "color_hex" and hasattr(self, '_update_color_swatch'): self.after_idle(self._update_color_swatch)
                 elif key == "target_color_hex" and hasattr(self, '_update_specific_color_swatch') and hasattr(self, 'region_color_swatch') and self.region_color_swatch.winfo_exists():
                      hex_entry_rc = self._find_widget_in_list(self.param_widgets.get("target_color_hex"), ttk.Entry)
                      if hex_entry_rc: self.after_idle(lambda: self._update_specific_color_swatch(None, hex_entry_rc, self.region_color_swatch))
                 return
             entry = self._find_widget_in_list(widget_info, ttk.Entry)
             if entry:
                 entry.delete(0, tk.END); entry.insert(0, str(val_to_set) if val_to_set is not None else "")
                 if key == "color_hex" and hasattr(self, '_update_color_swatch'): self.after_idle(self._update_color_swatch)
                 elif key == "target_color_hex" and hasattr(self, '_update_specific_color_swatch') and hasattr(self, 'region_color_swatch') and self.region_color_swatch.winfo_exists():
                      self.after_idle(lambda: self._update_specific_color_swatch(None, entry, self.region_color_swatch))

                 if key == "image_path" or key == "anchor_image_path" or key == "multi_anchor_image_path":
                     if val_to_set: self.after_idle(self._load_preview_image, str(val_to_set))
                     else: self.after_idle(self._clear_preview)
                 return
             combobox = self._find_widget_in_list(widget_info, ttk.Combobox)
             if combobox: combobox.set(str(val_to_set) if val_to_set is not None else ""); return
         except Exception as e: logger.error(f"Error setting widget value for key '{key}': {e}")

    def _get_current_ui_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for key in self.param_widgets.keys():
             if key.startswith("_") or key in ["preview_label", "recognized_text_label", "capture_button", "capture_region_btn", "browse_btn", "capture_save_btn", "capture_ocr_btn", "preview_button", "separator", "browse_user_words_btn", "browse_anchor_btn", "capture_anchor_btn", "capture_color_region_btn", "capture_overall_region_btn", "browse_ocr_user_words_btn", "multi_image_add_anchor_btn", "multi_image_add_sub_btn", "multi_image_clear_button", "add_target_color_button", "edit_target_color_button", "remove_target_color_button", "analyze_top_n_button", "analyze_targets_button"]:
                 continue
             params[key] = self._get_widget_value(key)
        return params

    def get_settings(self) -> Dict[str, Any]:
        selected_display_key = self.type_var.get()
        condition_type = self._filtered_action_condition_display_to_internal_map.get(selected_display_key, NoneCondition.TYPE)
        params: Dict[str, Any] = {}
        def get_val(key: str, type_func: Callable, default: Any = None, required: bool = False, validation_func: Optional[Callable[[Any], bool]] = None, error_msg: str = "") -> Any:
            val_str_or_bool = self._get_widget_value(key)
            
            if isinstance(val_str_or_bool, bool) and type_func == bool:
                val = val_str_or_bool
            elif val_str_or_bool is None or str(val_str_or_bool).strip() == "":
                if required: raise ValueError(f"'{key}' cannot be empty. {error_msg}")
                return default
            else:
                try: val = type_func(str(val_str_or_bool))
                except (ValueError, TypeError) as e: raise ValueError(f"Invalid value for '{key}': '{val_str_or_bool}'. Expected {type_func.__name__}. {error_msg} ({e})")
            
            if validation_func and not validation_func(val): raise ValueError(f"Validation failed for '{key}'. {error_msg}")
            return val

        try:
            if condition_type in [ColorAtPositionCondition.TYPE, ImageOnScreenCondition.TYPE, TextOnScreenCondition.TYPE, RegionColorCondition.TYPE, TextInRelativeRegionCondition.TYPE, MultiImageCondition.TYPE]:
                params["region_x1"] = get_val("region_x1", int, 0); params["region_y1"] = get_val("region_y1", int, 0)
                x2_default = params["region_x1"] + 1
                y2_default = params["region_y1"] + 1
                if condition_type == MultiImageCondition.TYPE:
                    x2_default = -1 
                    y2_default = -1

                x2 = get_val("region_x2", int, x2_default)
                y2 = get_val("region_y2", int, y2_default)
                
                if condition_type != MultiImageCondition.TYPE or (x2 != -1 and y2 != -1) :
                    if x2 != -1 and x2 <= params["region_x1"]: raise ValueError(f"Region X2 must be > X1 or -1")
                    if y2 != -1 and y2 <= params["region_y1"]: raise ValueError(f"Region Y2 must be > Y1 or -1")
                
                params["region_x2"] = x2; params["region_y2"] = y2


            if condition_type == ColorAtPositionCondition.TYPE:
                params["abs_color_x"] = get_val("abs_color_x", int, 0); params["abs_color_y"] = get_val("abs_color_y", int, 0)
                hex_val = get_val("color_hex", str, "#000000", required=True)
                try: hex_to_rgb(hex_val)
                except ValueError as hex_e: raise ValueError(f"Invalid Target Color format: {hex_e}")
                params["color_hex"] = hex_val
                params["tolerance"] = get_val("tolerance", int, 0, validation_func=lambda v: 0 <= v <= 765, error_msg="Tolerance must be 0-765")
            elif condition_type == ImageOnScreenCondition.TYPE:
                 params["image_path"] = get_val("image_path", str, "", required=True)
                 method_display = get_val("matching_method", str, "Template"); params["matching_method"]={"Template":"template","Feature":"feature"}.get(method_display,"template")
                 params["template_matching_method"]=get_val("template_matching_method",str,"TM_CCOEFF_NORMED")
                 params["threshold"]=get_val("threshold",float,0.8, validation_func=lambda v: 0.0 <= v <= 1.0, error_msg="Threshold 0.0-1.0")
                 params["orb_nfeatures"]=get_val("orb_nfeatures",int,500, validation_func=lambda v: v >= 50, error_msg="ORB Features >= 50")
                 params["min_feature_matches"]=get_val("min_feature_matches",int,10, validation_func=lambda v: v >= 4, error_msg="Min Matches >= 4")
                 params["homography_inlier_ratio"]=get_val("homography_inlier_ratio",float,0.8, validation_func=lambda v: 0.1 <= v <= 1.0, error_msg="Inlier Ratio 0.1-1.0")
                 params["selection_strategy"] = get_val("selection_strategy", str, "first_found")
                 if params["selection_strategy"] == "closest_to_point":
                     ref_x = get_val("reference_point_x", int, None) 
                     ref_y = get_val("reference_point_y", int, None)
                     if ref_x is None or ref_y is None:
                         raise ValueError("Reference X and Y are required for 'closest_to_point' strategy.")
                     params["reference_point_for_closest_strategy"] = f"{ref_x},{ref_y}"
                 else:
                     params.pop("reference_point_for_closest_strategy", None)
                     params.pop("reference_point_x", None) 
                     params.pop("reference_point_y", None)

                 params["grayscale"]=get_val("grayscale", bool, True); params["binarization"]=get_val("binarization", bool, False)
                 params["gaussian_blur"]=get_val("gaussian_blur", bool, False); params["median_blur"]=get_val("median_blur", bool, False)
                 params["clahe"]=get_val("clahe", bool, False); params["bilateral_filter"]=get_val("bilateral_filter", bool, False)
                 params["canny_edges"]=get_val("canny_edges", bool, False)
                 params["gaussian_blur_kernel"]=get_val("gaussian_blur_kernel", str, "3,3", validation_func=lambda v_str: parse_tuple_str(v_str, 2, int) is not None and all(k>0 and k%2==1 for k in parse_tuple_str(v_str,2,int) or [0,0]), error_msg="Kernel 'w,h', positive odd ints")
                 params["median_blur_kernel"]=get_val("median_blur_kernel", int, 3, validation_func=lambda v: v > 0 and v % 2 == 1, error_msg="Kernel positive odd int")
                 params["clahe_clip_limit"]=get_val("clahe_clip_limit", float, 2.0, validation_func=lambda v: v >= 1.0, error_msg="Clip limit >= 1.0")
                 params["clahe_tile_grid_size"]=get_val("clahe_tile_grid_size", str, "8,8", validation_func=lambda v_str: parse_tuple_str(v_str, 2, int) is not None and all(k>0 for k in parse_tuple_str(v_str,2,int) or [0,0]), error_msg="Tile 'w,h', positive ints")
                 params["bilateral_d"]=get_val("bilateral_d", int, 9)
                 params["bilateral_sigma_color"]=get_val("bilateral_sigma_color", float, 75.0); params["bilateral_sigma_space"]=get_val("bilateral_sigma_space", float, 75.0)
                 params["canny_threshold1"]=get_val("canny_threshold1", float, 50.0); params["canny_threshold2"]=get_val("canny_threshold2", float, 150.0)
            elif condition_type == TextOnScreenCondition.TYPE:
                 params["target_text"] = get_val("target_text", str, ""); params["use_regex"] = get_val("use_regex", bool, False)
                 if not params["target_text"] and not params["use_regex"]: raise ValueError("Target text cannot be empty if not using regex.")
                 params["case_sensitive"] = get_val("case_sensitive", bool, False)
                 params["ocr_language"] = get_val("ocr_language", str, "eng", required=True)
                 params["ocr_psm"] = get_val("ocr_psm", str, "6", validation_func=lambda v: v.isdigit() and 0 <= int(v) <= 13, error_msg="PSM must be 0-13")
                 params["ocr_char_whitelist"] = get_val("ocr_char_whitelist", str, "")
                 params["user_words_file_path"] = get_val("user_words_file_path", str, "")
                 params["grayscale"] = get_val("grayscale", bool, True); params["adaptive_threshold"] = get_val("adaptive_threshold", bool, True)
                 params["median_blur"] = get_val("median_blur", bool, True); params["gaussian_blur"] = get_val("gaussian_blur", bool, False)
                 params["clahe"] = get_val("clahe", bool, False)
                 params["ocr_upscale_factor"]=get_val("ocr_upscale_factor", float, 1.0, validation_func=lambda v: v >= 1.0, error_msg="Upscale Factor >= 1.0")
                 params["median_blur_kernel"]=get_val("median_blur_kernel", int, 3, validation_func=lambda v: v > 0 and v % 2 == 1, error_msg="Kernel positive odd int")
                 params["gaussian_blur_kernel"]=get_val("gaussian_blur_kernel", str, "3,3", validation_func=lambda v_str: parse_tuple_str(v_str, 2, int) is not None and all(k>0 and k%2==1 for k in parse_tuple_str(v_str,2,int) or [0,0]), error_msg="Kernel 'w,h', positive odd ints")
                 params["clahe_clip_limit"]=get_val("clahe_clip_limit", float, 2.0, validation_func=lambda v: v >= 1.0, error_msg="Clip limit >= 1.0")
                 params["clahe_tile_grid_size"]=get_val("clahe_tile_grid_size", str, "8,8", validation_func=lambda v_str: parse_tuple_str(v_str, 2, int) is not None and all(k>0 for k in parse_tuple_str(v_str,2,int) or [0,0]), error_msg="Tile 'w,h', positive ints")
            elif condition_type == WindowExistsCondition.TYPE:
                params["window_title"] = get_val("window_title", str, ""); params["window_class"] = get_val("window_class", str, "")
                if not params["window_title"] and not params["window_class"]: raise ValueError("Either Window Title or Window Class must be provided.")
            elif condition_type == ProcessExistsCondition.TYPE: params["process_name"] = get_val("process_name", str, "", required=True)
            elif condition_type == RegionColorCondition.TYPE:
                if self._current_condition_obj and hasattr(self._current_condition_obj, 'params') and isinstance(self._current_condition_obj.params, dict):
                    params["target_colors"] = self._current_condition_obj.params.get("target_colors", [])
                else:
                    params["target_colors"] = []

                if not params["target_colors"] and get_val("condition_logic",str) in ["ANY_TARGET_MET_THRESHOLD", "ALL_TARGETS_MET_THRESHOLD"]:
                     raise ValueError("At least one target color must be defined for the selected logic in RegionColorCondition.")

                params["match_percentage_threshold"] = get_val("match_percentage_threshold", float, 75.0, validation_func=lambda v: 0.0 <= v <= 100.0, error_msg="Match Percentage must be 0-100")
                params["sampling_step"] = get_val("sampling_step", int, 1, validation_func=lambda v: v >= 1, error_msg="Sampling Step must be >= 1")
                params["condition_logic"] = get_val("condition_logic", str, "ANY_TARGET_MET_THRESHOLD")
            elif condition_type == TextInRelativeRegionCondition.TYPE:
                params["anchor_image_path"] = get_val("anchor_image_path", str, "", required=True)
                params["anchor_matching_method"] = {"Template":"template","Feature":"feature"}.get(get_val("anchor_matching_method",str,"Template"), "template")
                params["anchor_threshold"] = get_val("anchor_threshold", float, 0.8, validation_func=lambda v:0.0<=v<=1.0)

                params["text_to_find"] = get_val("text_to_find", str, "")
                params["ocr_use_regex"] = get_val("ocr_use_regex", bool, False)
                if not params["text_to_find"] and not params["ocr_use_regex"]: raise ValueError("Text to find (or Regex) is required for relative region.")
                params["ocr_case_sensitive"] = get_val("ocr_case_sensitive", bool, False)
                params["ocr_language"] = get_val("ocr_language", str, "eng", required=True)
                params["ocr_psm"] = get_val("ocr_psm", str, "6", validation_func=lambda v: v.isdigit() and 0<=int(v)<=13)
                params["ocr_char_whitelist"] = get_val("ocr_char_whitelist", str, "")
                params["ocr_user_words_file_path"] = get_val("ocr_user_words_file_path", str, "")

                params["relative_x_offset"] = get_val("relative_x_offset", int, 0)
                params["relative_y_offset"] = get_val("relative_y_offset", int, 0)
                params["relative_width"] = get_val("relative_width", int, 50, validation_func=lambda v: v > 0)
                params["relative_height"] = get_val("relative_height", int, 20, validation_func=lambda v: v > 0)
                params["relative_to_corner"] = get_val("relative_to_corner", str, "top_left")
            elif condition_type == MultiImageCondition.TYPE:
                params["anchor_image_path"] = get_val("multi_anchor_image_path", str, "", required=True, error_msg="Anchor image path is required for Multi-Image pattern.")
                params["anchor_threshold"] = get_val("multi_anchor_threshold", float, 0.8, validation_func=lambda v: 0.0 <= v <= 1.0, error_msg="Anchor threshold must be between 0.0 and 1.0.")
                params["anchor_matching_method"] = {"Template":"template","Feature":"feature"}.get(get_val("multi_anchor_match_method",str,"Template"), "template")
                params["sub_image_threshold"] = get_val("multi_sub_image_threshold", float, 0.8, validation_func=lambda v: 0.0 <= v <= 1.0)
                params["sub_image_matching_method"] = {"Template":"template","Feature":"feature"}.get(get_val("multi_sub_image_match_method",str,"Template"), "template")
                params["position_tolerance_x"] = get_val("multi_pos_tolerance_x", int, 5, validation_func=lambda v: v >=0)
                params["position_tolerance_y"] = get_val("multi_pos_tolerance_y", int, 5, validation_func=lambda v: v >=0)
                
                cleaned_sub_images = []
                for sub_data_item in self.multi_image_sub_images_data:
                    cleaned_item = {
                        "path": sub_data_item.get("path"),
                        "offset_x_from_anchor": sub_data_item.get("offset_x_from_anchor"),
                        "offset_y_from_anchor": sub_data_item.get("offset_y_from_anchor"),
                    }
                    if cleaned_item["path"] is not None and cleaned_item["offset_x_from_anchor"] is not None and cleaned_item["offset_y_from_anchor"] is not None:
                        cleaned_sub_images.append(cleaned_item)
                params["sub_images"] = cleaned_sub_images
                if not params["sub_images"]:
                    logger.warning("MultiImageCondition: No valid sub-images defined, condition might not work as expected.")


        except ValueError as e: raise e
        except Exception as e: raise ValueError(f"Unexpected error collecting settings: {e}")
        return {"type": condition_type, "params": params}

    def set_settings(self, condition_data: Dict[str, Any]) -> None:
        if not isinstance(condition_data, dict): return
        self.initial_condition_data = copy.deepcopy(condition_data)
        self._current_condition_obj = create_condition(condition_data)
        new_internal_type = self._current_condition_obj.type

        if not hasattr(self, '_filtered_action_condition_display_to_internal_map') or \
           not self._filtered_action_condition_display_to_internal_map:
            logger.error("ConditionSettings.set_settings: Filtered type map not initialized. Cannot set new type.")
            return

        if new_internal_type in self.exclude_types:
            if self._filtered_action_condition_types_display:
                new_display_key = self._filtered_action_condition_types_display[0]
                self.initial_condition_data = {"type": self._filtered_action_condition_display_to_internal_map.get(new_display_key, NoneCondition.TYPE), "params": {}, "name": condition_data.get("name",""), "id": condition_data.get("id")}
                self._current_condition_obj = create_condition(self.initial_condition_data)
                new_internal_type = self._current_condition_obj.type
            else: messagebox.showerror("Configuration Error", "No valid condition types available.", parent=self); return

        new_display_key = self._filtered_condition_type_settings.get(new_internal_type, {}).get("display_name", self._filtered_action_condition_types_display[0] if self._filtered_action_condition_types_display else "")

        current_display_key = self.type_var.get()
        if new_display_key != current_display_key: self.type_var.set(new_display_key) 
        else: self._on_type_selected() 

    def _populate_params(self, params_data: Dict[str, Any]) -> None:
         if not isinstance(params_data, dict): params_data = {}
         current_type = self._filtered_action_condition_display_to_internal_map.get(self.type_var.get(), NoneCondition.TYPE)
         defaults = self._get_default_params_for_current_type()
         for key, widget_info_list in self.param_widgets.items():
             if key.startswith("_") or key in ["preview_label", "recognized_text_label", "capture_button", "capture_region_btn", "browse_btn", "capture_save_btn", "capture_ocr_btn", "preview_button", "separator", "browse_user_words_btn", "browse_anchor_btn", "capture_anchor_btn", "capture_color_region_btn", "capture_overall_region_btn", "browse_ocr_user_words_btn", "multi_image_add_anchor_btn", "multi_image_add_sub_btn", "multi_image_clear_button", "add_target_color_button", "edit_target_color_button", "remove_target_color_button", "analyze_top_n_button", "analyze_targets_button"]:
                 continue
             default_value = defaults.get(key)
             value_to_set = params_data.get(key, default_value)

             if key == "matching_method" and current_type == ImageOnScreenCondition.TYPE:
                 method_internal = str(value_to_set if value_to_set is not None else defaults.get("matching_method","template")).lower()
                 method_display = "Template"
                 if method_internal == "feature": method_display = "Feature"
                 self._set_widget_value(key, method_display)
             elif key == "anchor_matching_method" and current_type == TextInRelativeRegionCondition.TYPE:
                 method_internal_anchor = str(value_to_set if value_to_set is not None else defaults.get("anchor_matching_method","template")).lower()
                 method_display_anchor = "Template"
                 if method_internal_anchor == "feature": method_display_anchor = "Feature"
                 self._set_widget_value(key, method_display_anchor)
             elif key == "multi_anchor_match_method" and current_type == MultiImageCondition.TYPE:
                 method_internal_multi_anchor = str(value_to_set if value_to_set is not None else defaults.get("multi_anchor_match_method","template")).lower()
                 method_display_multi_anchor = "Template"
                 if method_internal_multi_anchor == "feature": method_display_multi_anchor = "Feature"
                 self._set_widget_value(key, method_display_multi_anchor)
             elif key == "multi_sub_image_match_method" and current_type == MultiImageCondition.TYPE:
                 method_internal_multi_sub = str(value_to_set if value_to_set is not None else defaults.get("multi_sub_image_match_method","template")).lower()
                 method_display_multi_sub = "Template"
                 if method_internal_multi_sub == "feature": method_display_multi_sub = "Feature"
                 self._set_widget_value(key, method_display_multi_sub)
             elif key == "reference_point_for_closest_strategy" and current_type == ImageOnScreenCondition.TYPE:
                 ref_point_tuple = parse_tuple_str(str(value_to_set), 2, int)
                 self._set_widget_value("reference_point_x", ref_point_tuple[0] if ref_point_tuple else "")
                 self._set_widget_value("reference_point_y", ref_point_tuple[1] if ref_point_tuple else "")
             else: self._set_widget_value(key, value_to_set, default=default_value)

         if current_type == ImageOnScreenCondition.TYPE:
              image_path = params_data.get("image_path", "")
              if self.image_storage: self.after_idle(self._load_preview_image, image_path)
              else: self.after_idle(self._clear_preview)
              self.after_idle(self._toggle_ref_point_visibility) 
         elif current_type == TextOnScreenCondition.TYPE or current_type == RegionColorCondition.TYPE or current_type == TextInRelativeRegionCondition.TYPE:
              self.after_idle(self._clear_preview)
              if current_type == TextOnScreenCondition.TYPE or current_type == TextInRelativeRegionCondition.TYPE:
                  self.after_idle(self._recognized_text_var.set, "Recognized text preview...")
              elif current_type == RegionColorCondition.TYPE:
                  if hasattr(self, '_recognized_text_var'): self.after_idle(self._recognized_text_var.set, "")
                  self.after_idle(self._populate_target_colors_treeview) 
         elif current_type == MultiImageCondition.TYPE:
             self.multi_image_sub_images_data = [] 
             sub_images_raw = params_data.get("sub_images", [])
             if isinstance(sub_images_raw, list) and self.image_storage:
                 for sub_data in sub_images_raw:
                     if isinstance(sub_data, dict) and sub_data.get("path"):
                         try:
                             pil_img = Image.open(self.image_storage.get_full_path(sub_data["path"]))
                             self.multi_image_sub_images_data.append({
                                 "path": sub_data["path"],
                                 "pil_image": pil_img,
                                 "offset_x_from_anchor": int(sub_data.get("offset_x_from_anchor",0)),
                                 "offset_y_from_anchor": int(sub_data.get("offset_y_from_anchor",0)),
                                 "canvas_item_id": None,
                                 "current_canvas_x": 0,
                                 "current_canvas_y": 0
                             })
                         except Exception as e:
                             logger.error(f"Failed to load sub-image {sub_data.get('path')} for MultiImage: {e}")
             anchor_path = params_data.get("multi_anchor_image_path", "")
             if anchor_path and self.image_storage:
                 try: self.multi_image_anchor_preview_image_pil = Image.open(self.image_storage.get_full_path(anchor_path))
                 except: self.multi_image_anchor_preview_image_pil = None
             else: self.multi_image_anchor_preview_image_pil = None
             self.after_idle(self._multi_image_redraw_canvas)
             self.after_idle(self._clear_preview) 
             if hasattr(self, '_recognized_text_var'): self.after_idle(self._recognized_text_var.set, "")

         else:
            self.after_idle(self._clear_preview)
            if hasattr(self, '_recognized_text_var'): self.after_idle(self._recognized_text_var.set, "")


    def _get_default_params_for_current_type(self) -> Dict[str, Any]:
        current_type = self._filtered_action_condition_display_to_internal_map.get(self.type_var.get(), NoneCondition.TYPE)
        try:
             default_cond = create_condition({"type": current_type, "params": {}})
             return default_cond.params if default_cond and hasattr(default_cond, 'params') and isinstance(default_cond.params, dict) else {}
        except Exception: return {}

    def destroy(self) -> None:
         if hasattr(self, 'canvas') and self.canvas and self.canvas.winfo_exists(): 
             self._unbind_mouse_wheel(self.canvas)
         if hasattr(self, 'param_frame') and self.param_frame and self.param_frame.winfo_exists(): 
             for child in list(self.param_frame.winfo_children()): self._unbind_recursive_mousewheel(child)
         super().destroy()

    def _unbind_recursive_mousewheel(self, widget: tk.Widget) -> None:
        if widget and widget.winfo_exists():
            self._unbind_mouse_wheel(widget)
            for child in list(widget.winfo_children()): self._unbind_recursive_mousewheel(child)
