import os
import json
import hashlib
import customtkinter as ctk
from concurrent.futures import ThreadPoolExecutor, as_completed
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv


load_dotenv()
AZURE_CONN = os.getenv("AZURE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "games")

def get_file_hash(filepath):
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def process_file(local_path, blob_client, relative_path):
    local_hash = get_file_hash(local_path)
    try:
        if blob_client.get_blob_properties().metadata.get('md5') == local_hash:
            return f"[SKIP] {relative_path}"
    except Exception:
        pass 
    with open(local_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True, metadata={'md5': local_hash})
    return f"[UPLOAD] {relative_path}"

class ModStateManager(ctk.CTk):
    def __init__(self):
        super().__init__()
        super().__init__()
        self.title("Enterprise State Manager")
        self.geometry("450x550")
        
        self.game_root = os.getcwd()
        self.master_dir = os.path.join(self.game_root, "MasterMods")
        self.profiles_dir = os.path.join(self.game_root, "AdminProfiles")
        
        os.makedirs(self.master_dir, exist_ok=True)
        os.makedirs(self.profiles_dir, exist_ok=True)
        
        # Load available profiles dynamically from environments.json or database
        env_db_path = os.path.join(self.profiles_dir, "environments.json")
        try:
            if os.path.exists(env_db_path):
                with open(env_db_path, "r") as f:
                    env_data = json.load(f)
                    available_profiles = list(env_data.keys())
            else:
                available_profiles = ["cluster_alpha", "cluster_beta"]
        except (FileNotFoundError, json.JSONDecodeError):
            available_profiles = ["cluster_alpha", "cluster_beta"]

        # Dynamic Cluster/Environment Selector
        default_selection = available_profiles[0] if available_profiles else "default"
        self.squad_var = ctk.StringVar(value=default_selection)
        self.squad_menu = ctk.CTkOptionMenu(
            self, 
            variable=self.squad_var, 
            values=available_profiles, 
            command=self.load_profile
        )
        self.squad_menu.pack(pady=15)
        
        # Mod List UI
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Master Repository")
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)
        self.checkboxes = {}
        
        self.refresh_repository()
        self.load_profile(self.squad_var.get())
        
        ctk.CTkButton(
            self, 
            text="Compile State & Deploy", 
            fg_color="#28a745", 
            hover_color="#218838", 
            command=self.deploy_state
        ).pack(pady=20)

    def refresh_repository(self):
        """Scans MasterMods and generates dynamic checkboxes."""
        mod_folders = [f for f in os.listdir(self.master_dir) if os.path.isdir(os.path.join(self.master_dir, f))]
        for mod in mod_folders:
            var = ctk.BooleanVar()
            cb = ctk.CTkCheckBox(self.scroll_frame, text=mod, variable=var)
            cb.pack(anchor="w", pady=5, padx=10)
            self.checkboxes[mod] = var

    def load_profile(self, squad_id):
        """Loads saved states so you don't have to re-select mods."""
        profile_path = os.path.join(self.profiles_dir, f"{squad_id}.json")
        saved_mods = []
        if os.path.exists(profile_path):
            with open(profile_path, "r") as f:
                saved_mods = json.load(f)
                
        for mod, var in self.checkboxes.items():
            var.set(mod in saved_mods)

    def deploy_state(self):
        squad_id = self.squad_var.get()
        selected_mods = [mod for mod, var in self.checkboxes.items() if var.get()]
        
        # Save state locally for future
        with open(os.path.join(self.profiles_dir, f"{squad_id}.json"), "w") as f:
            json.dump(selected_mods, f)
            
        print(f"\n[ENGINE] Compiling Build for {squad_id.upper()}...")
        manifest, load_order = [], []
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN)
        
        for mod in selected_mods:
            mod_path = os.path.join(self.master_dir, mod)
            for root, _, files in os.walk(mod_path):
                for file in files:
                    local_filepath = os.path.join(root, file)
                    rel_path = os.path.relpath(local_filepath, mod_path)
                    
                    load_order.append(rel_path)
                    cloud_path = f"green-hell/{squad_id}/{rel_path}".replace("\\", "/")
                    
                    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=cloud_path)
                    manifest.append((local_filepath, blob_client, rel_path))
                    
        # Write master blueprint
        blueprint_local = os.path.join(self.game_root, "load_order.txt")
        with open(blueprint_local, "w") as f:
            f.write("\n".join(load_order))
            
        manifest.append((blueprint_local, blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=f"green-hell/{squad_id}/load_order.txt"), "load_order.txt"))        
        print(f"[DEPLOY] Pushing {len(manifest)} dependencies. Igniting ThreadPool...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_file, item[0], item[1], item[2]) for item in manifest]
            for future in as_completed(futures): print(future.result())
        print("[SUCCESS] Pipeline Terminated cleanly.")

        self.title("Deployment Success! Closing...")
        self.after(1000, self.destroy)

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = ModStateManager()
    app.mainloop()