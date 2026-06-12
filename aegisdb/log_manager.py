import os
import struct
import threading
from typing import List, Dict, Iterator, Optional

from aegisdb.config import LOG_FILE_NAME
from aegisdb.log_record import LogRecord

class LogManager:
    """
    Manages the Write-Ahead Log (WAL), enforcing that log records
    are sequentially written and durably flushed to disk.
    Provides utilities for recovery.
    """

    def __init__(self, log_file_path: str = LOG_FILE_NAME):
        self.log_file_path = log_file_path
        self.next_lsn = 1
        self.flushed_lsn = 0
        self.log_buffer: List[LogRecord] = []
        self.lsn_offsets: Dict[int, int] = {}
        
        self.lock = threading.Lock()
        
        if not os.path.exists(self.log_file_path):
            with open(self.log_file_path, 'wb') as f:
                pass
                
        self.file = open(self.log_file_path, 'a+b')
        self._build_index()

    def _build_index(self):
        """Scans the log file to build an LSN -> Offset index and recover next_lsn."""
        with self.lock:
            self.file.seek(0)
            while True:
                file_offset = self.file.tell()
                header = self.file.read(LogRecord.HEADER_SIZE)
                if len(header) < LogRecord.HEADER_SIZE:
                    break
                
                lsn = struct.unpack("<Q", header[:8])[0]
                self.lsn_offsets[lsn] = file_offset
                
                b_len_data = self.file.read(4)
                if not b_len_data: break
                b_len = struct.unpack("<I", b_len_data)[0]
                self.file.seek(b_len, os.SEEK_CUR)
                
                a_len_data = self.file.read(4)
                if not a_len_data: break
                a_len = struct.unpack("<I", a_len_data)[0]
                self.file.seek(a_len, os.SEEK_CUR)
                
                self.next_lsn = max(self.next_lsn, lsn + 1)
                self.flushed_lsn = max(self.flushed_lsn, lsn)
            
            # Reset pointer to end for appending
            self.file.seek(0, os.SEEK_END)

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
                file_offset = self.file.tell()
                self.lsn_offsets[record.lsn] = file_offset
                self.file.write(record.serialize())
                
            self.file.flush()
            os.fsync(self.file.fileno())
            
            self.flushed_lsn = self.log_buffer[-1].lsn
            self.log_buffer.clear()

    def enforce_wal(self, page_lsn: int):
        if page_lsn > self.flushed_lsn:
            self.flush()

    def read_record(self, lsn: int) -> Optional[LogRecord]:
        """Reads a specific log record by its LSN from disk."""
        self.flush()  # Ensure it's on disk
        with self.lock:
            if lsn not in self.lsn_offsets:
                return None
            self.file.seek(self.lsn_offsets[lsn])
            
            # Read header
            header = self.file.read(LogRecord.HEADER_SIZE)
            if not header: return None
            
            # Read lengths
            b_len = struct.unpack("<I", self.file.read(4))[0]
            before_image = self.file.read(b_len)
            
            a_len = struct.unpack("<I", self.file.read(4))[0]
            after_image = self.file.read(a_len)
            
            raw_data = header + struct.pack("<I", b_len) + before_image + struct.pack("<I", a_len) + after_image
            
            # Restore file pointer
            self.file.seek(0, os.SEEK_END)
            return LogRecord.deserialize(raw_data)

    def read_log_forward(self, start_lsn: int = 1) -> Iterator[LogRecord]:
        """Yields log records sequentially starting from start_lsn."""
        self.flush()
        current_lsn = start_lsn
        while True:
            record = self.read_record(current_lsn)
            if not record:
                break
            yield record
            current_lsn += 1

    def close(self):
        self.flush()
        self.file.close()
