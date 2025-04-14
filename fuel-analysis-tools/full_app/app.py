import streamlit as st
import pandas as pd
import csv
import os

# 登録情報の保存ファイル
USER_DATA_FILE = "users.csv"

# 初回起動時にCSVファイルを読み込み
if "user_credentials" not in st.session_state:
    st.session_state["user_credentials"] = {}
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) == 2:
                    st.session_state["user_credentials"][row[0]] = row[1]

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
    df["運転時間_分"] = df["ハンドル時間－時分－"].apply(convert_time_to_minutes)
    df["アイドリング時間_分"] = df["アイドリング－時分－"].apply(convert_time_to_minutes)
    df["走行距離_km"] = pd.to_numeric(df["走行距離－ｋｍ－"], errors="coerce")
    df["アイドリング率_％"] = (df["アイドリング時間_分"] / df["運転時間_分"] * 100).round(2)
    df["平均速度_km_per_h"] = (df["走行距離_km"] / (df["運転時間_分"] / 60)).round(2)
    fuel_efficiency = 3.5
    df["燃料使用量_L"] = (df["走行距離_km"] / fuel_efficiency).round(2)
    df["燃料費_円"] = (df["燃料使用量_L"] * fuel_price).round(0)
    return df[[
        "乗務員", "運行日", "走行距離_km", "運転時間_分", "アイドリング時間_分",
        "アイドリング率_％", "平均速度_km_per_h", "燃料使用量_L", "燃料費_円"
    ]]

# ログイン機能（登録なし）
def login():
    st.sidebar.title("🔐 ログイン")
    username = st.sidebar.text_input("ユーザーID")
    password = st.sidebar.text_input("パスワード", type="password")
    if st.sidebar.button("ログイン"):
        if username in st.session_state["user_credentials"] and st.session_state["user_credentials"][username] == password:
            st.session_state["authenticated"] = True
            st.sidebar.success("ログイン成功！")
        else:
            st.sidebar.error("ユーザーIDまたはパスワードが間違っています。")

# メインアプリ
def main():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        login()
        return

    st.sidebar.button("ログアウト", on_click=lambda: st.session_state.update({"authenticated": False}))

    st.title("🚚 燃費見える化くん（ログイン制Web版）")
    st.write("CSVファイルをアップロードすると、燃費やコストが自動で表示されます。")

    fuel_price = st.number_input("燃料単価（円/L）を入力してください", value=160, step=1)
    uploaded_file = st.file_uploader("CSVファイルを選んでください", type=["csv"])

    if uploaded_file is not None:
        try:
            df = process_csv_data(uploaded_file, fuel_price)
            st.success("データを読み込みました！")
            st.dataframe(df)

            st.subheader("ドライバー別：燃料費")
            st.bar_chart(df.set_index("乗務員")["燃料費_円"])

            st.subheader("ドライバー別：アイドリング率")
            st.bar_chart(df.set_index("乗務員")["アイドリング率_％"])

            st.subheader("ドライバー別：平均速度")
            st.bar_chart(df.set_index("乗務員")["平均速度_km_per_h"])

        except Exception as e:
            st
