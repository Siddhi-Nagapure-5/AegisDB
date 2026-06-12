import argparse
import multiprocessing
import os
import signal
import sys
import time
import random

from aegisdb.config import DB_FILE_NAME, LOG_FILE_NAME
from aegisdb.storage_manager import StorageManager
from aegisdb.log_manager import LogManager
from aegisdb.buffer_pool import BufferPoolManager
from aegisdb.transaction_manager import TransactionManager

def db_process_workload(num_transactions: int):
    """
    Runs an endless or fixed-number transaction workload.
    If the process is killed by SIGKILL, this will abruptly stop.
    """
    print(f"Starting database worker process [PID: {os.getpid()}]")
    
    storage = StorageManager(DB_FILE_NAME)
    for i in range(5):
        try:
            storage.read_page(i)
        except Exception:
            storage.allocate_page()
            
    log_manager = LogManager(LOG_FILE_NAME)
    buffer_pool = BufferPoolManager(pool_size=10, storage_manager=storage, log_manager=log_manager)
    tm = TransactionManager(log_manager=log_manager, buffer_pool=buffer_pool)
    
    completed = 0
    while completed < num_transactions or num_transactions <= 0:
        tx_id = tm.begin()
        
        for _ in range(random.randint(1, 3)):
            page_id = random.randint(0, 4)
            offset = random.randint(16, 100)
            new_data = f"TX{tx_id}-UPD-{time.time()}".encode()[:20].ljust(20, b' ')
            tm.update(tx_id, page_id, offset, new_data)
            time.sleep(0.05)
            
        tm.commit(tx_id)
        completed += 1
        
        if completed % 10 == 0:
            print(f"  Worker: Completed {completed} transactions...")
            
    buffer_pool.flush_all_pages()
    log_manager.close()
    storage.close()
    print("Database worker finished gracefully.")

def main():
    parser = argparse.ArgumentParser(description="AegisDB Crash Simulator")
    parser.add_argument("--transactions", type=int, default=100, help="Number of transactions to run")
    parser.add_argument("--crash-interval", type=float, default=2.5, help="Seconds before pulling the plug")
    args = parser.parse_args()

    if os.path.exists(DB_FILE_NAME): os.remove(DB_FILE_NAME)
    if os.path.exists(LOG_FILE_NAME): os.remove(LOG_FILE_NAME)

    print("🛡️ Starting AegisDB Simulator...")
    print(f"Will run {args.transactions} transactions, but crash after {args.crash_interval}s.")
    
    worker = multiprocessing.Process(target=db_process_workload, args=(args.transactions,))
    worker.start()
    
    time.sleep(args.crash_interval)
    
    if worker.is_alive():
        print(f"\n⚡ CRASH INITIATED: Sending SIGKILL to Process {worker.pid}")
        os.kill(worker.pid, signal.SIGTERM if sys.platform == "win32" else signal.SIGKILL)
        worker.join()
        print("💥 System has crashed abruptly. Data pages in memory were lost!")
        print("Run `python -m aegisdb.verify` to recover and verify the database.")
    else:
        print("\nProcess finished before crash interval.")

if __name__ == "__main__":
    main()
