"""Run with unittest as well as the project's pytest security suite."""

import json
import unittest

from apps.assistant.validation import ModelOutputError, validate_model_output


class ModelOutputBoundaryTests(unittest.TestCase):
    def test_allows_only_structured_answer_and_known_proposals(self):
        answer = {"kind": "answer", "text": "请检查所选组别。"}
        self.assertEqual(validate_model_output(json.dumps(answer)), answer)
        for tool, arguments in (
            ("registration.open", {"registration_id": 1}),
            (
                "registration.update_draft",
                {
                    "registration_id": 1,
                    "version": 2,
                    "fields": {"selected_school_level": "HS"},
                },
            ),
        ):
            proposal = {"kind": "tool_proposal", "tool": tool, "arguments": arguments}
            self.assertEqual(validate_model_output(json.dumps(proposal)), proposal)

    def test_rejects_invalid_json_and_injection_without_echoing_secrets(self):
        malformed = [
            "not JSON",
            "```json\n{}\n```",
            "[]",
            "null",
            '{"kind":"answer","kind":"answer","text":"secret-sample"}',
            '{"kind":"answer","text":"ok","extra":NaN}',
            '{"kind":"answer","text":"ok","extra":1e999}',
            "[" * 20 + "0" + "]" * 20,
            '{"kind":"answer","text":"' + "x" * 33_000 + '"}',
            '{"kind":"answer","text":""}',
            '{"kind":"answer","text":"\\ud800"}',
            '{"kind":"answer","text":"ok","actor":1}',
        ]
        for raw in malformed:
            with self.subTest(raw=raw[:60]):
                with self.assertRaises(ModelOutputError) as result:
                    validate_model_output(raw)
                self.assertNotIn("secret-sample", str(result.exception))

    def test_rejects_unknown_tools_credentials_and_arbitrary_field_mutations(self):
        proposals = [
            {"tool": "sql.query", "arguments": {"sql": "select 1"}},
            {"tool": "registration.open", "arguments": {"registration_id": True}},
            {"tool": "registration.open", "arguments": {"registration_id": "1"}},
            {"tool": "registration.open", "arguments": {"registration_id": 0}},
            {"tool": "registration.open", "arguments": {"registration_id": 2**53}},
            {
                "tool": "registration.open",
                "arguments": {"registration_id": 1, "authorization": "secret-sample"},
            },
            {
                "tool": "registration.update_draft",
                "arguments": {
                    "registration_id": 1,
                    "version": 1,
                    "fields": {"status": "approved"},
                },
            },
            {
                "tool": "registration.update_draft",
                "arguments": {
                    "registration_id": 1,
                    "version": 1,
                    "fields": {"selected_school_level": []},
                },
            },
        ]
        for proposal in proposals:
            with self.subTest(tool=proposal["tool"]):
                with self.assertRaises(ModelOutputError):
                    validate_model_output(
                        json.dumps({"kind": "tool_proposal", **proposal})
                    )
