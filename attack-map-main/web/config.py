# web/config.py
import os
import sys
from pathlib import Path

# 기본 상수
HONEYPOT_LAT, HONEYPOT_LON = 37.5665, 126.9780  # 서울 허니팟 위치
DEFAULT_PORT = 2222
GREY = [150, 150, 150]

# 경로 설정
# 실행 파일의 위치를 기준으로 기본 경로를 설정합니다.
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
DEFAULT_EVENTS_PATH = BASE_DIR / "data" / "events.json"

def get_events_path():
    """환경 변수, CLI 인자, 또는 기본값 순서로 이벤트 파일 경로를 결정합니다."""
    # CLI 인자, 환경 변수, 기본값 순으로 경로를 찾습니다.
    # streamlit 앱에서는 argparse를 직접 사용하기 어려우므로, os.getenv로 주로 처리합니다.
    path_str = os.getenv("ATTACKMAP_EVENTS", str(DEFAULT_EVENTS_PATH))
    return Path(path_str).expanduser().resolve()

def ensure_events_file_exists(p: Path):
    """이벤트 파일 및 상위 디렉토리가 없으면 생성합니다."""
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists() or p.stat().st_size == 0:
        p.write_text("[]", encoding="utf-8")

# LLM 설정
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://127.0.0.1:1234")
LLM_MODEL = os.getenv("LLM_MODEL", "meta-llama-3.1-8b-instruct")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", LLM_MODEL) # Ollama 모델은 별도로 지정 가능