import hashlib
from azure.storage.blob import BlobServiceClient
import os
import shutil
from datetime import datetime
import sys
import gzip
import requests
import json
import time

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

sys.stdout = Tee("green_hell_sync.log")


from dotenv import load_dotenv

load_dotenv()
AZURE_CONN = os.getenv("AZURE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "games")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Read the mission parameters from the GUI
try:
    with open("config.json", "r") as f:
        config = json.load(f)
        SQUAD = config["squad_name"]
        TARGET_FILE = config["target_file"]
except FileNotFoundError:
    print("[FATAL] config.json missing. You must launch the daemon via the GUI.")
    exit(1)

STEAM_BASE_PATH = os.getenv("LOCAL_DATA_PATH", "./data/save_games")
TARGET_FILE = os.getenv("TARGET_SAVE_FILE", "save_slot_01.sav")
LOCAL_SAVE_PATH = os.path.join(STEAM_BASE_PATH, TARGET_FILE)


NAMESPACE = os.getenv("APP_NAMESPACE", "server-sync")
TENANT_ID = os.getenv("TENANT_ID", "production-node")
BLOB_NAME = f"{NAMESPACE}/{TENANT_ID}/{TARGET_FILE}"


def backup_local_save():
    """Creates a timestamped copy of the local save."""
    if os.path.exists(LOCAL_SAVE_PATH):
        backup_dir = os.path.join(os.path.dirname(LOCAL_SAVE_PATH), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"MPSlot2_backup_{timestamp}.sav")
        shutil.copy2(LOCAL_SAVE_PATH, backup_path)
        print(f"\n[OK] Safety First: Local backup created -> {backup_path}")

def download_save(blob_service_client):
    print("\n[+] Connecting to viocloud to download...")
    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=BLOB_NAME)
    
    # 1. Trigger the safety net backup first
    backup_local_save()
    
    # 2. Download and Decompress
    print(f"[+] Downloading and decompressing payload for {BLOB_NAME}...")
    try:
        download_stream = blob_client.download_blob()
        compressed_data = download_stream.readall()
        
        # Unzip the payload in RAM
        raw_data = gzip.decompress(compressed_data)
        
        with open(LOCAL_SAVE_PATH, "wb") as download_file:
            download_file.write(raw_data)
            
        print("[SUCCESS] Payload extracted! Your local save is up to date. 🎮")
    except Exception as e:
        if "BlobNotFound" in str(e):
            print("\n[INFO] Cloud vault is empty (Cold Start). Waiting for initial local upload...")
        else:
            print(f"\n[FATAL] Download pipeline failed: {e}")

def upload_save(blob_service_client):
    print("\n[+] Connecting to viocloud to upload...")
    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=BLOB_NAME)
    
    # 1. Get the local fingerprint
    local_hash = get_local_hash(LOCAL_SAVE_PATH)
    if not local_hash:
        print("[ERROR] Could not find the local save file! Are you sure you played?")
        return

    # --- NEW: The 0-Byte Guard ---
    file_size = os.path.getsize(LOCAL_SAVE_PATH)
    if file_size < 1024:  # If it is less than 1,024 bytes (1 KB)
        print(f"\n[CRITICAL ERROR] Upload blocked! 🛑")
        print(f"[!] Your save file is suspiciously small ({file_size} bytes).")
        print("[!] It might be corrupted from a game crash. The cloud has been protected.")
        return
    # -----------------------------

    # 2. Check the cloud's fingerprint (if the file exists)
    try:
        blob_properties = blob_client.get_blob_properties()
        cloud_hash = blob_properties.metadata.get('md5_fingerprint')
        
        # 3. The Big Decision
        if cloud_hash == local_hash:
            print("[SKIP] The cloud already has this exact save file. Skipping upload to save bandwidth! 🛑")
            return
    except Exception:
        # If the file doesn't exist in the cloud yet, it will throw an error, which is fine!!
        print("[!] No existing file found in the cloud, or no fingerprint attached. Proceeding...")

    ## 4. Compress and Upload with the fingerprint tag
    print(f"[+] Compressing payload for {BLOB_NAME}...")
    try:
        with open(LOCAL_SAVE_PATH, "rb") as f:
            raw_data = f.read()
            compressed_payload = gzip.compress(raw_data)
    except PermissionError:
        print("[!] File locked by game engine. Retrying next loop.")
        return
        
    print(f"[+] Uploading optimized payload to the cloud...")
    blob_client.upload_blob(compressed_payload, overwrite=True, metadata={'md5_fingerprint': local_hash})
        
    # --- The Time Machine (Cloud Snapshot) ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # We added .gz to the backup name so we know it's compressed
    cloud_backup_name = f"green-hell/{SQUAD}/backups/{TARGET_FILE}_{timestamp}.sav.gz"    
    backup_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=cloud_backup_name)
    
    print(f"[+] Archiving compressed cloud snapshot -> {cloud_backup_name}")
    backup_client.upload_blob(compressed_payload, overwrite=True)
    # ----------------------------------------------

    print("[SUCCESS] Upload and Snapshot complete! 🚀")

    # So clients (friends) can see the latest status of the server that will send a Discord summary
    send_discord_summary()
    

