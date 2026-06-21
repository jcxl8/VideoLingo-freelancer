# Source layout and maintenance boundaries

VideoLingo's supported application code lives in the repository root entry
points (`st.py` and `batch/`) and the importable modules under `core/`.
Production changes should be made in those locations and covered by tests in
`tests/`.

The `core` package keeps pipeline modules lazy. Importing `core` alone must not
load individual numbered stages; both `import core._7_sub_into_vid` and the
legacy `from core import _7_sub_into_vid` form remain supported.

Files whose names end in `.bak`, `.bak.py`, `.backup.py`, `-old.py`, or
`-vibenew.py`, together with the root `work/` directory, are local experiments
or recovery copies. They are ignored by Git and are not supported source
entries. Preserve any existing copies locally until their owner explicitly
chooses to remove them; do not import from them or rely on them in tests.

Reusable formatting and persistence helpers belong in focused modules instead
of numbered pipeline stages. For example, subtitle parsing and ASS conversion
live in `core/subtitle_formats.py`, while atomic file replacement lives in
`core/utils/atomic_files.py`.
