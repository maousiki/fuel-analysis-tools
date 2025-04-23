import sys
import types
# micropip がない環境向けのスタブ
sys.modules.setdefault('micropip', types.ModuleType('micropip'))

import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# ──────────── ヘルパー関数 ────────────
def convert_time_to_minutes(time_str):
    try:
        parts = list(map(int, str(time_str).split(':')))
        if len(parts) == 3:
            h, m, s = parts
            return h * 60 + m + s / 60
        elif len(parts) == 2:
            h, m = parts
            return h * 60 + m
    except:
        pass
    return pd.NA

# ──────────── データ処理関数 ────────────
def process_csv_data(df, fuel_price, fuel_efficiency, idling_threshold, date_col=None):
    # 走行距離のクリーニングと数値変換
    df['走行距離'] = (
        df['走行距離'].astype(str)
        .str.replace(r'[^0-9\.]', '', regex=True)
    )
    df['走行距離_km'] = pd.to_numeric(df['走行距離'], errors='coerce')
    df = df.dropna(subset=['走行距離_km'])

    # 燃料使用量と燃料費の計算
    df['燃料使用量_L'] = (df['走行距離_km'] / fuel_efficiency).round(2)
    df['燃料費_円'] = (df['燃料使用量_L'] * fuel_price).round(0)

    # 時間列の分変換
    for col in ['走行時間', 'アイドリング時間', '稼働時間']:
        if col in df.columns:
            df[f'{col}_分'] = df[col].apply(convert_time_to_minutes)
        else:
            df[f'{col}_分'] = pd.NA

    # アイドリング率: アイドリング時間 ÷ 稼働時間
    valid_active = df['稼働時間_分'] > 0
    df['アイドリング率_％'] = np.where(
        valid_active,
        (df['アイドリング時間_分'] / df['稼働時間_分'] * 100).round(2),
        pd.NA
    )

    # 平均速度: 走行距離 ÷ (走行時間/60)
    valid_drive = df['走行時間_分'] > 0
    df['平均速度_km_h'] = np.where(
        valid_drive,
        (df['走行距離_km'] / (df['走行時間_分'] / 60)).round(2),
        pd.NA
    )

    # 日付列の変換
    if date_col and date_col in df.columns:
        df['運行日'] = pd.to_datetime(df[date_col], errors='coerce')

    return df

# ──────────── Streamlit UI ────────────
st.set_page_config(page_title='燃費見える化ダッシュボード', layout='wide')
st.title('🚚 燃費見える化ダッシュボード')

# 入力パネル
col1, col2, col3 = st.columns(3)
fuel_price = col1.number_input('燃料単価 (円/L)', value=160, step=1)
fuel_efficiency = col2.number_input('想定燃費 (km/L)', value=5.0, step=0.1)
col2.markdown(
    '_（1〜3トン:10〜17km/L、4トン:約7.5km/L、8トン以上:3〜5km/L）_',
    unsafe_allow_html=True
)
idling_threshold = col3.slider('アイドリング率警告閾値 (%)', 0, 100, 20)

# ファイルアップロード
uploaded_file = st.file_uploader('CSV アップロード (cp932)', type=['csv'])
if uploaded_file:
    try:
        df_raw = pd.read_csv(uploaded_file, encoding='cp932')
        df_raw = df_raw.T.drop_duplicates(keep='first').T

        # 列名マッピング
        dist_col = '一般・実車走行距離' if '一般・実車走行距離' in df_raw.columns else (
            '走行距離' if '走行距離' in df_raw.columns else None
        )
        if not dist_col:
            raise Exception(f"走行距離列が見つかりません: {df_raw.columns.tolist()}")
        rename_map = {dist_col: '走行距離'}
        if 'アイドリング時間' in df_raw.columns:
            rename_map['アイドリング時間'] = 'アイドリング時間'
        if '稼働時間' in df_raw.columns:
            rename_map['稼働時間'] = '稼働時間'
        df = df_raw.rename(columns=rename_map)
        df = df.loc[:, ~df.columns.duplicated()]

        if '乗務員' not in df.columns:
            raise Exception("'乗務員' 列が見つかりません。CSVに '乗務員' 列を含めてください。")

        # データ処理
        df = process_csv_data(df, fuel_price, fuel_efficiency, idling_threshold, '日付')
        st.success('✅ データ読み込み完了')

        # データプレビュー
        st.subheader('🔍 データプレビュー')
        preview_cols = ['乗務員','運行日','走行距離_km','燃料使用量_L',
                        '燃料費_円','アイドリング率_％','平均速度_km_h']
        st.dataframe(df[preview_cols])

        # 月間ドライバー別集計
        summary = df.groupby('乗務員', as_index=False).agg(
            走行距離_km=('走行距離_km','sum'),
            燃料使用量_L=('燃料使用量_L','sum'),
            燃料費_円=('燃料費_円','sum'),
            走行時間_分=('走行時間_分','sum'),
            アイドリング時間_分=('アイドリング時間_分','sum'),
            稼働時間_分=('稼働時間_分','sum')
        )
        # 指標計算
        summary['月間平均燃費_km_L'] = np.where(
            summary['燃料使用量_L']>0,
            (summary['走行距離_km']/summary['燃料使用量_L']).round(2),
            pd.NA
        )
        summary['月間アイドリング率_％'] = np.where(
            summary['稼働時間_分']>0,
            (summary['アイドリング時間_分']/summary['稼働時間_分']*100).round(2),
            pd.NA
        )
        st.subheader('📅 月間ドライバー別集計')
        st.dataframe(summary)

        # グラフ表示
        st.subheader('📊 月間平均燃費ランキング')
        fig1 = px.bar(
            summary.sort_values('月間平均燃費_km_L', ascending=False),
            x='乗務員', y='月間平均燃費_km_L',
            title='ドライバー別 月間平均燃費 (km/L)'
        )
        fig1.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig1, use_container_width=True)

        # カラー分けアイドリング率 (閾値-10% に拡張)
        summary['アイドリング色'] = np.where(
            summary['月間アイドリング率_％'] >= idling_threshold, 'red',
            np.where(
                summary['月間アイドリング率_％'] < idling_threshold - 10,
                'blue',
                'yellow'
            )
        )
        st.subheader('📊 月間アイドリング率ランキング')
        fig2 = px.bar(
            summary.sort_values('月間アイドリング率_％', ascending=False),
            x='乗務員', y='月間アイドリング率_％',
            color='アイドリング色',
            color_discrete_map={'red':'red','yellow':'yellow','blue':'blue'},
            title=f'ドライバー別 月間アイドリング率 (%) (閾値: {idling_threshold}%)'
        )
        fig2.update_layout(xaxis_tickangle=-45, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

        # 算出式の表示
        st.markdown('**算出式**')
        st.markdown('- 燃料使用量 (L) = 走行距離_km ÷ 想定燃費 (km/L)')
        st.markdown('- 燃料費 (円) = 燃料使用量 (L) × 燃料単価 (円/L)')
        st.markdown('- 月間平均燃費 (km/L) = 走行距離合計_km ÷ 燃料使用量合計_L')
        st.markdown('- 月間アイドリング率 (%) = アイドリング時間合計_分 ÷ 稼働時間合計_分 × 100')
        st.markdown('- カラー条件:')
        st.markdown('  - 青: 設定閾値-10% 未満')
        st.markdown('  - 黄: 設定閾値-10% 以上かつ閾値未満')
        st.markdown('  - 赤: 設定閾値以上')
