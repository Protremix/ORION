"""
Unit tests for vision path traversal security (validate_image_path and GPT4oVisionAdapter).
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.models import VisionRequest
from src.models.gpt4o_adapters import GPT4oVisionAdapter, validate_image_path


class TestVisionPathSecurity:

    def test_normal_path_within_base_dir_allowed(self, tmp_path):
        base_dir = tmp_path / "vision"
        base_dir.mkdir()
        valid_file = base_dir / "sample.png"
        valid_file.write_bytes(b"fake image data")

        with patch.dict(os.environ, {"ORION_VISION_DATA_DIR": str(base_dir)}):
            result = validate_image_path("sample.png")
            assert isinstance(result, bytes)
            assert result == b"fake image data"

            result_full = validate_image_path(str(valid_file))
            assert isinstance(result_full, bytes)
            assert result_full == b"fake image data"

    def test_dot_dot_traversal_rejected(self, tmp_path):
        base_dir = tmp_path / "vision"
        base_dir.mkdir()
        outside_file = tmp_path / "secret.txt"
        outside_file.write_text("secret")

        with patch.dict(os.environ, {"ORION_VISION_DATA_DIR": str(base_dir)}):
            with pytest.raises(ValueError, match="Access denied|escapes"):
                validate_image_path("../secret.txt")

    def test_dot_dot_dot_dot_etc_passwd_rejected(self, tmp_path):
        base_dir = tmp_path / "vision"
        base_dir.mkdir()

        with patch.dict(os.environ, {"ORION_VISION_DATA_DIR": str(base_dir)}):
            with pytest.raises(ValueError, match="Access denied|escapes"):
                validate_image_path("../../etc/passwd")

            with pytest.raises(ValueError, match="Access denied|escapes"):
                validate_image_path("../../../etc/passwd")

    def test_absolute_path_etc_passwd_rejected(self, tmp_path):
        base_dir = tmp_path / "vision"
        base_dir.mkdir()

        with patch.dict(os.environ, {"ORION_VISION_DATA_DIR": str(base_dir)}):
            with pytest.raises(ValueError, match="Access denied|escapes"):
                validate_image_path("/etc/passwd")

    def test_symlink_to_outside_base_dir_rejected(self, tmp_path):
        base_dir = tmp_path / "vision"
        base_dir.mkdir()
        outside_file = tmp_path / "outside.txt"
        outside_file.write_text("outside data")

        symlink_file = base_dir / "bad_symlink.png"
        try:
            symlink_file.symlink_to(outside_file)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform/user")

        with patch.dict(os.environ, {"ORION_VISION_DATA_DIR": str(base_dir)}):
            with pytest.raises(ValueError, match="Access denied|escapes|symlink"):
                validate_image_path(str(symlink_file))

            with pytest.raises(ValueError, match="Access denied|escapes|symlink"):
                validate_image_path("bad_symlink.png")

    def test_valid_image_path_allowed(self, tmp_path):
        base_dir = tmp_path / "vision"
        base_dir.mkdir()
        image_file = base_dir / "test_image.png"
        image_file.write_bytes(b"PNG header bytes")

        with patch.dict(os.environ, {"ORION_VISION_DATA_DIR": str(base_dir)}):
            image_data = validate_image_path("test_image.png")
            assert isinstance(image_data, bytes)
            assert image_data == b"PNG header bytes"

    def test_empty_or_invalid_input_raises(self):
        with pytest.raises(ValueError, match="Image path must be a non-empty string"):
            validate_image_path("")

        with pytest.raises(ValueError, match="Image path must be a non-empty string"):
            validate_image_path(None)  # type: ignore

    def test_adapter_uses_validate_image_path_allowed(self, tmp_path):
        base_dir = tmp_path / "vision"
        base_dir.mkdir()
        img_file = base_dir / "valid.png"
        img_file.write_bytes(b"fake_image_bytes")

        adapter = GPT4oVisionAdapter(api_key="test-key")
        with patch.dict(os.environ, {"ORION_VISION_DATA_DIR": str(base_dir)}):
            prepared = adapter._prepare_image(VisionRequest(image_path=str(img_file)))
            assert prepared.startswith("data:image/png;base64,")

    def test_adapter_uses_validate_image_path_traversal_blocked(self, tmp_path):
        base_dir = tmp_path / "vision"
        base_dir.mkdir()

        adapter = GPT4oVisionAdapter(api_key="test-key")
        with patch.dict(os.environ, {"ORION_VISION_DATA_DIR": str(base_dir)}):
            with pytest.raises(ValueError, match="Access denied|escapes"):
                adapter._prepare_image(VisionRequest(image_path="/etc/passwd"))

            with pytest.raises(ValueError, match="Access denied|escapes"):
                adapter._prepare_image(VisionRequest(image_path="../../etc/passwd"))

    def test_url_loading_not_affected_by_path_validation(self):
        """Change #10: HTTPS URLs are now downloaded locally, not passed through.
        Use a data URL to verify URL-based image loading still works independently
        of path validation."""
        adapter = GPT4oVisionAdapter(api_key="test-key")
        url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAADAAFczf9pAAAAAElFTkSuQmCC"
        res = adapter._prepare_image(VisionRequest(image_url=url))
        assert res.startswith("data:image/")
