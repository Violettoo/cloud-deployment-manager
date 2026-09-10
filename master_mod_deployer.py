import os
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from azure.storage.blob import BlobServiceClient

from dotenv import load_dotenv

load_dotenv()
AZURE_CONN = os.getenv("AZURE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "games")

def get_file_hash(filepath):
    """Generates an MD5 fingerprint for delta comparison."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def process_file(local_path, blob_client, relative_path):
    """Handles the delta check and upload logic for a single file concurrently."""
    local_hash = get_file_hash(local_path)
    
    try:
        blob_props = blob_client.get_blob_properties()
        cloud_hash = blob_props.metadata.get('md5')
        
        if cloud_hash == local_hash:
            return f"[SKIP] {relative_path} (Unchanged)"
    except Exception:
        pass 

    with open(local_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True, metadata={'md5': local_hash})
    return f"[UPLOAD] {relative_path} (Success)"

def deploy_modpack():
    print("\n" + "="*55)
    print(" 🚀 ENTERPRISE MODPACK DEPLOYMENT PIPELINE 🚀 ")
    print("="*55)

    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            squad_id = config["squad_name"]
    except FileNotFoundError:
        print("[FATAL] config.json missing.")
        return

    # Dynamic Pathing 
    game_root = os.getcwd()

    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN)
    except Exception as e:
        print(f"[FATAL] Azure connection failed: {e}")
        return
    
    # 1. Target your frameworks
    target_folders = ["Mods", r"BepInEx\plugins"]
    
    manifest = []
    load_order_paths = [] 
    
    for folder in target_folders:
        local_folder_path = os.path.join(game_root, folder)
        
        if not os.path.exists(local_folder_path):
            continue
            
        print(f"[SCAN] Indexing directory: {folder}...")
        
        # os.walk automatically dives into subfolders like BetterLive
        for root, _, files in os.walk(local_folder_path):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, game_root)
                
                # Add to the text file list
                load_order_paths.append(relative_path)
                
                # Add to the upload queue
                cloud_path = f"green-hell/{squad_id}/{relative_path}".replace("\\", "/")
                blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=cloud_path)
                manifest.append((local_path, blob_client, relative_path))

    if len(manifest) == 0: 
        print("[FATAL] No mods found in specified directories. Aborting.")
        return

    # 2. GENERATE AND UPLOAD load_order.txt
    load_order_local = os.path.join(game_root, "load_order.txt")
    with open(load_order_local, "w") as f:
        for path in load_order_paths:
            f.write(path + "\n")
            
    cloud_manifest_path = f"green-hell/{squad_id}/load_order.txt"
    manifest_blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=cloud_manifest_path)
    manifest.append((load_order_local, manifest_blob_client, "load_order.txt"))

    print(f"[ENGINE] Manifest compiled: {len(manifest)} files. Igniting ThreadPool...\n")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_file, item[0], item[1], item[2]) for item in manifest]
        
        for future in as_completed(futures):
            try:
                print(future.result())
            except Exception as e:
                print(f"[ERROR] Thread failure: {e}")

    print("\n" + "="*55)
    print(" [SUCCESS] Deployment Pipeline Terminated Cleanly. 🎯")
    print("="*55)

if __name__ == "__main__":
    deploy_modpack()
    os.system("pause")