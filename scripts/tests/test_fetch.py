import sys
"""
Unit tests for the attachment reader — classification, PHI scanning,
quarantine, filename blocking, and text truncation.

Run from repo root:
    pytest scripts/tests/test_fetch.py -v
"""

import os
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.attachment_reader.fetch import (
    _classify,
    _has_phi_risk_filename,
    _quarantine_file,
    _scan_for_phi,
    _size_display,
    _truncate_text_file,
    PHI_RISK_EXTENSIONS,
    TEXT_EXTENSIONS,
)


# ── TestClassify ────────────────────────────────────────────────────

class TestClassify:
    """File-type classification by extension."""

    # Text files
    def test_log_is_text(self):
        assert _classify("error.log") == "text"

    def test_txt_is_text(self):
        assert _classify("notes.txt") == "text"

    def test_json_is_text(self):
        assert _classify("config.json") == "text"

    def test_yaml_is_text(self):
        assert _classify("values.yaml") == "text"

    def test_yml_is_text(self):
        assert _classify("values.yml") == "text"

    def test_sh_is_text(self):
        assert _classify("deploy.sh") == "text"

    def test_py_is_text(self):
        assert _classify("script.py") == "text"

    def test_sql_is_text(self):
        assert _classify("query.sql") == "text"

    # Images
    def test_png_is_image(self):
        assert _classify("screenshot.png") == "image"

    def test_jpg_is_image(self):
        assert _classify("photo.jpg") == "image"

    def test_jpeg_is_image(self):
        assert _classify("photo.jpeg") == "image"

    def test_gif_is_image(self):
        assert _classify("anim.gif") == "image"

    # PDF
    def test_pdf_is_pdf(self):
        assert _classify("report.pdf") == "pdf"

    # PHI-risk types — must return 'phi_risk', NOT 'text' or 'unsupported'
    def test_csv_is_phi_risk(self):
        assert _classify("data.csv") == "phi_risk"

    def test_xlsx_is_phi_risk(self):
        assert _classify("data.xlsx") == "phi_risk"

    def test_xls_is_phi_risk(self):
        assert _classify("data.xls") == "phi_risk"

    def test_parquet_is_phi_risk(self):
        assert _classify("data.parquet") == "phi_risk"

    def test_tsv_is_phi_risk(self):
        assert _classify("data.tsv") == "phi_risk"

    # Unsupported
    def test_zip_is_unsupported(self):
        assert _classify("archive.zip") == "unsupported"

    def test_docx_is_unsupported(self):
        assert _classify("doc.docx") == "unsupported"

    def test_no_extension_is_unsupported(self):
        assert _classify("Dockerfile") == "unsupported"

    # Case insensitivity
    def test_uppercase_extension(self):
        assert _classify("ERROR.LOG") == "text"

    def test_mixed_case_csv(self):
        assert _classify("Export.CSV") == "phi_risk"


# ── TestPhiRiskFilename ─────────────────────────────────────────────

class TestPhiRiskFilename:
    """Filename-based PHI risk detection."""

    def test_patient_blocked(self):
        assert _has_phi_risk_filename("patient_list.json") is True

    def test_member_blocked(self):
        assert _has_phi_risk_filename("member_data.txt") is True

    def test_claims_blocked(self):
        assert _has_phi_risk_filename("claims_export.log") is True

    def test_claim_singular_blocked(self):
        assert _has_phi_risk_filename("claim_detail.txt") is True

    def test_enrollment_blocked(self):
        assert _has_phi_risk_filename("enrollment_2024.json") is True

    def test_ssn_blocked(self):
        assert _has_phi_risk_filename("ssn_lookup.txt") is True

    def test_dob_blocked(self):
        assert _has_phi_risk_filename("dob_extract.log") is True

    def test_phi_blocked(self):
        assert _has_phi_risk_filename("phi_data.txt") is True

    def test_pii_blocked(self):
        assert _has_phi_risk_filename("pii_report.json") is True

    def test_hipaa_blocked(self):
        assert _has_phi_risk_filename("hipaa_audit.txt") is True

    def test_mrn_blocked(self):
        assert _has_phi_risk_filename("mrn_list.log") is True

    def test_medical_record_blocked(self):
        assert _has_phi_risk_filename("medical_record_export.txt") is True

    # Safe filenames — must NOT be blocked
    def test_airflow_error_log_safe(self):
        assert _has_phi_risk_filename("airflow_error.log") is False

    def test_dag_screenshot_safe(self):
        assert _has_phi_risk_filename("dag_screenshot.png") is False

    def test_config_safe(self):
        assert _has_phi_risk_filename("config.json") is False

    def test_pipeline_log_safe(self):
        assert _has_phi_risk_filename("pipeline_failure.log") is False


# ── TestScanForPhi ──────────────────────────────────────────────────

