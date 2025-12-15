# utils/image_analysis_utils.py
import os
import cv2
import numpy as np
import logging
from collections import Counter
from typing import List, Tuple, Dict, Optional

try:
    from .color_utils import rgb_to_hex, hex_to_rgb 
except ImportError:
    try:
        from color_utils import rgb_to_hex, hex_to_rgb
    except ImportError:
        logger_img_analysis = logging.getLogger(__name__)
        logger_img_analysis.error("image_analysis_utils: color_utils.py not found. HEX/RGB conversions will fail.")
        def rgb_to_hex(rgb: Tuple[int,int,int]) -> str: return "#000000"
        def hex_to_rgb(hex_str: str) -> Tuple[int,int,int]: return (0,0,0)


logger = logging.getLogger(__name__)

def analyze_region_colors(
    image_np_rgb: Optional[np.ndarray],
    target_colors_with_tolerance: List[Tuple[Tuple[int, int, int], int]],
    sampling_step: int = 1
) -> Dict[str, float]:
    if image_np_rgb is None:
        logger.debug("analyze_region_colors: Input image_np_rgb is None.")
        return {}
    if not isinstance(image_np_rgb, np.ndarray) or image_np_rgb.ndim != 3 or image_np_rgb.shape[2] != 3:
        logger.warning(f"analyze_region_colors: Input image is not a valid RGB numpy array. Shape: {image_np_rgb.shape if isinstance(image_np_rgb, np.ndarray) else type(image_np_rgb)}")
        return {}

    height, width = image_np_rgb.shape[:2]
    if height == 0 or width == 0:
        logger.debug("analyze_region_colors: Input image has zero height or width.")
        return {}
    if not target_colors_with_tolerance:
        logger.debug("analyze_region_colors: No target colors provided.")
        return {}
    if sampling_step < 1:
        logger.warning(f"analyze_region_colors: Invalid sampling_step {sampling_step}, using 1.")
        sampling_step = 1

    color_pixel_counts: Dict[str, int] = {}
    for target_rgb_tuple, _ in target_colors_with_tolerance:
        try:
            hex_key = rgb_to_hex(target_rgb_tuple)
            color_pixel_counts[hex_key] = 0
        except Exception as e_hex:
            logger.error(f"analyze_region_colors: Error converting target RGB {target_rgb_tuple} to HEX: {e_hex}")
            color_pixel_counts[f"ERROR_RGB({target_rgb_tuple[0]},{target_rgb_tuple[1]},{target_rgb_tuple[2]})"] = 0


    total_sampled_pixels = 0

    for r_idx in range(0, height, sampling_step):
        for c_idx in range(0, width, sampling_step):
            total_sampled_pixels += 1
            px_r, px_g, px_b = image_np_rgb[r_idx, c_idx]

            for target_rgb_tuple, tolerance in target_colors_with_tolerance:
                target_r, target_g, target_b = target_rgb_tuple
                if (abs(px_r - target_r) <= tolerance and
                    abs(px_g - target_g) <= tolerance and
                    abs(px_b - target_b) <= tolerance):
                    try:
                        hex_key = rgb_to_hex(target_rgb_tuple)
                        if hex_key in color_pixel_counts: 
                           color_pixel_counts[hex_key] += 1
                    except Exception:
                        pass
                    break 

    if total_sampled_pixels == 0:
        logger.debug("analyze_region_colors: No pixels were sampled.")
        return {hex_color: 0.0 for hex_color in color_pixel_counts.keys()}

    percentages = {
        hex_color: (count / total_sampled_pixels) * 100.0
        for hex_color, count in color_pixel_counts.items()
    }
    logger.debug(f"analyze_region_colors: Analysis complete. Percentages: {percentages}")
    return percentages


