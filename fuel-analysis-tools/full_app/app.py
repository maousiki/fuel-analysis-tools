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
    except Exception:
        pass
    return pd.NA

# ──────────── データ処理関数 ────────────
def process_csv_data(df, fuel_price, fuel_efficiency, idling_threshold, date_col=None):
    # 走行距離の数値変換
    df['走行距離'] = df['走行距離'].astype(str).str.replace(r'[^0-9\.]', '', regex=True)
    df['走行距離_km'] = pd.to_numeric(df['走行距離'], errors='coerce')
    df = df.dropna(subset=['走行距離_km'])

    # 燃料使用量・燃料費
    df['燃料使用量_L'] = (df['走行距離_km'] / fuel_efficiency).round(2)
    df['燃料費_円'] = (df['燃料使用量_L'] * fuel_price).round(0)

    # 時間関連の計算
    if '走行時間' in df.columns and 'アイドリング時間' in df.columns:
        df['運転時間_分'] = df['走行時間'].apply(convert_time_to_minutes)
        df['アイドリング時間_分'] = df['アイドリング時間'].apply(convert_time_to_minutes)
        valid = df['運転時間_分'] > 0
        df.loc[~valid, ['運転時間_分','アイドリング時間_分']] = pd.NA
        df['アイドリング率_％'] = (df['アイドリング時間_分'] / df['運転時間_分'] * 100).round(2)
        df['平均速度_km_h'] = (df['走行距離_km'] / (df['運転時間_分'] / 60)).round(2)
    else:
        df['運転時間_分'] = pd.NA
        df['アイドリング時間_分'] = pd.NA
        df['アイドリング率_％'] = pd.NA
        df['平均速度_km_h'] = pd.NA

    # 日付変換
    if date_col and date_col in df.columns:
        df['運行日'] = pd.to_datetime(df[date_col], errors='coerce')

    return df

# ──────────── Streamlit UI ────────────
st.set_page_config(page_title='燃費見える化ダッシュボード', layout='wide')
st.title('🚚 燃費見える化ダッシュボード')

# 入力パネル
cols = st.columns(3)
fuel_price = cols[0].number_input('燃料単価 (円/L)', value=160, step=1)
fuel_efficiency = cols[1].number_input('想定燃費 (km/L)', value=5.0, step=0.1)
idling_threshold = cols[2].slider('アイドリング率警告閾値 (%)', 0, 100, 20)

# CSVアップロード
uploaded_file = st.file_uploader('CSV アップロード (cp932)', type=['csv'])
if uploaded_file:
    try:
        df_raw = pd.read_csv(uploaded_file, encoding='cp932')
        # 重複カラム除去
        df_raw = df_raw.T.drop_duplicates(keep='first').T
        st.write('**DEBUG: CSV カラム一覧**', df_raw.columns.tolist())

        # 列名マッピング
        # 走行距離
        if '一般・実車走行距離' in df_raw.columns:
            dist_col = '一般・実車走行距離'
        elif '走行距離' in df_raw.columns:
            dist_col = '走行距離'
        else:
            raise Exception(f"走行距離列が見つかりません: {df_raw.columns.tolist()}")
        # アイドリング時間 （任意）
        idle_col = 'アイドリング時間' if 'アイドリング時間' in df_raw.columns else None
        # 日付列
        date_col = '日付' if '日付' in df_raw.columns else None

        # リネーム
        rename_map = {dist_col: '走行距離'}
        if idle_col:
            rename_map[idle_col] = 'アイドリング時間'
        df = df_raw.rename(columns=rename_map)
        # 同一カラム名による重複を削除して、Seriesとして扱えるようにする
        df = df.loc[:, ~df.columns.duplicated()]

        # ドライバー名必須
        if '乗務員' not in df.columns:
            raise Exception("'乗務員' 列が見つかりません。CSVに '乗務員' 列を含めてください。")

        # データ処理
        df = process_csv_data(df, fuel_price, fuel_efficiency, idling_threshold, date_col)
        st.success('✅ データ読み込み完了')

        # 原データプレビュー
        st.subheader('🔍 データプレビュー')
        st.dataframe(df[['乗務員','運行日','走行距離_km','燃料使用量_L','燃料費_円','アイドリング率_％','平均速度_km_h']])

        # 月間ドライバー別集計
        summary = df.groupby('乗務員', as_index=False).agg(
            走行距離_km=('走行距離_km','sum'),
            燃料使用量_L=('燃料使用量_L','sum'),
            燃料費_円=('燃料費_円','sum'),
            運転時間_分=('運転時間_分','sum'),
            アイドリング時間_分=('アイドリング時間_分','sum')
        )
        # 分母ゼロ回避
        summary['月間平均燃費_km_L'] = np.where(
            summary['燃料使用量_L']>0,
            (summary['走行距離_km']/summary['燃料使用量_L']).round(2),
            pd.NA
        )
        summary['月間アイドリング率_％'] = np.where(
            summary['運転時間_分']>0,
            (summary['アイドリング時間_分']/summary['運転時間_分']*100).round(2),
            pd.NA
        )
        st.subheader('📅 月間ドライバー別集計')
        st.dataframe(summary)

    except Exception as e:
        st.error(f"エラー: {e}")
