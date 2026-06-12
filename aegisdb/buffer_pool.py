from typing import Dict, Optional, List
from aegisdb.page import Page
from aegisdb.storage_manager import StorageManager
from aegisdb.log_manager import LogManager

class BufferPoolManager:
    """
    Manages in-memory page frames using a Steal/No-Force policy.
    Implements a simple LRU replacement policy.
    """

    def __init__(self, pool_size: int, storage_manager: StorageManager, log_manager: LogManager):
        self.pool_size = pool_size
        self.storage_manager = storage_manager
        self.log_manager = log_manager
        
        # page_id -> Page mapping
        self.pages: Dict[int, Page] = {}
        
        # LRU list storing page_ids (least recently used at index 0)
        self.lru_list: List[int] = []

    def fetch_page(self, page_id: int) -> Page:
        """Fetches a page from the buffer pool or loads it from disk."""
        if page_id in self.pages:
            self._update_lru(page_id)
            return self.pages[page_id]
            
        # Need to load from disk, check if we need to evict
        if len(self.pages) >= self.pool_size:
            self._evict_page()
            
        # Load from disk
        page = self.storage_manager.read_page(page_id)
        self.pages[page_id] = page
        self.lru_list.append(page_id)
        
        return page

    def unpin_page(self, page_id: int, is_dirty: bool):
        """Unpins a page, updating its dirty status."""
        if page_id not in self.pages:
            raise ValueError(f"Page {page_id} not in buffer pool")
            
        page = self.pages[page_id]
        if page.pin_count > 0:
            page.pin_count -= 1
            
        if is_dirty:
            page.is_dirty = True

    def pin_page(self, page_id: int):
        """Pins a page to prevent eviction."""
        if page_id in self.pages:
            self.pages[page_id].pin_count += 1
            self._update_lru(page_id)
        else:
            page = self.fetch_page(page_id)
            page.pin_count += 1

    def flush_page(self, page_id: int):
        """Flushes a single page to disk if it's dirty."""
        if page_id in self.pages:
            page = self.pages[page_id]
            if page.is_dirty:
                # WAL Constraint: Flush log records before writing the page to disk
                self.log_manager.enforce_wal(page.page_lsn)
                
                self.storage_manager.write_page(page)
                page.is_dirty = False

    def flush_all_pages(self):
        """Flushes all dirty pages to disk."""
        for page_id in list(self.pages.keys()):
            self.flush_page(page_id)

    def _update_lru(self, page_id: int):
        """Updates the LRU list to mark a page as recently used."""
        if page_id in self.lru_list:
            self.lru_list.remove(page_id)
        self.lru_list.append(page_id)

    def _evict_page(self):
        """Evicts a page using LRU policy (Steal policy)."""
        evicted_page_id = None
        
        # Find first unpinned page starting from least recently used
        for page_id in self.lru_list:
            if self.pages[page_id].pin_count == 0:
                evicted_page_id = page_id
                break
                
        if evicted_page_id is None:
            raise RuntimeError("All pages are pinned, cannot evict")
            
        # Steal policy: Flush dirty page before eviction
        self.flush_page(evicted_page_id)
        
        # Remove from buffer pool
        del self.pages[evicted_page_id]
        self.lru_list.remove(evicted_page_id)
