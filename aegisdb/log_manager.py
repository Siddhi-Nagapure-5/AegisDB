import os
import threading
from typing import List

from aegisdb.config import LOG_FILE_NAME
from aegisdb.log_record import LogRecord

class LogManager:
    """
    Manages the Write-Ahead Log (WAL), enforcing that log records
    are sequentially written and durably flushed to disk.
    """

    def __init__(self, log_file_path: str = LOG_FILE_NAME):
        self.log_file_path = log_file_path
        self.next_lsn = 1
        self.flushed_lsn = 0
        self.log_buffer: List[LogRecord] = []
        
        self.lock = threading.Lock()
        
        if not os.path.exists(self.log_file_path):
            with open(self.log_file_path, 'wb') as f:
                pass
                
        self.file = open(self.log_file_path, 'a+b')

    def append_record(self, record: LogRecord) -> int:
        """Appends a record to the log buffer and assigns it an LSN."""
        with self.lock:
            record.lsn = self.next_lsn
            self.next_lsn += 1
            self.log_buffer.append(record)
            return record.lsn

    def flush(self):
        """Forces all buffered log records to physical disk."""
        with self.lock:
            if not self.log_buffer:
                return
                
            for record in self.log_buffer:
                self.file.write(record.serialize())
                
            self.file.flush()
            os.fsync(self.file.fileno())
            
            self.flushed_lsn = self.log_buffer[-1].lsn
            self.log_buffer.clear()

    def enforce_wal(self, page_lsn: int):
        """
        Ensures that log records up to `page_lsn` are safely flushed
        to disk before the corresponding page can be written to disk.
        """
        if page_lsn > self.flushed_lsn:
            self.flush()

    def close(self):
        self.flush()
        self.file.close()
