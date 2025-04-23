import sys
import types
# micropip がない環境向けのスタブ
sys.modules.setdefault('micropip', types.ModuleType('micropip'))

import streamlit as st
import pandas as pd
import plotly.express as px

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
    # 燃料使用量・費用
    df['走行距離_km'] = pd.to_numeric(df['走行距離'], errors='coerce')
    df = df.dropna(subset=['走行距離_km'])
    df['燃料使用量_L'] = (df['走行距離_km'] / fuel_efficiency).round(2)
    df['燃料費_円'] = (df['燃料使用量_L'] * fuel_price).round(0)

    # 時間関連の列がある場合のみ計算
    if '走行時間' in df.columns and 'アイドリング時間' in df.columns:
        df['運転時間_分'] = df['走行時間'].apply(convert_time_to_minutes)
        df['アイドリング時間_分'] = df['アイドリング時間'].apply(convert_time_to_minutes)
        # 有効な運転時間のみ
        valid = df['運転時間_分'] > 0
        df.loc[~valid, ['運転時間_分','アイドリング時間_分']] = pd.NA
        # 指標
        df['アイドリング率_％'] = (df['アイドリング時間_分'] / df['運転時間_分'] * 100).round(2)
        df['平均速度_km_h'] = (df['走行距離_km'] / (df['運転時間_分'] / 60)).round(2)
    else:
        # 存在しない場合は NA
        df['運転時間_分'] = pd.NA
        df['アイドリング時間_分'] = pd.NA
        df['アイドリング率_％'] = pd.NA
        df['平均速度_km_h'] = pd.NA

    # 日付変換
    if date_col and date_col in df.columns:
        df['運行日'] = pd.to_datetime(df[date_col], errors='coerce')

    # カラー判定用
    df['燃料費カラー'] = df['燃料費_円'].apply(lambda x: 'red' if x > fuel_price * 100 else 'blue')
    df['アイドリングカラー'] = df['アイドリング率_％'].apply(lambda x: 'red' if pd.notna(x) and x > idling_threshold else 'blue')

    return df

# ──────────── Streamlit UI ────────────
st.set_page_config(page_title='燃費見える化ダッシュボード', layout='wide')
st.title('🚚 燃費見える化ダッシュボード')

# 入力
cols = st.columns(3)
fuel_price = cols[0].number_input('燃料単価 (円/L)', value=160, step=1)
fuel_efficiency = cols[1].number_input('想定燃費 (km/L)', value=5.0, step=0.1)
idling_threshold = cols[2].slider('アイドリング率警告閾値 (%)', 0, 100, 20)

uploaded_file = st.file_uploader('CSVアップロード (cp932)', type=['csv'])
if uploaded_file:
    try:
        df_raw = pd.read_csv(uploaded_file, encoding='cp932')
        # 重複カラムを除去
        df_raw = df_raw.T.drop_duplicates(keep='first').T
        st.write('**DEBUG: CSV カラム一覧**', df_raw.columns.tolist())

        # 列名検出
        idle_col = 'アイドリング時間' if 'アイドリング時間' in df_raw.columns else None
        # 運転時間列なしのためスキップ
        handle_col = None
        # 走行距離列
        if '走行距離' in df_raw.columns:
            dist_col = '走行距離'
        elif '一般・実車走行距離' in df_raw.columns:
            dist_col = '一般・実車走行距離'
        else:
            dist_col = None
        # 日付列
        date_col = '日付' if '日付' in df_raw.columns else None

        if not dist_col:
            raise Exception(f"走行距離列が見つかりません: {df_raw.columns.tolist()}")

        # リネーム
        rename_map = {dist_col:'走行距離'}
        if idle_col:
            rename_map[idle_col] = 'アイドリング時間'
        df = df_raw.rename(columns=rename_map)

        # データ処理
        df = process_csv_data(df, fuel_price, fuel_efficiency, idling_threshold, date_col)
        st.success('データ読み込み完了')

        # プレビュー
        display = ['運行日','走行距離_km','燃料使用量_L','燃料費_円','アイドリング率_％','平均速度_km_h']
        st.dataframe(df[[c for c in display if c in df.columns]])

    except Exception as e:
        st.error(f"エラー: {e}")
