# 🛠️ AegisDB Technology Stack & Architecture Documentation

This document outlines the system requirements, technical challenges, and language-specific ecosystems evaluated for implementing **AegisDB**—an educational Self-Recovery Database Engine implementing the ARIES recovery protocol.

---

## 🎯 Technical Requirements & Challenges

A self-recovery database engine requires low-level control over memory, concurrency, and storage. Below are the key engineering capabilities the chosen technology stack must support:

| Requirement | Technical Challenge | Key Capabilities Needed |
| :--- | :--- | :--- |
| **Storage & I/O Control** | Bypass operating system caching (or force flushes) to ensure Write-Ahead Logging (WAL) constraints. | Synchronous file writes (`fsync`/`sync_all`), binary page offset writes. |
| **Binary Serialization** | Efficiently pack and unpack structured database pages (4KB) and sequential WAL log records. | Struct packing/unpacking, byte-level buffer manipulation. |
| **Concurrency Control** | Support multiple transactions reading and writing concurrently. | Strict Two-Phase Locking (SS2PL), Mutexes, RWLocks, Thread Pools. |
| **Crash Simulation** | Simulate ungraceful process terminations (power loss, OS crashes) to test ARIES recovery. | Process signal handling, sub-process spawning, memory state termination. |

---

## 📊 Language Ecosystem Comparison

We evaluate three potential stacks for implementation: **Python** (for educational simplicity), **Go** (for balanced concurrency and performance), and **Rust** (for systems-level memory/byte control).

```mermaid
radialChart
    title "Language Match Profile for AegisDB"
    labels ["Educational Clarity", "Concurrency Model", "Byte Manipulation", "Memory Safety", "Low-level I/O Control"]
    "Python": [0.95, 0.60, 0.50, 0.90, 0.60]
    "Go": [0.85, 0.95, 0.80, 0.85, 0.80]
    "Rust": [0.70, 0.90, 0.98, 0.99, 0.95]
```

### 1. Python Stack (Educational & Readable)
*Best for clear algorithm readability and easy debugging.*
* **Pros:** Highly expressive code; simple to read ARIES logic (Analysis, Redo, Undo); quick iteration.
* **Cons:** GIL limits real multi-threaded execution; byte manipulation requires verbose packing (`struct` module); memory allocation is synthetic (no raw byte buffers without emulation).

### 2. Go Stack (Modern Concurrency)
*Best for robust concurrency modeling and clean system-level primitives.*
* **Pros:** Excellent concurrency primitives (goroutines, channels); built-in binary packing; compile-to-binary makes crash simulation very easy.
* **Cons:** Garbage collection runs in the background (makes manual buffer pool management feel slightly abstracted).

### 3. Rust Stack (Systems-Level Precision)
*Best for realistic database engine emulation.*
* **Pros:** Zero-cost abstractions; direct casting of byte slices to page structs (`zerocopy` or `unsafe`); absolute control over memory layout and disk writing; thread-safety checked at compile time.
* **Cons:** Steep learning curve; development velocity is slower.

---

## 🛠️ Detailed Tech Stack Blueprints

Here are the detailed package/module recommendations for implementing AegisDB under each stack.

