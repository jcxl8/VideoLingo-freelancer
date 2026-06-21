import ast
from numbers import Real


def _location(row):
    return f" at row {row}" if row is not None else ""


def parse_list_cell(value, *, field, row=None):
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(
                f"{field}{_location(row)} contains an invalid literal"
            ) from exc
    else:
        parsed = value
    if not isinstance(parsed, list):
        raise ValueError(f"{field}{_location(row)} must be a list")
    return parsed


def parse_time_ranges_cell(value, *, field="new_sub_times", row=None):
    ranges = parse_list_cell(value, field=field, row=row)
    normalized = []
    for index, item in enumerate(ranges):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(
                f"{field}{_location(row)} item {index} must contain start and end"
            )
        start, end = item
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, Real)
            or not isinstance(end, Real)
        ):
            raise ValueError(
                f"{field}{_location(row)} item {index} must contain numbers"
            )
        if end < start:
            raise ValueError(
                f"{field}{_location(row)} item {index} ends before it starts"
            )
        normalized.append([float(start), float(end)])
    return normalized
