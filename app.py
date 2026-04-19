import streamlit as st
import pdfplumber
import google.generativeai as genai
import json
import re
import time

# ==========================================
# 画面構成（UI）
# ==========================================
st.set_page_config(page_title="ラジオ進行表チェック", layout="wide")
st.title("📻 運行表・進行表 自動チェックシステム")

st.sidebar.header("⚙️ 設定")
api_key = st.sidebar.text_input("Gemini APIキーを入力", type="password")

tab1, tab2 = st.tabs(["事前チェック (ゲラ版)", "直前チェック (確定版)"])

with tab1:
    st.header("ゲラ版と週間番組表の比較")
    st.info("※この機能は現在開発中です。今後、ここに週間番組表との比較機能を実装します。")

# ==========================================
# 裏側の処理関数
# ==========================================
def identify_program_name(pdf_file, model):
    pdf_file.seek(0) # ファイルの読み込み位置をリセット
    try:
        with pdfplumber.open(pdf_file) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            
        prompt = f"""
        以下のラジオ番組の進行表テキストから、この「番組名」だけを抽出してください。
        余計な文章は一切含まず、番組名のみを返してください。（例：「あさミミ」「LIVE DRIVE」など）
        【テキスト】\n{first_page_text}
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        st.error(f"番組名の特定に失敗しました: {e}")
        return None

def extract_and_parse(pdf_file, is_unkou, target_keyword, model, progress_text):
    pdf_file.seek(0)
    pages_text = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text: continue
                if is_unkou and (target_keyword not in text): continue
                pages_text.append(text)
    except Exception as e:
        st.error(f"PDF読み込み失敗: {e}")
        return []

    doc_type = "運行表" if is_unkou else "進行表"
    all_results = []
    chunk_size = 5
    
    # プログレスバーの表示
    progress_bar = st.progress(0, text=f"{progress_text} (全{len(pages_text)}ページ)")
    
    for i in range(0, len(pages_text), chunk_size):
        chunk = "\n".join(pages_text[i:i+chunk_size])
        prompt = f"""
        あなたはラジオ局の優秀な運行管理者です。
        以下のテキストデータは{target_keyword}の{doc_type}の一部です。
        ここから、「放送時刻」「コーナー名」「CM秒数」「スポンサー名（提供）」を抽出し、JSON形式の配列で出力してください。
        ・JSON以外の文章は一切出力しないでください。抽出できない項目は null にしてください。
        ・CM秒数は数字のみ（例: 20, 60, 135）で抽出してください。
        【テキスト】\n{chunk}
        """
        try:
            response = model.generate_content(prompt)
            res_text = re.sub(r"```json|```", "", response.text).strip()
            if res_text and res_text != "[]":
                parsed_data = json.loads(res_text)
                if isinstance(parsed_data, list): all_results.extend(parsed_data)
        except:
            pass # エラー時はスキップ
            
        time.sleep(1)
        # プログレスバーの更新
        progress = min((i + chunk_size) / len(pages_text), 1.0)
        progress_bar.progress(progress, text=f"{progress_text} ({min(i+chunk_size, len(pages_text))}/{len(pages_text)}ページ完了)")
        
    return all_results

def normalize_time(time_str):
    if not time_str or str(time_str) == "None": return ""
    match = re.search(r'(\d{1,2}):(\d{2})', str(time_str))
    if match:
        h, m = match.groups()
        return f"{int(h)}:{m}"
    return str(time_str)

# ==========================================
# 直前チェック (確定版) タブの処理
# ==========================================
with tab2:
    st.header("運行表と進行表の突き合わせ")
    st.write("PDFをアップロードしてチェックを行います。")
    
    col1, col2 = st.columns(2)
    with col1:
        unkou_file = st.file_uploader("📄 運行表のPDF", type="pdf")
    with col2:
        shinkou_file = st.file_uploader("📄 進行表のPDF", type="pdf")

    if st.button("🚀 チェック開始", type="primary", use_container_width=True):
        if not api_key:
            st.error("👈 左のメニューからGemini APIキーを入力してください。")
        elif not unkou_file or not shinkou_file:
            st.warning("⚠️ 運行表と進行表の両方をアップロードしてください。")
        else:
            try:
                # APIの準備
                genai.configure(api_key=api_key)
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                model_name = next((name for name in available_models if '2.5-flash' in name), None)
                if not model_name:
                    model_name = next((name for name in available_models if '1.5-flash' in name), available_models[0])
                model = genai.GenerativeModel(model_name)
                
                with st.status("🔍 解析を実行中...", expanded=True) as status:
                    st.write(f"🤖 使用モデル: {model_name}")
                    
                    # 1. 番組名の特定
                    target_program = identify_program_name(shinkou_file, model)
                    if not target_program:
                        status.update(label="❌ エラー: 番組名を特定できませんでした", state="error")
                        st.stop()
                    st.write(f"✅ 番組名「{target_program}」を検出しました")
                    
                    # 2. 運行表の解析
                    unkou_data = extract_and_parse(unkou_file, True, target_program, model, "📄 運行表から該当箇所を抽出中")
                    
                    # 3. 進行表の解析
                    shinkou_data = extract_and_parse(shinkou_file, False, target_program, model, "📄 進行表を解析中")

                    status.update(label="✅ データの抽出が完了しました！突き合わせを開始します。", state="complete")

                # 4. 突き合わせ処理と結果表示
                st.divider()
                st.subheader(f"🚨 【{target_program}】 突き合わせ結果")
                
                error_count = 0
                for shinkou in shinkou_data:
                    corner = str(shinkou.get("コーナー名") or "").strip()
                    if not corner or corner == "None": continue
                    
                    s_time = str(shinkou.get("放送時刻") or "")
                    s_time_norm = normalize_time(s_time)
                        
                    matched_unkou = None
                    for u in unkou_data:
                        u_corn = str(u.get("コーナー名") or "").strip()
                        if not u_corn or u_corn == "None": continue
                        u_time = str(u.get("放送時刻") or "")
                        if (corner in u_corn or u_corn in corner) and s_time_norm == normalize_time(u_time):
                            matched_unkou = u
                            break
                    
                    if not matched_unkou:
                        for u in unkou_data:
                            u_corn = str(u.get("コーナー名") or "").strip()
                            if not u_corn or u_corn == "None": continue
                            if corner in u_corn or u_corn in corner:
                                matched_unkou = u
                                break

                    if matched_unkou:
                        errors = []
                        u_time = str(matched_unkou.get("放送時刻") or "")
                        if s_time_norm != normalize_time(u_time):
                            errors.append(f"**時刻**： 進行表 `{s_time}` / 運行表 `{u_time}`")
                        if str(shinkou.get("CM秒数")) != str(matched_unkou.get("CM秒数")):
                            errors.append(f"**CM秒**： 進行表 `{shinkou.get('CM秒数')}` / 運行表 `{matched_unkou.get('CM秒数')}`")
                        if str(shinkou.get("スポンサー名")) != str(matched_unkou.get("スポンサー名")):
                            errors.append(f"**提供**： 進行表 `{shinkou.get('スポンサー名')}` / 運行表 `{matched_unkou.get('スポンサー名')}`")
                            
                        if errors:
                            with st.expander(f"⚠️ {corner} (進行表: {s_time})", expanded=True):
                                for err in errors:
                                    st.write(f"- ❌ {err}")
                            error_count += 1
                            
                if error_count == 0:
                    st.success("✅ 運行表と進行表の間に相違は見つかりませんでした！完璧です！")
                else:
                    st.error(f"⚠️ 合計 {error_count} 件の相違が見つかりました。")

            except Exception as e:
                st.error(f"予期せぬエラーが発生しました: {e}")
