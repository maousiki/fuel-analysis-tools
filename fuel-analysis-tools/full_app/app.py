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
        else:
            return pd.NA
    except Exception:
        return pd.NA

# ──────────── CSV処理関数 ────────────
def process_csv_data(uploaded_file, fuel_price, fuel_efficiency, idling_threshold):
    # CSV 読み込み
    df = pd.read_csv(uploaded_file, encoding="cp932")

    # カラム名マッピング（CSVの実際の列名に合わせてリネーム）
    column_map = {
        'ハンドル時間－時分－': '走行時間',
        'アイドリング時間－時分－': 'アイドリング時間',
        # 必要に応じて他のカラムもマップ
    }
    df.rename(columns=column_map, inplace=True)

    # 時間変換
    df['運転時間_分']        = df['走行時間'].apply(convert_time_to_minutes)
    df['アイドリング時間_分'] = df['アイドリング時間'].apply(convert_time_to_minutes)

    # 数値変換
    df['走行距離_km'] = pd.to_numeric(df.get('走行距離', df.get('区間距離', '')), errors='coerce')

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
    if '日付' in df.columns:
        df['運行日'] = pd.to_datetime(df['日付'], errors='coerce')

    # カラー判定用列
    df['燃料費カラー']    = df['燃料費_円'].apply(lambda x: 'red' if x > fuel_price * 100 else 'blue')
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
        # データ処理
        df = process_csv_data(uploaded_file, fuel_price, fuel_efficiency, idling_threshold)
        st.success('データを正常に読み込みました！')

        # テーブル表示
        st.subheader('🔍 原データプレビュー')
        st.dataframe(df[['運行日','乗務員','走行距離_km','運転時間_分','アイドリング時間_分','燃料費_円','アイドリング率_％','平均速度_km_h']])

        # CSV ダウンロード
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button('📥 分析結果を CSV ダウンロード', data=csv, file_name='分析結果.csv', mime='text/csv')

        # ランキング表示
        col1, col2, col3 = st.columns(3)
        with col1:
            st.subheader('💡 燃料費ランキング')
            st.dataframe(df.sort_values('燃料費_円', ascending=False)[['乗務員','燃料費_円']])
        with col2:
            st.subheader('💡 アイドリング率ランキング')
            st.dataframe(df.sort_values('アイドリング率_％', ascending=False)[['乗務員','アイドリング率_％']])
        with col3:
            st.subheader('💡 平均速度ランキング')
            st.dataframe(df.sort_values('平均速度_km_h', ascending=False)[['乗務員','平均速度_km_h']])

        # ドライバー別グラフ
        st.subheader('📊 ドライバー別指標')
        fig1 = px.bar(df, x='乗務員', y='燃料費_円', color='燃料費カラー', title='燃料費 (円)')
        fig1.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.bar(df, x='乗務員', y='アイドリング率_％', color='アイドリングカラー', title='アイドリング率 (%)')
        fig2.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig2, use_container_width=True)

        fig3 = px.bar(df, x='乗務員', y='平均速度_km_h', title='平均速度 (km/h)')
        fig3.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig3, use_container_width=True)

        # １か月合計・平均指標
        st.subheader('📅 月次集計 (乗務員別)')
        summary = df.groupby('乗務員').agg({
            '走行距離_km':'sum',
            '燃料使用量_L':'sum',
            'アイドリング時間_分':'sum',
            '運転時間_分':'sum'
        }).reset_index()
        summary['月間平均燃費_km_L']   = (summary['走行距離_km'] / summary['燃料使用量_L']).round(2)
        summary['月間アイドリング率_％'] = (summary['アイドリング時間_分'] / summary['運転時間_分'] * 100).round(2)
        st.dataframe(summary[['乗務員','月間平均燃費_km_L','月間アイドリング率_％']])

        # 月次グラフ
        fig4 = px.bar(summary, x='乗務員', y='月間平均燃費_km_L', title='月間平均燃費 (km/L)')
        fig4.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig4, use_container_width=True)

        fig5 = px.bar(summary, x='乗務員', y='月間アイドリング率_％', title='月間アイドリング率 (%)')
        fig5.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig5, use_container_width=True)

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
