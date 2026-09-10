import customtkinter as ctk
import subprocess
import json
import os

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

ENV_DB = "environments.json"

class AdminDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Host Command Node - Green Hell")
        self.geometry("450x480")
        self.resizable(False, False)

        self.is_daemon_running = False

        # 1. Load Dynamic State
        self.environments = self.load_environments()

        self.label = ctk.CTkLabel(self, text="Admin Control Center", font=("Roboto", 22, "bold"))
        self.label.pack(pady=20)

        # 2. Dynamic Dropdown 
        self.label_env = ctk.CTkLabel(self, text="Target Server Environment:")
        self.label_env.pack()
        
        # Extract keys safely to avoid KeyError on boot
        env_keys = list(self.environments.keys())
        initial_value = env_keys[0] if env_keys else "default_vault"
        
        self.env_var = ctk.StringVar(value=initial_value)
        self.env_dropdown = ctk.CTkOptionMenu(
            self, variable=self.env_var, 
            values=env_keys,
            command=self.update_config
        )
        self.env_dropdown.pack(pady=5)

        # 3. State Mutation Button
        self.btn_add = ctk.CTkButton(self, text="+ Create New Server Name", 
                                     width=200, height=28, fg_color="#555555", hover_color="#333333",
                                     command=self.add_environment)
        self.btn_add.pack(pady=5)

        # Execution Nodes
        self.btn_deploy = ctk.CTkButton(self, text="1. Deploy Mod Payload", width=250, height=40, command=self.run_deployer)
        self.btn_deploy.pack(pady=(15,5))

        self.btn_daemon = ctk.CTkButton(self, text="2. Boot Sync Daemon", width=250, height=40, fg_color="#28a745", hover_color="#218838", command=self.toggle_daemon)
        self.btn_daemon.pack(pady=5)

        self.btn_game = ctk.CTkButton(self, text="3. Launch Green Hell", width=250, height=40, fg_color="#8b0000", hover_color="#660000", command=self.launch_game)
        self.btn_game.pack(pady=15)

        self.status_label = ctk.CTkLabel(self, text="System Idle...", font=("Roboto", 12, "italic"))
        self.status_label.pack(side="bottom", pady=10)

    def load_environments(self):
        if not os.path.exists(ENV_DB):
            default_db = {
                "cluster_alpha": {
                    "display_name": "Production Server 01",
                    "target_file": "save_slot_01.sav"
                },
                "cluster_beta": {
                    "display_name": "Staging Server 02",
                    "target_file": "save_slot_02.sav"
                }
            }
            with open(ENV_DB, 'w') as f:
                json.dump(default_db, f, indent=4)
            return default_db
            
        with open(ENV_DB, 'r') as f:
            return json.load(f)

    def add_environment(self):
        dialog = ctk.CTkInputDialog(text="Enter Display Name (e.g., Weekend Survival):", title="New Environment")
        display_name = dialog.get_input()
        
        if display_name and display_name.strip() != "":
            squad_id = display_name.strip().replace(" ", "_").lower()
            
            if squad_id not in self.environments:
                self.environments[squad_id] = {
                    "display_name": display_name,
                    "target_file": "MPSlot0.sav"
                }
                
                with open(ENV_DB, 'w') as f:
                    json.dump(self.environments, f, indent=4)
                
                self.env_dropdown.configure(values=list(self.environments.keys()))
                self.env_var.set(squad_id)
                self.update_config(squad_id)

    def update_config(self, selected_squad_id):
        profile = self.environments[selected_squad_id]
        display_name = profile["display_name"]
        
        # --- THE 2023 SAFEGUARD ---
        if profile["target_file"] == "MPSlot1.sav":
            self.status_label.configure(text="[FATAL ERROR] MPSlot1.sav is strictly locked!", text_color="#dc3545")
            print(f"[SECURITY] Blocked attempt to route {selected_squad_id} to MPSlot1.sav.")
            return  
        # --------------------------
        
        config_payload = {
            "squad_name": selected_squad_id,
            "target_file": profile["target_file"],
            "launcher_title": display_name,
            "local_mods_path": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Green Hell\\Mods"
        }
        with open("config.json", 'w') as f:
            json.dump(config_payload, f, indent=4)

        server_payload = {
            "display_name": display_name,
            "squad_id": selected_squad_id
        }
        with open("server_config.json", 'w') as f:
            json.dump(server_payload, f, indent=4)
            
        self.status_label.configure(text=f"Routed to: {display_name}", text_color="#ffffff")

    def run_deployer(self):
    """Launches the Enterprise State Manager GUI silently."""
    self.status_label.configure(text="Mod Manager Active...", text_color="#f39c12")
    
    # Pull the target directory from .env, or default to the current folder
    deployment_dir = os.getenv("APP_BASE_DIR", os.getcwd())
    
    subprocess.Popen(
        ["python", "deployment_mod_manager.py"], 
        cwd=deployment_dir,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    def toggle_daemon(self):
        host_dir = os.path.dirname(os.path.abspath(__file__))
        flag_path = os.path.join(host_dir, "stop_daemon.flag")

        if not self.is_daemon_running:
            if os.path.exists(flag_path):
                os.remove(flag_path)
            
            self.btn_daemon.configure(text="2. Stop Sync Daemon", fg_color="#dc3545")
            self.status_label.configure(text="Daemon Active...", text_color="#28a745")
            
            # CAPTURE THE PROCESS
            self.daemon_process = subprocess.Popen(
                ["python", "green_hell_sync.py"], 
                cwd=host_dir,
                
            )
            self.is_daemon_running = True
            
        else:
            self.status_label.configure(text="Shutting down daemon...", text_color="#f39c12")
            
            # Drops the flag in E:\
            with open(flag_path, "w") as f:
                f.write("STOP")
            
            self.btn_daemon.configure(text="2. Boot Sync Daemon", fg_color="#28a745", hover_color="#218838")
            self.status_label.configure(text="System Idle...", text_color="#ffffff")
            self.is_daemon_running = False

    def launch_game(self):
        os.system("start steam://rungameid/815370")

if __name__ == "__main__":
    app = AdminDashboard()
    
    def on_closing():
        if getattr(app, "is_daemon_running", False) and hasattr(app, "daemon_process"):
            host_dir = os.path.dirname(os.path.abspath(__file__))
            flag_path = os.path.join(host_dir, "stop_daemon.flag")
            with open(flag_path, "w") as f:
                f.write("STOP")
            try:
                app.daemon_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                app.daemon_process.terminate()
        app.destroy()
    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()