# web/pages/3_AI_공격_분석.py
import streamlit as st
import pandas as pd
import altair as alt
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import numpy as np

# 공용 모듈 import
from ui_components import setup_page, display_sidebar, display_footer
from data_handler import load_events

# 머신러닝 및 데이터 처리 함수
def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    df_engineered = df.copy()
    if 'ts' in df_engineered.columns and pd.api.types.is_datetime64_any_dtype(df_engineered['ts']):
        df_engineered['hour'] = df_engineered['ts'].dt.hour
    else:
        df_engineered['hour'] = 0
    if 'label' in df_engineered.columns:
        le = LabelEncoder()
        df_engineered['label_encoded'] = le.fit_transform(df_engineered['label'])
    else:
        df_engineered['label_encoded'] = 0
    return df_engineered

@st.cache_data
def find_optimal_k(X_scaled):
    inertias = []
    k_range = range(2, 11)
    for k in k_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto')
        kmeans.fit(X_scaled)
        inertias.append(kmeans.inertia_)
    try:
        deltas = np.diff(inertias, 2)
        optimal_k = k_range[np.argmax(deltas) + 1]
    except ValueError:
        optimal_k = 4
    elbow_df = pd.DataFrame({'K': k_range, 'Inertia': inertias})
    return optimal_k, elbow_df

@st.cache_data
def run_ml_analysis(df_engineered, features, optimal_k):
    X = df_engineered[features].copy()
    X.fillna(0, inplace=True)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init='auto')
    clusters = kmeans.fit_predict(X_scaled)
    pca = PCA(n_components=2, random_state=42)
    X_pca = pca.fit_transform(X_scaled)
    result_df = df_engineered.copy()
    result_df['cluster'] = clusters
    result_df['pca1'] = X_pca[:, 0]
    result_df['pca2'] = X_pca[:, 1]
    return result_df

# 메인 실행 로직
def main():
    setup_page("🤖", "머신러닝 기반 공격 분석")
    events_path = display_sidebar()
    df = load_events(str(events_path))

    st.markdown("KMeans를 사용하여 모델이 공격 데이터의 특징을 스스로 학습하여 클러스터링을 진행합니다. 여기서 사용하는 특징은 위도, 경도, 심각도, 시간, 공격유형의 5가지입니다.")
    st.markdown("이후 PCA를 통해 5가지 특징을 2차원으로 압축하여 주성분 축1, 주성분 축2를 기준으로 시각화하여 표시합니다. 산점도 그림 아래에 각 클러스터별 특징이 정리되어 있습니다.")
    st.markdown("---")
    
    if df.empty:
        st.warning("분석할 이벤트 데이터가 없습니다.")
        return

    # 1. 피처 엔지니어링 및 분석 실행
    df_engineered = feature_engineering(df)
    features_for_ml = ['lat', 'lon', 'severity', 'hour', 'label_encoded']
    X_scaled_for_k = StandardScaler().fit_transform(df_engineered[features_for_ml])
    optimal_k, elbow_df = find_optimal_k(X_scaled_for_k)
    result_df = run_ml_analysis(df_engineered, features_for_ml, optimal_k)
    
    st.subheader("🤖 PCA 분석 결과")
    st.info(f"데이터를 분석하여 **{optimal_k}개의 고유한 공격 패턴(그룹)**을 발견했습니다.", icon="💡")
    
    # 2. 공격 군집 시각화
    scatter_chart = alt.Chart(result_df).mark_circle(size=80).encode(
        x=alt.X('pca1:Q', title='주성분 1'),
        y=alt.Y('pca2:Q', title='주성분 2'),
        color=alt.Color('cluster:N', legend=alt.Legend(title="공격 그룹")),
        tooltip=['ts', 'src_ip', 'country_code', 'label', 'severity', 'hour', 'cluster']
    ).properties(height=500).interactive()
    
    st.altair_chart(scatter_chart, use_container_width=True)
    st.markdown("---")

    st.subheader("그룹별 공격 패턴 프로파일링")
    
    # 각 그룹에 대한 통계를 보여주기 위해 컬럼 대신 expander 사용
    for i in range(optimal_k):
        with st.expander(f"**그룹 {i}** 에 대한 상세 분석", expanded= i == 0):
            cluster_df = result_df[result_df['cluster'] == i]
            
            st.metric(label=f"그룹 {i}의 총 공격 횟수", value=f"{len(cluster_df)} 건")
            st.metric(label="평균 공격 심각도", value=f"{cluster_df['severity'].mean():.2f}")

            st.markdown("---")

            # 2단 컬럼으로 통계 차트 표시
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("##### 주요 공격 국가 (Top 5)")
                top_countries = cluster_df['country_code'].value_counts().head(5).reset_index()
                top_countries.columns = ['country', 'count']
                
                country_chart = alt.Chart(top_countries).mark_bar().encode(
                    x=alt.X('count:Q', title='횟수'),
                    y=alt.Y('country:N', title='국가', sort='-x'),
                    tooltip=['country', 'count']
                ).properties(height=200)
                st.altair_chart(country_chart, use_container_width=True)

            with col2:
                st.markdown("##### 주요 공격 유형 (Top 5)")
                top_labels = cluster_df['label'].value_counts().head(5).reset_index()
                top_labels.columns = ['label', 'count']

                label_chart = alt.Chart(top_labels).mark_bar().encode(
                    x=alt.X('count:Q', title='횟수'),
                    y=alt.Y('label:N', title='유형', sort='-x'),
                    tooltip=['label', 'count']
                ).properties(height=200)
                st.altair_chart(label_chart, use_container_width=True)

    display_footer()

if __name__ == "__main__":
    main()