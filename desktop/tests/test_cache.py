"""Test CacheManager"""
import pytest
import tempfile
from pathlib import Path
from app.services.cache import CacheManager


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestCacheManager:
    def test_init_creates_directory(self, temp_cache_dir):
        """Test cache directory is created"""
        cache_dir = temp_cache_dir / "cache"
        cache = CacheManager(cache_dir, max_size_mb=10)
        
        assert cache_dir.exists()
        assert cache_dir.is_dir()
    
    def test_put_and_get(self, temp_cache_dir):
        """Test putting and getting from cache"""
        cache = CacheManager(temp_cache_dir, max_size_mb=10)
        
        data = b"test data"
        key = "test_file"
        
        path = cache.put(key, data)
        
        assert path.exists()
        assert path.read_bytes() == data
        
        # Get from cache
        cached = cache.get_path(key)
        assert cached == path
        assert cached.read_bytes() == data
    
    def test_get_nonexistent(self, temp_cache_dir):
        """Test getting nonexistent key"""
        cache = CacheManager(temp_cache_dir, max_size_mb=10)
        
        result = cache.get_path("nonexistent")
        assert result is None
    
    def test_lru_eviction(self, temp_cache_dir):
        """Test LRU eviction when size limit exceeded"""
        cache = CacheManager(temp_cache_dir, max_size_mb=0.001)  # 1KB limit
        
        # Add files that exceed limit
        data1 = b"x" * 512  # 512 bytes
        data2 = b"y" * 512  # 512 bytes
        data3 = b"z" * 512  # 512 bytes (should trigger eviction of data1)
        
        cache.put("file1", data1)
        cache.put("file2", data2)
        cache.put("file3", data3)
        
        # file1 should be evicted
        assert cache.get_path("file1") is None
        assert cache.get_path("file2") is not None
        assert cache.get_path("file3") is not None
    
    def test_get_updates_lru(self, temp_cache_dir):
        """Test that get updates LRU order"""
        cache = CacheManager(temp_cache_dir, max_size_mb=0.001)  # 1KB
        
        data = b"x" * 400
        
        cache.put("file1", data)
        cache.put("file2", data)
        
        # Access file1 (moves it to end of LRU)
        cache.get_path("file1")
        
        # Add file3 (should evict file2, not file1)
        cache.put("file3", data)
        
        assert cache.get_path("file1") is not None
        assert cache.get_path("file2") is None
        assert cache.get_path("file3") is not None
    
    def test_put_file(self, temp_cache_dir):
        """Test putting file by copying"""
        cache = CacheManager(temp_cache_dir, max_size_mb=10)
        
        # Create source file
        source = temp_cache_dir / "source.txt"
        source.write_text("test content")
        
        cached_path = cache.put_file("cached_file", source)
        
        assert cached_path.exists()
        assert cached_path.read_text() == "test content"
        assert cached_path != source
    
    def test_clear(self, temp_cache_dir):
        """Test clearing cache"""
        cache = CacheManager(temp_cache_dir, max_size_mb=10)
        
        cache.put("file1", b"data1")
        cache.put("file2", b"data2")
        
        assert cache.get_path("file1") is not None
        
        cache.clear()
        
        assert cache.get_path("file1") is None
        assert cache.get_path("file2") is None
        assert cache.get_size_mb() == 0
    
    def test_get_size_mb(self, temp_cache_dir):
        """Test getting cache size"""
        cache = CacheManager(temp_cache_dir, max_size_mb=10)
        
        data = b"x" * 1024  # 1KB
        cache.put("file1", data)
        
        size = cache.get_size_mb()
        assert 0.0009 < size < 0.0011  # ~1KB in MB
    
    def test_scan_cache_on_init(self, temp_cache_dir):
        """Test that existing files are scanned on init"""
        # Create files directly in cache dir
        (temp_cache_dir / "existing1").write_bytes(b"data1")
        (temp_cache_dir / "existing2").write_bytes(b"data2")
        
        cache = CacheManager(temp_cache_dir, max_size_mb=10)
        
        assert cache.get_path("existing1") is not None
        assert cache.get_path("existing2") is not None
