import os
import json
import shutil
import sys
import zipfile
import io
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

class Tee:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.log_file = open(filepath, "a", encoding="utf-8")
    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.log_file.flush()
    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

sys.stdout = Tee("cloud_fetcher.log")

# Hardcode fallback if running outside the game directory
STEAM_GH_PATH = os.getcwd()


load_dotenv()
AZURE_CONN = os.getenv("AZURE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "games")
BEPINEX_BLOB_PATH = os.getenv("BEPINEX_BLOB_PATH", "core/bepinex_5.4.23.zip")
BEPINEX_VERSION = os.getenv("BEPINEX_VERSION", "5.4.23")
BEPINEX_MARKER = os.getenv("BEPINEX_MARKER", "bepinex_version.json")

def get_installed_bepinex_version(game_dir: str) -> str | None:
    marker_path = os.path.join(game_dir, BEPINEX_MARKER)
    if not os.path.isfile(marker_path):
        return None
    with open(marker_path, "r") as f:
        return json.load(f).get("version")

def install_bepinex(container_client, game_dir: str) -> None:
    installed = get_installed_bepinex_version(game_dir)
    if installed == BEPINEX_VERSION:
        return
    try:
        blob_client = container_client.get_blob_client(BEPINEX_BLOB_PATH)
        zip_bytes = blob_client.download_blob().readall()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(game_dir)
        with open(os.path.join(game_dir, BEPINEX_MARKER), "w") as f:
            json.dump({"version": BEPINEX_VERSION}, f)
    except Exception as e:
        print(f"[BEPINEX ERROR] Setup skipped: {e}")

def fetch_payload():
    print("[SYNC NODE] Initializing Azure Connection...")
    try:
        with open("server_config.json", "r") as f:
            squad_id = json.load(f)["squad_id"]
    except FileNotFoundError:
        print("[FATAL] server_config.json missing.")
        return

    target_cache = os.path.join(STEAM_GH_PATH, ".VaultCache", squad_id)
    os.makedirs(target_cache, exist_ok=True)

    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
    except Exception as e:
        print(f"[FATAL] Azure connection failed: {e}")
        return

    install_bepinex(container_client, STEAM_GH_PATH)

    # Prefix aligned with admin_mod_manager.py
    cloud_folder_prefix = f"green-hell/{squad_id}/"
    print(f"[SYNC NODE] Pulling partition: {cloud_folder_prefix}")
    
    blob_list = container_client.list_blobs(name_starts_with=cloud_folder_prefix)
    download_count = 0
    for blob in blob_list:
        if "server_status.txt" in blob.name or "backups/" in blob.name:
            continue
            
        relative_path = blob.name.replace(cloud_folder_prefix, "", 1)
        if not relative_path:
            continue
            
        download_path = os.path.normpath(os.path.join(target_cache, relative_path))
        os.makedirs(os.path.dirname(download_path), exist_ok=True)
        
        print(f"  -> Downloading: {relative_path}")
        with open(download_path, "wb") as f:
            f.write(container_client.get_blob_client(blob).download_blob().readall())
        download_count += 1

    print(f"[SUCCESS] {download_count} asset(s) synced to {target_cache}")

if __name__ == "__main__":
    fetch_payload()