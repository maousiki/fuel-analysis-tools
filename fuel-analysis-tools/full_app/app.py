import sys
import types
# ★ micropip が見つからない環境向けのスタブを先に登録しておく
sys.modules.setdefault('micropip', types.ModuleType('micropip'))

import streamlit as st
import pandas as pd
import plotly.express as px

# ──────────── ヘルパー関数 ────────────
def convert_time_to_minutes(time_str):
    """
    "hh:mm" または "hh:mm:ss" の文字列を分に変換。
    変換エラー時には pandas.NA を返す。
    """
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

# ──────────── CSV処理関数 ────────────
def process_csv_data(df, fuel_price, fuel_efficiency, idling_threshold, date_col=None):
    # 時間変換
    df['運転時間_分']        = df['走行時間'].apply(convert_time_to_minutes)
    df['アイドリング時間_分'] = df['アイドリング時間'].apply(convert_time_to_minutes)

    # 数値変換
    df['走行距離_km'] = pd.to_numeric(df['走行距離'], errors='coerce')

    # 欠損・ゼロ値除外
    df = df.dropna(subset=['運転時間_分', '走行距離_km'])
    df = df[df['運転時間_分'] > 0]

    # 燃料使用量・費用計算
    df['燃料使用量_L'] = (df['走行距離_km'] / fuel_efficiency).round(2)
    df['燃料費_円']    = (df['燃料使用量_L'] * fuel_price).round(0)

    # 指標計算
    df['アイドリング率_％'] = (df['アイドリング時間_分'] / df['運転時間_分'] * 100).round(2)
    df['平均速度_km_h']    = (df['走行距離_km'] / (df['運転時間_分'] / 60)).round(2)

    # 日付型変換
    if date_col:
        df['運行日'] = pd.to_datetime(df[date_col], errors='coerce')

    # カラー判定用
    df['燃料費カラー']     = df['燃料費_円'].apply(lambda x: 'red' if x > fuel_price * 100 else 'blue')
    df['アイドリングカラー'] = df['アイドリング率_％'].apply(lambda x: 'red' if x > idling_threshold else 'blue')

    return df

# ──────────── Streamlit UI ────────────
st.set_page_config(page_title='燃費見える化ダッシュボード', layout='wide')
st.title('🚚 燃費見える化ダッシュボード')

# ユーザー入力
cols = st.columns(3)
fuel_price       = cols[0].number_input('燃料単価 (円/L)', value=160, step=1)
fuel_efficiency  = cols[1].number_input('想定燃費 (km/L)', value=5.0, step=0.1)
idling_threshold = cols[2].slider('アイドリング率警告閾値 (%)', min_value=0, max_value=100, value=20)

uploaded_file = st.file_uploader('走行ログ CSV をアップロード (cp932 形式)', type=['csv'])

if uploaded_file:
    try:
        # CSV読み込み
        df_raw = pd.read_csv(uploaded_file, encoding='cp932')
        # 重複カラム除去
        df_raw = df_raw.T.drop_duplicates(keep='first').T
        # デバッグ用：列名一覧表示
        st.write('**DEBUG: 読み込んだ CSV カラム一覧**', df_raw.columns.tolist())

        # 必須列の検出とリネーム
        # アイドリング時間列
        idle_col = next((c for c in df_raw.columns if 'アイドリング' in c), None)
        # 走行時間列：'ハンドル'または『時間』を含むがアイドリングでないもの
        handle_col = next((c for c in df_raw.columns
                            if ('ハンドル' in c or ('時間' in c and 'アイドリング' not in c))
                           ), None)
        # 走行距離列
        dist_col = next((c for c in df_raw.columns if '走行距離' in c or '区間距離' in c), None)
        # 日付列
        date_col = next((c for c in df_raw.columns if '日付' in c), None)

        missing = [name for name, col in [('走行時間', handle_col), ('アイドリング時間', idle_col), ('走行距離', dist_col)] if not col]
        if missing:
            raise Exception(f"必須列が見つかりません: {missing}. CSVカラム一覧: {df_raw.columns.tolist()}")

        # 標準カラムにリネーム
        df_raw = df_raw.rename(columns={
            handle_col: '走行時間',
            idle_col:   'アイドリング時間',
            dist_col:   '走行距離'
        })

        # データ処理
        df = process_csv_data(df_raw, fuel_price, fuel_efficiency, idling_threshold, date_col)
        st.success('✅ データを正常に読み込みました！')

        # プレビュー表示
        display_cols = ['運行日','乗務員','走行距離_km','運転時間_分','アイドリング時間_分','燃料費_円','アイドリング率_％','平均速度_km_h']
        st.subheader('🔍 データプレビュー')
        st.dataframe(df[[c for c in display_cols if c in df.columns]])

        # CSVダウンロード
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button('📥 分析結果 CSV ダウンロード', data=csv, file_name='analysis.csv', mime='text/csv')

        # （ランキング・グラフ処理）

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
