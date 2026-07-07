import importlib.util
import subprocess
import sys
from pathlib import Path

from .logger import Logger

DEFAULT_MODEL = "htdemucs"


class VocalIsolator:
    """Separates the vocal track from background music/sound effects.

    Uses Demucs (Hybrid Transformer Demucs) in ``--two-stems=vocals`` mode so
    only clean speech is passed to the STT server. Demucs is an optional,
    heavy (PyTorch) dependency and is invoked as a subprocess, so it is only
    required when vocal isolation is actually enabled.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        device: str | None = None,
        output_mp3: bool = True,
    ):
        self.model = model or DEFAULT_MODEL
        self.device = device or None  # None -> demucs auto-detects (cuda/mps/cpu)
        self.output_mp3 = output_mp3

    @staticmethod
    def is_available() -> bool:
        return importlib.util.find_spec("demucs") is not None

    def isolate(self, audio_path: Path, out_dir: Path) -> Path:
        """Runs Demucs and returns the path to the isolated vocals file."""
        if not self.is_available():
            raise RuntimeError(
                "Vocal isolation requires 'demucs', which is not installed. "
                "Install it with: uv sync --extra separate"
            )

        sep_root = out_dir / "separated"
        ext = "mp3" if self.output_mp3 else "wav"
        cmd = [
            sys.executable,
            "-m",
            "demucs",
            "--two-stems",
            "vocals",
            "-n",
            self.model,
            "-o",
            str(sep_root),
        ]
        if self.device:
            cmd += ["-d", self.device]
        if self.output_mp3:
            cmd += ["--mp3"]
        cmd.append(str(audio_path))

        Logger.info(
            f"Isolating vocals with demucs (model={self.model}); this can take a while..."
        )
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(f"demucs failed (exit {result.returncode}):\n{stderr}")

        track = audio_path.stem
        vocals = sep_root / self.model / track / f"vocals.{ext}"
        if not vocals.is_file():
            matches = sorted(sep_root.rglob(f"vocals.{ext}")) or sorted(
                sep_root.rglob("vocals.*")
            )
            if not matches:
                raise RuntimeError(
                    f"Could not locate the isolated vocals stem under {sep_root}."
                )
            vocals = matches[0]

        Logger.success(f"Isolated vocals: {vocals}")
        return vocals
