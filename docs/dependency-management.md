# Dependency management

Python 3.12 is the maintained runtime. `requirements.txt` is the cross-platform declaration used by the installer. Its PEP 508 marker installs `mlx-whisper` only on Apple Silicon macOS; Windows, Linux, and Intel macOS use the WhisperX path. PyTorch and Demucs remain installer-managed because their wheel indexes and torchaudio constraints vary by platform.

`requirements-ci.txt` is the smaller, pinned environment used by deterministic unit tests and does not install speech-model runtimes, platform GPU stacks, or model weights.

`constraints-py312.txt` records versions available in the maintained Python 3.12 development environment. Regenerate it after intentional dependency changes:

```bash
python scripts/generate_constraints.py
```

Review the diff before using the snapshot. Packages listed under “Not installed” are installed by platform-specific setup paths or were absent from the machine that produced the snapshot; the generator never downloads or upgrades packages.

The recommended installation creates a fresh Python 3.12 environment through uv:

```bash
python setup_env.py --no-launch
```

For a manually managed Python 3.12 environment, use:

```bash
python -m pip install -r requirements.txt -c constraints-py312.txt
```

The snapshot is not a universal lock for CUDA, Apple MLX, or system FFmpeg. Those platform runtimes continue to follow dedicated installer paths. Do not apply the constraints file to a different Python minor version.
