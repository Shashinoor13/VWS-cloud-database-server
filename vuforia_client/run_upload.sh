#!/bin/bash

# Simple script to run the Vuforia image uploader with default credentials

# Check if images directory exists
IMAGES_DIR="${1:-images}"
OUTPUT_FORMAT="${2:-csv}"
OUTPUT_FILE="${3}"

if [ ! -d "$IMAGES_DIR" ]; then
    echo "Error: Directory '$IMAGES_DIR' does not exist."
    echo "Creating directory '$IMAGES_DIR'..."
    mkdir -p "$IMAGES_DIR"
    echo "Please place your images in the '$IMAGES_DIR' directory and run the script again."
    exit 1
fi

# Count images in the directory
IMAGE_COUNT=$(find "$IMAGES_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) | wc -l)
if [ "$IMAGE_COUNT" -eq 0 ]; then
    echo "Warning: No images found in '$IMAGES_DIR' directory."
    echo "Please add some images (JPG, JPEG, or PNG) to the directory and run again."
    exit 1
fi

echo "Found $IMAGE_COUNT images in '$IMAGES_DIR'"

# Run the Python script with the parameters
if [ -n "$OUTPUT_FILE" ]; then
    echo "Running with custom output file: $OUTPUT_FILE"
    python3 upload_vuforia_images.py --images-dir "$IMAGES_DIR" --output-format "$OUTPUT_FORMAT" --output-file "$OUTPUT_FILE"
else
    echo "Running with default output file: vuforia_results.$OUTPUT_FORMAT"
    python3 upload_vuforia_images.py --images-dir "$IMAGES_DIR" --output-format "$OUTPUT_FORMAT"
fi