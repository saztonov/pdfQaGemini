"""Test Pydantic schemas"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import ValidationError
from app.models.schemas import (
    TreeNode, NodeFile, Conversation, Message,
    ContextItem, ModelAction, ModelReply
)


class TestTreeNode:
    def test_valid_tree_node(self):
        node_id = uuid4()
        node = TreeNode(
            id=node_id,
            parent_id=None,
            client_id="test_client",
            node_type="project",
            name="Test Project",
            code="PRJ-001",
            version=1,
            status="active",
            attributes={"key": "value"},
            sort_order=0
        )
        assert node.id == node_id
        assert node.client_id == "test_client"
        assert node.attributes == {"key": "value"}
    
    def test_default_attributes(self):
        node = TreeNode(
            id=uuid4(),
            client_id="test",
            node_type="folder",
            name="Folder",
            code="F1",
            version=1,
            status="active"
        )
        assert node.attributes == {}
        assert node.sort_order == 0


class TestNodeFile:
    def test_valid_node_file(self):
        file = NodeFile(
            id=uuid4(),
            node_id=uuid4(),
            file_type="pdf",
            r2_key="files/test.pdf",
            file_name="test.pdf",
            file_size=1024,
            mime_type="application/pdf",
            metadata={"pages": 10}
        )
        assert file.file_size == 1024
        assert file.metadata["pages"] == 10


class TestConversation:
    def test_valid_conversation(self):
        now = datetime.now(timezone.utc)
        conv = Conversation(
            id=uuid4(),
            client_id="client1",
            title="Test Chat",
            model_default="gemini-3-flash-preview",
            created_at=now,
            updated_at=now
        )
        assert conv.title == "Test Chat"
        assert conv.model_default == "gemini-3-flash-preview"
    
    def test_default_title(self):
        now = datetime.now(timezone.utc)
        conv = Conversation(
            id=uuid4(),
            client_id="client1",
            created_at=now,
            updated_at=now
        )
        assert conv.title == ""


class TestMessage:
    def test_valid_message(self):
        msg = Message(
            id=uuid4(),
            conversation_id=uuid4(),
            role="user",
            content="Hello",
            meta={},
            created_at=datetime.now(timezone.utc)
        )
        assert msg.role == "user"
        assert msg.content == "Hello"
    
    def test_invalid_role(self):
        with pytest.raises(ValidationError):
            Message(
                id=uuid4(),
                conversation_id=uuid4(),
                role="invalid",  # type: ignore
                content="Test",
                created_at=datetime.now(timezone.utc)
            )
    
    def test_empty_content(self):
        with pytest.raises(ValidationError) as exc:
            Message(
                id=uuid4(),
                conversation_id=uuid4(),
                role="user",
                content="   ",
                created_at=datetime.now(timezone.utc)
            )
        assert "content cannot be empty" in str(exc.value)
    
    def test_all_roles(self):
        for role in ["user", "assistant", "tool", "system"]:
            msg = Message(
                id=uuid4(),
                conversation_id=uuid4(),
                role=role,  # type: ignore
                content="Test",
                created_at=datetime.now(timezone.utc)
            )
            assert msg.role == role


class TestContextItem:
    def test_valid_context_item(self):
        item = ContextItem(
            id=str(uuid4()),
            title="Document.pdf",
            node_file_id=uuid4(),
            r2_key="files/doc.pdf",
            mime_type="application/pdf",
            status="uploaded",
            gemini_name="files/abc123",
            gemini_uri="https://generativelanguage.googleapis.com/..."
        )
        assert item.status == "uploaded"
        assert item.gemini_name == "files/abc123"
    
    def test_minimal_context_item(self):
        item = ContextItem(
            id=str(uuid4()),
            title="Image",
            mime_type="image/png"
        )
        assert item.status == "local"
        assert item.node_id is None
    
    def test_empty_title(self):
        with pytest.raises(ValidationError) as exc:
            ContextItem(
                id=str(uuid4()),
                title="  ",
                mime_type="text/plain"
            )
        assert "title cannot be empty" in str(exc.value)
    
    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            ContextItem(
                id=str(uuid4()),
                title="Test",
                mime_type="text/plain",
                status="invalid"  # type: ignore
            )


class TestModelAction:
    def test_valid_actions(self):
        actions = [
            ModelAction(type="answer", payload={"text": "Response"}),
            ModelAction(type="open_image", payload={"url": "/img"}, note="Check this"),
            ModelAction(type="request_roi", payload={"page": 1}),
            ModelAction(type="final", payload={})
        ]
        assert len(actions) == 4
        assert actions[1].note == "Check this"
    
    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            ModelAction(type="unknown", payload={})  # type: ignore


class TestModelReply:
    def test_valid_reply(self):
        reply = ModelReply(
            assistant_text="Here is your answer",
            actions=[
                ModelAction(type="answer", payload={"data": "x"}),
                ModelAction(type="final", payload={})
            ],
            is_final=True
        )
        assert reply.is_final
        assert len(reply.actions) == 2
    
    def test_empty_assistant_text(self):
        with pytest.raises(ValidationError) as exc:
            ModelReply(assistant_text="  ", actions=[], is_final=False)
        assert "assistant_text cannot be empty" in str(exc.value)
    
    def test_default_values(self):
        reply = ModelReply(assistant_text="Test")
        assert reply.actions == []
        assert reply.is_final is False
