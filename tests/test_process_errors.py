import unittest


class ProcessErrorsTest(unittest.TestCase):
    def test_process_error_is_bounded_labeled_and_redacted(self):
        from core.utils.process_errors import format_process_error

        secret = "sk-" + "x" * 32
        message = format_process_error(
            "FFmpeg preview",
            7,
            f"failed with {secret}\n" + "detail " * 1000,
            secret_values=[secret],
            maximum_length=300,
        )

        self.assertIn("FFmpeg preview", message)
        self.assertIn("exit code 7", message)
        self.assertNotIn(secret, message)
        self.assertLessEqual(len(message), 300)

    def test_empty_stderr_still_has_actionable_stage(self):
        from core.utils.process_errors import format_process_error

        message = format_process_error("FFmpeg burn-in", 1, "")

        self.assertEqual(message, "FFmpeg burn-in failed with exit code 1.")


if __name__ == "__main__":
    unittest.main()
