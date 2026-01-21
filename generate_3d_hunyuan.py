import requests
import json
import time
import os
from PIL import Image
import io

BASE_URL = "http://localhost:7842/api/v1"
IMAGE_PATH = "test.jpg"

def wait_for_server(url, timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{url}/system/status/")
            if response.status_code == 200:
                print("Server is up!")
                return True
        except requests.exceptions.ConnectionError:
            pass
        print("Waiting for server...")
        time.sleep(2)
    return False

def upload_image(image_path):
    print(f"Uploading {image_path}...")
    url = f"{BASE_URL}/file-upload/image"
    
    # Check resolution and resize if necessary
    with Image.open(image_path) as img:
        width, height = img.size
        print(f"Original resolution: {width}x{height}")
        if width > 2048 or height > 2048:
            print("Image exceeds limit. Resizing...")
            ratio = min(2048 / width, 2048 / height)
            new_size = (int(width * ratio), int(height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
            print(f"New resolution: {img.size}")
            
            # Save to byte buffer
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            img_byte_arr.seek(0)
            files = {"file": (os.path.basename(image_path), img_byte_arr, "image/jpeg")}
        else:
            files = {"file": (os.path.basename(image_path), open(image_path, "rb"), "image/jpeg")}

    response = requests.post(url, files=files)
    
    # Close the file if it was opened directly
    if "file" in files and hasattr(files["file"][1], 'close'):
        files["file"][1].close()
    
    if response.status_code != 200:
        print(f"Upload failed: {response.text}")
        return None
    
    file_id = response.json().get("file_id")
    print(f"Uploaded successfully. File ID: {file_id}")
    return file_id

def generate_3d(file_id, model="hunyuan3dv21_image_to_textured_mesh"):
    print(f"Starting 3D generation using {model}...")
    url = f"{BASE_URL}/mesh-generation/image-to-textured-mesh"
    payload = {
        "image_file_id": file_id,
        "texture_resolution": 1024,
        "output_format": "glb",
        "model_preference": model
    }
    response = requests.post(url, json=payload)
    
    if response.status_code != 200:
        print(f"Generation request failed: {response.text}")
        return None
    
    job_id = response.json().get("job_id")
    print(f"Job submitted. Job ID: {job_id}")
    return job_id

def poll_job(job_id, timeout=1200):
    print(f"Polling job {job_id}...")
    url = f"{BASE_URL}/system/jobs/{job_id}"
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            progress = data.get("progress", 0)
            print(f"Status: {status}, Progress: {progress}%")
            
            if status == "completed":
                print("Job completed!")
                return data
            if status == "failed":
                print(f"Job failed: {data.get('error')}")
                return None
        else:
            print(f"Failed to get job status: {response.text}")
        
        time.sleep(10)
    
    print("Job timed out.")
    return None

def download_result(job_id, output_path):
    print(f"Downloading result for {job_id}...")
    url = f"{BASE_URL}/system/jobs/{job_id}/download"
    response = requests.get(url)
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"Result saved to {output_path}")
        return True
    else:
        print(f"Download failed: {response.text}")
        return False

def main():
    if not wait_for_server(BASE_URL):
        print("Could not connect to server.")
        return

    file_id = upload_image(IMAGE_PATH)
    if not file_id:
        return

    # Try textured mesh first, if it fails maybe because of VRAM, user might want raw mesh
    # But let's start with textured as it's more common.
    job_id = generate_3d(file_id)
    if not job_id:
        return

    result = poll_job(job_id)
    if result:
        download_result(job_id, "test_result.glb")

if __name__ == "__main__":
    main()
