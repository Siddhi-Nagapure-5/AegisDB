import os

from aegisdb.config import PAGE_SIZE
from aegisdb.page import Page

class StorageManager:
    """
    Manages reading and writing pages to the database file on disk.
    Bypasses OS cache where possible or forces flushes.
    """

    def __init__(self, db_file_path: str):
        self.db_file_path = db_file_path
        
        # Create file if it doesn't exist
        if not os.path.exists(self.db_file_path):
            with open(self.db_file_path, 'wb') as f:
                pass
                
        # Open in read-write binary mode
        self.file = open(self.db_file_path, 'r+b')

    def read_page(self, page_id: int) -> Page:
        """Reads a page from disk."""
        offset = page_id * PAGE_SIZE
        self.file.seek(offset)
        raw_data = self.file.read(PAGE_SIZE)
        
        if not raw_data:
            return Page(page_id)
            
        if len(raw_data) < PAGE_SIZE:
            raw_data = raw_data.ljust(PAGE_SIZE, b'\0')
            
        return Page.deserialize(raw_data)

    def write_page(self, page: Page):
        """Writes a page to disk and forces an OS sync."""
        offset = page.page_id * PAGE_SIZE
        self.file.seek(offset)
        self.file.write(page.serialize())
        self.file.flush()
        # Force write to physical disk (bypass OS buffer)
        os.fsync(self.file.fileno())

    def allocate_page(self) -> int:
        """Allocates a new page at the end of the file and returns its ID."""
        self.file.seek(0, os.SEEK_END)
        file_size = self.file.tell()
        page_id = file_size // PAGE_SIZE
        
        new_page = Page(page_id)
        self.write_page(new_page)
        return page_id

    def close(self):
        """Closes the database file."""
        self.file.close()
