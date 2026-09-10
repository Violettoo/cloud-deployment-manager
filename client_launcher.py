import customtkinter as ctk
import os
import sys
import shutil
import urllib.request
import psutil
import subprocess
import threading
import glob
import json
import time
from azure.storage.blob import BlobServiceClient

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

sys.stdout = Tee("client_launcher.log")


# Configure the visual theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# --- DYNAMIC PATH CONFIGURATION ---
# Automatically detects the current folder 
STEAM_GH_PATH = os.getcwd()




def is_game_running():
    """Checks Windows Task Manager for Green Hell."""
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] and proc.info['name'].lower() == "gh.exe":
            return True
    return False

def run_watchdog(squad_id):
    """Stays awake in the background to clean up after the game closes."""
    
   # Base paths pointing directly to squad cache and game root
    vault_path = os.path.join(STEAM_GH_PATH, ".VaultCache", squad_id)
    
    # Inject symlinks dynamically across root
    generate_holographic_mods(vault_path, STEAM_GH_PATH)

    print("[WATCHDOG] Launching Green Hell via Steam...")
    os.system("start steam://rungameid/815370")
    
    print("[WATCHDOG] Waiting for game engine to boot...")
    game_detected = False
        
    # Wait up to 60 seconds for the game to appear in Task Manager
    for _ in range(60): 
        if is_game_running():
            game_detected = True
            break
        time.sleep(1)
        
    if not game_detected:
        print("[WATCHDOG ERROR] Game didn't launch in time. Aborting and cleaning up.")
        nuclear_sanitation()
        return

    print("[WATCHDOG] Game is active. Monitoring process in the background...")
    
    # The Infinite Loop: Check every 5 seconds if anyone is still playing
    while is_game_running():
        time.sleep(5) 
        
    # THE TRIGGER: The loop breaks because the game closed!
    print("[WATCHDOG] Game exit detected. Initiating Vanilla Restoration...")
    
    # Run the exact same cleanup sweep used on startup
    nuclear_sanitation()
    
    print("[WATCHDOG] Environment is pristine. Shutting down system. Goodbye!")

def nuclear_sanitation():
    """Self-healing function: Purges orphaned mods and restores vanilla backups."""
    print("[SANITATION] Commencing Pre-Flight Sweep...")
    
    # 1. Vaporize the custom Mods folder if it exists
    mods_folder = os.path.join(STEAM_GH_PATH, "Mods")
    if os.path.exists(mods_folder):
        print("[SANITATION] Orphaned Mods folder detected. Vaporizing...")
        try:
            # Use rmtree (Remove Tree) to brutally delete the folder and everything inside it
            shutil.rmtree(mods_folder) 
        except Exception as e:
            print(f"[SANITATION ERROR] Failed to delete Mods folder: {e}")

    # 2. Restore any overwritten base files (The .vanilla_backup protocol)
    # This searches the entire Green Hell folder for anything ending in .vanilla_backup
    search_pattern = os.path.join(STEAM_GH_PATH, "**", "*.vanilla_backup")
    backups = glob.glob(search_pattern, recursive=True)
    
    for backup_path in backups:
        # Get the original file name by removing the .vanilla_backup extension
        original_file_path = backup_path.replace(".vanilla_backup", "")
        
        print(f"[SANITATION] Restoring core file: {os.path.basename(original_file_path)}")
        
        # Delete the tampered mod file if it exists
        if os.path.exists(original_file_path):
            os.remove(original_file_path)
            
        # Rename the backup back to the original name
        os.rename(backup_path, original_file_path)
        
    print("[SANITATION] Sweep Complete. Environment is 100% Vanilla.")


