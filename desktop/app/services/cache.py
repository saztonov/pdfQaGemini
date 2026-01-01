"""Caching utilities"""
import os
import shutil
from pathlib import Path
from typing import Optional
from collections import OrderedDict


class CacheManager:
    """File cache with LRU eviction and size limits"""
    
    def __init__(self, cache_dir: Path, max_size_mb: int = 500):
        self.cache_dir = Path(cache_dir)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # LRU tracking: key -> (path, size)
        self._lru: OrderedDict[str, tuple[Path, int]] = OrderedDict()
        self._current_size = 0
        
        # Initialize from existing files
        self._scan_cache()
    
    def _scan_cache(self):
        """Scan cache directory and build LRU index"""
        for file_path in self.cache_dir.glob("*"):
            if file_path.is_file():
                size = file_path.stat().st_size
                key = file_path.name
                self._lru[key] = (file_path, size)
                self._current_size += size
    
    def get_path(self, key: str) -> Optional[Path]:
        """Get cached file path if exists (updates LRU)"""
        if key in self._lru:
            # Move to end (most recently used)
            path, size = self._lru.pop(key)
            self._lru[key] = (path, size)
            
            if path.exists():
                return path
            else:
                # File was deleted, remove from tracking
                del self._lru[key]
                self._current_size -= size
        
        return None
    
    def put(self, key: str, data: bytes) -> Path:
        """Cache data, evict if needed"""
        file_size = len(data)
        
        # Evict if needed
        while self._current_size + file_size > self.max_size_bytes and self._lru:
            self._evict_oldest()
        
        # Write file
        file_path = self.cache_dir / key
        file_path.write_bytes(data)
        
        # Track
        self._lru[key] = (file_path, file_size)
        self._current_size += file_size
        
        return file_path
    
    def put_file(self, key: str, source_path: Path) -> Path:
        """Cache file by copying"""
        file_size = source_path.stat().st_size
        
        # Evict if needed
        while self._current_size + file_size > self.max_size_bytes and self._lru:
            self._evict_oldest()
        
        # Copy file
        dest_path = self.cache_dir / key
        shutil.copy2(source_path, dest_path)
        
        # Track
        self._lru[key] = (dest_path, file_size)
        self._current_size += file_size
        
        return dest_path
    
    def _evict_oldest(self):
        """Remove oldest (least recently used) file"""
        if not self._lru:
            return
        
        key, (path, size) = self._lru.popitem(last=False)
        
        try:
            if path.exists():
                path.unlink()
            self._current_size -= size
        except Exception:
            pass  # Ignore errors during eviction
    
    def clear(self):
        """Clear entire cache"""
        for path, _ in self._lru.values():
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass
        
        self._lru.clear()
        self._current_size = 0
    
    def get_size_mb(self) -> float:
        """Get current cache size in MB"""
        return self._current_size / (1024 * 1024)
