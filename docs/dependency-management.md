# Dependency management

`requirements.txt` remains the cross-platform declaration used by VideoLingo installers. `requirements-ci.txt` is the smaller, pinned environment used by deterministic unit tests and does not install speech-model runtimes or model weights.

`constraints-py312.txt` records versions available in the maintained Python 3.12 development environment. Regenerate it after intentional dependency changes:

```bash
python scripts/generate_constraints.py
```

Review the diff before using the snapshot. Packages listed under “Not installed” are installed by platform-specific setup paths or were absent from the machine that produced the snapshot; the generator never downloads or upgrades packages.

For a reproducible local installation, create a fresh Python 3.12 environment and use:

```bash
python -m pip install -r requirements.txt -c constraints-py312.txt
```

The snapshot is not a universal lock for CUDA, Apple MLX, or system FFmpeg. Those platform runtimes must continue to follow their dedicated installer paths.
