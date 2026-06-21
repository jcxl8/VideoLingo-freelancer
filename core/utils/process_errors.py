import re


PROBABLE_API_TOKEN_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")


def _redact(text, secret_values):
    redacted = str(text or "")
    for secret in secret_values or ():
        if secret:
            redacted = redacted.replace(str(secret), "[REDACTED]")
    return PROBABLE_API_TOKEN_RE.sub("[REDACTED]", redacted)


def format_process_error(
    stage,
    returncode,
    stderr,
    *,
    secret_values=(),
    maximum_length=2000,
):
    base = f"{stage} failed with exit code {returncode}."
    detail = _redact(stderr, secret_values).strip()
    if not detail:
        return base[:maximum_length]
    message = f"{base} {detail}"
    if len(message) <= maximum_length:
        return message
    if maximum_length <= 1:
        return message[:maximum_length]
    return message[: maximum_length - 1].rstrip() + "…"
