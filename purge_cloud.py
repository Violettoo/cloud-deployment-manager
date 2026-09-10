import os
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

load_dotenv()

AZURE_CONN = os.getenv("AZURE_CONNECTION_STRING")
CONTAINER_NAME = "games"
SQUAD_ID = os.getenv("CLIENT_NODE_ID", "client-node-01")

def sanitize_cloud():
    print(f"[PURGE] Scanning Azure vault for {SQUAD_ID}...")
    blob_service = BlobServiceClient.from_connection_string(AZURE_CONN)
    container = blob_service.get_container_client(CONTAINER_NAME)
    
    blobs = container.list_blobs(name_starts_with=f"{SQUAD_ID}/")
    deleted = 0
    
    for blob in blobs:
        # We preserve your save files and server status!
        if "backups/" in blob.name or "MPSlot" in blob.name or "server_status" in blob.name:
            continue
            
        print(f"  -> [DELETING] {blob.name}")
        container.delete_blob(blob.name)
        deleted += 1
        
    print(f"[SUCCESS] {deleted} orphaned artifacts vaporized from the cloud.")

if __name__ == "__main__":
    sanitize_cloud()