def generate_holographic_mods(vault_path, steam_root_path):
    """Dynamically creates Symlinks based on relative paths defined in the manifest."""
    print("\n[ENGINE] Enforcing Manifest-Driven Load Order...")
    
    load_order_path = os.path.join(vault_path, "load_order.txt")
    
    if not os.path.exists(load_order_path):
        print("[WARN] load_order.txt missing. Execution sequence undefined. Aborting injection.")
        return

    with open(load_order_path, "r") as f:
        # Read lines and strip empty space
        manifest_entries = [line.strip() for line in f if line.strip()]
        
    print(f"[ENGINE] Parsed {len(manifest_entries)} entries. Commencing dynamic routing...")
    
    for relative_path in manifest_entries:
        # Source file inside the hidden Azure vault cache
        real_file_path = os.path.join(vault_path, relative_path)
        
        # Target destination inside the active Green Hell game directory
        symlink_target = os.path.join(steam_root_path, relative_path)
        
        if os.path.exists(real_file_path):
            # Automatically creates subdirectories (e.g., BepInEx/plugins) 
            os.makedirs(os.path.dirname(symlink_target), exist_ok=True)
            try:
                if not os.path.exists(symlink_target):
                    os.symlink(real_file_path, symlink_target)
                    print(f"  -> [LINKED] {relative_path}")
                else:
                    print(f"  -> [EXISTS] {relative_path}")
            except OSError as e:
                print(f"[ERROR] Symlink failed for {relative_path}. (Run as Admin) {e}")
        else:
            print(f"[WARN] Manifest requested '{relative_path}', but it is missing from vault.")


class ClientLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Instantly run the sanitation sweep before the GUI renders!
        nuclear_sanitation()

        # --- WHITE-LABEL CONFIG READER ---
        try:
            with open("server_config.json", "r") as f:
                config = json.load(f)
                self.server_name = config["display_name"]
                self.squad_id = config["squad_id"]
        except FileNotFoundError:
            self.server_name = "Unknown Server"
            self.squad_id = "default"

        self.title(f"{self.server_name} - Server Sync")
        self.geometry("450x300") 
        self.resizable(False, False)
        self.configure(fg_color="#0d0d0d")

        self.label = ctk.CTkLabel(self, text=f"Green Hell: {self.server_name}", font=("Roboto", 22, "bold"), text_color="white")
        self.label.pack(pady=(20, 5))
        
        self.sub_label = ctk.CTkLabel(self, text="1-Click Mod Sync & Launch", font=("Roboto", 14), text_color="#A0A0A0")
        self.sub_label.pack(pady=(0, 20))


        
        self.btn_launch = ctk.CTkButton(self, text="Sync Mods & Play", width=250, height=50, 
                                        font=("Roboto", 16, "bold"), 
                                        fg_color="#121212", hover_color="#1f1f1f", 
                                        border_color="#00ffcc", border_width=2, text_color="#00ffcc",
                                        command=self.start_preflight_thread)
        self.btn_launch.pack(pady=20)

        self.console_label = ctk.CTkLabel(self, text="Ready.", font=("Consolas", 12), text_color="white")
        self.console_label.pack(pady=10)

        self.progress_bar = ctk.CTkProgressBar(self, width=300, height=10, fg_color="#1f1f1f", progress_color="#00ffcc")
        self.progress_bar.set(0)
        
   

    def log(self, message, error=False):
        color = "#dc3545" if error else "#28a745" if "SUCCESS" in message else "white"
        self.console_label.configure(text=message, text_color=color)
        print(f"[GATEKEEPER] {message}")

    def start_preflight_thread(self):
        self.btn_launch.configure(state="disabled") 
        threading.Thread(target=self.run_preflight, daemon=True).start()

    def run_preflight(self):
        # CHECK 1: (REMOVED) - Clients do not need to disable Steam Cloud.

        # CHECK 2: The Process Lock
        self.log("Scanning Windows for running games...")
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and proc.info['name'].lower() == "gh.exe":
                self.log("ERROR: Green Hell is currently running! Close it.", error=True)
                self.btn_launch.configure(state="normal")
                return

        # CHECK 3: The Capacity Audit
        self.log("Auditing hard drive capacity...")
        required_space_gb = 2
        total, used, free = shutil.disk_usage("C:\\")
        free_gb = free / (2**30)
        
        if free_gb < required_space_gb:
            self.log(f"ERROR: Need {required_space_gb}GB space, you have {free_gb:.1f}GB.", error=True)
            self.btn_launch.configure(state="normal")
            return

       # CHECK 4: The Network Handshake & Digital Padlock
        self.log("Pinging Cloud Server...")
        try:
            # 1. Check if they have internet first
            urllib.request.urlopen('http://www.google.com', timeout=3) 
            
            # 2. THE DIGITAL PADLOCK CHECK
            self.log("Scanning cloud for Host signal...")
            
            
            AZURE_CONN = "DefaultEndpointsProtocol=https;AccountName..."
            blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN)
            
            status_blob_name = f"green-hell/{self.squad_id}/server_status.txt"
            blob_client = blob_service_client.get_blob_client(container="games", blob=status_blob_name)
            
            # Download and read the tiny text file
            # Force string sanitization 
            status = blob_client.download_blob().readall().decode('utf-8').strip()
            
            with open("launcher_debug.log", "a", encoding="utf-8") as logf:
                logf.write(f"[{time.ctime()}] squad_id={self.squad_id!r} blob={status_blob_name!r} raw_status={status!r}\n")

            if status != "ONLINE":
                # If host (me) is offline, the client cannot proceed
                self.log("ACCESS DENIED: HOST IS OFFLINE.", error=True)
                self.btn_launch.configure(state="normal")
                return
                
        except urllib.error.URLError:
            self.log("ERROR: Cannot reach the internet.", error=True)
            self.btn_launch.configure(state="normal")
            return
        except Exception as e:
            with open("launcher_debug.log", "a", encoding="utf-8") as logf:
                logf.write(f"[{time.ctime()}] AZURE STATUS CHECK FAILED\n")
                logf.write(f"  squad_id  = {self.squad_id!r}\n")
                logf.write(f"  blob_path = {status_blob_name!r}\n")
                logf.write(f"  exception = {repr(e)}\n\n")

            self.log("ACCESS DENIED: Host signal not found.", error=True)
            self.btn_launch.configure(state="normal")
            return

    
       # --- PRE-FLIGHT PASSED ---
        self.log(f"Environment Secure. Establishing handshake with {self.squad_id}...")
        
        # 1. Reveal the progress bar
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0.3)
        
        self.log("Triggering Azure Sync Node (suffer2gether)...")
        
        # 2. Execute the actual download tool
        try:
            # Tries to run the compiled .exe first (for when the zip files is distributed)
            subprocess.run(["cloud_fetcher.exe"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except FileNotFoundError:
            try:
                # Fallback: Runs the .py version if testing in VS Code
                subprocess.run(["python", "cloud_fetcher.py"], check=True)
            except Exception as e:
                self.log(f"SYNC FATAL ERROR: {e}", error=True)
                self.btn_launch.configure(state="normal")
                return
        except subprocess.CalledProcessError:
            self.log("SYNC FAILED. Check Azure connection.", error=True)
            self.btn_launch.configure(state="normal")
            return

        self.progress_bar.set(1.0)
        self.log("Payload synchronized successfully.", error=False)
        
        # 3. THE VANISH COMMAND: Closes GUI and triggers Watchdog symlinks
        self.launch_approved = True  
        self.after(2000, self.destroy)

if __name__ == "__main__":
    app = ClientLauncher()
    app.launch_approved = False 
    
    # Capture the dynamic namespace ID before the UI is destroyed
    target_namespace = app.squad_id 
    
    app.mainloop() 
    
    if getattr(app, "launch_approved", False):
        # Pass the ID to the watchdog for targeted symlinking
        run_watchdog(target_namespace)