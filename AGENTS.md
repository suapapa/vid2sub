# AGENTS.md

이 파일은 **video2srt** 프로젝트를 개발하는 AI 에이전트들을 위한 가이드라인 및 진행 상황을 기록하는 문서입니다.

## 에이전트 행동 지침

1. **문서 동기화**: 새로운 기능(예: STT 통합, SRT 포맷팅 등)을 구현할 때마다 `README.md`의 기능 목록과 사용 방법을 최신 정보로 업데이트하십시오.
2. **진행 상황 업데이트**: 본 문서의 [개발 로드맵](#개발-로드맵) 섹션에서 완료된 항목의 상태를 변경하십시오.
3. **일관성 유지**: 기존의 코드 스타일과 의존성 관리 방식(`uv`)을 존중하여 구현하십시오.

## 개발 로드맵

| 기능 | 상태 | 비고 |
| :--- | :---: | :--- |
| 프로젝트 구조 설정 및 의존성 정의 | ✅ 완료 | `pyproject.toml`, `uv` 사용 |
| YouTube URL 기반 음성 추출 | ✅ 완료 | `yt-dlp` → MP3 |
| 로컬 비디오 파일 기반 음성 추출 | ✅ 완료 | `moviepy` → MP3 |
| STT(Speech-to-Text) 연동 | ✅ 완료 | `whisper-server --convert` + `config.yaml`의 `server_url`에 `POST …/inference` (multipart, `requests`). 클라이언트는 MP3만 업로드 |
| SRT 출력 | ✅ 완료 | 서버 응답(`response_format=srt`)을 그대로 저장 |
| 설정 파일(`config.yaml`) 연동 | ✅ 완료 | `server_url`, `default_language` (`pyyaml`) |
| Gemini 기반 SRT 퇴고(`--polish_with`, `GEMINI_API_KEY`) | ✅ 완료 | `google-genai`, 레퍼런스는 로컬 파일 또는 URL |

## 기술 스택 관련 참고 사항

- **FFmpeg**: `moviepy` / `yt-dlp` 후처리에서 사용됩니다. 시스템에 설치되어 있어야 합니다.
- **STT**: 로컬 `whisper-cli` 바이너리가 아니라, **`whisper-server --convert`**로 띄운 HTTP 서버를 가정합니다. 엔드포인트는 `{server_url}/inference`이며, 본문은 `file`, `response_format=srt`, `language` 필드를 사용합니다. 오디오 포맷 변환은 클라이언트가 하지 않습니다.
- **언어**: CLI `--lang`이 없으면 `whisper_cpp.default_language`를 사용합니다.
