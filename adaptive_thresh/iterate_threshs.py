import time
import cv2
import numpy as np
import os
import csv
from scipy.optimize import curve_fit

# Tunable parameters.
VAR_THRESHOLD = 5.0    # Variance below this is acceptable.
HUGE_METRIC = 1e9      # Value to assign if skip condition is met.

def compute_threshold_pattern(image_shape, bottom_threshold, slope):
    """
    Compute a 2D threshold pattern image.
    Each row's threshold linearly interpolates from (bottom_threshold - slope) at the top
    to bottom_threshold at the bottom.
    """
    H, W = image_shape
    row_indices = np.arange(H)
    row_thresholds = bottom_threshold - slope * ((H - 1 - row_indices) / (H - 1))
    row_thresholds = np.clip(row_thresholds, 0, 255).astype(np.uint8)
    threshold_pattern = np.tile(row_thresholds[:, np.newaxis], (1, W))
    return threshold_pattern

def apply_threshold(image, threshold_pattern):
    """
    Apply the threshold pattern to the image.
    For each pixel, if image value > corresponding threshold, set to 255; otherwise, set to 0.
    """
    binary_output = (image > threshold_pattern).astype(np.uint8) * 255
    return binary_output

def compute_metric(masked_img, template_mask):
    """
    Computes five metrics for the masked image: 1 - (overlap ratio with template_mask).
      
    Skip conditions:
      If the binary mask is trivial (all 0 or all 255), if there are fewer than 6 unmasked pixels,
      if unmasked fraction is less than 10% (i.e. area_metric > 0.9),
      or if the overlap with the template mask is less than 50% (i.e. overlap_ratio < 0.5),
      then all metrics are returned as HUGE_METRIC.
      
    Returns: overlap_metric
    """

    total_pixels = masked_img.size
    # # Unmasked pixels: pixels with value > 5.
    mask = (masked_img > 4)
    unmasked_count = np.count_nonzero(mask)
    unmasked_fraction = unmasked_count / total_pixels

    # Compute overlap metric with the template mask.
    overlap_ratio = np.sum(masked_img == template_mask) / total_pixels
    overlap_metric = 1 - overlap_ratio

    # Skip condition if too few unmasked pixels or unmasked fraction < 10%.
    if unmasked_count < 6 or unmasked_fraction < 0.1:
        # print(f"Skip condition -- too few unmasked pixels ({unmasked_count}) or unmasked fraction ({unmasked_fraction}) < 10%")
        return HUGE_METRIC * overlap_metric

    # New skip condition: if overlap_ratio is less than 20% then skip then skip.
    if overlap_ratio < 0.2:
        # print(f"Skip condition -- overlap_ratio ({overlap_ratio}) is less than 20%")
        return HUGE_METRIC * overlap_metric
    
    return overlap_metric


if __name__ == "__main__":
    # Load the grayscale depth image.
    img = cv2.imread("depth_image.jpg", cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise IOError("Could not load depth_image.jpg. Check the file path.")
    
    # Load the template mask image.
    template_mask = cv2.imread("template_mask.jpg", cv2.IMREAD_GRAYSCALE)
    if template_mask is None:
        raise IOError("Could not load template_mask.jpg. Check the file path.")
    if template_mask.shape != img.shape:
        raise ValueError("template_mask.jpg must have the same dimensions as depth_image.jpg.")
    
    # Create output directory for masked images.
    output_dir = "masked_images"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Prepare CSV file with exactly six columns:
    # image_name, cmb_metric, var_metric, area_metric, grad_metric, overlap_metric
    csv_filename = "metrics.csv"
    csv_filepath = os.path.join(output_dir, csv_filename)
    with open(csv_filepath, mode='w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow([
            "image_name",
            "overlap_metric"
        ])
        
        # Iterate through bottom_threshold and slope values (step size 5).
        for bottom_threshold in range(0, 256, 5):
            for slope in range(0, 256, 5):
                threshold_pattern = compute_threshold_pattern(img.shape, bottom_threshold, slope)
                binary_output = apply_threshold(img, threshold_pattern)
                image_name = f"masked_bt{bottom_threshold:03d}_slope{slope:03d}.jpg"
                print(image_name)
                
                # Check trivial condition: if binary_output is completely 0 or 255.
                if np.all(binary_output == 0) or np.all(binary_output == 255):
                    metrics = HUGE_METRIC
                else:
                    # Create masked image: keep original pixel where binary_output is 0.
                    masked_image = np.where(binary_output == 0, img, 0).astype(np.uint8)
                    overlap_metric = compute_metric(masked_image, template_mask)
                
                # Save the masked image only if cmb_metric is not HUGE_METRIC.
                if overlap_metric < 0.01 * HUGE_METRIC:
                    cv2.imwrite(os.path.join(output_dir, image_name), masked_image)
                
                csv_writer.writerow([
                    image_name,
                    overlap_metric
                ])
    
    print(f"Metrics saved to {csv_filepath}")
