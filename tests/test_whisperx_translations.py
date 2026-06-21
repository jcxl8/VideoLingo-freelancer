import json
import unittest


class WhisperXTranslationTest(unittest.TestCase):
    def test_whisperx_sidebar_text_has_simplified_chinese_translations(self):
        with open("translations/zh-CN.json", encoding="utf-8") as f:
            zh = json.load(f)

        expected = {
            "Local WhisperX runtime — requires >8GB GPU": "本地 WhisperX 运行环境，需要 8GB 以上显存",
            "Whisper large-v3 model": "Whisper large-v3 模型",
            "Local": "本地",
            "ASR Runtime": "ASR 运行环境",
            "Choose WhisperX for stricter alignment or MLX Whisper for Apple Silicon Metal acceleration": "WhisperX 对齐更严格；MLX Whisper 使用 Apple Silicon Metal 加速，速度更快",
        }
        for key, value in expected.items():
            self.assertEqual(zh.get(key), value)


if __name__ == "__main__":
    unittest.main()
