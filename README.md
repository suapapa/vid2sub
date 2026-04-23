# video2srt

YouTube URL이나 로컬 비디오 파일로부터 음성을 추출하고, 이를 분석하여 SRT 자막 파일을 생성하는 프로젝트입니다.

## 주요 기능

- **YouTube 지원**: `yt-dlp`를 사용하여 YouTube 영상에서 고음질 오디오를 추출합니다.
- **로컬 파일 지원**: MP4, MKV 등 다양한 로컬 비디오 파일에서 오디오를 추출합니다.
- **자막 생성**: 추출된 오디오를 바탕으로 시간 정보가 포함된 SRT 자막 파일을 생성합니다. (구현 중)

## 요구 사항

- Python 3.12 이상
- [FFmpeg](https://ffmpeg.org/): 오디오 추출 및 변환을 위해 시스템에 설치되어 있어야 합니다.
- `PyYAML`: 설정 파일(`config.yaml`) 로드를 위해 사용됩니다.

## 설치 방법

본 프로젝트는 `uv`를 사용하여 의존성을 관리합니다.

```bash
# 저장소 복제
git clone <repository-url>
cd video2srt

# 의존성 설치
uv sync
```

## 사용 방법

비디오에서 오디오를 추출하고 `whisper.cpp`를 사용하여 SRT 자막을 생성합니다.

```bash
# YouTube 영상에서 자막 생성
uv run main.py "https://www.youtube.com/watch?v=..." -o output.srt

# 로컬 비디오 파일에서 자막 생성
uv run main.py video.mp4 -o output.srt
```

### 상세 옵션

- `--min_len`: 무음으로 간주될 최소 길이 (기본값: 500ms)
- `--thresh`: 무음으로 간주될 데시벨 임계값 (기본값: -40dB)
- `--temp_dir`: 디버깅용 임시 디렉토리 경로 (지정 시 작업 후 삭제되지 않음)

## 라이선스

MIT License
