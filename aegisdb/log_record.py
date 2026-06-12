from enum import IntEnum
import struct
from typing import Optional

class LogRecordType(IntEnum):
    BEGIN = 1
    COMMIT = 2
    ABORT = 3
    UPDATE = 4
    CLR = 5
    CHECKPOINT = 6

class LogRecord:
    """
    Represents a single entry in the write-ahead log.
    Header format:
    LSN (8), PrevLSN (8), TxID (4), Type (2), PageID (4), Offset (2), UndoNextLSN (8) = 36 bytes
    """
    
    # Q (8), Q (8), I (4), H (2), I (4), H (2), Q (8) = 36 bytes
    HEADER_FORMAT = "<QQIHIHQ"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    
    def __init__(self, lsn: int, prev_lsn: int, tx_id: int, record_type: LogRecordType,
                 page_id: int = 0, offset: int = 0, undo_next_lsn: int = 0,
                 before_image: bytes = b'', after_image: bytes = b''):
        self.lsn = lsn
        self.prev_lsn = prev_lsn
        self.tx_id = tx_id
        self.record_type = record_type
        self.page_id = page_id
        self.offset = offset
        self.undo_next_lsn = undo_next_lsn
        self.before_image = before_image
        self.after_image = after_image

    def serialize(self) -> bytes:
        header = struct.pack(self.HEADER_FORMAT, 
                             self.lsn, self.prev_lsn, self.tx_id, self.record_type.value,
                             self.page_id, self.offset, self.undo_next_lsn)
        
        # Pack payload lengths and data
        b_len = len(self.before_image)
        a_len = len(self.after_image)
        
        payload = struct.pack(f"<I{b_len}sI{a_len}s", b_len, self.before_image, a_len, self.after_image)
        return header + payload

    @classmethod
    def deserialize(cls, raw_data: bytes) -> 'LogRecord':
        if len(raw_data) < cls.HEADER_SIZE:
            raise ValueError("Data too short for log record header")
            
        header = raw_data[:cls.HEADER_SIZE]
        lsn, prev_lsn, tx_id, record_type_val, page_id, offset, undo_next_lsn = struct.unpack(cls.HEADER_FORMAT, header)
        
        offset_idx = cls.HEADER_SIZE
        
        b_len = struct.unpack("<I", raw_data[offset_idx:offset_idx+4])[0]
        offset_idx += 4
        
        before_image = raw_data[offset_idx:offset_idx+b_len]
        offset_idx += b_len
        
        a_len = struct.unpack("<I", raw_data[offset_idx:offset_idx+4])[0]
        offset_idx += 4
        
        after_image = raw_data[offset_idx:offset_idx+a_len]
        
        return cls(lsn, prev_lsn, tx_id, LogRecordType(record_type_val), 
                   page_id, offset, undo_next_lsn, before_image, after_image)