class TestScanForPhi:
    """PHI content regex scanning."""

    def _make_file(self, content: str) -> Path:
        """Helper: write content to a temp file and return its path."""
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write(content)
        f.flush()
        f.close()
        return Path(f.name)

    def test_ssn_detected(self):
        p = self._make_file("User SSN: 123-45-6789 found in record.")
        findings = _scan_for_phi(p)
        p.unlink()
        assert "SSN" in findings

    def test_mrn_detected(self):
        p = self._make_file("MRN: 987654321 assigned to patient.")
        findings = _scan_for_phi(p)
        p.unlink()
        assert "MRN" in findings

    def test_mrn_label_detected(self):
        p = self._make_file("Medical Record Number: 123456789")
        findings = _scan_for_phi(p)
        p.unlink()
        assert "MRN" in findings

    def test_dob_detected(self):
        p = self._make_file("DOB: 01/15/1980 on file.")
        findings = _scan_for_phi(p)
        p.unlink()
        assert "DOB" in findings

    def test_dob_label_detected(self):
        p = self._make_file("Date of Birth: 03/22/1975")
        findings = _scan_for_phi(p)
        p.unlink()
        assert "DOB" in findings

    def test_patient_name_detected(self):
        p = self._make_file("Patient Name: John Smith")
        findings = _scan_for_phi(p)
        p.unlink()
        assert "Patient/Member ID" in findings

    def test_member_id_detected(self):
        p = self._make_file("Member ID: ABC123456")
        findings = _scan_for_phi(p)
        p.unlink()
        assert "Patient/Member ID" in findings

    def test_email_detected(self):
        p = self._make_file("Contact: john.doe@hospital.org for follow-up.")
        findings = _scan_for_phi(p)
        p.unlink()
        assert "Email Address" in findings

    def test_phone_detected(self):
        p = self._make_file("Call 8005551234 for support.")
        findings = _scan_for_phi(p)
        p.unlink()
        assert "Phone Number (10-digit)" in findings

    def test_insurance_id_detected(self):
        p = self._make_file("Insurance ID: POL-987654")
        findings = _scan_for_phi(p)
        p.unlink()
        assert "Insurance ID" in findings

    def test_fhir_patient_resource_detected(self):
        p = self._make_file('{"resourceType": "Patient", "id": "12345"}')
        findings = _scan_for_phi(p)
        p.unlink()
        assert "FHIR Patient Resource" in findings

    def test_fhir_patient_reference_detected(self):
        p = self._make_file('{"subject": {"reference": "Patient/67890"}}')
        findings = _scan_for_phi(p)
        p.unlink()
        assert "FHIR Patient Reference" in findings

    def test_icd10_detected(self):
        p = self._make_file("Diagnosis code: J18.9 (pneumonia)")
        findings = _scan_for_phi(p)
        p.unlink()
        assert "ICD-10 Code" in findings

    def test_npi_detected(self):
        p = self._make_file("NPI: 1234567890")
        findings = _scan_for_phi(p)
        p.unlink()
        assert "NPI Number" in findings

    # Clean files — must return empty list
    def test_clean_log_file(self):
        p = self._make_file(
            "2024-01-15 10:23:45 ERROR airflow.task.runner - Task failed\n"
            "Traceback (most recent call last):\n"
            "  File 'dag.py', line 42, in run\n"
            "    raise ValueError('Connection timeout')\n"
        )
        findings = _scan_for_phi(p)
        p.unlink()
        assert findings == []

    def test_clean_json_config(self):
        p = self._make_file(
            '{"env": "prod", "region": "us-east-1", "bucket": "abacus-data"}'
        )
        findings = _scan_for_phi(p)
        p.unlink()
        assert findings == []

    def test_clean_pipeline_error(self):
        p = self._make_file(
            "Pipeline FHIR_LOAD_001 failed at step 3.\n"
            "Error: S3 bucket not found: s3://abacus-fhir-prod\n"
            "Retry count: 3/3\n"
        )
        findings = _scan_for_phi(p)
        p.unlink()
        assert findings == []

    def test_empty_file_is_clean(self):
        p = self._make_file("")
        findings = _scan_for_phi(p)
        p.unlink()
        assert findings == []

    def test_multiple_phi_types_detected(self):
        p = self._make_file(
            "SSN: 123-45-6789\n"
            "DOB: 05/10/1990\n"
            "Email: patient@example.com\n"
        )
        findings = _scan_for_phi(p)
        p.unlink()
        assert "SSN" in findings
        assert "DOB" in findings
        assert "Email Address" in findings

    def test_nonexistent_file_returns_empty(self):
        findings = _scan_for_phi(Path("/nonexistent/path/file.txt"))
        assert findings == []


# ── TestQuarantineFile ──────────────────────────────────────────────

