from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    def intersects(self, other):
        return not (
            self.right <= other.left
            or self.left >= other.right
            or self.bottom <= other.top
            or self.top >= other.bottom
        )

    def move_y(self, delta):
        return Box(self.left, self.top + delta, self.right, self.bottom + delta)


@dataclass(frozen=True)
class PortraitMetrics:
    width: int
    height: int
    source_font_size: int
    translation_font_size: int
    hardsub_translation_font_size: int
    watermark_font_size: int
    side_margin: int
    safe_vertical_margin: int
    subtitle_gap: int
    watermark_gap: int


@dataclass(frozen=True)
class PortraitLayout:
    source: Box | None
    translation: Box
    watermark: Box | None
    translation_alignment: int
    placement: str


def _clamp(value, minimum, maximum):
    if maximum < minimum:
        return minimum
    return max(minimum, min(maximum, value))


def _line_height(font_size, ratio=1.24):
    return max(1, int(round(font_size * ratio)))


def _full_width_box(metrics, top, height):
    return Box(
        metrics.side_margin,
        int(top),
        metrics.width - metrics.side_margin,
        int(top + height),
    )


def _watermark_box(metrics, top):
    width = max(metrics.watermark_font_size * 9, metrics.width // 3)
    left = max(metrics.side_margin, (metrics.width - width) // 2)
    right = min(metrics.width - metrics.side_margin, left + width)
    return Box(left, int(top), right, int(top + metrics.watermark_font_size))


def _place_watermark_around_block(metrics, block_top, block_bottom, offset):
    safe_top = metrics.safe_vertical_margin
    safe_bottom = metrics.height - metrics.safe_vertical_margin
    height = metrics.watermark_font_size
    above_max = block_top - metrics.watermark_gap - height
    if above_max >= safe_top:
        top = _clamp(above_max - offset, safe_top, above_max)
        return _watermark_box(metrics, top)
    below_min = block_bottom + metrics.watermark_gap
    top = _clamp(below_min - offset, below_min, safe_bottom - height)
    return _watermark_box(metrics, top)


def layout_bilingual(
    metrics,
    source_lines,
    translation_lines,
    mode,
    bilingual_offset,
    watermark_offset,
):
    source_height = max(1, source_lines) * _line_height(metrics.source_font_size, 1.28)
    translation_height = max(1, translation_lines) * _line_height(metrics.translation_font_size)
    block_height = source_height + metrics.subtitle_gap + translation_height
    safe_top = metrics.safe_vertical_margin
    safe_bottom = metrics.height - metrics.safe_vertical_margin
    default_bottom = int(round(metrics.height * 0.78))
    block_top = default_bottom - block_height - int(bilingual_offset)
    block_top = _clamp(block_top, safe_top, safe_bottom - block_height)

    translation_first = mode in ("bilingual_trans_top", "single_bilingual_trans_top")
    if translation_first:
        translation = _full_width_box(metrics, block_top, translation_height)
        source = _full_width_box(
            metrics,
            translation.bottom + metrics.subtitle_gap,
            source_height,
        )
    else:
        source = _full_width_box(metrics, block_top, source_height)
        translation = _full_width_box(
            metrics,
            source.bottom + metrics.subtitle_gap,
            translation_height,
        )
    watermark = _place_watermark_around_block(
        metrics,
        min(source.top, translation.top),
        max(source.bottom, translation.bottom),
        int(watermark_offset),
    )
    return PortraitLayout(source, translation, watermark, 2, "bilingual")


def _layout_hardsub_below(metrics, hard_box, translation_height, translation_offset, watermark_offset):
    safe_bottom = metrics.height - metrics.safe_vertical_margin
    group_top = hard_box.bottom + metrics.subtitle_gap
    watermark = _watermark_box(metrics, group_top)
    translation_top = watermark.bottom + metrics.watermark_gap - int(translation_offset)
    translation_top = max(translation_top, watermark.bottom + metrics.watermark_gap)
    translation = _full_width_box(metrics, translation_top, translation_height)
    if translation.bottom > safe_bottom:
        return None

    watermark_top = watermark.top - int(watermark_offset)
    minimum_below = hard_box.bottom + metrics.subtitle_gap
    maximum_below = translation.top - metrics.watermark_gap - metrics.watermark_font_size
    if watermark_top < minimum_below:
        above_hard = hard_box.top - metrics.subtitle_gap - metrics.watermark_font_size
        watermark_top = above_hard if above_hard >= metrics.safe_vertical_margin else minimum_below
    else:
        watermark_top = _clamp(watermark_top, minimum_below, maximum_below)
    watermark = _watermark_box(metrics, watermark_top)
    return PortraitLayout(None, translation, watermark, 8, "below")


def _layout_hardsub_above(metrics, hard_box, translation_height, translation_offset, watermark_offset):
    safe_top = metrics.safe_vertical_margin
    watermark_bottom = hard_box.top - metrics.subtitle_gap
    watermark_top = watermark_bottom - metrics.watermark_font_size - int(watermark_offset)
    translation_bottom = watermark_top - metrics.watermark_gap - int(translation_offset)
    translation_top = translation_bottom - translation_height
    if translation_top < safe_top:
        required = safe_top - translation_top
        translation_top += required
        translation_bottom += required
        watermark_top += required
        watermark_bottom += required
    if watermark_bottom > hard_box.top - metrics.subtitle_gap:
        shift = watermark_bottom - (hard_box.top - metrics.subtitle_gap)
        translation_top -= shift
        translation_bottom -= shift
        watermark_top -= shift
        watermark_bottom -= shift
    translation = _full_width_box(metrics, translation_top, translation_height)
    watermark = _watermark_box(metrics, watermark_top)
    if translation.top < safe_top:
        # The safe interval is smaller than the configured block. Keep it in-frame;
        # the caller can surface a warning and choose a smaller configured size.
        translation = _full_width_box(metrics, safe_top, translation_height)
        watermark = _watermark_box(metrics, translation.bottom + metrics.watermark_gap)
    return PortraitLayout(None, translation, watermark, 2, "above")


def layout_hardsub(
    metrics,
    hard_box,
    translation_lines,
    translation_offset,
    watermark_offset,
    prefer=None,
):
    """Compute portrait hard-sub avoiding layout.

    prefer:
      - None / "auto": smart placement. If the detected hard subtitle is very
        close to the bottom edge, try the translation above it first; otherwise
        try below to preserve the legacy layout when the lower group still fits.
      - "above": try above first.
      - "below": try below first.
    """
    translation_height = max(1, translation_lines) * _line_height(
        metrics.hardsub_translation_font_size
    )
    if prefer is None or prefer == "auto":
        first = "above" if hard_box.bottom >= int(metrics.height * 0.8) else "below"
    else:
        first = prefer

    if first == "above":
        above = _layout_hardsub_above(
            metrics,
            hard_box,
            translation_height,
            translation_offset,
            watermark_offset,
        )
        if above is not None:
            return above
        return _layout_hardsub_below(
            metrics,
            hard_box,
            translation_height,
            translation_offset,
            watermark_offset,
        )

    below = _layout_hardsub_below(
        metrics,
        hard_box,
        translation_height,
        translation_offset,
        watermark_offset,
    )
    if below is not None:
        return below
    return _layout_hardsub_above(
        metrics,
        hard_box,
        translation_height,
        translation_offset,
        watermark_offset,
    )
