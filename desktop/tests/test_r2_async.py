"""Test R2AsyncClient"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from app.services.r2_async import R2AsyncClient


@pytest.fixture
def mock_cache(tmp_path):
    """Mock cache manager"""
    with patch("app.services.r2_async.CacheManager") as mock:
        cache_instance = Mock()
        cache_instance.get_path = Mock(return_value=None)
        cache_instance.put = Mock(return_value=tmp_path / "cached_file")
        mock.return_value = cache_instance
        yield cache_instance


@pytest.fixture
def r2_client(tmp_path, mock_cache):
    """Create R2 client with mocks"""
    client = R2AsyncClient(
        r2_public_base_url="https://pub-test.r2.dev",
        r2_endpoint="https://test.r2.cloudflarestorage.com",
        r2_bucket="test-bucket",
        r2_access_key="test-key",
        r2_secret_key="test-secret",
        local_cache_dir=tmp_path / "cache",
    )
    return client


class TestR2AsyncClient:
    def test_build_public_url(self, r2_client):
        """Test building public URL"""
        url = r2_client.build_public_url("files/test.pdf")
        assert url == "https://pub-test.r2.dev/files/test.pdf"
        
        # Test with leading slash
        url = r2_client.build_public_url("/files/test.pdf")
        assert url == "https://pub-test.r2.dev/files/test.pdf"
    
    @pytest.mark.asyncio
    async def test_download_to_cache_from_cache(self, r2_client, mock_cache, tmp_path):
        """Test download when file is already cached"""
        cached_file = tmp_path / "cached"
        mock_cache.get_path.return_value = cached_file
        
        result = await r2_client.download_to_cache(
            "https://example.com/file.pdf",
            cache_key="test_key"
        )
        
        assert result == cached_file
        mock_cache.get_path.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_download_to_cache_new_file(self, r2_client, mock_cache, tmp_path):
        """Test downloading new file"""
        mock_cache.get_path.return_value = None
        cached_path = tmp_path / "downloaded"
        mock_cache.put.return_value = cached_path
        
        # Mock HTTP client
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.aiter_bytes = AsyncMock(return_value=[b"chunk1", b"chunk2"])
        
        mock_http_client = AsyncMock()
        mock_http_client.stream = MagicMock()
        mock_http_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_http_client.stream.return_value.__aexit__ = AsyncMock()
        
        r2_client._http_client = mock_http_client
        
        result = await r2_client.download_to_cache(
            "https://example.com/file.pdf",
            cache_key="test_key"
        )
        
        assert result == cached_path
        mock_cache.put.assert_called_once()
        call_args = mock_cache.put.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][1] == b"chunk1chunk2"
    
    @pytest.mark.asyncio
    async def test_upload_bytes(self, r2_client):
        """Test uploading bytes"""
        mock_s3 = Mock()
        r2_client._s3_client = mock_s3
        
        data = b"test data"
        url = await r2_client.upload_bytes("files/test.txt", data, "text/plain")
        
        assert url == "https://pub-test.r2.dev/files/test.txt"
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"] == "files/test.txt"
        assert call_kwargs["Body"] == data
        assert call_kwargs["ContentType"] == "text/plain"
    
    @pytest.mark.asyncio
    async def test_upload_file(self, r2_client, tmp_path):
        """Test uploading file"""
        mock_s3 = Mock()
        r2_client._s3_client = mock_s3
        
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        url = await r2_client.upload_file(
            "files/uploaded.txt",
            test_file,
            "text/plain"
        )
        
        assert url == "https://pub-test.r2.dev/files/uploaded.txt"
        mock_s3.put_object.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_download_bytes(self, r2_client):
        """Test downloading bytes"""
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.content = b"file content"
        
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        
        r2_client._http_client = mock_http_client
        
        data = await r2_client.download_bytes("files/test.pdf")
        
        assert data == b"file content"
        mock_http_client.get.assert_called_once_with(
            "https://pub-test.r2.dev/files/test.pdf"
        )
    
    @pytest.mark.asyncio
    async def test_close(self, r2_client):
        """Test cleanup"""
        mock_http = AsyncMock()
        r2_client._http_client = mock_http
        
        await r2_client.close()
        
        mock_http.aclose.assert_called_once()
        assert r2_client._http_client is None
