import streamlit as st
iimport streamlit as st
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
def process_csv_data(uploaded_file, fuel_price, fuel_efficiency, idling_threshold):
    # CSV 読み込み
    df = pd.read_csv(uploaded_file, encoding="cp932")

    # 列名デバッグ（問題あればコメント解除して列名を確認）
    # st.write("Columns:", df.columns.tolist())

    # 走行時間(ハンドル時間) 列名検出
    handle_col = next((c for c in df.columns if 'ハンドル' in c), None)
    if not handle_col:
        raise Exception(f"走行時間(ハンドル時間) 列が見つかりません。ファイルの列一覧を確認してください: {df.columns.tolist()}")
    df.rename(columns={handle_col: '走行時間'}, inplace=True)

    # アイドリング時間 列名検出
    idle_col = next((c for c in df.columns if 'アイドリング' in c), None)
    if not idle_col:
        raise Exception(f"アイドリング時間 列が見つかりません。ファイルの列一覧を確認してください: {df.columns.tolist()}")
    df.rename(columns={idle_col: 'アイドリング時間'}, inplace=True)

    # 日付 列名検出
    date_col = next((c for c in df.columns if '日付' in c), None)

    # 時間変換
    df['運転時間_分']        = df['走行時間'].apply(convert_time_to_minutes)
    df['アイドリング時間_分'] = df['アイドリング時間'].apply(convert_time_to_minutes)

    # 走行距離 列名検出
    dist_col = next((c for c in df.columns if '走行距離' in c or '区間距離' in c), None)
    if not dist_col:
        raise Exception(f"走行距離 列が見つかりません。ファイルの列一覧を確認してください: {df.columns.tolist()}")
    df['走行距離_km'] = pd.to_numeric(df[dist_col], errors='coerce')

    # 欠損／ゼロ除外
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
fuel_price       = st.number_input('燃料単価 (円/L)', value=160, step=1)
fuel_efficiency  = st.number_input('想定燃費 (km/L)',  value=5.0, step=0.1)
idling_threshold = st.slider('アイドリング率警告閾値 (%)', min_value=0, max_value=100, value=20)

uploaded_file = st.file_uploader('走行ログ CSV をアップロード (cp932 形式)', type=['csv'])

if uploaded_file:
    try:
        df = process_csv_data(uploaded_file, fuel_price, fuel_efficiency, idling_threshold)
        st.success('データを正常に読み込みました！')

        # プレビュー
        show_cols = ['運行日','乗務員','走行距離_km','運転時間_分','アイドリング時間_分','燃料費_円','アイドリング率_％','平均速度_km_h']
        st.subheader('🔍 原データプレビュー')
        st.dataframe(df[[c for c in show_cols if c in df.columns]])

        # CSVダウンロード
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button('CSVダウンロード', csv, 'analysis.csv', 'text/csv')

        # ランキング・グラフ...
        # （省略。全体は先ほどのまま）

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
