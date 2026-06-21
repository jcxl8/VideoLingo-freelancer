import os
import json
import tempfile
import hashlib
from contextlib import contextmanager
from threading import Lock
import json_repair
from rich import print as rprint
from core.utils.decorator import except_handler
from core.utils.model_router import router

try:
    import fcntl
except ImportError:
    fcntl = None

# ------------
# cache gpt response
# ------------

LOCK = Lock()
GPT_LOG_FOLDER = 'output/gpt_log'
GPT_CACHE_FOLDER = 'output/gpt_cache'

@contextmanager
def _cache_file_lock(file):
    """Serialize cache access across threads and processes on macOS/Linux."""
    lock_file = f"{file}.lock"
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with LOCK:
        with open(lock_file, "a+", encoding="utf-8") as lock_handle:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

def _save_cache(model, prompt, resp_content, resp_type, resp, message=None, log_title="default", api_role="workflow"):
    record = {
        "api_role": api_role,
        "model": model,
        "prompt": prompt,
        "resp_content": resp_content,
        "resp_type": resp_type,
        "resp": resp,
        "message": message,
    }
    cache_file = _cache_path(prompt, resp_type, log_title, api_role)
    with _cache_file_lock(cache_file):
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        fd, tmp_file = tempfile.mkstemp(
            prefix=f".{os.path.basename(cache_file)}.",
            suffix=".tmp",
            dir=os.path.dirname(cache_file),
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False)
            os.replace(tmp_file, cache_file)
        finally:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)

    log_file = os.path.join(GPT_LOG_FOLDER, f"{log_title}.jsonl")
    with _cache_file_lock(log_file):
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

def _load_cache(prompt, resp_type, log_title, api_role="workflow"):
    cache_file = _cache_path(prompt, resp_type, log_title, api_role)
    with _cache_file_lock(cache_file):
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    item = json.load(f)
                return item["resp"]
            except Exception:
                pass

    legacy_file = os.path.join(GPT_LOG_FOLDER, f"{log_title}.json")
    with _cache_file_lock(legacy_file):
        if os.path.exists(legacy_file):
            try:
                with open(legacy_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except Exception:
                logs = []
            for item in logs:
                if isinstance(item, dict):
                    if item.get("prompt") == prompt and item.get("resp_type") == resp_type and item.get("api_role", "workflow") == api_role:
                        return item["resp"]
        return False

def _cache_path(prompt, resp_type, log_title, api_role):
    payload = json.dumps(
        {
            "api_role": api_role,
            "log_title": log_title,
            "resp_type": resp_type,
            "prompt": prompt,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return os.path.join(GPT_CACHE_FOLDER, api_role, log_title, f"{digest}.json")

def list_available_models(api_role="workflow"):
    return router.list_available_models(api_role)

# ------------
# ask gpt once
# ------------

@except_handler("GPT request failed", retry=5)
def ask_gpt(prompt, resp_type=None, valid_def=None, log_title="default", api_role="workflow"):
    # check cache
    cached = _load_cache(prompt, resp_type, log_title, api_role=api_role)
    if cached:
        rprint("use cache response")
        return cached

    messages = [{"role": "user", "content": prompt}]
    resp_raw, api_config = router.chat_completion(messages, resp_type=resp_type, api_role=api_role)
    model = api_config.model

    # process and return full result
    resp_content = resp_raw.choices[0].message.content
    if resp_type == "json":
        resp = json_repair.loads(resp_content)
    else:
        resp = resp_content
    
    # check if the response format is valid
    if valid_def:
        valid_resp = valid_def(resp)
        if valid_resp['status'] != 'success':
            _save_cache(model, prompt, resp_content, resp_type, resp, log_title="error", message=valid_resp['message'], api_role=api_role)
            raise ValueError(f"❎ API response error: {valid_resp['message']}")

    _save_cache(model, prompt, resp_content, resp_type, resp, log_title=log_title, api_role=api_role)
    return resp


if __name__ == '__main__':
    from rich import print as rprint
    
    result = ask_gpt("""test respond ```json\n{\"code\": 200, \"message\": \"success\"}\n```""", resp_type="json")
    rprint(f"Test json output result: {result}")
