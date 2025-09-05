# web/ui_components.py
import time
import streamlit as st
import pandas as pd
from pathlib import Path

from config import get_events_path, ensure_events_file_exists

def setup_page(title_emoji: str, title_text: str):
    """페이지 기본 설정 및 전역 CSS를 적용합니다."""
    st.set_page_config(
        page_title=f"{title_text} — Attack Live Map",
        layout="wide",
        page_icon=title_emoji,
    )
    # 전역 CSS (다크모드, 카드 스타일 등)
    st.markdown("""
        <style>
        /* 기본 폰트 및 배경 설정 */
        body { font-family: 'sans-serif'; background-color: #0e1117; color: #fafafa; }
        
        /* 메트릭 카드 스타일 */
        .metric-card { background-color: #1c1f26; padding: 16px; border-radius: 12px; text-align: center; box-shadow: 0 0 6px rgba(0,0,0,0.5); }
        .metric-card h3 { margin: 0; color: #aaa; font-size: 14px; font-weight: 400; }
        .metric-card p { margin: 0; font-size: 24px; font-weight: bold; color: #00d084; }

        /* 푸터 스타일 */
        .footer { text-align: center; color: #888; font-size: 12px; margin-top: 40px; padding-bottom: 20px; }
        </style>
    """, unsafe_allow_html=True)
    st.title(f"{title_emoji} {title_text}")

def display_sidebar():
    """공통 사이드바 UI를 렌더링하고 사용자의 선택값을 반환합니다."""
    sb = st.sidebar
    sb.header("⚙️ 데이터 소스")

    events_path_str = str(get_events_path())
    path_input = sb.text_input("이벤트 파일 경로", value=events_path_str)
    events_path = Path(path_input).expanduser().resolve()
    ensure_events_file_exists(events_path)

    if sb.button("♻️ 데이터 캐시 비우기"):
        st.cache_data.clear()
        st.toast("캐시가 초기화되었습니다.", icon="✅")
    
    sb.markdown("---")
    return events_path

def display_metrics(df: pd.DataFrame):
    """상단에 위치한 4개의 핵심 지표 카드를 표시합니다."""
    c1, c2, c3, c4 = st.columns(4)
    metric_template = '<div class="metric-card"><h3>{}</h3><p>{}</p></div>'
    
    with c1:
        st.markdown(metric_template.format("총 이벤트 수", len(df)), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_template.format("고유 공격 IP", df['src_ip'].nunique() if not df.empty else 0), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_template.format("공격 발생 국가 수", df['country_code'].nunique() if not df.empty else 0), unsafe_allow_html=True)
    with c4:
        st.markdown(metric_template.format("마지막 갱신", time.strftime('%H:%M:%S')), unsafe_allow_html=True)
    
    st.markdown("---")

def display_footer():
    """페이지 하단 공통 푸터를 표시합니다."""
    st.markdown("""
        <div class="footer">
        Attack Live Map • Inspired by Shodan.io <br>
        Built with using Streamlit, Pydeck & Altair
        </div>
    """, unsafe_allow_html=True)