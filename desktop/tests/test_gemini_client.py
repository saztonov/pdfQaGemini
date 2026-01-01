"""Test GeminiClient"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from app.services.gemini_client import GeminiClient
from app.utils.errors import ServiceError


@pytest.fixture
def mock_genai_client():
    """Mock genai.Client"""
    with patch("app.services.gemini_client.genai.Client") as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def gemini_client(mock_genai_client):
    """Create GeminiClient with mocked client"""
    client = GeminiClient(api_key="test-api-key")
    client._client = mock_genai_client
    return client


@pytest.mark.asyncio
class TestGeminiClient:
    async def test_list_files(self, gemini_client, mock_genai_client):
        """Test listing files"""
        mock_file1 = Mock()
        mock_file1.name = "files/abc123"
        mock_file1.uri = "https://generativelanguage.googleapis.com/v1beta/files/abc123"
        mock_file1.mime_type = "application/pdf"
        mock_file1.display_name = "test.pdf"
        mock_file1.create_time = "2025-01-01T00:00:00Z"
        mock_file1.expiration_time = "2025-01-02T00:00:00Z"
        mock_file1.size_bytes = 1024
        mock_file1.sha256_hash = "abcd1234"
        
        mock_genai_client.files.list.return_value = [mock_file1]
        
        result = await gemini_client.list_files()
        
        assert len(result) == 1
        assert result[0]["name"] == "files/abc123"
        assert result[0]["mime_type"] == "application/pdf"
        assert result[0]["display_name"] == "test.pdf"
    
    async def test_list_files_error(self, gemini_client, mock_genai_client):
        """Test list files error handling"""
        mock_genai_client.files.list.side_effect = Exception("API Error")
        
        with pytest.raises(ServiceError) as exc:
            await gemini_client.list_files()
        
        assert "Failed to list Gemini files" in str(exc.value)
    
    async def test_upload_file(self, gemini_client, mock_genai_client, tmp_path):
        """Test uploading file"""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content")
        
        mock_uploaded = Mock()
        mock_uploaded.name = "files/xyz789"
        mock_uploaded.uri = "https://generativelanguage.googleapis.com/v1beta/files/xyz789"
        mock_uploaded.mime_type = "application/pdf"
        mock_uploaded.display_name = "test.pdf"
        mock_uploaded.size_bytes = 11
        
        mock_genai_client.files.upload.return_value = mock_uploaded
        
        result = await gemini_client.upload_file(
            test_file,
            mime_type="application/pdf",
            display_name="My PDF"
        )
        
        assert result["name"] == "files/xyz789"
        assert result["uri"] == "https://generativelanguage.googleapis.com/v1beta/files/xyz789"
        assert result["mime_type"] == "application/pdf"
        
        mock_genai_client.files.upload.assert_called_once()
    
    async def test_upload_file_auto_mime(self, gemini_client, mock_genai_client, tmp_path):
        """Test upload with auto-detected mime type"""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")
        
        mock_uploaded = Mock()
        mock_uploaded.name = "files/test"
        mock_uploaded.uri = "https://example.com/files/test"
        mock_uploaded.mime_type = "application/pdf"
        
        mock_genai_client.files.upload.return_value = mock_uploaded
        
        result = await gemini_client.upload_file(test_file)
        
        assert result["name"] == "files/test"
    
    async def test_upload_file_error(self, gemini_client, mock_genai_client, tmp_path):
        """Test upload error handling"""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")
        
        mock_genai_client.files.upload.side_effect = Exception("Upload failed")
        
        with pytest.raises(ServiceError) as exc:
            await gemini_client.upload_file(test_file)
        
        assert "Failed to upload file" in str(exc.value)
    
    async def test_delete_file(self, gemini_client, mock_genai_client):
        """Test deleting file"""
        await gemini_client.delete_file("files/abc123")
        
        mock_genai_client.files.delete.assert_called_once_with(name="files/abc123")
    
    async def test_delete_file_error(self, gemini_client, mock_genai_client):
        """Test delete error handling"""
        mock_genai_client.files.delete.side_effect = Exception("Delete failed")
        
        with pytest.raises(ServiceError) as exc:
            await gemini_client.delete_file("files/abc123")
        
        assert "Failed to delete Gemini file" in str(exc.value)
    
    async def test_generate_structured(self, gemini_client, mock_genai_client):
        """Test structured generation"""
        mock_response = Mock()
        mock_response.text = '{"result": "success", "value": 42}'
        
        mock_genai_client.models.generate_content.return_value = mock_response
        
        schema = {
            "type": "object",
            "properties": {
                "result": {"type": "string"},
                "value": {"type": "integer"}
            }
        }
        
        result = await gemini_client.generate_structured(
            model="gemini-3-flash-preview",
            system_prompt="You are a helpful assistant",
            user_text="Give me a result",
            file_uris=["https://example.com/file1"],
            schema=schema,
            thinking_level="low",
        )
        
        assert result == {"result": "success", "value": 42}
        mock_genai_client.models.generate_content.assert_called_once()
    
    async def test_generate_structured_error(self, gemini_client, mock_genai_client):
        """Test structured generation error"""
        mock_genai_client.models.generate_content.side_effect = Exception("API Error")
        
        with pytest.raises(ServiceError) as exc:
            await gemini_client.generate_structured(
                model="gemini-3-flash-preview",
                system_prompt="Test",
                user_text="Test",
                file_uris=[],
                schema={},
            )
        
        assert "Failed to generate structured content" in str(exc.value)
    
    async def test_generate_simple(self, gemini_client, mock_genai_client):
        """Test simple text generation"""
        mock_response = Mock()
        mock_response.text = "This is the generated response"
        
        mock_genai_client.models.generate_content.return_value = mock_response
        
        result = await gemini_client.generate_simple(
            model="gemini-3-flash-preview",
            prompt="Hello, how are you?",
            file_uris=None,
        )
        
        assert result == "This is the generated response"
    
    async def test_generate_simple_with_files(self, gemini_client, mock_genai_client):
        """Test simple generation with files"""
        mock_response = Mock()
        mock_response.text = "Response based on files"
        
        mock_genai_client.models.generate_content.return_value = mock_response
        
        result = await gemini_client.generate_simple(
            model="gemini-3-flash-preview",
            prompt="Analyze this document",
            file_uris=["https://example.com/file1", "https://example.com/file2"],
        )
        
        assert result == "Response based on files"
        mock_genai_client.models.generate_content.assert_called_once()
    
    async def test_generate_simple_error(self, gemini_client, mock_genai_client):
        """Test simple generation error"""
        mock_genai_client.models.generate_content.side_effect = Exception("Generation failed")
        
        with pytest.raises(ServiceError) as exc:
            await gemini_client.generate_simple(
                model="gemini-3-flash-preview",
                prompt="Test",
            )
        
        assert "Failed to generate content" in str(exc.value)