def get_top_n_colors_histogram_peaks(
    image_np_rgb: Optional[np.ndarray],
    n_colors: int,
    num_bins_per_channel: int = 16,
    sampling_step: int = 1,
    peak_min_distance_factor: float = 1.5, 
) -> List[Tuple[Tuple[int, int, int], float]]:
    if image_np_rgb is None:
        logger.debug("get_top_n_colors_histogram_peaks: Input image_np_rgb is None.")
        return []
    if not isinstance(image_np_rgb, np.ndarray) or image_np_rgb.ndim != 3 or image_np_rgb.shape[2] != 3:
        logger.warning(f"get_top_n_colors_histogram_peaks: Input image is not a valid RGB numpy array. Shape: {image_np_rgb.shape if isinstance(image_np_rgb, np.ndarray) else type(image_np_rgb)}")
        return []
    if n_colors <= 0:
        logger.warning(f"get_top_n_colors_histogram_peaks: n_colors must be positive, got {n_colors}.")
        return []
    if num_bins_per_channel <= 1:
        logger.warning(f"get_top_n_colors_histogram_peaks: num_bins_per_channel must be > 1, got {num_bins_per_channel}.")
        return []
    if sampling_step < 1:
        logger.warning(f"get_top_n_colors_histogram_peaks: Invalid sampling_step {sampling_step}, using 1.")
        sampling_step = 1

    logger.debug(f"get_top_n_colors_histogram_peaks: n_colors={n_colors}, bins_per_channel={num_bins_per_channel}, sampling={sampling_step}, peak_dist_factor={peak_min_distance_factor}")

    h, w, _ = image_np_rgb.shape
    if h == 0 or w == 0:
        logger.debug("get_top_n_colors_histogram_peaks: Input image has zero height or width.")
        return []

    if sampling_step > 1:
        sampled_image = image_np_rgb[::sampling_step, ::sampling_step, :]
        if sampled_image.size == 0:
             logger.warning("get_top_n_colors_histogram_peaks: Image becomes empty after sampling.")
             return []
        logger.debug(f"Histogram: Original shape: {image_np_rgb.shape}, Sampled shape for hist: {sampled_image.shape}")
    else:
        sampled_image = image_np_rgb

    total_pixels_in_sample = sampled_image.shape[0] * sampled_image.shape[1]
    if total_pixels_in_sample == 0:
        logger.debug("get_top_n_colors_histogram_peaks: No pixels in sample for histogram.")
        return []

    try:
        hist = cv2.calcHist(
            [sampled_image],
            [0, 1, 2],
            None,
            [num_bins_per_channel, num_bins_per_channel, num_bins_per_channel],
            [0, 256, 0, 256, 0, 256]
        )
        logger.debug(f"Histogram calculated. Shape: {hist.shape}, Max value: {np.max(hist)}")
    except cv2.error as e:
        logger.error(f"Error calculating 3D histogram: {e}")
        return []
    except Exception as e_hist:
        logger.error(f"Unexpected error during histogram calculation: {e_hist}", exc_info=True)
        return []

    hist_flat = hist.flatten()
    significant_bin_indices_flat = np.where(hist_flat > 0)[0]

    if significant_bin_indices_flat.size == 0:
        logger.debug("No significant bins (count > 0) found in histogram.")
        return []

    significant_bin_values = hist_flat[significant_bin_indices_flat]
    sorted_indices_of_significant_flat = significant_bin_indices_flat[np.argsort(significant_bin_values)[::-1]]

    bin_width = 256.0 / num_bins_per_channel
    peak_min_bin_index_dist = int(max(1, peak_min_distance_factor))


    extracted_colors_with_counts = []
    for flat_idx in sorted_indices_of_significant_flat:
        r_idx = flat_idx // (num_bins_per_channel * num_bins_per_channel)
        remainder = flat_idx % (num_bins_per_channel * num_bins_per_channel)
        g_idx = remainder // num_bins_per_channel
        b_idx = remainder % num_bins_per_channel

        r_val = int((r_idx + 0.5) * bin_width)
        g_val = int((g_idx + 0.5) * bin_width)
        b_val = int((b_idx + 0.5) * bin_width)
        current_color_rgb = (r_val, g_val, b_val)
        count = hist[r_idx, g_idx, b_idx]

        is_too_close_to_existing = False
        for existing_rgb, _ in extracted_colors_with_counts:

            existing_r_idx = int(existing_rgb[0] / bin_width)
            existing_g_idx = int(existing_rgb[1] / bin_width)
            existing_b_idx = int(existing_rgb[2] / bin_width)

            dist_r = abs(r_idx - existing_r_idx)
            dist_g = abs(g_idx - existing_g_idx)
            dist_b = abs(b_idx - existing_b_idx)

            if dist_r < peak_min_bin_index_dist and \
               dist_g < peak_min_bin_index_dist and \
               dist_b < peak_min_bin_index_dist:
                is_too_close_to_existing = True
                break
        
        if not is_too_close_to_existing:
            extracted_colors_with_counts.append((current_color_rgb, count))
            if len(extracted_colors_with_counts) >= n_colors: 
                break
    
    if not extracted_colors_with_counts:
        logger.debug("No distinct dominant colors extracted after proximity filtering.")
        return []

    extracted_colors_with_counts.sort(key=lambda x: x[1], reverse=True)

    final_top_colors_with_percentage: List[Tuple[Tuple[int, int, int], float]] = []
    for rgb_tuple, count in extracted_colors_with_counts:
        percentage = (count / total_pixels_in_sample) * 100.0
        final_top_colors_with_percentage.append((rgb_tuple, percentage))

    logger.debug(f"Final top {len(final_top_colors_with_percentage)} colors (Histogram Peaks): {final_top_colors_with_percentage}")
    return final_top_colors_with_percentage

