"""
Unit and integration tests for Lumen AI Flask backend.
Tests health endpoint, homepage, input validation, conversation history,
rate limiting, security barriers, and mocked Gemini API responses.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import json

# Ensure app is imported in test mode with in-memory limiter
os.environ["RATELIMIT_STORAGE_URI"] = "memory://"
os.environ["RATELIMIT_CHAT"] = "5 per minute; 2 per second"

from app import app, limiter, MAX_MESSAGE_LENGTH, MAX_PAYLOAD_BYTES

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

    def test_chat_invalid_history_type_returns_400(self):
        """Verify that history must be an array."""
        res = self.client.post("/chat", json={"message": "hello", "history": "not-a-list"})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data.get("code"), "INVALID_HISTORY")
        res.close()

    @patch("app.get_genai_client")
    def test_chat_successful_mock_response(self, mock_get_client):
        """Verify that /chat returns 200 and reply when Gemini generates content."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This is a stellar celestial reply from Lumen."
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        res = self.client.post("/chat", json={
            "message": "What is the nature of light?",
            "history": [
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Greetings traveller."}
            ]
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("reply"), "This is a stellar celestial reply from Lumen.")
        self.assertTrue(mock_client.models.generate_content.called)
        res.close()

    @patch("app.get_genai_client")
    def test_chat_provider_failure_returns_503(self, mock_get_client):
        """Verify that when all models fail to return content, /chat returns 503."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("Service unavailable")
        mock_get_client.return_value = mock_client

        res = self.client.post("/chat", json={"message": "Hello?"})
        self.assertEqual(res.status_code, 503)
        data = res.get_json()
        self.assertEqual(data.get("code"), "PROVIDER_UNAVAILABLE")
        res.close()

    @patch("app.get_genai_client")
    def test_chat_missing_api_key_returns_503(self, mock_get_client):
        """Verify that missing API key returns 503 with API_KEY_MISSING code."""
        mock_get_client.return_value = None

        res = self.client.post("/chat", json={"message": "Hello without key?"})
        self.assertEqual(res.status_code, 503)
        data = res.get_json()
        self.assertEqual(data.get("code"), "API_KEY_MISSING")
        res.close()

    @patch("app.get_genai_client")
    def test_rate_limiting_triggers_429(self, mock_get_client):
        """Verify that exceeding rate limit on /chat triggers 429."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Mock reply"
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        hit_429 = False
        # Limit is 5 per minute in this test suite setup
        for i in range(10):
            res = self.client.post("/chat", json={"message": f"ping {i}"})
            if res.status_code == 429:
                hit_429 = True
                data = res.get_json()
                self.assertEqual(data.get("code"), "RATE_LIMIT_EXCEEDED")
                res.close()
                break
            res.close()

        self.assertTrue(hit_429, "Rate limiter did not trigger 429 after exceeding limit.")

if __name__ == "__main__":
    unittest.main()
