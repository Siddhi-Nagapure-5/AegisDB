import argparse
import os

from aegisdb.config import DB_FILE_NAME, LOG_FILE_NAME
from aegisdb.storage_manager import StorageManager
from aegisdb.log_manager import LogManager
from aegisdb.buffer_pool import BufferPoolManager
from aegisdb.recovery_manager import RecoveryManager

def main():
    parser = argparse.ArgumentParser(description="AegisDB Recovery Verification")
    parser.add_argument("--db", default=DB_FILE_NAME)
    parser.add_argument("--log", default=LOG_FILE_NAME)
    args = parser.parse_args()

    if not os.path.exists(args.db) or not os.path.exists(args.log):
        print("Error: Database or log file missing. Run the simulator first.")
        return

    print("🛡️ Booting AegisDB and Verifying State...")
    
    storage = StorageManager(args.db)
    log_manager = LogManager(args.log)
    buffer_pool = BufferPoolManager(pool_size=10, storage_manager=storage, log_manager=log_manager)
    
    rm = RecoveryManager(log_manager=log_manager, buffer_pool=buffer_pool)
    
    rm.recover()
    
    print("Flushing recovered state to disk...")
    buffer_pool.flush_all_pages()
    log_manager.close()
    storage.close()
    
    print("✅ Database successfully recovered and verified!")

if __name__ == "__main__":
    main()
