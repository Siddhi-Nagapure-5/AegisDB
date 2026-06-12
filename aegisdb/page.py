import struct

from aegisdb.config import PAGE_SIZE

class Page:
    """
    Represents a 4KB database page in memory.
    Header Layout (16 bytes):
        - PageLSN (uint64): 8 bytes
        - PageID (uint32): 4 bytes
        - FreeSpacePointer (uint16): 2 bytes
        - Padding/Reserved: 2 bytes
    Data Area:
        - 4080 bytes
    """
    
    HEADER_FORMAT = "<QIH2x" 
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    DATA_SIZE = PAGE_SIZE - HEADER_SIZE

    def __init__(self, page_id: int):
        self.page_id = page_id
        self.page_lsn = 0
        self.free_space_pointer = self.HEADER_SIZE
        # Initialize data area with zeros
        self.data = bytearray(self.DATA_SIZE)
        self.is_dirty = False
        self.pin_count = 0

    def serialize(self) -> bytes:
        """Packs the page into a 4KB byte array."""
        header = struct.pack(self.HEADER_FORMAT, self.page_lsn, self.page_id, self.free_space_pointer)
        return header + self.data

    @classmethod
    def deserialize(cls, raw_data: bytes) -> 'Page':
        """Unpacks a 4KB byte array into a Page object."""
        if len(raw_data) != PAGE_SIZE:
            raise ValueError(f"Invalid page size: {len(raw_data)}, expected {PAGE_SIZE}")
        
        header = raw_data[:cls.HEADER_SIZE]
        page_lsn, page_id, free_space_pointer = struct.unpack(cls.HEADER_FORMAT, header)
        
        page = cls(page_id)
        page.page_lsn = page_lsn
        page.free_space_pointer = free_space_pointer
        page.data = bytearray(raw_data[cls.HEADER_SIZE:])
        return page

    def write_data(self, offset: int, data: bytes):
        """Writes data at the given offset within the data area."""
        if offset < 0 or offset + len(data) > self.DATA_SIZE:
            raise ValueError("Write exceeds page boundaries")
        
        end = offset + len(data)
        self.data[offset:end] = data
        self.is_dirty = True
        
        if offset + self.HEADER_SIZE >= self.free_space_pointer:
            self.free_space_pointer = offset + len(data) + self.HEADER_SIZE

    def read_data(self, offset: int, size: int) -> bytes:
        """Reads data from the given offset."""
        if offset < 0 or offset + size > self.DATA_SIZE:
            raise ValueError("Read exceeds page boundaries")
        
        end = offset + size
        return bytes(self.data[offset:end])
