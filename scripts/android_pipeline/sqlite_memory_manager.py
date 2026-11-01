#!/usr/bin/env python3
"""
SQLite Pipeline Memory Manager — Concurrent-safe, TTL-enabled, Migration-ready
Replaces file-based JSON with SQLite (WAL mode) for production-grade state management.
"""

import os
import json
import sqlite3
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from contextlib import contextmanager
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -32768;  -- 32MB cache
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;  -- 256MB mmap

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at REAL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE IF NOT EXISTS compilation_state (
    run_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    created_at REAL DEFAULT (strftime('%s', 'now')),
    updated_at REAL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE IF NOT EXISTS packaging_record (
    apk_name TEXT PRIMARY KEY,
    record_json TEXT NOT NULL,
    created_at REAL DEFAULT (strftime('%s', 'now')),
    updated_at REAL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE IF NOT EXISTS transient_cache (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    expires_at REAL,  -- NULL = no expiry
    created_at REAL DEFAULT (strftime('%s', 'now')),
    updated_at REAL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE IF NOT EXISTS persistent_records (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    created_at REAL DEFAULT (strftime('%s', 'now')),
    updated_at REAL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL,
    table_name TEXT NOT NULL,
    key TEXT,
    old_value_json TEXT,
    new_value_json TEXT,
    timestamp REAL DEFAULT (strftime('%s', 'now')),
    actor TEXT DEFAULT 'system'
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_transient_expires ON transient_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_persistent_category ON persistent_records(category);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_table_key ON audit_log(table_name, key);
"""


@dataclass
class CacheEntry:
    key: str
    value: Any
    expires_at: Optional[float] = None
    created_at: float = 0
    updated_at: float = 0


class SQLiteMemoryManager:
    """Thread-safe SQLite memory manager with TTL and audit logging"""
    
    def __init__(self, db_path: str = "/var/minis/workspace/pipeline_memory.db"):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()
        self._migrate_from_json()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
                isolation_level=None  # Autocommit mode
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            self._local.conn = conn
        return self._local.conn
    
    def _init_db(self):
        """Initialize database schema"""
        conn = self._get_connection()
        conn.executescript(SCHEMA_SQL)
        
        # Check/set schema version
        cursor = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        row = cursor.fetchone()
        current_version = row[0] if row else 0
        
        if current_version < SCHEMA_VERSION:
            self._run_migrations(conn, current_version)
            conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        
        conn.commit()
    
    def _run_migrations(self, conn: sqlite3.Connection, from_version: int):
        """Run database migrations"""
        if from_version < 1:
            pass
        if from_version < 2:
            pass
        logger.info(f"Migrated database from version {from_version} to {SCHEMA_VERSION}")
    
    def _migrate_from_json(self):
        """Migrate data from old file-based JSON storage"""
        old_base = Path("/var/minis/skills/github-actions-codespaces/data_memory")
        if not old_base.exists():
            return
        
        migration_count = 0
        
        # Migrate compilation state
        build_dir = old_base / "compilation"
        if build_dir.exists():
            for json_file in build_dir.glob("*.json"):
                run_id = json_file.stem.replace("run_", "")
                try:
                    data = json.loads(json_file.read_text())
                    self._save_compilation_state_impl(run_id, data)
                    migration_count += 1
                except Exception as e:
                    logger.warning(f"Failed to migrate {json_file}: {e}")
        
        # Migrate packaging records
        pkg_dir = old_base / "packaging"
        if pkg_dir.exists():
            for json_file in pkg_dir.glob("*.json"):
                apk_name = json_file.stem.replace("pkg_", "")
                try:
                    data = json.loads(json_file.read_text())
                    self._save_packaging_record_impl(apk_name, data)
                    migration_count += 1
                except Exception as e:
                    logger.warning(f"Failed to migrate {json_file}: {e}")
        
        # Migrate transient cache
        transient_dir = old_base / "transient"
        if transient_dir.exists():
            for json_file in transient_dir.glob("*.json"):
                key = json_file.stem
                try:
                    data = json.loads(json_file.read_text())
                    self._save_transient_cache_impl(key, data)
                    migration_count += 1
                except Exception as e:
                    logger.warning(f"Failed to migrate {json_file}: {e}")
        
        # Migrate persistent records
        persistent_dir = old_base / "persistent"
        if persistent_dir.exists():
            for json_file in persistent_dir.glob("*.json"):
                key = json_file.stem
                try:
                    data = json.loads(json_file.read_text())
                    category = data.pop("_category", "general") if isinstance(data, dict) else "general"
                    self._save_persistent_record_impl(key, data, category)
                    migration_count += 1
                except Exception as e:
                    logger.warning(f"Failed to migrate {json_file}: {e}")
        
        if migration_count > 0:
            logger.info(f"Migrated {migration_count} records from JSON to SQLite")
    
    @contextmanager
    def _transaction(self):
        """Transaction context manager"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    # =========================================================================
    # COMPILATION STATE (Derleme Hafızası)
    # =========================================================================
    
    def _save_compilation_state_impl(self, run_id: str, state_data: Dict[str, Any]) -> bool:
        """Internal implementation"""
        try:
            state_data = dict(state_data)
            state_data["timestamp"] = time.time()
            state_json = json.dumps(state_data)
            
            with self._transaction() as conn:
                conn.execute("""
                    INSERT INTO compilation_state (run_id, state_json, updated_at)
                    VALUES (?, ?, strftime('%s', 'now'))
                    ON CONFLICT(run_id) DO UPDATE SET
                        state_json = excluded.state_json,
                        updated_at = excluded.updated_at
                """, (run_id, state_json))
                
                conn.execute("""
                    INSERT INTO audit_log (operation, table_name, key, new_value_json)
                    VALUES ('upsert', 'compilation_state', ?, ?)
                """, (run_id, state_json))
            
            return True
        except Exception as e:
            logger.error(f"Failed to save compilation state: {e}")
            return False
    
    def save_compilation_state(self, run_id: str, state_data: Dict[str, Any]) -> bool:
        """Public API: Save compilation/build state"""
        return self._save_compilation_state_impl(run_id, state_data)
    
    def get_compilation_state(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get compilation state by run_id"""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT state_json FROM compilation_state WHERE run_id = ?",
                (run_id,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["state_json"])
            return None
        except Exception as e:
            logger.error(f"Failed to get compilation state: {e}")
            return None
    
    def list_compilation_states(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List recent compilation states"""
        try:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT run_id, state_json, created_at, updated_at
                FROM compilation_state
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            return [
                {
                    "run_id": row["run_id"],
                    "state": json.loads(row["state_json"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            logger.error(f"Failed to list compilation states: {e}")
            return []
    
    def delete_compilation_state(self, run_id: str) -> bool:
        """Delete compilation state"""
        try:
            with self._transaction() as conn:
                conn.execute("DELETE FROM compilation_state WHERE run_id = ?", (run_id,))
                conn.execute("""
                    INSERT INTO audit_log (operation, table_name, key)
                    VALUES ('delete', 'compilation_state', ?)
                """, (run_id,))
            return True
        except Exception as e:
            logger.error(f"Failed to delete compilation state: {e}")
            return False
    
    # =========================================================================
    # PACKAGING RECORDS (Paketleme Hafızası)
    # =========================================================================
    
    def _save_packaging_record_impl(self, apk_name: str, package_data: Dict[str, Any]) -> bool:
        """Internal implementation"""
        try:
            package_data = dict(package_data)
            package_data["timestamp"] = time.time()
            record_json = json.dumps(package_data)
            
            with self._transaction() as conn:
                conn.execute("""
                    INSERT INTO packaging_record (apk_name, record_json, updated_at)
                    VALUES (?, ?, strftime('%s', 'now'))
                    ON CONFLICT(apk_name) DO UPDATE SET
                        record_json = excluded.record_json,
                        updated_at = excluded.updated_at
                """, (apk_name, record_json))
                
                conn.execute("""
                    INSERT INTO audit_log (operation, table_name, key, new_value_json)
                    VALUES ('upsert', 'packaging_record', ?, ?)
                """, (apk_name, record_json))
            
            return True
        except Exception as e:
            logger.error(f"Failed to save packaging record: {e}")
            return False
    
    def save_packaging_record(self, apk_name: str, package_data: Dict[str, Any]) -> bool:
        """Public API: Save APK/AAB packaging metadata"""
        return self._save_packaging_record_impl(apk_name, package_data)
    
    def get_packaging_record(self, apk_name: str) -> Optional[Dict[str, Any]]:
        """Get packaging record by APK name"""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT record_json FROM packaging_record WHERE apk_name = ?",
                (apk_name,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["record_json"])
            return None
        except Exception as e:
            logger.error(f"Failed to get packaging record: {e}")
            return None
    
    def list_packaging_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List packaging records"""
        try:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT apk_name, record_json, created_at, updated_at
                FROM packaging_record
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            return [
                {
                    "apk_name": row["apk_name"],
                    "record": json.loads(row["record_json"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            logger.error(f"Failed to list packaging records: {e}")
            return []
    
    # =========================================================================
    # TRANSIENT CACHE (Geçici Hafıza) — with TTL
    # =========================================================================
    
    def _save_transient_cache_impl(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Internal implementation"""
        try:
            value_json = json.dumps(value)
            expires_at = time.time() + ttl_seconds if ttl_seconds else None
            
            with self._transaction() as conn:
                conn.execute("""
                    INSERT INTO transient_cache (key, value_json, expires_at, updated_at)
                    VALUES (?, ?, ?, strftime('%s', 'now'))
                    ON CONFLICT(key) DO UPDATE SET
                        value_json = excluded.value_json,
                        expires_at = excluded.expires_at,
                        updated_at = excluded.updated_at
                """, (key, value_json, expires_at))
            
            return True
        except Exception as e:
            logger.error(f"Failed to save transient cache: {e}")
            return False
    
    def save_transient_cache(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Public API: Save transient cache entry with optional TTL"""
        return self._save_transient_cache_impl(key, value, ttl_seconds)
    
    def get_transient_cache(self, key: str) -> Optional[Any]:
        """Get transient cache entry (auto-expires)"""
        try:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT value_json, expires_at FROM transient_cache WHERE key = ?
            """, (key,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # Check expiry
            if row["expires_at"] is not None and row["expires_at"] < time.time():
                self.delete_transient_cache(key)
                return None
            
            return json.loads(row["value_json"])
        except Exception as e:
            logger.error(f"Failed to get transient cache: {e}")
            return None
    
    def delete_transient_cache(self, key: str) -> bool:
        """Delete transient cache entry"""
        try:
            with self._transaction() as conn:
                conn.execute("DELETE FROM transient_cache WHERE key = ?", (key,))
            return True
        except Exception as e:
            logger.error(f"Failed to delete transient cache: {e}")
            return False
    
    def cleanup_expired_cache(self) -> int:
        """Remove all expired transient cache entries"""
        try:
            with self._transaction() as conn:
                cursor = conn.execute("""
                    DELETE FROM transient_cache 
                    WHERE expires_at IS NOT NULL AND expires_at < strftime('%s', 'now')
                """)
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}")
            return 0
    
    def list_transient_cache(self, limit: int = 100) -> List[CacheEntry]:
        """List transient cache entries"""
        try:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT key, value_json, expires_at, created_at, updated_at
                FROM transient_cache
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            entries = []
            for row in cursor.fetchall():
                if row["expires_at"] and row["expires_at"] < time.time():
                    continue
                entries.append(CacheEntry(
                    key=row["key"],
                    value=json.loads(row["value_json"]),
                    expires_at=row["expires_at"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                ))
            return entries
        except Exception as e:
            logger.error(f"Failed to list transient cache: {e}")
            return []
    
    # =========================================================================
    # PERSISTENT RECORDS (Kalıcı Hafıza)
    # =========================================================================
    
    def _save_persistent_record_impl(self, key: str, value: Any, category: str = "general") -> bool:
        """Internal implementation"""
        try:
            value_json = json.dumps(value)
            
            with self._transaction() as conn:
                conn.execute("""
                    INSERT INTO persistent_records (key, value_json, category, updated_at)
                    VALUES (?, ?, ?, strftime('%s', 'now'))
                    ON CONFLICT(key) DO UPDATE SET
                        value_json = excluded.value_json,
                        category = excluded.category,
                        updated_at = excluded.updated_at
                """, (key, value_json, category))
                
                conn.execute("""
                    INSERT INTO audit_log (operation, table_name, key, new_value_json)
                    VALUES ('upsert', 'persistent_records', ?, ?)
                """, (key, value_json))
            
            return True
        except Exception as e:
            logger.error(f"Failed to save persistent record: {e}")
            return False
    
    def save_persistent_record(self, key: str, value: Any, category: str = "general") -> bool:
        """Public API: Save persistent record with category"""
        return self._save_persistent_record_impl(key, value, category)
    
    def get_persistent_record(self, key: str) -> Optional[Any]:
        """Get persistent record"""
        try:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT value_json FROM persistent_records WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["value_json"])
            return None
        except Exception as e:
            logger.error(f"Failed to get persistent record: {e}")
            return None
    
    def list_persistent_records(self, category: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List persistent records"""
        try:
            conn = self._get_connection()
            if category:
                cursor = conn.execute("""
                    SELECT key, value_json, category, created_at, updated_at
                    FROM persistent_records
                    WHERE category = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (category, limit))
            else:
                cursor = conn.execute("""
                    SELECT key, value_json, category, created_at, updated_at
                    FROM persistent_records
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (limit,))
            
            return [
                {
                    "key": row["key"],
                    "value": json.loads(row["value_json"]),
                    "category": row["category"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            logger.error(f"Failed to list persistent records: {e}")
            return []
    
    # =========================================================================
    # STATS & MAINTENANCE
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            conn = self._get_connection()
            stats = {}
            
            for table in ["compilation_state", "packaging_record", "transient_cache", "persistent_records", "audit_log"]:
                cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()["count"]
            
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM transient_cache
                WHERE expires_at IS NOT NULL AND expires_at < strftime('%s', 'now')
            """)
            stats["expired_cache_count"] = cursor.fetchone()["count"]
            
            stats["db_size_bytes"] = self.db_path.stat().st_size
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}
    
    def vacuum(self) -> bool:
        """Vacuum database to reclaim space"""
        try:
            conn = self._get_connection()
            conn.execute("VACUUM")
            return True
        except Exception as e:
            logger.error(f"Vacuum failed: {e}")
            return False
    
    def close(self):
        """Close thread-local connection"""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
    
    def __del__(self):
        self.close()


# Backward compatibility alias
PipelineMemoryManager = SQLiteMemoryManager


if __name__ == "__main__":
    # Test
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_memory.db"
        mgr = SQLiteMemoryManager(str(db_path))
        
        # Test compilation state
        mgr.save_compilation_state("run_123", {"status": "success", "duration": 45.2})
        state = mgr.get_compilation_state("run_123")
        assert state["status"] == "success"
        print("✓ Compilation state")
        
        # Test packaging record
        mgr.save_packaging_record("app-release.apk", {"size": 1234567, "version": "1.0.0"})
        pkg = mgr.get_packaging_record("app-release.apk")
        assert pkg["size"] == 1234567
        print("✓ Packaging record")
        
        # Test transient cache with TTL
        mgr.save_transient_cache("temp_key", {"data": "value"}, ttl_seconds=60)
        cached = mgr.get_transient_cache("temp_key")
        assert cached["data"] == "value"
        print("✓ Transient cache with TTL")
        
        # Test persistent record
        mgr.save_persistent_record("config", {"debug": True}, category="settings")
        persistent = mgr.get_persistent_record("config")
        assert persistent["debug"] is True
        print("✓ Persistent record")
        
        # Stats
        stats = mgr.get_stats()
        print(f"✓ Stats: {stats}")
        
        mgr.close()
        print("\nAll SQLite memory manager tests passed!")