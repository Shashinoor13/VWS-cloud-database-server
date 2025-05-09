import os
import cv2
import csv
import numpy as np
from pathlib import Path

def process_images(csv_path):
    """
    Process images based on CSV file containing image metadata.
    The CSV structure should be: name,file_path,target_id,tracking_rating
    
    This script will extract:
    1. Feature points (SIFT)
    2. Edge detection (Canny)
    3. Contrast map
    4. Grayscale
    5. Blur detection
    """
    # Create output directories if they don't exist
    output_dirs = {
        'features': 'output_features',
        'edges': 'output_edges',
        'contrast': 'output_contrast',
        'grayscale': 'output_grayscale',
        'blur': 'output_blur'
    }
    
    for dir_name in output_dirs.values():
        os.makedirs(dir_name, exist_ok=True)
    
    # Initialize SIFT detector
    sift = cv2.SIFT_create()
    
    # Read CSV file
    with open(csv_path, 'r') as csv_file:
        csv_reader = csv.reader(csv_file)
        
        # Skip header if present
        header = next(csv_reader, None)
        
        # Process each row
        for row in csv_reader:
            name, file_path, target_id, tracking_rating = row
            
            # Ensure the image file exists
            if not os.path.exists(file_path):
                print(f"Warning: File {file_path} not found. Skipping.")
                continue
            
            # Read the image
            img = cv2.imread(file_path)
            if img is None:
                print(f"Warning: Could not read image {file_path}. Skipping.")
                continue
            
            # Get original filename without extension
            original_filename = Path(file_path).stem
            
            # Convert to grayscale for feature extraction
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 1. Extract SIFT features
            keypoints, descriptors = sift.detectAndCompute(gray, None)
            
            # Filter keypoints based on response value (strength)
            threshold = 0.05  # Adjust this threshold as needed
            strong_keypoints = [kp for kp in keypoints if kp.response > threshold]
            
            # Draw only the strong keypoints
            img_features = cv2.drawKeypoints(gray, strong_keypoints, None, flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
            output_path = os.path.join(output_dirs['features'], f"{original_filename}_features.jpg")
            cv2.imwrite(output_path, img_features)
            
            # 2. Edge detection
            edges = cv2.Canny(gray, 100, 200)
            output_path = os.path.join(output_dirs['edges'], f"{original_filename}_edges.jpg")
            cv2.imwrite(output_path, edges)
            
            # 3. Contrast map
            # Calculate local contrast using standard deviation filter
            mean, std_dev = cv2.meanStdDev(gray)
            contrast_map = np.zeros_like(gray, dtype=np.float32)
            
            kernel_size = 3
            for y in range(gray.shape[0] - kernel_size + 1):
                for x in range(gray.shape[1] - kernel_size + 1):
                    region = gray[y:y+kernel_size, x:x+kernel_size].astype(np.float32)
                    contrast_map[y+kernel_size//2, x+kernel_size//2] = np.std(region)
            
            # Normalize contrast map to 0-255
            contrast_map = cv2.normalize(contrast_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            contrast_map_color = cv2.applyColorMap(contrast_map, cv2.COLORMAP_JET)
            output_path = os.path.join(output_dirs['contrast'], f"{original_filename}_contrast.jpg")
            cv2.imwrite(output_path, contrast_map_color)
            
            # 4. Grayscale
            output_path = os.path.join(output_dirs['grayscale'], f"{original_filename}_grayscale.jpg")
            cv2.imwrite(output_path, gray)
            
            # 5. Blur detection
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            blur_text = f"Blur score: {laplacian_var:.2f}"
            blur_img = img.copy()
            cv2.putText(blur_img, blur_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            output_path = os.path.join(output_dirs['blur'], f"{original_filename}_blur.jpg")
            cv2.imwrite(output_path, blur_img)
            
            print(f"Processed: {name} ({file_path})")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Process images based on CSV data.')
    parser.add_argument('csv_file', help='Path to the CSV file containing image metadata')
    
    args = parser.parse_args()
    
    if os.path.exists(args.csv_file):
        process_images(args.csv_file)
    else:
        print(f"Error: CSV file {args.csv_file} not found.")