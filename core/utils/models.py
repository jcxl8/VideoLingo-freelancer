# ------------------------------------------
# 定义中间产出文件
# ------------------------------------------

_2_CLEANED_CHUNKS = "output/log/cleaned_chunks.xlsx"
_2_ABNORMAL_WORDS = "output/log/asr_abnormal_words.json"
_2_ABNORMAL_WORDS_MD = "output/log/asr_abnormal_words.md"
_2_ASR_QUALITY_REPORT = "output/log/asr_quality_report.json"
_2_ASR_QUALITY_REPORT_MD = "output/log/asr_quality_report.md"
_3_1_SPLIT_BY_NLP = "output/log/split_by_nlp.txt"
_3_2_SPLIT_BY_MEANING = "output/log/split_by_meaning.txt"
_3_2_SEGMENTATION_REPORT = "output/log/segmentation_quality_report.json"
_3_2_SEGMENTATION_REPORT_MD = "output/log/segmentation_quality_report.md"
_4_1_TERMINOLOGY = "output/log/terminology.json"
_4_2_TRANSLATION = "output/log/translation_results.xlsx"
_4_3_AMBIGUITY = "output/log/ambiguity_report.json"
_5_SPLIT_SUB = "output/log/translation_results_for_subtitles.xlsx"
_5_REMERGED = "output/log/translation_results_remerged.xlsx"

_8_1_AUDIO_TASK = "output/audio/tts_tasks.xlsx"


# ------------------------------------------
# 定义音频文件
# ------------------------------------------
_OUTPUT_DIR = "output"
_AUDIO_DIR = "output/audio"
_RAW_AUDIO_FILE = "output/audio/raw.mp3"
_VOCAL_AUDIO_FILE = "output/audio/vocal.mp3"
_BACKGROUND_AUDIO_FILE = "output/audio/background.mp3"
_AUDIO_REFERS_DIR = "output/audio/refers"
_AUDIO_SEGS_DIR = "output/audio/segs"
_AUDIO_TMP_DIR = "output/audio/tmp"

# ------------------------------------------
# 导出
# ------------------------------------------

__all__ = [
    "_2_CLEANED_CHUNKS",
    "_2_ABNORMAL_WORDS",
    "_2_ABNORMAL_WORDS_MD",
    "_2_ASR_QUALITY_REPORT",
    "_2_ASR_QUALITY_REPORT_MD",
    "_3_1_SPLIT_BY_NLP",
    "_3_2_SPLIT_BY_MEANING",
    "_3_2_SEGMENTATION_REPORT",
    "_3_2_SEGMENTATION_REPORT_MD",
    "_4_1_TERMINOLOGY",
    "_4_2_TRANSLATION",
    "_4_3_AMBIGUITY",
    "_5_SPLIT_SUB",
    "_5_REMERGED",
    "_8_1_AUDIO_TASK",
    "_OUTPUT_DIR",
    "_AUDIO_DIR",
    "_RAW_AUDIO_FILE",
    "_VOCAL_AUDIO_FILE",
    "_BACKGROUND_AUDIO_FILE",
    "_AUDIO_REFERS_DIR",
    "_AUDIO_SEGS_DIR",
    "_AUDIO_TMP_DIR"
]