### Option A: Python Ecosystem (Recommended for Education)
If we choose Python (as referenced in the [README.md](file:///c:/Users/Asus/Desktop/New%20folder/Projects/AegisDB/README.md)), here is the recommended tech stack:

*   **Runtime:** Python 3.10+
*   **Byte Manipulation:** `struct` (standard library) for packing/unpacking pages and log entries.
*   **Concurrency:** `threading` and `threading.Lock`/`threading.RLock` (Transaction Lock Manager).
*   **File I/O:** `os` and `io` modules, specifically calling `os.fsync()` to force write-ahead logs to disk.
*   **CLI & Visualization:** `rich` for displaying transaction progress, buffer pool states, and recovery processes.
*   **Crash Simulator:** `multiprocessing` or `subprocess` to spawn a separate database runner and abruptly terminate it using `os.kill(pid, signal.SIGKILL)`.
*   **Testing:** `pytest` for unit testing and automated crash-and-verify loops.

### Option B: Go Ecosystem
If we choose Go for a more robust multi-threaded server architecture:

*   **Runtime:** Go 1.20+
*   **Byte Manipulation:** `encoding/binary` and `unsafe` / `bytes` buffers.
*   **Concurrency:** Goroutines, `sync.Mutex`, `sync.RWMutex`, and `sync/atomic` for Log Sequence Numbers (LSNs).
*   **File I/O:** `os.File` with `f.Sync()` or using `syscall.O_DIRECT` for bypassing disk cache.
*   **CLI & Visualization:** `github.com/charmbracelet/bubbletea` for a interactive terminal user interface (TUI) crash simulator.
*   **Crash Simulator:** Master process executing the database as an external command, killing it with `syscall.Kill(pid, syscall.SIGKILL)`.

### Option C: Rust Ecosystem
If we choose Rust for production-like performance and pointer control:

*   **Runtime:** Rust Edition 2021
*   **Byte Manipulation:** `zerocopy` or `bytemuck` for safe zero-copy deserialization of pages; `byteorder` for writing integers.
*   **Concurrency:** `std::thread`, `parking_lot` (for fast Mutexes/RwLocks), and `crossbeam` channels.
*   **File I/O:** `std::fs::File`, utilizing `std::os::unix::fs::OpenOptionsExt` (on Unix) or specific Windows APIs to bypass OS buffering.
*   **CLI & Visualization:** `ratatui` (formerly `tui-rs`) for an immersive dashboard showing the live state of buffer frames and transactions.
*   **Crash Simulator:** Rust `std::process::Command` to manage database execution and calling `.kill()`.

---

## 📐 Component Architecture Mapping

Regardless of the language chosen, the components will interact as follows:

```
+--------------------------------------------------------+
|                      CLIENT / CLI                      |
| (Interactive commands: BEGIN, COMMIT, UPDATE, CRASH!)  |
+---------------------------+----------------------------+
                            |
                            v
+---------------------------+----------------------------+
|                  TRANSACTION MANAGER                   |
|  - Tracks Active Transactions                          |
|  - Acquires locks via Lock Manager                     |
+---------------------------+----------------------------+
                            |
                            v
+---------------------------+----------------------------+
|                    RECOVERY MANAGER                    |
|  - Appends logs to Log Manager                         |
|  - Pin/Unpin/Dirty pages in Buffer Pool Manager       |
|  - ARIES Engine (Analysis -> Redo -> Undo)             |
+-----------------+------------------+-------------------+
                  |                  |
                  v                  v
+-----------------+----+    +--------+-------------------+
|     LOG MANAGER      |    |    BUFFER POOL MANAGER     |
|  - Log Buffer        |    |  - Clock/LRU Page Frames   |
|  - WAL Flushing      |    |  - Page Eviction Policy    |
+-----------------+----+    +--------+-------------------+
                  |                  |
                  v                  v
+-----------------+----+    +--------+-------------------+
|    LOG FILE          |    |      DATABASE FILE         |
|  (aegis.log)         |    |       (aegis.db)           |
+----------------------+    +----------------------------+
```

## 🚀 Execution Strategy & Next Steps

1. **Language Agreement:** Confirm whether to proceed with **Python** (excellent for readable implementation of components), **Go**, or **Rust**.
2. **Setup Workspace:** Create the file structures based on the chosen language.
3. **Phase 1 Implementation:** Begin with the **Storage Manager** and **Buffer Pool Manager** logic, mapping out page frames and page storage layouts.

---

## 📜 References & Further Reading

For a deeper dive into the theory and mechanics of database recovery and concurrency, consult the following key publications:

1. **Härder, T., & Reuter, A. (1983).** *Principles of transaction-oriented database recovery.* ACM Computing Surveys (CSUR), 15(4), 287-317.
   * *Significance:* This seminal paper defined the database recovery taxonomies (including **Steal/No-Force**) that AegisDB implements.
2. **Mohan, C., Haderle, D., Lindsay, B., Pirahesh, H., & Schwarz, P. (1992).** *ARIES: A transaction recovery method supporting fine-granularity locking and partial rollbacks using write-ahead logging.* ACM Transactions on Database Systems (TODS), 17(1), 94-162.
   * *Significance:* The original paper describing the ARIES algorithm, detailing the Analysis, Redo, and Undo passes along with CLR logs.
3. **Bernstein, P. A., Hadzilacos, V., & Goodman, N. (1987).** *Concurrency Control and Recovery in Database Systems.* Addison-Wesley.
   * *Significance:* A foundational textbook that models strict serialization theory and transaction management.
4. **Mohan, C., & Levine, F. (1992).** *ARIES/IM: A method for high concurrency index management and recovery with fine-granularity locking.* Proceedings of the 1992 ACM SIGMOD international conference on Management of data, 244-253.
   * *Significance:* An extension of ARIES to handle high-concurrency operations on B+-tree index structures.
