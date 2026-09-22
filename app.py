import os
import json
import base64
from datetime import date

import requests
import streamlit as st
from openai import OpenAI
from PIL import Image, ImageOps

# =========================================================
# 基本設定
# =========================================================
st.set_page_config(
    page_title="日めくり一言開運 AI",
    page_icon="🌿",
    layout="wide",
)

st.title("🌿 日めくり一言開運 AI")
st.caption(
    "日めくりを撮影 → AIが一言を読み取る → "
    "やさしい開運画像と投稿文を作る → Instagramへ投稿"
)

# Streamlit Community Cloud の Secrets を優先し、
# ローカル実行時は環境変数も使えるようにする
def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(name, default)

api_key = get_secret("OPENAI_API_KEY")
text_model = get_secret("OPENAI_MODEL", "gpt-5.6-luna")
image_model = get_secret("OPENAI_IMAGE_MODEL", "gpt-image-2")

client = OpenAI(api_key=api_key) if api_key else None

# =========================================================
# セッション
# =========================================================
defaults = {
    "result": None,
    "generated_image_bytes": None,
    "generated_image_name": None,
    "ig_creation_id": None,
    "wp_image_url": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =========================================================
# 入力
# =========================================================
uploaded = st.file_uploader(
    "今日の日めくり写真を選択してください",
    type=["jpg", "jpeg", "png", "webp"],
)

hashtags = st.text_input(
    "ハッシュタグ",
    value="#今日の運勢 #開運 #日めくり #日めくり一言開運",
)

st.info(
    "元の日めくり写真は読み取り専用です。"
    "Instagramには、AIが新しく作った画像を投稿します。"
)

if uploaded:
    original_image = ImageOps.exif_transpose(Image.open(uploaded))
    st.image(
        original_image,
        caption="読み取り用の日めくり写真（この写真は投稿しません）",
        width=360,
    )

# =========================================================
# 1. 日めくりを読み取り、投稿文を作成
# =========================================================
if uploaded and st.button("① 今日の一言を読み取る", type="primary"):
    if not client:
        st.error("OPENAI_API_KEY が設定されていません。")
        st.stop()

    # 前回データをリセット
    st.session_state.result = None
    st.session_state.generated_image_bytes = None
    st.session_state.generated_image_name = None
    st.session_state.ig_creation_id = None
    st.session_state.wp_image_url = None

    b64 = base64.b64encode(uploaded.getvalue()).decode("utf-8")
    mime = uploaded.type or "image/jpeg"

    prompt = f"""
あなたは「日めくり一言開運」の編集者です。
添付の日めくり画像を正確に読み取ってください。
読めない箇所は絶対に推測せず「確認できません」としてください。

今日の日付は {date.today().isoformat()} です。

必ず次のJSONだけを返してください。
{{
  "calendar_date": "画像から確認できた日付",
  "one_word": "画像の中心となる今日の一言・格言を原文どおり",
  "original_fortune": "画像に書かれた運勢や説明の原文",
  "easy_explanation": "今日の一言を、やさしく前向きに100〜180字で説明",
  "today_action": [
    "今日できる小さな行動1",
    "今日できる小さな行動2",
    "今日気をつけたいこと"
  ],
  "instagram_caption": "Instagram用。最初に日付と今日の一言。やさしく親しみやすい文章を200〜400字。最後に {hashtags}",
  "image_mood": "今日の一言に合う自然風景のイメージを日本語で短く"
}}

重要:
- 元画像の内容を勝手に変えない。
- 占い・格言にない具体的な事実を作らない。
- 人を不安にさせる断定表現は避ける。
"""

    with st.spinner("日めくりを読み取っています..."):
        response = client.responses.create(
            model=text_model,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime};base64,{b64}",
                    },
                ],
            }],
        )

    raw = response.output_text.strip()

    # ```json ... ``` が返った場合にも対応
    if raw.startswith("```"):
        raw = raw.replace("```json", "", 1).replace("```", "").strip()

    try:
        st.session_state.result = json.loads(raw)
        st.success("今日の一言を読み取りました。")
    except json.JSONDecodeError:
        st.error("AIの返答を整理できませんでした。もう一度実行してください。")
        st.text_area("AIの返答", raw, height=300)
        st.stop()

data = st.session_state.result