def get_top_n_colors_kmeans(
    image_np_rgb: Optional[np.ndarray],
    n_colors: int,
    sampling_step: int = 1
) -> List[Tuple[Tuple[int, int, int], float]]:
    if image_np_rgb is None:
        logger.debug("get_top_n_colors_kmeans: Input image_np_rgb is None.")
        return []
    if not isinstance(image_np_rgb, np.ndarray) or image_np_rgb.ndim != 3 or image_np_rgb.shape[2] != 3:
        logger.warning(f"get_top_n_colors_kmeans: Input image is not a valid RGB numpy array. Shape: {image_np_rgb.shape if isinstance(image_np_rgb, np.ndarray) else type(image_np_rgb)}")
        return []
    if n_colors <= 0:
        logger.warning(f"get_top_n_colors_kmeans: n_colors (K for KMeans) must be positive, got {n_colors}.")
        return []
    if sampling_step < 1:
        logger.warning(f"get_top_n_colors_kmeans: Invalid sampling_step {sampling_step}, using 1.")
        sampling_step = 1
        
    logger.debug(f"get_top_n_colors_kmeans: n_colors(K)={n_colors}, sampling={sampling_step}")

    h, w, _ = image_np_rgb.shape
    if h == 0 or w == 0:
        logger.debug("get_top_n_colors_kmeans: Input image has zero height or width.")
        return []

    if sampling_step > 1:
        pixels_for_kmeans_list = []
        for r_idx in range(0, h, sampling_step):
            for c_idx in range(0, w, sampling_step):
                pixels_for_kmeans_list.append(image_np_rgb[r_idx, c_idx])
        if not pixels_for_kmeans_list:
            logger.warning("KMeans: Image becomes empty after sampling.")
            return []
        pixel_data = np.float32(pixels_for_kmeans_list)
        logger.debug(f"KMeans: Original shape: {image_np_rgb.shape}, Sampled points for KMeans: {pixel_data.shape[0]}")
    else:
        pixel_data = np.float32(image_np_rgb.reshape(-1, 3))

    if pixel_data.shape[0] == 0:
        logger.debug("KMeans: No pixels in data for KMeans.")
        return []

    actual_k = min(n_colors, pixel_data.shape[0])
    if actual_k == 0:
        logger.debug("KMeans: actual_k is 0, cannot run KMeans.")
        return []
    
    logger.debug(f"KMeans: Running with K={actual_k} on {pixel_data.shape[0]} data points.")

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5) # Tăng max_iter, giảm epsilon
    attempts = 5 
    try:
        compactness, labels, centers = cv2.kmeans(pixel_data, actual_k, None, criteria, attempts, cv2.KMEANS_PP_CENTERS)
    except cv2.error as e:
        logger.error(f"cv2.kmeans error: {e}. pixel_data shape: {pixel_data.shape}, K: {actual_k}")
        if "ncenters" in str(e).lower() and pixel_data.shape[0] < actual_k and actual_k > 1:
            try:
                actual_k_retry = max(1, pixel_data.shape[0]) # Use all available points if fewer than K
                if actual_k_retry == 0 : return []
                logger.info(f"Retrying kmeans with K={actual_k_retry} (number of samples)")
                compactness, labels, centers = cv2.kmeans(pixel_data, actual_k_retry, None, criteria, attempts, cv2.KMEANS_PP_CENTERS)
            except Exception as e2:
                logger.error(f"cv2.kmeans retry also failed: {e2}")
                return []
        else:
            return []
    except Exception as e_kmeans_unexpected:
        logger.error(f"Unexpected error during KMeans: {e_kmeans_unexpected}", exc_info=True)
        return []


    centers_int = np.uint8(centers)
    counts = Counter(labels.flatten())
    
    dominant_colors_with_percentage: List[Tuple[Tuple[int, int, int], float]] = []
    total_pixels_in_sample = len(labels)

    for i in range(len(centers_int)):
        center_color_tuple = tuple(map(int, centers_int[i])) 
        count = counts[i]
        percentage = (count / total_pixels_in_sample) * 100.0
        dominant_colors_with_percentage.append((center_color_tuple, percentage))
    
    dominant_colors_with_percentage.sort(key=lambda x: x[1], reverse=True)
    
    logger.debug(f"Top {len(dominant_colors_with_percentage)} colors (KMeans): {dominant_colors_with_percentage}")
    return dominant_colors_with_percentage[:n_colors]

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    test_image_path = "test_color_analysis_image.png" #
    if not os.path.exists(test_image_path):
        img_test = np.zeros((100, 100, 3), dtype=np.uint8)
        img_test[:50, :50] = [255, 0, 0]
        img_test[:50, 50:] = [0, 255, 0]
        img_test[50:, :50] = [0, 0, 255]
        img_test[50:, 50:] = [250, 0, 0]
        img_test[75:85, 75:85] = [20,20,20]
        cv2.imwrite(test_image_path, cv2.cvtColor(img_test, cv2.COLOR_RGB2BGR)) 
        print(f"Created test image: {test_image_path}")

    if os.path.exists(test_image_path):
        print(f"\n--- Testing with image: {test_image_path} ---")
        test_img_bgr = cv2.imread(test_image_path)
        test_img_rgb = cv2.cvtColor(test_img_bgr, cv2.COLOR_BGR2RGB)

        print("\n--- Test analyze_region_colors ---")
        targets = [
            ((255, 0, 0), 10),  
            ((0, 255, 0), 10),  
            ((0, 0, 255), 10),  
            ((128, 128, 128), 20) 
        ]
        percentages = analyze_region_colors(test_img_rgb, targets, sampling_step=1)
        for color_hex, perc in percentages.items():
            print(f"Target Color {color_hex} (RGB: {hex_to_rgb(color_hex)}): {perc:.2f}%")

        print("\n--- Test get_top_n_colors_histogram_peaks (N=4, bins=8) ---")
        top_hist_colors = get_top_n_colors_histogram_peaks(test_img_rgb, n_colors=4, num_bins_per_channel=8, sampling_step=1, peak_min_distance_factor=1.0)
        if top_hist_colors:
            for (r,g,b), perc in top_hist_colors:
                print(f"Hist Peak Color RGB: ({r},{g},{b}), HEX: {rgb_to_hex((r,g,b))}, Percentage: {perc:.2f}%")
        else:
            print("No colors returned by histogram peak method.")

        print("\n--- Test get_top_n_colors_kmeans (N=4, K=8) ---")
        top_kmeans_colors = get_top_n_colors_kmeans(test_img_rgb, n_colors=4, sampling_step=1) 
        if top_kmeans_colors:
            for (r,g,b), perc in top_kmeans_colors: 
                print(f"KMeans Dominant Color RGB: ({r},{g},{b}), HEX: {rgb_to_hex((r,g,b))}, Percentage: {perc:.2f}%")
        else:
            print("No colors returned by KMeans method.")

    else:
        print(f"Test image '{test_image_path}' not found. Skipping tests.")
