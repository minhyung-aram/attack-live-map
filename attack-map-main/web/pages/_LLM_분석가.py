# web/pages/2_LLM_분석가.py
import streamlit as st
import json
import requests
import pandas as pd
from pathlib import Path

# 공용 모듈 및 함수 import
from ui_components import setup_page, display_sidebar, display_footer
from data_handler import load_events
from config import LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT, OLLAMA_MODEL

# 페이지 전용 UI 및 로직 

def get_llm_response_stream(context_df: pd.DataFrame, user_query: str):
    """LLM 서버에 스트리밍 요청을 보내고 응답을 실시간으로 yield하는 함수."""
    if context_df.empty:
        yield "분석할 데이터가 없습니다. 먼저 이벤트 로그를 확인해주세요."
        return

    ctx_records = context_df.to_dict(orient="records")
    ctx_json = json.dumps(ctx_records, ensure_ascii=False, default=str)
    
    # 서버 종류 판별
    try:
        requests.get(f"{LLM_BASE_URL}/v1/models", timeout=2)
        mode = "openai"
    except Exception:
        mode = "ollama"

    try:
        if mode == "openai":
            payload = {
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "너는 보안 로그 분석 전문가다. 반드시 한국어로만, 주어진 로그(context)에 기반해서만 요약/설명해라. 추측이나 외부 지식은 사용하지 마라."},
                    {"role": "user", "content": f"다음 최근 5개 이벤트 로그를 분석해서 답해줘.\n\ncontext:\n{ctx_json}\n\n질문:\n{user_query}"}
                ], 
                "temperature": 0.2, 
                "max_tokens": 1024,
                "stream": True  # 스트리밍 옵션 활성화
            }
            resp = requests.post(f"{LLM_BASE_URL}/v1/chat/completions", json=payload, timeout=LLM_TIMEOUT, stream=True)
            resp.raise_for_status()
            
            for line in resp.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        json_str = decoded_line[6:]
                        if json_str.strip() == '[DONE]':
                            break
                        try:
                            chunk = json.loads(json_str)
                            content = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        else: # Ollama
            payload = {
                "model": OLLAMA_MODEL, 
                "messages": [{"role": "user", "content": f"context:\n{ctx_json}\n\n질문:\n{user_query}"}], 
                "stream": True # 스트리밍 옵션 활성화
            }
            resp = requests.post(f"{LLM_BASE_URL}/api/chat", json=payload, timeout=LLM_TIMEOUT, stream=True)
            resp.raise_for_status()

            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line.decode('utf-8'))
                    content = chunk.get("message", {}).get("content")
                    if content:
                        yield content

    except requests.exceptions.ReadTimeout:
        yield f"⏱️ 타임아웃: 서버가 {LLM_TIMEOUT}초 내에 응답하지 않았습니다. 모델이 로드 중인지 확인해주세요."
    except Exception as e:
        yield f"❌ LLM 호출 오류: {e}\n 서버 주소({LLM_BASE_URL})와 모델 실행 여부를 확인해주세요."


# 메인 실행 로직
def main():
    setup_page("💬", "LLM 기반 로그 분석가")
    events_path = display_sidebar()
    df = load_events(str(events_path))
    
    st.markdown("최신 공격 이벤트 5개를 기반으로 **상황을 요약**하거나 **궁금한 점을 질문**할 수 있습니다.")

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 저는 최신 보안 로그를 분석하는 AI입니다. 무엇을 도와드릴까요?"}]

    col1, col2 = st.columns([2, 1])

    with col2:
        st.markdown("#### 📜 분석 컨텍스트")
        st.info("AI는 아래의 최신 이벤트 5개를 기반으로 답변합니다.", icon="ℹ️")
        context_df = df.sort_values("ts", ascending=False).head(5)
        st.dataframe(context_df[['ts', 'src_ip', 'country_code', 'label']], hide_index=True, use_container_width=True)
        
        with st.expander("💡 질문 예시 보기"):
            st.markdown("""
            - "가장 많이 발생한 공격 유형은 뭐야?"
            - "Seychelles에서 들어온 공격에 대해 설명해줘."
            - "IP `120.26.230.64`는 몇 번이나 접속했어?"
            - "전체적인 상황을 요약해줘."
            """)

    with col1:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("질문을 입력하세요..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # AI 응답을 생성하고 표시
            with st.chat_message("assistant"):
                # st.write_stream을 사용하여 실시간으로 응답을 표시
                response_generator = get_llm_response_stream(context_df, prompt)
                full_response = st.write_stream(response_generator)
            
            # 전체 응답을 받은 후, 세션 기록에 추가
            st.session_state.messages.append({"role": "assistant", "content": full_response})

    display_footer()

if __name__ == "__main__":
    main()