# =========================================================
# 2. 内容確認・AI画像生成
# =========================================================
if data:
    st.divider()
    st.subheader("☀️ 今日の一言")

    c1, c2 = st.columns(2)
    with c1:
        st.write("**日付:**", data.get("calendar_date", ""))
        st.write("**今日の一言:**", data.get("one_word", ""))
        st.write("**元の内容:**", data.get("original_fortune", ""))

    with c2:
        st.write("**やさしく言うと:**")
        st.write(data.get("easy_explanation", ""))
        st.write("**今日のポイント:**")
        for item in data.get("today_action", []):
            st.write("・", item)

    st.subheader("📸 Instagram投稿文")
    instagram_caption = st.text_area(
        "投稿文",
        value=data.get("instagram_caption", ""),
        height=230,
        key="instagram_caption_editor",
    )

    if st.button("② やさしい開運画像を作る", type="primary"):
        if not client:
            st.error("OPENAI_API_KEY が設定されていません。")
            st.stop()

        one_word = data.get("one_word", "")
        calendar_date = data.get("calendar_date", "")
        explanation = data.get("easy_explanation", "")
        image_mood = data.get("image_mood", "")

        image_prompt = f"""
Instagramの「日めくり一言開運」用の正方形ポスターを1枚作ってください。

【固定する世界観】
- やさしい、穏やか、温かい、上品
- 日本の自然を感じる美しい風景
- 朝日、夕日、穏やかな海、空、山、草花、木漏れ日などを、
  今日の言葉に合うように自然に選ぶ
- パステル調の光、柔らかな空気感
- 威圧的・力強すぎる・暗すぎる表現は禁止
- 人物は基本的に入れない
- 写真のように美しいが、少し絵画的で癒やされる雰囲気
- Instagramで見た瞬間に心が落ち着くデザイン
- 余白を十分に取り、文字を読みやすくする

【文字の雰囲気】
- 日本語は、細めで優しい手書き風・筆文字風
- 太く荒々しい書、いかつい書体、極端な黒太字は禁止
- 色は焦げ茶、淡い茶、生成りなど自然な色
- 装飾は小さな葉や細い曲線程度で上品に

【必ず表示する内容】
上部に小さく「今日の一言」
日付: {calendar_date}
中央に一番大きく「{one_word}」
その下に、読みやすい小さめの文字で:
「{explanation}」
下部に小さく「日めくり一言開運」
最後に「今日も、よい一日を」

【今日の風景イメージ】
{image_mood}

重要:
- 日本語をできるだけ正確に表示する。
- 文字が風景に埋もれないようにする。
- 文字量が多すぎる場合は説明文を自然に短くしてよいが、
  「{one_word}」は絶対に変えない。
- ロゴ、透かし、SNSのUIは入れない。
"""

        try:
            with st.spinner("今日の一言に合う、やさしい画像を作っています..."):
                image_result = client.images.generate(
                    model=image_model,
                    prompt=image_prompt,
                    size="1024x1024",
                    quality="medium",
                    output_format="png",
                    n=1,
                )

            image_b64 = image_result.data[0].b64_json
            if not image_b64:
                st.error("画像データを取得できませんでした。")
                st.stop()

            image_bytes = base64.b64decode(image_b64)
            st.session_state.generated_image_bytes = image_bytes
            st.session_state.generated_image_name = (
                f"himekuri_kaiun_{date.today().isoformat()}.png"
            )
            st.session_state.ig_creation_id = None
            st.session_state.wp_image_url = None
            st.success("新しい開運画像ができました。")

        except Exception as e:
            st.error("AI画像の作成に失敗しました。")
            st.write(str(e))

# =========================================================
# 3. 生成画像の確認
# =========================================================
if st.session_state.generated_image_bytes:
    st.divider()
    st.subheader("🌿 Instagramに載せる画像")
    st.image(
        st.session_state.generated_image_bytes,
        caption="このAI画像をInstagramへ投稿します",
        width=600,
    )

    st.download_button(
        "画像を保存する",
        data=st.session_state.generated_image_bytes,
        file_name=st.session_state.generated_image_name or "himekuri_kaiun.png",
        mime="image/png",
    )

    if data:
        instagram_caption = st.text_area(
            "最終確認：Instagram投稿文",
            value=data.get("instagram_caption", ""),
            height=230,
            key="instagram_caption_final",
        )
    else:
        instagram_caption = ""

    # =====================================================
    # 4. WordPressへAI画像をアップロード → IGコンテナ作成
    # =====================================================
    st.divider()
    st.subheader("📤 Instagram投稿")

    st.info(
        "まず投稿準備をします。この時点ではまだInstagramには公開されません。"
    )

    if st.button("③ Instagram投稿の準備をする"):
        ig_token = get_secret("INSTAGRAM_ACCESS_TOKEN")
        ig_user_id = get_secret("INSTAGRAM_USER_ID")
        wp_url = get_secret("WORDPRESS_URL")
        wp_username = get_secret("WORDPRESS_USERNAME")
        wp_password = get_secret("WORDPRESS_APP_PASSWORD")

        if not ig_token or not ig_user_id:
            st.error("Instagramの接続情報が不足しています。")
            st.stop()

        if not wp_url or not wp_username or not wp_password:
            st.error("WordPressの接続情報が不足しています。")
            st.stop()

        try:
            with st.spinner("AI画像を公開用に準備しています..."):
                image_bytes = st.session_state.generated_image_bytes
                filename = st.session_state.generated_image_name or (
                    f"himekuri_kaiun_{date.today().isoformat()}.png"
                )

                wp_response = requests.post(
                    f"{wp_url.rstrip('/')}/wp-json/wp/v2/media",
                    auth=(wp_username, wp_password),
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"',
                        "Content-Type": "image/png",
                    },
                    data=image_bytes,
                    timeout=60,
                )

            if wp_response.status_code != 201:
                st.error("WordPressへの画像準備に失敗しました。")
                st.write("エラー番号:", wp_response.status_code)
                try:
                    st.write(wp_response.json())
                except Exception:
                    st.write(wp_response.text[:500])
                st.stop()

            media = wp_response.json()
            image_url = media.get("source_url", "")

            if not image_url:
                st.error("公開画像URLを取得できませんでした。")
                st.stop()

            st.session_state.wp_image_url = image_url

            with st.spinner("Instagram投稿を準備しています..."):
                container_response = requests.post(
                    f"https://graph.instagram.com/{ig_user_id}/media",
                    data={
                        "image_url": image_url,
                        "caption": instagram_caption,
                        "access_token": ig_token,
                    },
                    timeout=60,
                )

            container_data = container_response.json()

            if container_response.ok and container_data.get("id"):
                st.session_state.ig_creation_id = container_data["id"]
                st.success("Instagram投稿の準備ができました。")
                st.warning("まだ公開されていません。下で最終確認してください。")
            else:
                st.error("Instagram投稿の準備に失敗しました。")
                st.write(
                    container_data.get("error", {}).get(
                        "message", "詳細不明"
                    )
                )

        except Exception as e:
            st.error("投稿準備中にエラーが発生しました。")
            st.write(str(e))

