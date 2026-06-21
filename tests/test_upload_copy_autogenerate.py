import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.st_utils import upload_copy


class UploadCopyAutogenerateTest(unittest.TestCase):
    @contextmanager
    def render_context(self, buttons, stored_data=None):
        generated_data = {
            "original": {"zh_title": "标题", "zh_description": "简介"},
            "suggestions": [],
        }
        column_one = MagicMock()
        column_two = MagicMock()
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(upload_copy, "_current_video_title", return_value="Video")
            )
            stack.enter_context(
                patch.object(upload_copy, "_upload_copy_source", return_value={})
            )
            stack.enter_context(
                patch.object(upload_copy, "_load_cached_upload_copy", return_value=None)
            )
            stack.enter_context(
                patch.object(
                    upload_copy,
                    "_load_stored_upload_copy",
                    return_value=stored_data,
                    create=True,
                )
            )
            generate = stack.enter_context(
                patch.object(
                    upload_copy,
                    "generate_upload_copy_suggestions",
                    return_value=generated_data,
                )
            )
            stack.enter_context(
                patch.object(upload_copy.st, "columns", return_value=(column_one, column_two))
            )
            stack.enter_context(
                patch.object(upload_copy.st, "button", side_effect=buttons)
            )
            stack.enter_context(patch.object(upload_copy.st, "subheader"))
            stack.enter_context(patch.object(upload_copy.st, "spinner", return_value=MagicMock()))
            stack.enter_context(patch.object(upload_copy.st, "caption"))
            stack.enter_context(patch.object(upload_copy.st, "markdown"))
            write = stack.enter_context(patch.object(upload_copy.st, "write"))
            stack.enter_context(patch.object(upload_copy.st, "dataframe"))
            generate.write_mock = write
            yield generate

    def test_cache_miss_does_not_generate_when_auto_generation_is_disabled(self):
        with self.render_context(buttons=[False, False]) as generate:
            upload_copy.render_upload_copy_suggestions(auto_generate_missing=False)

        generate.assert_not_called()

    def test_manual_generate_still_runs_when_auto_generation_is_disabled(self):
        with self.render_context(buttons=[True, False]) as generate:
            upload_copy.render_upload_copy_suggestions(auto_generate_missing=False)

        generate.assert_called_once_with(force=False)

    def test_manual_regenerate_still_runs_when_auto_generation_is_disabled(self):
        with self.render_context(buttons=[False, True]) as generate:
            upload_copy.render_upload_copy_suggestions(auto_generate_missing=False)

        generate.assert_called_once_with(force=True)

    def test_disabled_auto_generation_displays_previous_saved_copy(self):
        previous = {
            "original": {"zh_title": "已有标题", "zh_description": "已有简介"},
            "suggestions": [],
        }
        with self.render_context(buttons=[False, False], stored_data=previous) as generate:
            upload_copy.render_upload_copy_suggestions(auto_generate_missing=False)

        generate.assert_not_called()
        generate.write_mock.assert_any_call("已有标题")

    def test_suppression_flag_is_consumed_once(self):
        with patch.object(upload_copy.st, "session_state", {}):
            upload_copy.suppress_upload_copy_autogenerate_once()

            self.assertFalse(upload_copy.consume_upload_copy_autogenerate_setting())
            self.assertTrue(upload_copy.consume_upload_copy_autogenerate_setting())

    def test_remerge_action_precedes_upload_copy_render(self):
        source = Path("st.py").read_text(encoding="utf-8")
        block = source[source.index('key="remerge_generated_video"') - 200 :]

        self.assertLess(
            block.index("suppress_upload_copy_autogenerate_once"),
            block.index("render_upload_copy_suggestions"),
        )


if __name__ == "__main__":
    unittest.main()