class TestQuarantineFile:
    """Quarantine replaces file content with a notice."""

    def test_quarantine_replaces_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("SSN: 123-45-6789\nPatient Name: John Doe\n")
            path = Path(f.name)

        _quarantine_file(path, ["SSN", "Patient/Member ID"])
        content = path.read_text()
        path.unlink()

        assert "QUARANTINED" in content
        assert "SSN" in content
        assert "Patient/Member ID" in content
        # Original PHI must NOT be present
        assert "123-45-6789" not in content
        assert "John Doe" not in content

    def test_quarantine_notice_contains_action_required(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("DOB: 01/01/1980")
            path = Path(f.name)

        _quarantine_file(path, ["DOB"])
        content = path.read_text()
        path.unlink()

        assert "Action required" in content or "human reviewer" in content.lower()


# ── TestSizeDisplay ─────────────────────────────────────────────────

class TestSizeDisplay:
    """Human-readable file size formatting."""

    def test_bytes(self):
        assert _size_display(500) == "500 B"

    def test_kilobytes(self):
        assert "KB" in _size_display(12_000)

    def test_megabytes(self):
        assert "MB" in _size_display(5_000_000)

    def test_exactly_1kb(self):
        assert "KB" in _size_display(1024)

    def test_exactly_1mb(self):
        assert "MB" in _size_display(1_048_576)

    def test_zero_bytes(self):
        assert _size_display(0) == "0 B"


# ── TestTruncateTextFile ────────────────────────────────────────────

class TestTruncateTextFile:
    """Text file head+tail truncation."""

    def test_small_file_not_truncated(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n".join(f"line {i}" for i in range(10)))
            path = Path(f.name)

        result = _truncate_text_file(path)
        path.unlink()
        assert result is False

    def test_large_file_truncated(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n".join(f"line {i}: some log content here" for i in range(1000)))
            path = Path(f.name)

        # Patch MAX_TEXT_LINES for this test
        import scripts.attachment_reader.fetch as fetch_module
        original = fetch_module.MAX_TEXT_LINES
        fetch_module.MAX_TEXT_LINES = 100

        result = _truncate_text_file(path)
        content = path.read_text()
        path.unlink()

        fetch_module.MAX_TEXT_LINES = original

        assert result is True
        assert "lines omitted" in content

    def test_truncated_file_has_head_and_tail(self):
        lines = [f"line {i}" for i in range(200)]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n".join(lines))
            path = Path(f.name)

        import scripts.attachment_reader.fetch as fetch_module
        original = fetch_module.MAX_TEXT_LINES
        fetch_module.MAX_TEXT_LINES = 50

        _truncate_text_file(path)
        content = path.read_text()
        path.unlink()

        fetch_module.MAX_TEXT_LINES = original

        assert "line 0" in content       # head preserved
        assert "line 199" in content     # tail preserved
        assert "lines omitted" in content


# ── TestPhiPipeline ─────────────────────────────────────────────────

class TestPhiPipeline:
    """End-to-end: scan → quarantine pipeline."""

    def test_phi_file_is_quarantined_after_scan(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("Patient Name: Jane Doe\nSSN: 987-65-4321\n")
            path = Path(f.name)

        findings = _scan_for_phi(path)
        assert len(findings) > 0

        _quarantine_file(path, findings)
        content = path.read_text()
        path.unlink()

        assert "QUARANTINED" in content
        assert "Jane Doe" not in content
        assert "987-65-4321" not in content

    def test_clean_file_passes_scan(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("ERROR: Connection refused to 10.0.0.1:5432\nRetrying...\n")
            path = Path(f.name)

        findings = _scan_for_phi(path)
        path.unlink()
        assert findings == []

    def test_csv_blocked_by_classify(self):
        """CSV must be classified as phi_risk and never reach the download step."""
        assert _classify("export.csv") == "phi_risk"
        assert _classify("EXPORT.CSV") == "phi_risk"

    def test_phi_filename_blocked(self):
        """Patient filename must be blocked before download."""
        assert _has_phi_risk_filename("patient_export.log") is True
        assert _has_phi_risk_filename("airflow_error.log") is False


# ── TestClassificationConsistency ──────────────────────────────────

class TestClassificationConsistency:
    """Ensure no overlap between extension sets."""

    def test_phi_risk_not_in_text_extensions(self):
        """PHI-risk extensions must not appear in TEXT_EXTENSIONS."""
        overlap = PHI_RISK_EXTENSIONS & TEXT_EXTENSIONS
        assert overlap == set(), f"Overlap found: {overlap}"

    def test_csv_not_in_text_extensions(self):
        assert ".csv" not in TEXT_EXTENSIONS

    def test_xlsx_not_in_text_extensions(self):
        assert ".xlsx" not in TEXT_EXTENSIONS
