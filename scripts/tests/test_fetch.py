import sys
"""Unit tests for the attachment reader — classification & text truncation."""

import os
import tempfile
from pathlib import Path

import pytest

# We import the internal helpers — adjust the import path if needed.
# When running from repo root: pytest scripts/attachment_reader/tests/
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.attachment_reader.fetch import _classify, _truncate_text_file, _size_display


class TestClassify:
    """File-type classification by extension."""

    def test_log_is_text(self):
        assert _classify("error.log") == "text"

    def test_txt_is_text(self):
        assert _classify("notes.txt") == "text"

    def test_json_is_text(self):
        assert _classify("config.json") == "text"

    def test_yaml_is_text(self):
        assert _classify("values.yaml") == "text"

    def test_csv_is_text(self):
        assert _classify("data.csv") == "text"

    def test_png_is_image(self):
        assert _classify("screenshot.png") == "image"

    def test_jpg_is_image(self):
        assert _classify("photo.jpg") == "image"

    def test_jpeg_is_image(self):
        assert _classify("photo.jpeg") == "image"

    def test_pdf_is_pdf(self):
        assert _classify("report.pdf") == "pdf"

    def test_zip_is_unsupported(self):
        assert _classify("archive.zip") == "unsupported"

    def test_xlsx_is_unsupported(self):
        assert _classify("data.xlsx") == "unsupported"

    def test_docx_is_unsupported(self):
        assert _classify("doc.docx") == "unsupported"

    def test_no_extension_is_unsupported(self):
        assert _classify("Dockerfile") == "unsupported"


class TestSizeDisplay:
    """Human-readable file size formatting."""

    def test_bytes(self):
        assert _size_display(500) == "500 B"

    def test_kilobytes(self):
        assert "KB" in _size_display(12_000)

    def test_megabytes(self):
        assert "MB" in _size_display(5_000_000)


class TestTruncateTextFile:
    """Text file head+tail truncation."""

    def test_small_file_not_truncated(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n".join(f"line {i}" for i in range(10)))
            f.flush()
            path = Path(f.name)

        os.environ["ATTACHMENT_MAX_TEXT_LINES"] = "500"
        result = _truncate_text_file(path)
        assert result is False
        path.unlink()

    def test_large_file_truncated(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n".join(f"line {i}: some log content here" for i in range(1000)))
            f.flush()
            path = Path(f.name)

        # Force a low threshold
        os.environ["ATTACHMENT_MAX_TEXT_LINES"] = "100"
        # Re-import to pick up new env value — or just test directly
        from scripts.attachment_reader.fetch import MAX_TEXT_LINES
        result = _truncate_text_file(path)

        content = path.read_text()
        assert "lines omitted" in content
        path.unlink()
