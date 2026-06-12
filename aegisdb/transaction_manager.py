import threading
from typing import Dict

from aegisdb.log_manager import LogManager
from aegisdb.buffer_pool import BufferPoolManager
from aegisdb.log_record import LogRecord, LogRecordType

class TransactionManager:
    """
    Coordinates transactions, logging, and buffer pool operations.
    """

    def __init__(self, log_manager: LogManager, buffer_pool: BufferPoolManager):
        self.log_manager = log_manager
        self.buffer_pool = buffer_pool
        self.next_tx_id = 1
        
        # TxID -> Last LSN
        self.active_txns: Dict[int, int] = {}
        self.lock = threading.Lock()

    def begin(self) -> int:
        """Starts a new transaction."""
        with self.lock:
            tx_id = self.next_tx_id
            self.next_tx_id += 1
            
        record = LogRecord(lsn=0, prev_lsn=0, tx_id=tx_id, record_type=LogRecordType.BEGIN)
        lsn = self.log_manager.append_record(record)
        
        with self.lock:
            self.active_txns[tx_id] = lsn
            
        return tx_id

    def update(self, tx_id: int, page_id: int, offset: int, new_data: bytes):
        """Modifies data within a page as part of a transaction."""
        with self.lock:
            if tx_id not in self.active_txns:
                raise ValueError(f"Transaction {tx_id} is not active")
            prev_lsn = self.active_txns[tx_id]

        page = self.buffer_pool.fetch_page(page_id)
        
        before_image = page.read_data(offset, len(new_data))
        
        record = LogRecord(
            lsn=0,
            prev_lsn=prev_lsn,
            tx_id=tx_id,
            record_type=LogRecordType.UPDATE,
            page_id=page_id,
            offset=offset,
            before_image=before_image,
            after_image=new_data
        )
        lsn = self.log_manager.append_record(record)
        
        page.write_data(offset, new_data)
        page.page_lsn = lsn
        
        self.buffer_pool.unpin_page(page_id, is_dirty=True)
        
        with self.lock:
            self.active_txns[tx_id] = lsn

    def commit(self, tx_id: int):
        """Commits a transaction, ensuring durability."""
        with self.lock:
            if tx_id not in self.active_txns:
                raise ValueError(f"Transaction {tx_id} is not active")
            prev_lsn = self.active_txns[tx_id]
            del self.active_txns[tx_id]
            
        record = LogRecord(lsn=0, prev_lsn=prev_lsn, tx_id=tx_id, record_type=LogRecordType.COMMIT)
        self.log_manager.append_record(record)
        
        self.log_manager.flush()
