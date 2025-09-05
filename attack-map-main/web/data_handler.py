# web/data_handler.py
import json
from pathlib import Path
import pandas as pd
import streamlit as st
import pycountry # 국가 이름 변환을 위해 import
from functools import lru_cache # 변환 작업 캐싱으로 속도 향상

from config import HONEYPOT_LAT, HONEYPOT_LON
from utils import get_flag_emoji

@lru_cache(maxsize=512) # 동일한 국가 이름 변환 시 캐시를 사용해 빠르게 처리
def get_country_code(country_name: str) -> str:
    """국가 전체 이름을 두 글자 코드로 변환합니다. (예: South Korea -> KR)"""
    if not country_name or not isinstance(country_name, str):
        return "NA"
    try:
        # pycountry 라이브러리를 사용해 국가 객체를 찾음
        country_obj = pycountry.countries.get(name=country_name)
        if country_obj:
            return country_obj.alpha_2
        # 일부 국가 이름 변형에 대응 
        country_obj = pycountry.countries.search_fuzzy(country_name)[0]
        if country_obj:
            return country_obj.alpha_2
        return "NA"
    except (LookupError, IndexError):
        # 라이브러리에서 국가를 찾지 못한 경우
        return "NA"

@st.cache_data(ttl=120) # 캐시의 ttl을 120초로 설정
def load_events(path_str: str) -> pd.DataFrame:
    """
    JSON 또는 JSONL 형식의 이벤트 파일을 로드하고,
    표준화된 Pandas DataFrame으로 변환합니다.
    """
    base_cols = ["ts", "src_ip", "country", "label", "lat", "lon"]
    p = Path(path_str)
    
    try:
        txt = p.read_bytes().decode("utf-8-sig").strip()
        if not txt: return pd.DataFrame(columns=base_cols)
        
        # JSONL 또는 JSON 배열 형식 처리
        if "\n" in txt and txt.lstrip().startswith("{"):
            records = [json.loads(line) for line in txt.splitlines() if line.strip()]
        else:
            obj = json.loads(txt)
            records = obj if isinstance(obj, list) else obj.get("data", [])
    except (json.JSONDecodeError, FileNotFoundError):
        return pd.DataFrame(columns=base_cols)

    if not records: return pd.DataFrame(columns=base_cols)

    df = pd.DataFrame(records)
    
    # 1. 컬럼 이름 표준화
    df = df.rename(columns={"latitude": "lat", "longitude": "lon", "timestamp": "ts", "time": "ts"})

    # 2. label 필드 처리: 기존 필드를 그대로 사용하도록 단순화
    if 'label' not in df.columns:
        df['label'] = 'unknown' # label 필드가 없는 경우에만 unknown
    df['label'] = df['label'].fillna('unknown').astype(str)

    # 3. country 필드 처리: 국가 이름을 코드로 변환
    if 'country' not in df.columns:
        df['country'] = 'Unknown'
    df['country_full_name'] = df['country'].fillna('Unknown') # 원본 국가 이름 백업
    df['country_code'] = df['country_full_name'].apply(get_country_code) # 국가 코드로 변환
    
    # 국기 이모지 + 국가 코드로 표시될 country 컬럼 최종 생성
    df["country"] = df["country_code"].apply(get_flag_emoji) + " " + df["country_code"]

    # 필수 컬럼 존재 여부 확인 및 생성
    for c in ["ts", "src_ip", "lat", "lon"]:
        if c not in df.columns:
            df[c] = None
            
    # 데이터 타입 보정 및 결측치 처리
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["src_ip"] = df["src_ip"].fillna("N/A").astype(str)
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")

    df = df.dropna(subset=["lat", "lon", "ts"]).reset_index(drop=True)

    # 목적지 좌표(허니팟) 추가
    df["dst_lat"], df["dst_lon"] = HONEYPOT_LAT, HONEYPOT_LON
    
    return df