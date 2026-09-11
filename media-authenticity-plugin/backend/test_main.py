import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

import main


class AnalyzeTests(unittest.TestCase):
    def test_rejects_blank_text(self):
        with self.assertRaises(HTTPException) as error:
            main.analyze(main.AnalyzeRequest(text="  "))

        self.assertEqual(error.exception.status_code, 400)

    @patch.object(main, "HF_TOKEN", "test-token")
    @patch.object(main, "InferenceClient")
    @patch.object(
        main,
        "verify_claim",
        return_value={
            "claim_status": "Verified in mainstream media",
            "sources": [{"title": "Example source", "url": "https://reuters.com/example"}],
        },
    )
    def test_forwards_text_and_returns_two_factor_response(
        self, verify_claim_mock, client_class_mock
    ):
        client_class_mock.return_value.text_classification.return_value = [
            SimpleNamespace(label="Fake", score=0.91)
        ]

        result = main.analyze(main.AnalyzeRequest(text="  sample text  "))

        self.assertEqual(
            result,
            {
                "ai_score": {"percentage": 91, "label": "91% AI-Generated"},
                "claim_status": "Verified in mainstream media",
                "sources": [
                    {"title": "Example source", "url": "https://reuters.com/example"}
                ],
            },
        )
        verify_claim_mock.assert_called_once_with("sample text")
        client_class_mock.assert_called_once_with(
            provider="hf-inference",
            api_key="test-token",
        )
        client_class_mock.return_value.text_classification.assert_called_once_with(
            text="sample text",
            model="openai-community/roberta-base-openai-detector",
        )

    @patch.object(main, "HF_TOKEN", "test-token")
    @patch.object(main, "InferenceClient")
    def test_maps_upstream_auth_failure(self, client_class_mock):
        client_class_mock.return_value.text_classification.side_effect = Exception(
            "unauthorized"
        )

        with self.assertRaises(HTTPException) as error:
            main.analyze(main.AnalyzeRequest(text="sample text"))

        self.assertEqual(error.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()