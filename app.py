import streamlit as st

st.set_page_config(page_title="ラジオ進行表チェック", layout="wide")
st.title("📻 運行表・進行表 自動チェックシステム")

# 左側のサイドバー（メニュー）
st.sidebar.header("⚙️ 設定")
api_key = st.sidebar.text_input("Gemini APIキー", type="password")

# メイン画面のタブ
tab1, tab2 = st.tabs(["事前チェック (ゲラ版)", "直前チェック (確定版)"])

with tab1:
    st.header("ゲラ版と週間番組表の比較")
    st.info("※この機能は現在開発中です。ここに週間番組表との比較機能を実装します。")

with tab2:
    st.header("運行表と進行表の突き合わせ")
    st.write("PDFをアップロードしてチェックを行います。")

    # ファイルアップロード欄
    col1, col2 = st.columns(2)
    with col1:
        unkou_file = st.file_uploader("運行表のPDFをアップロード", type="pdf")
    with col2:
        shinkou_file = st.file_uploader("進行表のPDFをアップロード", type="pdf")

    if st.button("🚀 チェック開始", type="primary"):
        if not api_key:
            st.error("👈 左のメニューからAPIキーを入力してください。")
        elif not unkou_file or not shinkou_file:
            st.warning("運行表と進行表の両方をアップロードしてください。")
        else:
            st.success("準備OK！ここに先ほど完成したチェック結果が表示されます！（これから組み込みます）")
