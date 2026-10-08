"""Unit tests for runledger.redact.

Direct coverage of redact() and redact_argv(): bare and quoted key/value
assignments (including JSON), token-shaped values, count accuracy, and
innocuous text that must pass through untouched.
"""

from __future__ import annotations

import time
import unittest

from runledger.redact import redact, redact_argv


class TestAssignmentRedaction(unittest.TestCase):
    def test_equals_assignment(self) -> None:
        text, count = redact("api_key=supersecret123")
        self.assertEqual(text, "api_key=[REDACTED]")
        self.assertEqual(count, 1)

    def test_colon_assignment(self) -> None:
        text, count = redact("password: hunter2")
        self.assertEqual(text, "password: [REDACTED]")
        self.assertEqual(count, 1)

    def test_case_insensitive_key(self) -> None:
        text, count = redact("API_KEY=topsecret")
        self.assertEqual(text, "API_KEY=[REDACTED]")
        self.assertEqual(count, 1)

    def test_dash_and_underscore_key_variants(self) -> None:
        for key in ("api-key", "api_key", "access-token", "access_token", "auth-token", "auth_token", "passwd", "secret"):
            text, count = redact(f"{key}=value123")
            self.assertEqual(text, f"{key}=[REDACTED]", key)
            self.assertEqual(count, 1, key)

    def test_spaces_around_separator(self) -> None:
        text, count = redact("secret   =   spaced-out")
        self.assertEqual(text, "secret   =   [REDACTED]")
        self.assertEqual(count, 1)

    def test_key_prefix_kept_value_with_equals(self) -> None:
        text, _ = redact("secret=abc=def")
        self.assertEqual(text, "secret=[REDACTED]")

    def test_multiple_assignments_counted(self) -> None:
        text, count = redact("user=bob password=hunter2 api_key=zz9")
        self.assertEqual(text, "user=bob password=[REDACTED] api_key=[REDACTED]")
        self.assertEqual(count, 2)

    def test_key_as_word_prefix_not_redacted(self) -> None:
        text, count = redact("secretary=not-a-secret")
        self.assertEqual(text, "secretary=not-a-secret")
        self.assertEqual(count, 0)


class TestQuotedAssignmentRedaction(unittest.TestCase):
    def test_double_quoted_json_assignment(self) -> None:
        text, count = redact('"password": "hunter2"')
        self.assertEqual(text, '"password": "[REDACTED]"')
        self.assertEqual(count, 1)

    def test_single_quoted_assignment(self) -> None:
        text, count = redact("'secret': 'abc123'")
        self.assertEqual(text, "'secret': '[REDACTED]'")
        self.assertEqual(count, 1)

    def test_quoted_key_unquoted_value(self) -> None:
        text, count = redact('"api_key": sk_live_abcdef123456')
        self.assertEqual(text, '"api_key": [REDACTED]')
        self.assertEqual(count, 1)

    def test_unquoted_key_quoted_value(self) -> None:
        text, count = redact("api_key='sk_live_abcdef123456'")
        self.assertEqual(text, "api_key='[REDACTED]'")
        self.assertEqual(count, 1)

    def test_nested_json_object(self) -> None:
        payload = '{"config": {"auth": {"api_key": "sk_test_12345678901234567890"}}}'
        text, count = redact(payload)
        self.assertNotIn("sk_test_12345678901234567890", text)
        self.assertIn('"api_key": "[REDACTED]"', text)
        self.assertEqual(count, 1)

    def test_nested_json_plain_password(self) -> None:
        payload = '{"db": {"credentials": {"password": "hunter2-super-secret"}}}'
        text, count = redact(payload)
        self.assertNotIn("hunter2-super-secret", text)
        self.assertIn('"password": "[REDACTED]"', text)
        self.assertEqual(count, 1)

    def test_json_array_of_assignments(self) -> None:
        payload = '{"keys": ["api_key=first-secret", "password=second-secret"]}'
        text, count = redact(payload)
        self.assertNotIn("first-secret", text)
        self.assertNotIn("second-secret", text)
        self.assertEqual(count, 2)


class TestTokenRedaction(unittest.TestCase):
    def test_github_token(self) -> None:
        token = "ghp_" + "a" * 36
        text, count = redact(f"deploying with {token} now")
        self.assertEqual(text, "deploying with [REDACTED] now")
        self.assertEqual(count, 1)

    def test_stripe_style_secret_key(self) -> None:
        token = "sk_test_12345678901234567890"
        text, count = redact(f"key={token}")
        self.assertNotIn(token, text)
        self.assertEqual(count, 1)

    def test_short_sk_prefix_not_redacted(self) -> None:
        text, count = redact("prefix sk_short suffix")
        self.assertEqual(text, "prefix sk_short suffix")
        self.assertEqual(count, 0)

    def test_aws_access_key_id(self) -> None:
        text, count = redact("using AKIAIOSFODNN7EXAMPLE for s3")
        self.assertEqual(text, "using [REDACTED] for s3")
        self.assertEqual(count, 1)

    def test_jwt(self) -> None:
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        text, count = redact(f"Authorization: Bearer {jwt}")
        self.assertNotIn(jwt, text)
        self.assertIn("[REDACTED]", text)
        self.assertEqual(count, 1)

    def test_very_long_token_redacted(self) -> None:
        token = "ghp_" + "z" * 500
        text, count = redact(f"token={token}")
        self.assertNotIn(token, text)
        self.assertEqual(count, 1)

    def test_long_input_stays_fast(self) -> None:
        blob = ("log line with nothing secret " * 200) + "api_key=" + "k" * 1000
        started = time.perf_counter()
        text, count = redact(blob)
        elapsed = time.perf_counter() - started
        self.assertEqual(count, 1)
        self.assertLess(elapsed, 1.0)

    def test_innocuous_text_untouched(self) -> None:
        text, count = redact("just a regular log line, nothing to hide")
        self.assertEqual(text, "just a regular log line, nothing to hide")
        self.assertEqual(count, 0)


class TestRedactArgv(unittest.TestCase):
    def test_argv_redacted_with_total(self) -> None:
        argv, total = redact_argv(["runledger", "record", "--api-key", "api_key=topsecret", "clean-arg"])
        self.assertEqual(argv, ["runledger", "record", "--api-key", "api_key=[REDACTED]", "clean-arg"])
        self.assertEqual(total, 1)

    def test_argv_all_clean(self) -> None:
        argv, total = redact_argv(["runledger", "status"])
        self.assertEqual(argv, ["runledger", "status"])
        self.assertEqual(total, 0)


if __name__ == "__main__":
    unittest.main()
