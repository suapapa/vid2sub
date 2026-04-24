# video2srt

YouTube URL이나 로컬 비디오에서 음성을 추출한 뒤, **[whisper.cpp](https://github.com/ggml-org/whisper.cpp)**의 **`whisper-server`**로 띄운 HTTP 엔드포인트에 전체 오디오를 보내 받은 SRT를 저장하는 CLI입니다. 오디오를 무음 단위로 나누지 않고 한 번에 전송합니다.

## 주요 기능

- **YouTube**: `yt-dlp`로 베스트 오디오를 받아 MP3로 추출합니다.
- **로컬 비디오**: `moviepy`로 오디오 트랙을 MP3로 추출합니다.
- **업로드**: 추출한 MP3를 그대로 `/inference`로 보냅니다. 포맷 변환은 **서버 쪽**(`whisper-server --convert`)에서 처리합니다.
- **자막**: 서버가 반환하는 SRT 본문을 출력 파일에 그대로 씁니다.
- **퇴고(선택)**: `--polish_with`로 프로젝트 레퍼런스(로컬 파일 또는 URL)를 주면, 생성된 SRT의 오역·오탈자를 손봅니다. 기본적으로 `llama-server`(OpenAI 호환)를 사용하며, `--use_gemini` 플래그 사용 시 **Google Gemini**를 사용합니다.
- **번역(선택)**: `--translate_to en,pl`처럼 쉼표로 구분된 언어 코드를 주면, **최종 SRT**를 번역해 추가 저장합니다. 마찬가지로 기본은 `llama-server`, 선택 시 Gemini를 사용합니다.

## 요구 사항

- Python 3.12 이상
- [FFmpeg](https://ffmpeg.org/): `moviepy` / `yt-dlp` 오디오 처리에 필요합니다.
- **whisper-server (`--convert`)**: [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) 저장소의 빌드·실행 안내에 따라 **`whisper-server`**를 띄울 때 반드시 **`--convert`** 플래그를 켜 두세요. 클라이언트는 MP3 등 그대로 올리고, 서버가 업로드 오디오를 인식에 맞게 변환합니다. 모델 경로 등 나머지 옵션은 upstream 문서를 따릅니다. 이 프로젝트는 해당 서버의 **`/inference`** multipart API에 맞춰 동작합니다.
- **네트워크**: `config.yaml`의 `whisper_cpp.server_url`에서 클라이언트가 서버에 도달할 수 있어야 합니다.
- **LLM 서버 (퇴고·번역)**: 퇴고/번역 기능을 위해 기본적으로 OpenAI 호환 API를 제공하는 **llama-server**가 필요합니다. `config.yaml`의 `llamma_cpp.server_url`을 설정하세요. `--use_gemini`를 사용하는 경우 Google Gemini API 접근이 가능해야 합니다.

## STT 서버(whisper-server)

인식은 모두 서버에서 이루어집니다. 로컬이든 원격이든, [whisper.cpp](https://github.com/ggml-org/whisper.cpp)를 클론·빌드한 뒤 **`whisper-server`를 `--convert`와 함께** 실행해 HTTP 서비스를 올려 두세요. `--convert`가 없으면 업로드된 MP3 등이 서버에서 기대하는 WAV/샘플레이트로 바뀌지 않아 인식이 실패할 수 있습니다.

빌드 산출물 경로·모델 파일명은 환경마다 다르므로, 저장소 README의 `whisper-server` 예시에 **`--convert`만 반드시 포함**시키면 됩니다. 예시 형태는 다음과 같습니다(모델·포트는 본인 환경에 맞게 바꿉니다).

```bash
# whisper.cpp 빌드 디렉터리에서 (예시)
./build/bin/whisper-server -m models/ggml-base.en.bin --host 0.0.0.0 --port 8080 --convert
```

`server_url`에는 그 서버의 베이스 URL(스킴·호스트·포트)만 넣으면 되고, 클라이언트는 `{server_url}/inference`로 요청합니다.

## 설정

`config.yaml`(또는 복사본)에 다음을 둡니다. 예시는 `config_sample.yaml`을 참고하세요.

```yaml
whisper_cpp:
  server_url: "http://호스트:포트"   # 끝 슬래시 없이; 실제 요청은 …/inference
  default_language: "auto"          # 예: ko, en. CLI --lang 으로 덮어쓸 수 있음

llamma_cpp:
  server_url: "http://호스트:포트"   # OpenAI 호환 API 서버 (llama-server 등)
```

서버 측은 대략 다음과 같은 multipart 요청을 받는 형태를 가정합니다.

- `file`: 오디오 파일
- `response_format`: `srt`
- `language`: 인식 언어(또는 서버가 허용하는 값)

## 설치

```bash
git clone <repository-url>
cd video2srt
uv sync
```

## 사용법

```bash
# YouTube → SRT (MP3 업로드; 서버는 whisper-server --convert 로 띄워 둔 상태여야 함)
uv run main.py "https://www.youtube.com/watch?v=..." -o output.srt

# 로컬 파일 → SRT
uv run main.py video.mp4 -o output.srt

# 언어 오버라이드
uv run main.py video.mp4 -o output.srt --lang ko

# 디버깅: 임시 파일 유지
uv run main.py video.mp4 -o output.srt --temp_dir ./tmp_work

# 레퍼런스 문서를 참고해 SRT 퇴고 (기본적으로 config.yaml의 llama-server 사용)
uv run main.py video.mp4 -o output.srt --polish_with ./README.md

# Gemini를 사용하여 퇴고 및 번역
export GEMINI_API_KEY=...
uv run main.py video.mp4 -o output.srt --use_gemini --polish_with ./README.md
uv run main.py video.mp4 -o out.srt --use_gemini --translate_to en,pl
```

### CLI 옵션

| 옵션 | 설명 |
| :--- | :--- |
| `-o`, `--output` | 출력 SRT 경로 (필수) |
| `--lang` | 언어 코드. 생략 시 `whisper_cpp.default_language` |
| `--temp_dir` | 임시 디렉터리를 고정하면 작업 후에도 삭제하지 않음 |
| `--use_gemini` | Gemini API를 사용하여 퇴고/번역을 수행 (`GEMINI_API_KEY` 필요) |
| `--polish_with` | 레퍼런스 경로 또는 `http(s)` URL. STT 결과를 퇴고해 `-o` 파일을 덮어씀. (`--use_gemini` 미지정 시 llama-server 사용) |
| `--translate_to` | 쉼표 구분 언어 코드(예: `en,pl`). `stem_<코드>.srt`로 번역본 저장. (`--use_gemini` 미지정 시 llama-server 사용) |

## 의존성 요약

`pyproject.toml` 기준: `requests`, `yt-dlp`, `moviepy`, `pyyaml`, `google-genai` 등. 자세한 버전은 저장소의 lock/메타데이터를 참고하세요.

## 라이선스

MIT License
