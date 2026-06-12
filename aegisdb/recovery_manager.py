from typing import Dict, Set

from aegisdb.log_manager import LogManager
from aegisdb.buffer_pool import BufferPoolManager
from aegisdb.log_record import LogRecordType, LogRecord

class RecoveryManager:
    """
    Implements the ARIES 3-Pass Recovery Algorithm:
    1. Analysis
    2. Redo
    3. Undo
    """

    def __init__(self, log_manager: LogManager, buffer_pool: BufferPoolManager):
        self.log_manager = log_manager
        self.buffer_pool = buffer_pool
        
        # Transaction Table: TxID -> LastLSN
        self.active_txns: Dict[int, int] = {}
        
        # Dirty Page Table: PageID -> RecLSN
        self.dirty_pages: Dict[int, int] = {}

    def recover(self):
        """Executes the full ARIES recovery process."""
        print("Starting ARIES Recovery...")
        
        # Step 1: Analysis
        self._analysis_phase()
        print(f"Analysis complete. Active TXNs: {len(self.active_txns)}, Dirty Pages: {len(self.dirty_pages)}")
        
        # Step 2: Redo
        self._redo_phase()
        print("Redo complete.")
        
        # Step 3: Undo
        self._undo_phase()
        print("Undo complete. System is consistent.")

    def _analysis_phase(self):
        """
        Scans log forward to reconstruct Transaction Table and Dirty Page Table.
        Finds the starting point for Redo (smallest RecLSN).
        """
        for record in self.log_manager.read_log_forward(start_lsn=1):
            
            # Update Transaction Table
            if record.record_type == LogRecordType.BEGIN:
                self.active_txns[record.tx_id] = record.lsn
            elif record.record_type in (LogRecordType.UPDATE, LogRecordType.CLR):
                self.active_txns[record.tx_id] = record.lsn
                
                # Update Dirty Page Table
                if record.page_id not in self.dirty_pages:
                    self.dirty_pages[record.page_id] = record.lsn
                    
            elif record.record_type in (LogRecordType.COMMIT, LogRecordType.ABORT):
                if record.tx_id in self.active_txns:
                    del self.active_txns[record.tx_id]

    def _redo_phase(self):
        """
        Repeats history by reapplying all updates to dirty pages
        starting from the oldest RecLSN.
        """
        if not self.dirty_pages:
            return
            
        redo_lsn = min(self.dirty_pages.values())
        
        for record in self.log_manager.read_log_forward(start_lsn=redo_lsn):
            if record.record_type not in (LogRecordType.UPDATE, LogRecordType.CLR):
                continue
                
            page_id = record.page_id
            
            # Filter checks
            if page_id not in self.dirty_pages or record.lsn < self.dirty_pages[page_id]:
                continue
                
            # Fetch page and check PageLSN
            page = self.buffer_pool.fetch_page(page_id)
            if page.page_lsn >= record.lsn:
                self.buffer_pool.unpin_page(page_id, is_dirty=False)
                continue
                
            # Redo the operation
            page.write_data(record.offset, record.after_image)
            page.page_lsn = record.lsn
            
            self.buffer_pool.unpin_page(page_id, is_dirty=True)

    def _undo_phase(self):
        """
        Rolls back all uncommitted transactions (losers) by traversing
        their PrevLSN chains backward and applying CLRs.
        """
        if not self.active_txns:
            return
            
        # Put all loser LastLSNs into a set
        to_undo = set(self.active_txns.values())
        
        while to_undo:
            max_lsn = max(to_undo)
            to_undo.remove(max_lsn)
            
            record = self.log_manager.read_record(max_lsn)
            if not record:
                continue
                
            if record.record_type == LogRecordType.UPDATE:
                # 1. Undo the operation
                page_id = record.page_id
                page = self.buffer_pool.fetch_page(page_id)
                page.write_data(record.offset, record.before_image)
                
                # 2. Write CLR
                clr = LogRecord(
                    lsn=0,  # Will be assigned by LogManager
                    prev_lsn=self.active_txns[record.tx_id],
                    tx_id=record.tx_id,
                    record_type=LogRecordType.CLR,
                    page_id=page_id,
                    offset=record.offset,
                    undo_next_lsn=record.prev_lsn,
                    before_image=record.before_image,
                    after_image=record.before_image # After image of CLR is the before image of the update
                )
                clr_lsn = self.log_manager.append_record(clr)
                
                # Update Page LSN and Transaction Table
                page.page_lsn = clr_lsn
                self.buffer_pool.unpin_page(page_id, is_dirty=True)
                self.active_txns[record.tx_id] = clr_lsn
                
            # Add PrevLSN to the undo set if it exists
            if record.record_type == LogRecordType.CLR:
                if record.undo_next_lsn > 0:
                    to_undo.add(record.undo_next_lsn)
            else:
                if record.prev_lsn > 0:
                    to_undo.add(record.prev_lsn)
                    
        # Flush all CLRs
        self.log_manager.flush()
