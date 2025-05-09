#!/usr/bin/env python3

"""
Script to upload all images from 'images' folder to Vuforia Cloud and 
save their name and tracking_rating to a CSV or JSON file.
"""

import os
import csv
import json
import time
import argparse
from pathlib import Path
from cloud_target_webapi_client import VuforiaVwsClient, CloudTargetWebAPIClient

def upload_images_to_vuforia(access_key="d306876ea81bf63b81cad417ca639f1171a84818", secret_key="6bdc3b50e72a1aaa32c75c8ed3cae3113bfab0f1", images_dir="./images", output_format="csv", output_file=None, width=1.0):
    """
    Upload all images from a directory to Vuforia Cloud and save their name and tracking_rating.
    
    Args:
        access_key (str): Vuforia access key
        secret_key (str): Vuforia secret key
        images_dir (str): Directory containing images to upload
        output_format (str): Format for output file ('csv' or 'json')
        output_file (str): Output file name
        width (float): Width of the target in scene units
    """
    # Initialize VWS client
    vws_client = VuforiaVwsClient("https://vws.vuforia.com", access_key, secret_key)
    client = CloudTargetWebAPIClient(vws_client)
    
    # Prepare output file name if not provided
    if output_file is None:
        output_file = f"vuforia_results.{output_format.lower()}"
    
    # List to store results
    results = []
    
    # Get list of image files in the directory
    image_files = []
    for ext in ['.jpg', '.jpeg', '.png']:
        image_files.extend(list(Path(images_dir).glob(f"*{ext}")))
        image_files.extend(list(Path(images_dir).glob(f"*{ext.upper()}")))
    
    print(f"Found {len(image_files)} images to upload")
    
    # Process each image
    for image_path in image_files:
        image_name = image_path.stem
        print(f"Uploading {image_name} from {image_path}...")
        
        try:
            # Create the target
            response = client.create_target(
                image=image_path,
                name=image_name,
                width=width,
                metadata_base64=None,
                active=True
            )
            
            # Extract target ID from the response
            response_json = response.json()
            target_id = response_json.get("target_id")
            
            if target_id:
                print(f"Successfully created target with ID: {target_id}")
                
                # Wait for target to be processed
                tracking_rating = None
                attempts = 0
                max_attempts = 10
                
                while attempts < max_attempts:
                    time.sleep(5)  # Wait 5 seconds between status checks
                    attempts += 1
                    
                    try:
                        target_report_response = client.get_target_report(target_id)
                        report_json = target_report_response.json()
                        
                        status = report_json.get("status")
                        print(f"Target status: {status} (Attempt {attempts}/{max_attempts})")
                        
                        if status == "success":
                            tracking_rating = report_json.get("tracking_rating")
                            print(f"Target processed. Tracking rating: {tracking_rating}")
                            break
                        elif status == "failed":
                            print(f"Target processing failed")
                            break
                    except Exception as e:
                        print(f"Error checking target status: {str(e)}")
                
                # Add to results
                results.append({
                    "name": image_name,
                    "file_path": str(image_path),
                    "target_id": target_id,
                    "tracking_rating": tracking_rating
                })
            
        except Exception as e:
            print(f"Error uploading {image_name}: {str(e)}")
    
    # Save results to file
    if output_format.lower() == "csv":
        with open(output_file, 'w', newline='') as csvfile:
            fieldnames = ['name', 'file_path', 'target_id', 'tracking_rating']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for result in results:
                writer.writerow(result)
    else:  # json format
        with open(output_file, 'w') as jsonfile:
            json.dump(results, jsonfile, indent=2)
    
    print(f"Results saved to {output_file}")
    return results

def main():
    parser = argparse.ArgumentParser(description="Upload images to Vuforia Cloud and save tracking ratings")
    parser.add_argument("--images-dir", type=str, default="images", help="Directory containing images to upload")
    parser.add_argument("--output-format", type=str, choices=["csv", "json"], default="csv", 
                        help="Format for output file (csv or json)")
    parser.add_argument("--output-file", type=str, help="Output file name")
    parser.add_argument("--width", type=float, default=1.0, help="Width of the target in scene units")
    
    args = parser.parse_args()
    
    # Ensure the images directory exists
    if not os.path.isdir(args.images_dir):
        print(f"Error: Directory '{args.images_dir}' does not exist.")
        return 1
    
    upload_images_to_vuforia(
        images_dir=args.images_dir,
        output_format=args.output_format,
        output_file=args.output_file,
        width=args.width
    )
    
    return 0

if __name__ == "__main__":
    main()