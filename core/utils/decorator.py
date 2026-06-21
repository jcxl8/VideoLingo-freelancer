import functools
import os
import time

from rich import print as rprint


def except_handler(error_msg, retry=0, delay=1, default_return=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            total_attempts = retry + 1
            for attempt in range(total_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exception = exc
                    rprint(
                        f"[red]{error_msg}: {exc}, "
                        f"retry: {attempt + 1}/{total_attempts}[/red]"
                    )
                    if attempt == retry:
                        if default_return is not None:
                            return default_return
                        raise last_exception
                    time.sleep(delay * (2**attempt))

        return wrapper

    return decorator

def check_file_exists(file_path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if os.path.exists(file_path):
                rprint(
                    f"[yellow]⚠️ File <{file_path}> already exists, "
                    f"skip <{func.__name__}> step.[/yellow]"
                )
                return None
            return func(*args, **kwargs)

        return wrapper

    return decorator
