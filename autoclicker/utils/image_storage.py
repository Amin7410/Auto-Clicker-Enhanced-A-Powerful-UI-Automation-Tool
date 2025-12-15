# utils/image_storage.py
import os
import cv2
import time 
import logging
from PIL import Image
import numpy as np 

logger = logging.getLogger(__name__)

class ImageStorage:
    """
    Manages storing and retrieving image files captured by the application.
    Stores images in a designated directory and provides methods to get full paths.
    """
    def __init__(self, storage_dir: str = "captured_images"):
        """
        Initializes the ImageStorage.

        Args:
            storage_dir (str): The directory where images will be stored.
                               Created relative to the script's directory.
        """
        if not isinstance(storage_dir, str) or not storage_dir.strip():
             raise ValueError("Image storage directory path cannot be empty.")

        self.storage_dir = storage_dir.strip()
        logger.debug(f"ImageStorage initialized for directory: '{self.storage_dir}'")

        self._ensure_storage_dir_exists()

    def _ensure_storage_dir_exists(self):
        """Ensures the storage directory exists. Called on init and before saving."""
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
            logger.debug(f"Image storage directory '{os.path.abspath(self.storage_dir)}' ensured.")
        except Exception as e:
            logger.error(f"Failed to create image storage directory '{self.storage_dir}': {e}", exc_info=True)
            pass


    def save_image(self, img_np: np.ndarray, file_name_base: str = None) -> str:
        """
        Saves a numpy image array to the storage directory with a unique name.

        Args:
            img_np (np.ndarray): The image data as a numpy array (e.g., BGRA or BGR from mss/cv2/C#).
            file_name_base (str, optional): A base name for the file (e.g., "button").
                                            If None, a timestamp will be used. Defaults to None.

        Returns:
            str: The **relative path** to the saved image file (relative from script dir,
                 including storage_dir). Example: "captured_images\\button_1678886400000.png"

        Raises:
            ValueError: If img_np is not a valid numpy array or has an unsupported shape/format.
            IOError: If there is an error creating the directory or saving the file.
            Exception: For other unexpected errors.
        """
        if not isinstance(img_np, np.ndarray) or img_np.ndim not in [2, 3]:
            raise ValueError("Input img_np must be a 2D (grayscale) or 3D (color/alpha) numpy array.")

        self._ensure_storage_dir_exists()

        if not file_name_base or not isinstance(file_name_base, str):
             file_name_base = "captured_image"
        file_name_base = "".join(c for c in file_name_base if c.isalnum() or c in ('_', '-')).strip('_')
        if not file_name_base: file_name_base = "captured_image"


        timestamp_ms = int(time.time() * 1000)
        file_name = f"{file_name_base}_{timestamp_ms}.png"

        full_path_to_save = os.path.join(self.storage_dir, file_name)
        logger.debug(f"Attempting to save image to: {full_path_to_save}")

        try:
            img_pil = None
            if img_np.ndim == 3:
                 if img_np.shape[2] == 4: 
                      img_pil = Image.fromarray(cv2.cvtColor(img_np, cv2.COLOR_BGRA2RGBA), 'RGBA')
                 elif img_np.shape[2] == 3: 
                      img_pil = Image.fromarray(cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB), 'RGB')
                 else:
                      raise ValueError(f"Unsupported number of image channels for saving: {img_np.shape[2]}")
            elif img_np.ndim == 2: 
                 img_pil = Image.fromarray(img_np, 'L')
            else:
                 raise ValueError(f"Unsupported image numpy dimensions for saving: {img_np.ndim}")

            if img_pil is None:
                 raise ValueError("Failed to convert numpy array to PIL Image.")

            img_pil.save(full_path_to_save, format='PNG')
            logger.info(f"Image saved successfully to '{full_path_to_save}'")

            relative_path_to_return = os.path.join(self.storage_dir, file_name)
            relative_path_to_return = relative_path_to_return.replace('\\', '/')
            logger.debug(f"save_image returning relative path: '{relative_path_to_return}'")

            return relative_path_to_return

        except ValueError as e:
             logger.error(f"Invalid image data or format for saving: {e}.", exc_info=True)
             raise ValueError(f"Invalid image data or format for saving: {e}") from e
        except Exception as e:
            logger.error(f"Error saving image file '{full_path_to_save}': {e}.", exc_info=True)
            raise IOError(f"Failed to save image file '{full_path_to_save}': {e}") from e


    def get_full_path(self, relative_path: str) -> str:
         """
         Resolves the absolute full path for an image file given its **relative path**
         (the path returned by save_image and stored in config).

         Args:
             relative_path (str): The path relative to the script's working directory,
                                  including the storage directory name (e.g., "captured_images/my_image.png").

         Returns:
             str: The absolute full path to the image file. Returns empty string for invalid input.
         """
         if not isinstance(relative_path, str) or not relative_path.strip():
              return ""

         full_path = os.path.abspath(relative_path)
         return full_path

    def file_exists(self, relative_path: str) -> bool:
        """
        Checks if an image file exists given its **relative path**
        (the path stored in config).

        Args:
            relative_path (str): The relative path to the file (e.g., "captured_images/my_image.png").

        Returns:
            bool: True if the file exists at the resolved absolute path, False otherwise or for invalid input.
        """
        if not isinstance(relative_path, str) or not relative_path.strip():
             return False

        full_path = self.get_full_path(relative_path)
        exists = os.path.exists(full_path)
        return exists

    def delete_image(self, relative_path: str) -> bool:
        """
        Deletes an image file given its **relative path**
        (the path stored in config).

        Args:
            relative_path (str): The relative path to the file to delete.

        Returns:
            bool: True if deleted successfully, False if file did not exist, input was invalid, or error occurred.
        """
        if not isinstance(relative_path, str) or not relative_path.strip():
            logger.warning(f"Attempted to delete with invalid relative_path: '{relative_path}'. Returning False.")
            return False

        full_path = self.get_full_path(relative_path)

        if not os.path.exists(full_path):
            logger.warning(f"Attempted to delete non-existent image file: '{full_path}'.")
            return False

        try:
            os.remove(full_path)
            logger.info(f"Deleted image file: '{full_path}'")
            return True
        except Exception as e:
            logger.error(f"Error deleting image file '{full_path}': {e}.", exc_info=True)
            return False
