import streamlit as st
import plotly.express as px
import pandas as pd
import os

# 時間を分に変換する関数
def convert_time_to_minutes(time_str):
    try:
        hours, minutes = map(int, str(time_str).split(":"))
        return hours * 60 + minutes
    except:
        return 0

# CSVデータを処理する関数
def process_csv_data(uploaded_file, fuel_price):
    df = pd.read_csv(uploaded_file, encoding="cp932")

    df["運転時間_分"] = df["走行時間"].apply(convert_time_to_minutes)
    df["アイドリング時間_分"] = df["アイドリング時間"].apply(convert_time_to_minutes)
    df["走行距離_km"] = pd.to_numeric(df["走行距離"], errors="coerce")  # 列名を修正

    df["アイドリング率_％"] = (df["アイドリング時間_分"] / df["運転時間_分"] * 100).round(2)
    df["平均速度_km_per_h"] = (df["走行距離_km"] / (df["運転時間_分"] / 60)).round(2)

    fuel_efficiency = 3.5
    df["燃料使用量_L"] = (df["走行距離_km"] / fuel_efficiency).round(2)
    df["燃料費_円"] = (df["燃料使用量_L"] * fuel_price).round(0)

    df["運行日"] = pd.to_datetime(df["日付"], errors="coerce")  # '運行日' がない場合の対応
    return df[[
        "乗務員", "運行日", "走行距離_km", "運転時間_分", "アイドリング時間_分",
        "アイドリング率_％", "平均速度_km_per_h", "燃料使用量_L", "燃料費_円"
    ]]

# メイン処理
st.title("🚚 燃費見える化くん（Web版）")
st.write("CSVファイルをアップロードすると、燃費やコスト、ランキングが表示されます。")

fuel_price = st.number_input("燃料単価（円/L）を入力してください", value=160, step=1)

uploaded_file = st.file_uploader("CSVファイルを選んでください", type=["csv"])

if uploaded_file is not None:
    try:
        df = process_csv_data(uploaded_file, fuel_price)
        st.success("データを読み込みました！")
        st.dataframe(df)
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 分析結果をCSVでダウンロード",
            data=csv,
            file_name="分析結果.csv",
            mime="text/csv"
        )

        # ランキングテーブル表示
        st.subheader("💡 ランキング：燃料費（高い順）")
        st.dataframe(df.sort_values("燃料費_円", ascending=False)[["乗務員", "燃料費_円"]])

        st.subheader("💡 ランキング：アイドリング率（高い順）")
        st.dataframe(df.sort_values("アイドリング率_％", ascending=False)[["乗務員", "アイドリング率_％"]])

        st.subheader("💡 ランキング：平均速度（高い順）")
        st.dataframe(df.sort_values("平均速度_km_per_h", ascending=False)[["乗務員", "平均速度_km_per_h"]])

        # グラフ表示
        st.subheader("📊 ドライバー別：燃料費")
        fig1 = px.bar(df, x="乗務員", y="燃料費_円", height=500, color=df["燃料費_円"].apply(lambda x: 'red' if x > 10000 else 'blue'))
        fig1.update_layout(
            xaxis={'tickangle': -45},
            yaxis_range=[0, None],
            yaxis_tickformat=',',
            margin=dict(l=0, r=0, t=30, b=150),
            xaxis_title=None
        )
        st.plotly_chart(fig1, use_container_width=True)

        st.subheader("📊 ドライバー別：アイドリング率")
        fig2 = px.bar(df, x="乗務員", y="アイドリング率_％", height=500, color=df["アイドリング率_％"].apply(lambda x: 'red' if x > 100 else 'blue'))
        fig2.update_layout(
            xaxis={'tickangle': -45},
            yaxis_range=[0, None],
            margin=dict(l=0, r=0, t=30, b=150),
            xaxis_title=None
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("📊 ドライバー別：平均速度")
        fig3 = px.bar(df, x="乗務員", y="平均速度_km_per_h", height=500)
        fig3.update_layout(
            xaxis={'tickangle': -45},
            yaxis_range=[0, None],
            margin=dict(l=0, r=0, t=30, b=150),
            xaxis_title=None
        )
        st.plotly_chart(fig3, use_container_width=True)

        # 1か月集計（同じ乗務員ごとの合計）
        summary = df.groupby("乗務員")[['燃料費_円','アイドリング率_％']].sum().reset_index()
        st.subheader("📅 1か月合計：燃料費 & アイドリング率（合計）")
        st.write("同じ乗務員の1か月間の燃料費とアイドリング率の合計です。")
        # 合計グラフ
        st.bar_chart(summary.set_index("乗務員")["燃料費_円"])
        st.bar_chart(summary.set_index("乗務員")["アイドリング率_％"])

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        st.error(f"エラーが発生しました: {e}")

