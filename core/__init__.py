import importlib


_PIPELINE_MODULES = {
    "_1_ytdlp",
    "_2_asr",
    "_3_1_split_nlp",
    "_3_2_split_meaning",
    "_4_1_summarize",
    "_4_2_translate",
    "_5_split_sub",
    "_6_gen_sub",
    "_7_sub_into_vid",
    "_8_1_audio_task",
    "_8_2_dub_chunks",
    "_9_refer_audio",
    "_10_gen_audio",
    "_11_merge_audio",
    "_12_dub_to_vid",
    "subtitle_formats",
    "subtitle_layout",
    "job_manifest",
}
_UTILITY_EXPORTS = {
    "ask_gpt",
    "load_key",
    "update_key",
}


def __getattr__(name):
    if name in _PIPELINE_MODULES:
        value = importlib.import_module(f"{__name__}.{name}")
    elif name in _UTILITY_EXPORTS:
        value = getattr(importlib.import_module("core.utils"), name)
    elif name == "cleanup":
        value = importlib.import_module("core.utils.onekeycleanup").cleanup
    elif name == "delete_dubbing_files":
        value = importlib.import_module("core.utils.delete_retry_dubbing").delete_dubbing_files
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


__all__ = sorted(
    _PIPELINE_MODULES
    | _UTILITY_EXPORTS
    | {"cleanup", "delete_dubbing_files"}
)
