import glob
import os
import time
from threading import Timer
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from azure.storage.blob import BlobServiceClient
from green_hell_sync import upload_save, verify_steam_cloud_killswitch
from dotenv import load_dotenv

# green_hell_sync must be in same folder!!
from green_hell_sync import upload_save

# --- Configuration ---
load_dotenv()
CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
# Watch the entire folder, not just the file
WATCH_DIR = os.getenv("LOCAL_WATCH_DIR", "./default_save_dir")
list_of_saves = glob.glob(os.path.join(WATCH_DIR, "*.sav"))
if list_of_saves:
    TARGET_FILE = max(list_of_saves, key=os.path.getmtime) 
else:
    TARGET_FILE = None
# ---------------------

class SaveFileHandler(FileSystemEventHandler):
    def __init__(self, blob_service_client):
        self.blob_service_client = blob_service_client
        self.debounce_timer = None

    def on_modified(self, event):
        # Ignore directory changes and only look for specific save file
        if not event.is_directory and event.src_path.endswith(TARGET_FILE):
            print(f"\n[EVENT] Disk write detected on {TARGET_FILE}...")
            
            # If the timer is already running (game is still writing), cancel it
            if self.debounce_timer:
                self.debounce_timer.cancel()
            
            # Start a fresh 5-second countdown
            self.debounce_timer = Timer(5.0, self.trigger_upload)
            self.debounce_timer.start()

    def trigger_upload(self):
        print("\n[DAEMON] File write stabilized. Waking up upload engine...")
        try:
            upload_save(self.blob_service_client)
            print("[DAEMON] Engine returned to sleep. Listening for OS events... 🎧")
        except Exception as e:
            print(f"[DAEMON ERROR] Sync failed: {e}")

def start_daemon():
    print("="*45)
    print(" 🛡️ GREEN HELL BACKGROUND DAEMON ONLINE 🛡️ ")
    print("="*45)

    verify_steam_cloud_killswitch()

    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    
    # Set up the file system observer
    event_handler = SaveFileHandler(blob_service_client)
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=False)
    observer.start()
    
    print(f"[STATUS] Monitoring directory: {WATCH_DIR}")
    print("[STATUS] Waiting for game engine to write to disk. Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1) # Keeps the main thread alive without burning CPU
    except KeyboardInterrupt:
        print("\n[!] Shutting down daemon...")
        observer.stop()
    
    observer.join()

if __name__ == "__main__":
    start_daemon()