# =========================================================
# 5. Instagramへ実際に公開
# =========================================================
if st.session_state.ig_creation_id:
    st.divider()
    st.success("投稿準備済みです。")

    confirm = st.checkbox(
        "画像と文章を確認しました。Instagramへ投稿します。"
    )

    if st.button(
        "④ Instagramへ公開する",
        type="primary",
        disabled=not confirm,
    ):
        ig_token = get_secret("INSTAGRAM_ACCESS_TOKEN")
        ig_user_id = get_secret("INSTAGRAM_USER_ID")
        creation_id = st.session_state.ig_creation_id

        try:
            with st.spinner("Instagramへ投稿しています..."):
                publish_response = requests.post(
                    f"https://graph.instagram.com/{ig_user_id}/media_publish",
                    data={
                        "creation_id": creation_id,
                        "access_token": ig_token,
                    },
                    timeout=60,
                )

            publish_data = publish_response.json()

            if publish_response.ok and publish_data.get("id"):
                st.success("Instagramへの投稿が完了しました！")
                st.write("投稿ID:", publish_data.get("id"))
                st.session_state.ig_creation_id = None
                st.session_state.wp_image_url = None
            else:
                st.error("Instagramへの投稿に失敗しました。")
                st.write(
                    publish_data.get("error", {}).get(
                        "message", "詳細不明"
                    )
                )

        except Exception as e:
            st.error("Instagram投稿中にエラーが発生しました。")
            st.write(str(e))

# =========================================================
# 接続確認
# =========================================================
st.divider()
with st.expander("🔗 Instagram接続を確認する"):
    if st.button("Instagramの接続を確認"):
        ig_token = get_secret("INSTAGRAM_ACCESS_TOKEN")
        ig_user_id = get_secret("INSTAGRAM_USER_ID")

        if not ig_token or not ig_user_id:
            st.error("Instagramの接続情報が設定されていません。")
        else:
            try:
                response = requests.get(
                    "https://graph.instagram.com/me",
                    params={
                        "fields": "id,username",
                        "access_token": ig_token,
                    },
                    timeout=20,
                )
                ig_data = response.json()

                if response.ok and ig_data.get("id"):
                    st.success("Instagramに接続できました。")
                    st.write(
                        "Instagramユーザー名:",
                        ig_data.get("username", "確認できませんでした"),
                    )
                    st.write(
                        "ユーザーID一致:",
                        str(ig_data.get("id")) == str(ig_user_id),
                    )
                else:
                    st.error("Instagramへの接続を確認できませんでした。")
                    st.write(
                        ig_data.get("error", {}).get(
                            "message", "詳細不明"
                        )
                    )
            except Exception as e:
                st.error("接続確認中にエラーが発生しました。")
                st.write(str(e))

st.divider()
st.markdown(
    """
### 毎日の使い方
1. iPhoneで日めくりを撮影
2. このアプリで写真を選ぶ
3. 「今日の一言を読み取る」
4. 「やさしい開運画像を作る」
5. 画像と文章を確認
6. Instagram投稿の準備
7. 最後にInstagramへ公開

**元の日めくり写真はInstagramには投稿されません。**
"""
)
