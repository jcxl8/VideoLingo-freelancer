from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallationContractTest(unittest.TestCase):
    def test_uv_bootstrap_targets_python_312(self):
        setup_env = ROOT / "setup_env.py"
        self.assertTrue(setup_env.is_file())
        text = setup_env.read_text(encoding="utf-8")
        self.assertIn('PYTHON_VERSION = "3.12"', text)
        self.assertIn('VENV_DIR = ".venv"', text)
        self.assertIn('"uv", "venv"', text)
        self.assertIn('"--python", PYTHON_VERSION', text)
        self.assertIn('"--no-launch"', text)

    def test_installer_has_automation_safe_flags_and_interpreter_bound_launch(self):
        text = (ROOT / "install.py").read_text(encoding="utf-8")
        self.assertIn('"--no-launch"', text)
        self.assertIn('"--skip-torch"', text)
        self.assertIn(
            'subprocess.Popen([sys.executable, "-m", "streamlit", "run", "st.py"])',
            text,
        )
        self.assertIn('@except_handler("Failed to install PyTorch", retry=1, delay=5)', text)

    def test_apple_silicon_mlx_dependency_is_conditional(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn(
            'mlx-whisper==0.4.3; sys_platform == "darwin" and platform_machine == "arm64"',
            requirements,
        )
        constraints = (ROOT / "constraints-py312.txt").read_text(encoding="utf-8")
        self.assertIn("mlx-whisper==0.4.3", constraints)

    def test_package_metadata_declares_supported_python_and_packages(self):
        text = (ROOT / "setup.py").read_text(encoding="utf-8")
        self.assertIn("VideoLingo-Freelancer", text)
        self.assertIn('python_requires=">=3.12,<3.13"', text)
        self.assertIn("packages=find_packages()", text)
        self.assertIn("and not line.startswith(", text)

    def test_windows_uv_launcher_uses_project_venv(self):
        launcher = ROOT / "OneKeyStart_uv.bat"
        self.assertTrue(launcher.is_file())
        text = launcher.read_text(encoding="utf-8")
        self.assertIn(r".venv\Scripts\python.exe", text)
        self.assertIn("python setup_env.py", text)

    def test_ci_validates_installation_entrypoints(self):
        workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("install.py setup_env.py setup.py", workflow)
        self.assertIn("python setup_env.py --help", workflow)
        self.assertIn("python install.py --help", workflow)
        self.assertIn("python setup.py --name", workflow)

    def test_local_optimization_guide_uses_current_installer(self):
        guide = (ROOT / "LOCAL_OPTIMIZATION_GUIDE.md").read_text(encoding="utf-8")
        self.assertIn("python setup_env.py --no-launch", guide)
        self.assertIn("OneKeyStart_uv.bat", guide)
        self.assertIn("mlx-whisper==0.4.3", guide)


if __name__ == "__main__":
    unittest.main()
