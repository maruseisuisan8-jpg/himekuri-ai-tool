import os
from dotenv import load_dotenv
import json
import base64
from datetime import date

import streamlit as st
from openai import OpenAI
from PIL import Image, ImageOps
load_dotenv()
st.set_page_config(page_title="日めくり運勢 AI 発信ツール", page_icon="🌞", layout="wide")

st.title("☀️ 日めくり運勢 AI 発信ツール")
st.caption("日めくりを撮影 → AIが内容を読み取り → わかりやすく書き換え → Instagram / note 用の文章を作成")

api_key = os.getenv("OPENAI_API_KEY", "")
if not api_key:
    st.warning("OPENAI_API_KEY が設定されていません。先に設定してください。")

uploaded = st.file_uploader("今日の日めくり写真を選択してください", type=["jpg", "jpeg", "png", "webp"])

style = st.selectbox(
    "文章の雰囲気",
    ["やさしく親しみやすい", "前向きで元気", "落ち着いた大人向け", "経営者・仕事向け"]
)

brand = st.text_input("発信アカウント名（任意）", value="日めくり一言開運")
hashtags = st.text_input("追加したいハッシュタグ（任意）", value="#今日の運勢 #開運 #日めくり")

if "result" not in st.session_state:
    st.session_state.result = None

if uploaded:
    image = ImageOps.exif_transpose(Image.open(uploaded))
    st.image(image, caption="アップロードした日めくり", width=420)

    if st.button("AIで読み取り・投稿文を作る", type="primary"):
        if not api_key:
            st.error("先に OPENAI_API_KEY を設定してください。")
            st.stop()

        b64 = base64.b64encode(uploaded.getvalue()).decode("utf-8")
        mime = uploaded.type or "image/jpeg"

        prompt = f"""
あなたは「日めくり運勢」の編集者です。
添付画像を正確に読み取ってください。読めない箇所は推測せず「確認できません」としてください。

今日の日付は {date.today().isoformat()} です。
文章の雰囲気: {style}
発信名: {brand}

必ずJSONのみで返してください。
{{
  "calendar_date": "画像から確認できた日付",
  "original_fortune": "画像に書かれた運勢の原文。読めない部分は確認できません",
  "easy_explanation": "小学生でも意味がわかる、短く噛み砕いた説明",
  "today_action": ["今日やると良いこと1", "今日やると良いこと2", "今日気をつけること"],
  "instagram_caption": "Instagram投稿文。絵文字は少なめ。200〜500字程度。最後に {hashtags} を自然に付ける",
  "note_draft": "note用の少し丁寧な記事。見出しを付けて600〜1000字程度",
  "short_story": "Instagramストーリーズ向け。50〜100字"
}}

重要:
- 占いの内容を勝手に追加・改変しない。
- 画像に書かれていない事実は作らない。
"""

        client = OpenAI(api_key=api_key)
        with st.spinner("日めくりを読み取り、投稿文を作成しています..."):
            response = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": f"data:{mime};base64,{b64}"}
                    ]
                }]
            )

        raw = response.output_text.strip()
        try:
            st.session_state.result = json.loads(raw)
        except json.JSONDecodeError:
            st.error("AIの返答を整理できませんでした。もう一度実行してください。")
            st.text_area("AIの返答", raw, height=400)
            st.stop()

data = st.session_state.result

if data:
    st.success("作成できました。内容を確認して、そのままコピーできます。")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📅 日めくりの内容")
        st.write("**日付:**", data.get("calendar_date", ""))
        st.write("**原文:**", data.get("original_fortune", ""))
        st.write("**わかりやすく言うと:**", data.get("easy_explanation", ""))

    with c2:
        st.subheader("✅ 今日のポイント")
        for item in data.get("today_action", []):
            st.write("・", item)

    st.subheader("📸 Instagram投稿文")
    st.text_area("Instagram", value=data.get("instagram_caption", ""), height=260)

    st.subheader("📝 note用記事")
    st.text_area("note", value=data.get("note_draft", ""), height=420)

    st.subheader("📱 ストーリーズ用")
    st.text_area("Story", value=data.get("short_story", ""), height=120)

    export = json.dumps(data, ensure_ascii=False, indent=2)
    st.download_button(
        "結果をJSONで保存",
        export,
        file_name=f"himekuri_{date.today().isoformat()}.json",
        mime="application/json"
    )

    st.divider()
    st.subheader("📤 Instagram自動投稿")
    st.info(
        "完全自動投稿には、Instagram Login用のMetaアプリ設定、Instagramユーザーアクセストークン、"
        "およびMetaから取得できる公開HTTPS画像URLが必要です。設定後に投稿ボタンを追加します。"
    )

st.divider()
st.markdown(
    "### 現在できること\n"
    "1. 毎日の日めくりをスマホで撮影\n"
    "2. 写真をアップロード\n"
    "3. AIが文字と運勢を読み取る\n"
    "4. 意味をわかりやすく整理\n"
    "5. Instagram用・note用・ストーリーズ用を自動作成\n\n"
    "### 次に追加する機能\n"
    "- Instagram Professional Accountへの自動投稿\n"
    "- 毎朝決まった時刻への投稿予約\n"
    "- 投稿履歴の保存")



# Instagram自動投稿テスト
st.divider()
st.subheader("📸 Instagramへ投稿")

instagram_image_url = st.text_input(
    "WordPress画像URL",
    placeholder="https://anorifugu.co.jp/wp-content/uploads/..."
)

instagram_caption = st.text_area(
    "Instagram投稿文",
    height=180
)

st.info("画像URLと投稿文を確認してから投稿します。")

if st.button("📤 Instagramへ投稿する", type="primary"): 
    st.write("投稿ボタンが押されました")

