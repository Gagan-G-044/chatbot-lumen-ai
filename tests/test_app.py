"""
Unit and integration tests for Lumen AI Flask backend.
Tests health endpoint, homepage, input validation, rate limiting,
security barriers, and mocked Gemini API responses.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import io

# Ensure app is imported in test mode with in-memory limiter
os.environ["RATELIMIT_STORAGE_URI"] = "memory://"
os.environ["RATELIMIT_CHAT"] = "5 per minute; 2 per second"

from google.genai import errors as genai_errors
from app import app, limiter, MAX_MESSAGE_LENGTH, MAX_FILE_SIZE, PRIMARY_MODEL, FALLBACK_MODEL

class LumenAITestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["RATELIMIT_ENABLED"] = True
        limiter.reset()
        self.client = app.test_client()

    def tearDown(self):
        limiter.reset()

    def test_health_endpoint(self):
        """Verify that /health returns 200 and expected health metadata."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "online")
        self.assertEqual(data.get("service"), "lumen-ai")
        self.assertIn("api_configured", data)
        self.assertIn("models", data)
        self.assertEqual(data.get("primary_model"), PRIMARY_MODEL)
        self.assertEqual(data.get("fallback_model"), FALLBACK_MODEL)
        res.close()

    def test_homepage_serves_html(self):
        """Verify that GET / returns 200 with the index.html content."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Lumen", res.data)
        self.assertIn(b"<!DOCTYPE html>", res.data)
        res.close()

    def test_static_security_blocks_root_files(self):
        """Verify that sensitive root files like .env or app.py are NOT accessible via web routes."""
        res_env = self.client.get("/.env")
        self.assertEqual(res_env.status_code, 404)
        res_env.close()

        res_app = self.client.get("/app.py")
        self.assertEqual(res_app.status_code, 404)
        res_app.close()

        res_req = self.client.get("/requirements.txt")
        self.assertEqual(res_req.status_code, 404)
        res_req.close()

    def test_chat_non_json_returns_400(self):
        """Verify that non-JSON request body to /chat returns 400."""
        res = self.client.post("/chat", data="not json", content_type="text/plain")
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data.get("code"), "INVALID_JSON")
        res.close()

    def test_chat_missing_message_returns_400(self):
        """Verify that request missing 'message' key returns 400."""
        res = self.client.post("/chat", json={})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data.get("code"), "MISSING_MESSAGE")
        res.close()

    def test_chat_empty_message_returns_400(self):
        """Verify that empty or whitespace-only message returns 400."""
        res = self.client.post("/chat", json={"message": "   "})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data.get("code"), "EMPTY_MESSAGE")
        res.close()

    def test_chat_non_string_message_returns_400(self):
        """Verify that numeric/boolean/dict message returns 400."""
        res = self.client.post("/chat", json={"message": 12345})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data.get("code"), "INVALID_MESSAGE_TYPE")
        res.close()

    def test_chat_oversized_message_returns_413(self):
        """Verify that a message exceeding MAX_MESSAGE_LENGTH returns 413."""
        long_msg = "a" * (MAX_MESSAGE_LENGTH + 10)
        res = self.client.post("/chat", json={"message": long_msg})
        self.assertEqual(res.status_code, 413)
        data = res.get_json()
        self.assertEqual(data.get("code"), "MESSAGE_TOO_LONG")
        res.close()

    @patch("app.get_genai_client")
    def test_chat_without_pdf_refuses_without_calling_gemini(self, mock_get_client):
        """Verify that /chat without a PDF returns 400 and does NOT call Gemini generation."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        res = self.client.post("/chat", json={"message": "Tell me about quantum physics."})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data.get("code"), "NO_PDF_UPLOADED")
        self.assertEqual(data.get("error"), "Please upload a PDF first. General questions are disabled.")
        self.assertFalse(mock_client.models.generate_content.called)
        res.close()

    @patch("app.get_genai_client")
    def test_chat_successful_mock_response(self, mock_get_client):
        """Verify that /chat returns 200 and reply when Gemini generates content for a PDF."""
        mock_client = MagicMock()
        mock_file = MagicMock()
        mock_client.files.get.return_value = mock_file
        mock_response = MagicMock()
        mock_response.text = "This is a stellar celestial reply from Lumen."
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        res = self.client.post("/chat", json={
            "message": "What is the nature of light?",
            "file_id": "files/test_pdf"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("reply"), "This is a stellar celestial reply from Lumen.")
        self.assertEqual(data.get("model_used"), PRIMARY_MODEL)
        self.assertEqual(mock_client.models.generate_content.call_count, 1)
        res.close()

    @patch("app.get_genai_client")
    def test_chat_fallback_on_primary_rate_limit_429(self, mock_get_client):
        """Verify that when PRIMARY_MODEL hits a 429 rate limit, /chat immediately retries FALLBACK_MODEL once."""
        mock_client = MagicMock()
        mock_file = MagicMock()
        mock_client.files.get.return_value = mock_file

        # 1st call (primary) raises 429 ClientError, 2nd call (fallback) succeeds
        rate_limit_err = genai_errors.ClientError(429, "Resource has been exhausted (e.g. check quota)")
        mock_success = MagicMock()
        mock_success.text = "Grounded response from fallback model."

        mock_client.models.generate_content.side_effect = [rate_limit_err, mock_success]
        mock_get_client.return_value = mock_client

        res = self.client.post("/chat", json={
            "message": "What is the key takeaway?",
            "file_id": "files/test_pdf"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("reply"), "Grounded response from fallback model.")
        self.assertEqual(data.get("model_used"), FALLBACK_MODEL)
        self.assertTrue(data.get("grounded"))
        self.assertEqual(mock_client.models.generate_content.call_count, 2)

        # First call was with PRIMARY_MODEL, second with FALLBACK_MODEL
        calls = mock_client.models.generate_content.call_args_list
        self.assertEqual(calls[0].kwargs["model"], PRIMARY_MODEL)
        self.assertEqual(calls[1].kwargs["model"], FALLBACK_MODEL)
        self.assertEqual(calls[1].kwargs["config"].temperature, 0.0)
        res.close()

    @patch("app.get_genai_client")
    def test_chat_both_models_rate_limited_returns_429(self, mock_get_client):
        """Verify that when both PRIMARY_MODEL and FALLBACK_MODEL hit 429, /chat returns 429 RATE_LIMIT_EXCEEDED."""
        mock_client = MagicMock()
        mock_file = MagicMock()
        mock_client.files.get.return_value = mock_file

        rate_limit_err = genai_errors.ClientError(429, "Resource exhausted (quota exceeded)")
        mock_client.models.generate_content.side_effect = [rate_limit_err, rate_limit_err]
        mock_get_client.return_value = mock_client

        res = self.client.post("/chat", json={
            "message": "What is in chapter 1?",
            "file_id": "files/test_pdf"
        })
        self.assertEqual(res.status_code, 429)
        data = res.get_json()
        self.assertEqual(data.get("code"), "RATE_LIMIT_EXCEEDED")
        self.assertIn("Rate limit exceeded on all AI models", data.get("error"))
        self.assertEqual(mock_client.models.generate_content.call_count, 2)
        res.close()

    @patch("app.get_genai_client")
    def test_chat_provider_failure_returns_503(self, mock_get_client):
        """Verify that when all models fail to return content, /chat returns 503."""
        mock_client = MagicMock()
        mock_file = MagicMock()
        mock_client.files.get.return_value = mock_file
        mock_client.models.generate_content.side_effect = Exception("Service unavailable")
        mock_get_client.return_value = mock_client

        res = self.client.post("/chat", json={"message": "Hello?", "file_id": "files/test_pdf"})
        self.assertEqual(res.status_code, 503)
        data = res.get_json()
        self.assertEqual(data.get("code"), "PROVIDER_UNAVAILABLE")
        res.close()

    @patch("app.get_genai_client")
    def test_chat_missing_api_key_returns_503(self, mock_get_client):
        """Verify that missing API key returns 503 with API_KEY_MISSING code."""
        mock_get_client.return_value = None

        res = self.client.post("/chat", json={"message": "Hello without key?", "file_id": "files/test_pdf"})
        self.assertEqual(res.status_code, 503)
        data = res.get_json()
        self.assertEqual(data.get("code"), "API_KEY_MISSING")
        res.close()

    @patch("app.get_genai_client")
    def test_rate_limiting_triggers_429(self, mock_get_client):
        """Verify that exceeding rate limit on /chat triggers 429."""
        mock_client = MagicMock()
        mock_file = MagicMock()
        mock_client.files.get.return_value = mock_file
        mock_response = MagicMock()
        mock_response.text = "Mock reply"
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        hit_429 = False
        for i in range(10):
            res = self.client.post("/chat", json={"message": f"ping {i}", "file_id": "files/test_pdf"})
            if res.status_code == 429:
                hit_429 = True
                data = res.get_json()
                self.assertEqual(data.get("code"), "RATE_LIMIT_EXCEEDED")
                res.close()
                break
            res.close()

        self.assertTrue(hit_429, "Rate limiter did not trigger 429 after exceeding limit.")

    # ── DOCUMENT QA & FILE API TESTS ──────────────────────────────────────────

    @patch("app.get_genai_client")
    def test_upload_missing_file_returns_400(self, mock_get_client):
        """Verify that uploading with missing file returns 400 MISSING_FILE."""
        mock_get_client.return_value = MagicMock()
        res = self.client.post("/upload", data={}, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data.get("code"), "MISSING_FILE")
        res.close()

    @patch("app.get_genai_client")
    def test_upload_invalid_extension_returns_400(self, mock_get_client):
        """Verify that uploading an unsupported file format (.exe) returns 400 INVALID_FILE_TYPE."""
        mock_get_client.return_value = MagicMock()
        data = {
            "file": (io.BytesIO(b"malicious executable"), "virus.exe")
        }
        res = self.client.post("/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        json_data = res.get_json()
        self.assertEqual(json_data.get("code"), "INVALID_FILE_TYPE")
        self.assertEqual(json_data.get("error"), "Only PDF files are supported. Please upload a .pdf document.")
        res.close()

    @patch("app.get_genai_client")
    def test_upload_non_pdf_rejected_multiple_formats(self, mock_get_client):
        """Verify that uploading non-PDF formats (.txt, .docx, .png) are strictly rejected."""
        mock_get_client.return_value = MagicMock()
        for filename in ["notes.txt", "document.docx", "photo.png", "table.csv"]:
            data = {"file": (io.BytesIO(b"dummy data"), filename)}
            res = self.client.post("/upload", data=data, content_type="multipart/form-data")
            self.assertEqual(res.status_code, 400)
            json_data = res.get_json()
            self.assertEqual(json_data.get("code"), "INVALID_FILE_TYPE")
            self.assertEqual(json_data.get("error"), "Only PDF files are supported. Please upload a .pdf document.")
            res.close()

    @patch("app.get_genai_client")
    def test_upload_file_too_large_returns_413(self, mock_get_client):
        """Verify that uploading a file larger than MAX_FILE_SIZE returns 413 FILE_TOO_LARGE."""
        mock_get_client.return_value = MagicMock()
        large_bytes = b"a" * (MAX_FILE_SIZE + 1024)
        data = {
            "file": (io.BytesIO(large_bytes), "huge_manual.pdf")
        }
        res = self.client.post("/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 413)
        json_data = res.get_json()
        self.assertEqual(json_data.get("code"), "FILE_TOO_LARGE")
        res.close()

    @patch("app.get_genai_client")
    def test_upload_successful_mock(self, mock_get_client):
        """Verify successful upload returns 200 with file_id from Gemini File API."""
        mock_client = MagicMock()
        mock_file = MagicMock()
        mock_file.name = "files/test_abc123"
        mock_file.mime_type = "application/pdf"
        mock_client.files.upload.return_value = mock_file
        mock_get_client.return_value = mock_client

        data = {
            "file": (io.BytesIO(b"%PDF-1.4 test document content"), "policy.pdf")
        }
        res = self.client.post("/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertEqual(json_data.get("file_id"), "files/test_abc123")
        self.assertEqual(json_data.get("file_name"), "policy.pdf")
        self.assertTrue(mock_client.files.upload.called)
        res.close()

    @patch("app.get_genai_client")
    def test_delete_file_success_mock(self, mock_get_client):
        """Verify /delete-file successfully calls client.files.delete."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        res = self.client.post("/delete-file", json={"file_id": "files/test_abc123"})
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertEqual(json_data.get("status"), "deleted")
        mock_client.files.delete.assert_called_with(name="files/test_abc123")
        res.close()

    @patch("app.get_genai_client")
    def test_delete_file_invalid_id_returns_400(self, mock_get_client):
        """Verify /delete-file with invalid file_id returns 400 INVALID_FILE_ID."""
        mock_get_client.return_value = MagicMock()
        res = self.client.post("/delete-file", json={"file_id": "not_a_valid_id"})
        self.assertEqual(res.status_code, 400)
        json_data = res.get_json()
        self.assertEqual(json_data.get("code"), "INVALID_FILE_ID")
        res.close()

    @patch("app.get_genai_client")
    def test_chat_with_invalid_file_id_returns_400(self, mock_get_client):
        """Verify /chat with malformed file_id returns 400."""
        mock_get_client.return_value = MagicMock()
        res = self.client.post("/chat", json={
            "message": "What is on page 3?",
            "file_id": "invalid_prefix"
        })
        self.assertEqual(res.status_code, 400)
        json_data = res.get_json()
        self.assertEqual(json_data.get("code"), "INVALID_FILE_ID")
        res.close()

    @patch("app.get_genai_client")
    def test_chat_file_not_found_returns_404(self, mock_get_client):
        """Verify /chat returns 404 when file does not exist on Gemini."""
        mock_client = MagicMock()
        mock_client.files.get.side_effect = Exception("File not found")
        mock_get_client.return_value = mock_client

        res = self.client.post("/chat", json={
            "message": "What is the policy?",
            "file_id": "files/missing_file"
        })
        self.assertEqual(res.status_code, 404)
        json_data = res.get_json()
        self.assertEqual(json_data.get("code"), "FILE_NOT_FOUND")
        res.close()

    @patch("app.get_genai_client")
    def test_chat_grounded_mock_response(self, mock_get_client):
        """Verify /chat uses strict grounding instruction and returns grounded flag when file_id is supplied."""
        mock_client = MagicMock()
        mock_file = MagicMock()
        mock_file.name = "files/test_doc"
        mock_client.files.get.return_value = mock_file

        mock_response = MagicMock()
        mock_response.text = "According to Section 2, the limit is $500."
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        res = self.client.post("/chat", json={
            "message": "What is the limit?",
            "file_id": "files/test_doc"
        })
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertEqual(json_data.get("reply"), "According to Section 2, the limit is $500.")
        self.assertTrue(json_data.get("grounded"))

        # Verify generate_content call received file and strict temperature config
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(call_kwargs["contents"][0], mock_file)
        self.assertEqual(call_kwargs["contents"][1], "What is the limit?")
        self.assertEqual(call_kwargs["config"].temperature, 0.0)
        self.assertIn("explicit facts directly mentioned in the attached PDF", call_kwargs["config"].system_instruction)
        self.assertIn("Not present in the uploaded document.", call_kwargs["config"].system_instruction)
        res.close()

    @patch("app.get_genai_client")
    def test_chat_strict_not_present_fallback_response(self, mock_get_client):
        """Verify /chat returns 'Not present in the uploaded document.' when information is absent."""
        mock_client = MagicMock()
        mock_file = MagicMock()
        mock_client.files.get.return_value = mock_file

        mock_response = MagicMock()
        mock_response.text = "Not present in the uploaded document."
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        res = self.client.post("/chat", json={
            "message": "What is the employee stock vesting schedule?",
            "file_id": "files/test_doc"
        })
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertEqual(json_data.get("reply"), "Not present in the uploaded document.")
        res.close()

if __name__ == "__main__":
    unittest.main()
