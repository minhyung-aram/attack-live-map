# web/1_실시간_공격_맵.py
import streamlit as st
import pandas as pd
import pydeck as pdk
import altair as alt
import time
from pathlib import Path
from datetime import datetime

now = datetime.now()
# 분을 10 단위로 내림
rounded_minute = (now.minute // 10) * 10
rounded_time = now.replace(minute=rounded_minute, second=0, microsecond=0)
# 보기 좋은 형식으로 출력
time_str = rounded_time.strftime("%Y-%m-%d %H:%M")

# 공용 모듈 및 함수 import
from sync_daemon import start_sync_daemon
from data_handler import load_events
from ui_components import setup_page, display_sidebar, display_metrics, display_footer
from utils import interp
from config import DEFAULT_PORT, HONEYPOT_LAT, HONEYPOT_LON

# 페이지 전용 UI 함수 정의

def display_attack_map(map_placeholder, df: pd.DataFrame, settings: dict):
    """지정된 placeholder에 Pydeck 맵을 그립니다."""
    with map_placeholder.container():
        st.subheader("🗺️ 실시간 공격 맵")
    
        
        view_state = pdk.ViewState(
            latitude=HONEYPOT_LAT, longitude=HONEYPOT_LON,
            zoom=settings.get('zoom_init', 2.0)
        )
        
        if df.empty:
            st.info(f"표시할 이벤트가 없습니다. (포트 {DEFAULT_PORT}/tcp 기준)")
            deck = pdk.Deck(layers=[], initial_view_state=view_state, map_style="dark")
            st.pydeck_chart(deck, use_container_width=True)
            return

        view_state.latitude = df["dst_lat"].iloc[0]
        view_state.longitude = df["dst_lon"].iloc[0]

        layers = []
        if settings.get('show_arcs', True):
            layers.append(pdk.Layer(
                "ArcLayer", data=df,
                get_source_position=["lon", "lat"], get_target_position=["dst_lon", "dst_lat"],
                get_source_color=[255, 77, 77], get_target_color=[0, 200, 200],
                get_width=2, pickable=True, auto_highlight=True,
            ))

        tooltip = {
            "html": "<b>Time:</b> {ts}<br><b>IP:</b> {src_ip}<br><b>Country:</b> {country_code}<br><b>Label:</b> {label}<br>",
            "style": {"backgroundColor": "white", "color": "black"},
        }
        
        deck_placeholder = st.empty()

        if settings.get('enable_anim', True):
            t = 0
            duration_ms = settings.get('duration_ms', 2000)
            sleep_s = settings.get('sleep_s', 0.06)
            frame_step = settings.get('frame_step', 50)

            while t <= duration_ms:
                alpha = t / duration_ms
                planes_data = [{
                    "pos": interp(r["lon"], r["lat"], r["dst_lon"], r["dst_lat"], alpha),
                    **r[['src_ip', 'label', 'ts', 'country_code']].to_dict()
                } for _, r in df.iterrows()]
                
                scatterplot_layer = pdk.Layer(
                    "ScatterplotLayer", data=planes_data,
                    get_position="pos", get_fill_color=[255, 200, 0],
                    get_radius=30000, stroked=False, opacity=0.95,
                )
                
                deck = pdk.Deck(layers=layers + [scatterplot_layer], initial_view_state=view_state, tooltip=tooltip, map_style="dark")
                deck_placeholder.pydeck_chart(deck, use_container_width=True)
                
                time.sleep(float(sleep_s))
                t += int(frame_step)
        else:
            deck = pdk.Deck(layers=layers, initial_view_state=view_state, tooltip=tooltip, map_style="dark")
            deck_placeholder.pydeck_chart(deck, use_container_width=True)

def display_dashboard(df: pd.DataFrame):
    """하단 분석 대시보드 (국가 랭킹, 최근 이벤트, 공격 유형)를 표시합니다."""
    st.markdown("---")
    st.header("📊 분석 대시보드")
    

    
    st.subheader("🌍 공격 국가 랭킹 (Top 10)")
    if not df.empty:
        st.markdown(
            '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/flag-icon-css/6.6.6/css/flag-icons.min.css">',
            unsafe_allow_html=True
        )
        top_countries = df["country_code"].value_counts().head(10)
        max_count = top_countries.max() if not top_countries.empty else 1
        colors = ["#5778a4", "#e49444", "#d1615d", "#85b6b2", "#6a9f58", "#e7ca60", "#a87c9f", "#967662", "#b8b0ac", "#5f9e6e"]
        
        chart_html = '<div style="font-family: sans-serif; font-size: 14px; color: #fafafa;">'
        for i, (country_code, count) in enumerate(top_countries.items()):
            bar_width = (count / max_count) * 100
            flag_html = f'<span class="fi fi-{country_code.lower()}"></span>' if len(country_code) == 2 else "🏳️"
            bar_color = colors[i % len(colors)]
            chart_html += (
                f'<div style="display: flex; align-items: center; margin-bottom: 6px;">'
                f'  <div style="width: 60px; text-align: left;">{flag_html}&nbsp;{country_code}</div>'
                f'  <div style="flex-grow: 1;">'
                f'    <div style="width: {bar_width}%; background: {bar_color}; height: 20px; border-radius: 4px; text-align: right; padding-right: 5px; color: white; line-height: 20px; font-weight: bold; min-width: 20px;">{count}</div>'
                f'  </div>'
                f'</div>'
            )
        chart_html += '</div>'
        st.markdown(chart_html, unsafe_allow_html=True)
    else:
        st.info("국가 정보가 없어 랭킹을 표시할 수 없습니다.")

    st.divider() # 각 섹션 사이에 구분선 추가

    st.subheader("📄 최근 이벤트")
    if not df.empty:
        st.dataframe(df.sort_values("ts", ascending=False)[["ts", "src_ip", "country", "label"]].head(15), hide_index=True, use_container_width=True)
    else:
        st.info("표시할 이벤트 데이터가 없습니다.")

    st.divider() # 각 섹션 사이에 구분선 추가

    st.subheader("🛡️ 공격 유형 랭킹 (Top 5)")
    if not df.empty and 'label' in df.columns:
        top_labels = df["label"].value_counts().head(5).reset_index()
        top_labels.columns = ["label", "count"]
        chart = alt.Chart(top_labels).mark_arc(outerRadius=120).encode(
            theta=alt.Theta("count", stack=True),
            color=alt.Color("label", legend=alt.Legend(title="공격 유형", labelFontSize=12, titleFontSize=14)),
            tooltip=["label", "count"]
        ).properties(title="").configure_legend(orient='bottom', columns=2)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("공격 유형 정보가 없어 랭킹을 표시할 수 없습니다.")


# 메인 실행 로직
def main():
    st.subheader("")
    setup_page("🌍", "실시간 공격 맵")

    st.markdown(
    f"""
    <p style="color:gray; font-size:14px; text-align:right;">
    본 사이트는 허니팟을 통해 수집된 공격 데이터를 시각화하는 곳입니다.<br>
    2222번 포트를 열고 cowrie를 통해 AWS EC2와 ubuntu에서 수집된 데이터를 실시간으로 시각화합니다.<br>
    수집하여 시각화된 데이터는 {time_str} 기준으로 업데이트 되었습니다.
    </p>
    """,
    unsafe_allow_html=True
)
    start_sync_daemon()
    events_path = display_sidebar()

    st.sidebar.header("맵/애니메이션 옵션")
    with st.sidebar.expander("🗺️ 맵 옵션", expanded=True):
        show_arcs = st.checkbox("곡선 경로(Arc) 보이기", True, key="show_arcs")
        zoom_init = st.slider("초기 줌", 1.0, 5.0, 2.0, 0.1, key="zoom_init")
    
    with st.sidebar.expander("🚀 애니메이션 옵션", expanded=True):
        enable_anim = st.checkbox("이동 애니메이션", True, key="enable_anim")
        duration_ms = st.slider("애니메이션 시간(ms)", 600, 6000, 2000, 200, key="duration_ms")
        frame_step = st.slider("프레임 간격(ms)", 20, 200, 50, 10, key="frame_step")
        sleep_s = st.slider("프레임 지연(초)", 0.02, 0.20, 0.06, 0.01, key="sleep_s")

    # 1. 현재 맵 설정을 딕셔너리로 만듦
    current_map_settings = {
        'show_arcs': show_arcs, 'zoom_init': zoom_init, 'enable_anim': enable_anim,
        'duration_ms': duration_ms, 'frame_step': frame_step, 'sleep_s': sleep_s,
    }

    # 2. session_state에 이전 설정이 없으면 현재 설정으로 초기화
    if 'prev_map_settings' not in st.session_state:
        st.session_state.prev_map_settings = current_map_settings

    # 3. 데이터 로딩은 최초 한 번만 실행되도록 session_state 활용
    if 'df' not in st.session_state:
        st.session_state.df = load_events(str(events_path))
    
    df = st.session_state.df
    
    # 4. 페이지의 나머지 부분은 항상 표시
    display_metrics(df)
    
    # 5. 맵을 그릴 공간을 미리 확보
    map_placeholder = st.empty()

    # 6. 설정이 변경되었을 때만 맵을 다시 그림
    if st.session_state.prev_map_settings != current_map_settings:
        print("===== MAP SETTINGS CHANGED, RE-RENDERING MAP =====")
        display_attack_map(map_placeholder, df, current_map_settings)
        st.session_state.prev_map_settings = current_map_settings # 변경된 설정을 저장
    else:
        # 변경이 없으면 이전 설정으로 맵을 그림
        display_attack_map(map_placeholder, df, st.session_state.prev_map_settings)

    display_dashboard(df)
    display_footer()

if __name__ == "__main__":
    main()