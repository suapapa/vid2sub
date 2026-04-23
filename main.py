import argparse
import os
import tempfile
import yaml
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

import yt_dlp
from moviepy import VideoFileClip
from pydub import AudioSegment
from pydub.silence import split_on_silence
from tqdm import tqdm

class SubtitleGenerator:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.whisper_bin = self.config.get("whisper_cpp", {}).get("bin_path")
        self.whisper_model = self.config.get("whisper_cpp", {}).get("model_path")
        
        if not self.whisper_bin or not self.whisper_model:
            raise ValueError("whisper_cpp 설정(bin_path, model_path)이 올바르지 않습니다.")

    def _load_config(self, path: str) -> dict:
        if not Path(path).exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            try:
                return yaml.safe_load(f) or {}
            except yaml.YAMLError:
                return {}

    def extract_audio(self, source: str, temp_dir: Path) -> Path:
        """YouTube URL 또는 로컬 파일에서 오디오를 추출합니다."""
        if source.startswith(("http://", "https://", "www.", "youtu.be")):
            return self._download_youtube(source, temp_dir)
        return self._extract_from_file(Path(source), temp_dir)

    def _download_youtube(self, url: str, temp_dir: Path) -> Path:
        print(f"[*] Downloading YouTube audio: {url}")
        output_path = temp_dir / "raw_audio.mp3"
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(temp_dir / 'raw_audio.%(ext)s'),
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'no_cache_dir': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
        return output_path

    def _extract_from_file(self, file_path: Path, temp_dir: Path) -> Path:
        print(f"[*] Extracting audio from local file: {file_path}")
        if not file_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        output_path = temp_dir / "raw_audio.mp3"
        video = VideoFileClip(str(file_path))
        if not video.audio:
            raise ValueError("비디오에 오디오 트랙이 없습니다.")
        
        video.audio.write_audiofile(str(output_path), logger=None)
        video.close()
        return output_path

    def prepare_wav(self, input_path: Path, output_path: Path) -> AudioSegment:
        """whisper.cpp 호환 형식(16kHz, mono)으로 변환합니다."""
        print(f"[*] Converting to 16kHz WAV...")
        audio = AudioSegment.from_file(str(input_path))
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(str(output_path), format="wav")
        return audio

    def transcribe(self, chunk_path: Path) -> str:
        """whisper.cpp를 사용하여 단일 청크를 텍스트로 변환합니다."""
        output_base = chunk_path.with_suffix('')
        cmd = [
            self.whisper_bin, "-m", self.whisper_model,
            "-f", str(chunk_path), "-l", "ko", "-nt", "-otxt", "-of", str(output_base)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            txt_path = output_base.with_suffix('.txt')
            if txt_path.exists():
                with open(txt_path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                return text
        except subprocess.CalledProcessError as e:
            print(f"[!] Whisper Error: {e.stderr}")
        return ""

    def process(self, source: str, output_path: str, silence_thresh: int, min_silence_len: int, temp_dir: Optional[str] = None):
        """전체 자막 생성 프로세스를 실행합니다."""
        out_p = Path(output_path)
        if out_p.exists():
            out_p.unlink()

        if temp_dir:
            temp_path = Path(temp_dir)
            temp_path.mkdir(parents=True, exist_ok=True)
            self._run_process(source, output_path, silence_thresh, min_silence_len, temp_path)
        else:
            with tempfile.TemporaryDirectory() as td:
                self._run_process(source, output_path, silence_thresh, min_silence_len, Path(td))

    def _run_process(self, source: str, output_path: str, silence_thresh: int, min_silence_len: int, temp_path: Path):
        # 1. 추출
        raw_audio = self.extract_audio(source, temp_path)
        
        # 2. WAV 변환
        wav_path = temp_path / "processed.wav"
        audio = self.prepare_wav(raw_audio, wav_path)
        
        # 3. 분할
        print(f"[*] Splitting audio (thresh: {silence_thresh}dB, min_len: {min_silence_len}ms)...")
        chunks = split_on_silence(
            audio, min_silence_len=min_silence_len, 
            silence_thresh=silence_thresh, keep_silence=200
        )
        
        # 4. 변환 및 타임라인 생성
        print(f"[*] Transcribing {len(chunks)} chunks...")
        current_ms = 0
        results = []
        
        for i, chunk in tqdm(enumerate(chunks), total=len(chunks)):
            chunk_file = temp_path / f"chunk_{i}.wav"
            chunk.export(str(chunk_file), format="wav")
            
            text = self.transcribe(chunk_file)
            
            # 환각 필터링
            if self._is_hallucination(text):
                text = ""

            if text:
                start, end = current_ms, current_ms + len(chunk)
                results.append((start, end, text))
            
            current_ms += len(chunk) + (min_silence_len / 2)

        # 5. SRT 저장
        self._save_srt(results, output_path)

    def _is_hallucination(self, text: str) -> bool:
        if not text: return True
        keywords = ["뉴스 스토리", "MBC 뉴스", "시청해 주셔서", "구독과 좋아요"]
        if any(kw in text for kw in keywords) and len(text) < 30:
            # 주요 키워드가 포함되지 않은 경우만 환각으로 간주
            return not any(k in text for k in ["AMD", "BC250", "모듈", "개조"])
        return False

    def _save_srt(self, data: List[Tuple[int, int, str]], path: str):
        print(f"[*] Saving SRT: {path}")
        with open(path, "w", encoding="utf-8") as f:
            for i, (start, end, text) in enumerate(data, 1):
                f.write(f"{i}\n{self._format_time(start)} --> {self._format_time(end)}\n{text}\n\n")

    def _format_time(self, ms: int) -> str:
        s, ms_part = divmod(int(ms), 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms_part:03d}"

def main():
    parser = argparse.ArgumentParser(description="video2srt - Advanced Subtitle Generator")
    parser.add_argument("input", help="YouTube URL or Local Video Path")
    parser.add_argument("-o", "--output", required=True, help="Output SRT Path")
    parser.add_argument("--thresh", type=int, default=-40, help="Silence threshold (dB)")
    parser.add_argument("--min_len", type=int, default=500, help="Min silence length (ms)")
    parser.add_argument("--temp_dir", help="Explicit temporary directory (for debugging)")
    
    args = parser.parse_args()
    
    try:
        gen = SubtitleGenerator()
        gen.process(args.input, args.output, args.thresh, args.min_len, args.temp_dir)
        print("[+] Done!")
    except Exception as e:
        print(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