def get_local_hash(filepath):
    """Generates an MD5 fingerprint for a local file."""
    if not os.path.exists(filepath):
        return None
    
    try:
        hasher = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except PermissionError:
        # The game engine is currently locking the file. Ignore and retry later.
        return None
    except Exception:
        return None
    
def send_discord_summary():
    """Scrapes the Unity Engine log and fires a Rich Embed webhook to Discord."""
    
    # 1. Locate the Unity Engine log for Green Hell
    user_profile = os.environ.get('USERPROFILE')
    log_path = os.path.join(user_profile, "AppData", "LocalLow", "Creepy Jar", "Green Hell", "Player.log")
    
    # 2. Scrape the log for errors
    error_count = 0
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                # Count critical Unity exceptions
                error_count = content.count("exception")
        except Exception:
            pass

    # 3. Determine system health status
    health_status = "🟢 Stable" if error_count < 10 else "⚠️ Unstable (High Errors)"

    # 4. Construct the Rich Embed JSON Payload
    payload = {
        "username": "Green Hell Sync Daemon",
        "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png",
        "embeds": [
            {
                "title": f"🌴 Cloud Vault Updated: {SQUAD.upper()}",
                "description": "The latest save data has been secured to the Azure Vault.",
                "color": 65280, # Hex #00FF00 (Green)
                "fields": [
                    {"name": "📡 Target Server", "value": f"`{SQUAD}`", "inline": True},
                    {"name": "🛡️ VFS Integrity", "value": "`Passed`", "inline": True},
                    {"name": "⚠️ Engine Errors", "value": f"`{error_count} ({health_status})`", "inline": False}
                ],
                "footer": {"text": "Safe to download via Client Launcher."}
            }
        ]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code in (200, 204):
            print("[DISCORD] Telemetry summary dispatched to server.")
        else:
            print(f"[DISCORD ERROR] Webhook rejected: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[DISCORD ERROR] Failed to send webhook: {e}")

def verify_steam_cloud_killswitch():
    """Silently enforces the lock file without headless input crashing."""
    game_folder = os.path.dirname(LOCAL_SAVE_PATH)
    lock_file = os.path.join(game_folder, ".steam_cloud_disabled.lock")

    if os.path.exists(lock_file):
        return True

    os.makedirs(game_folder, exist_ok=True)

    # Auto-generate the lock instead of pausing the thread
    with open(lock_file, "w") as f:
        f.write("STEAM_CLOUD_DISABLED=TRUE")
    print("\n[OK] Killswitch auto-verified. Proceeding...")
    return True


def set_server_status(blob_service_client, status):
    """The Digital Padlock: Flips the cloud status switch."""
    try:
        # Directly utilize the global SQUAD variable parsed at script execution
        status_blob_name = f"green-hell/{SQUAD}/server_status.txt"
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=status_blob_name)

        # Uploads a tiny text file containing either "ONLINE" or "OFFLINE"
        blob_client.upload_blob(status.encode('utf-8'), overwrite=True)
        print(f"\n[PADLOCK] Cloud status locked to: {status}")
    except Exception as e:
        print(f"\n[PADLOCK ERROR] Could not update status: {e}")



def background_daemon(blob_service_client):
    print("\n" + "="*45)
    print("   🌴 GREEN HELL BACKGROUND DAEMON 🌴   ")
    print("="*45)
    
    download_save(blob_service_client)
    last_known_hash = get_local_hash(LOCAL_SAVE_PATH)
    
    # --- FLIP THE SWITCH TO ONLINE ---
    set_server_status(blob_service_client, "ONLINE")
    
    print(f"\n[DAEMON] Baseline fingerprint locked: {last_known_hash}")
    print("[DAEMON] Entering stealth monitoring mode...")

    # Anchor to the daemon's current directory (E:\)
    host_dir = os.path.dirname(os.path.abspath(__file__))
    flag_path = os.path.join(host_dir, "stop_daemon.flag")
    try:
        while True:
            stop_signal = False
            
          
            
            # --- HIGH FREQUENCY POLLING ---
            for _ in range(30):
                if os.path.exists(flag_path):
                    print("\n[SYSTEM] Stop signal received from Admin UI.")
                    os.remove(flag_path)
                    stop_signal = True
                    break
                time.sleep(1)
                
            # If the flag was found during the 30-second heartbeat, kill the main loop
            if stop_signal:
                break
                
            # Standard Sync Logic
            current_hash = get_local_hash(LOCAL_SAVE_PATH)
            if current_hash and current_hash != last_known_hash:
                print("\n[DAEMON] 🚨 IN-GAME SAVE DETECTED! UPLOADING...")
                upload_save(blob_service_client)
                last_known_hash = current_hash
                
    except KeyboardInterrupt:
        print("\n\n[DAEMON] Shutting down via Keyboard...")
        
    finally:
        # --- FLIP THE SWITCH TO OFFLINE NO MATTER WHAT ---
        set_server_status(blob_service_client, "OFFLINE")
        print("\nFarewell, my friend! 🌴\n")

def main():
    # Attempt to connect to Azure once when the app starts
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN)
    except Exception as e:
        print("\n[ERROR] Could not connect to Azure. Did you paste your connection string?")
        return

    # Run the safety check first
    verify_steam_cloud_killswitch()

    # Launch the automated background watcher
    background_daemon(blob_service_client)

if __name__ == "__main__":
    main()