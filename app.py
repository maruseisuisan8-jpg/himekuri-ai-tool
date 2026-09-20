import os
from dotenv import load_dotenv
import json
import base64
from datetime import date
import requests

import streamlit as st
from openai import OpenAI
from PIL import Image, ImageOps

load_dotenv()

st.set_page_config(
    page_title="日めくり運勢 AI 発信ツール",
    page_icon="🌞",
    layout="wide"
)

st.title("☀️ 日めくり運勢 AI 発信ツール")
st.caption(
    "日めくりを撮影 → AIが内容を読み取り → "
    "わかりやすく書き換え → Instagram / note 用の文章を作成"
)

api_key = os.getenv("OPENAI_API_KEY", "")

if not api_key:
    st.warning("OPENAI_API_KEY が設定されていません。先に設定してください。")

uploaded = st.file_uploader(
    "今日の日めくり写真を選択してください",
    type=["jpg", "jpeg", "png", "webp"]
)

style = st.selectbox(
    "文章の雰囲気",
    [
        "やさしく親しみやすい",
        "前向きで元気",
        "落ち着いた大人向け",
        "経営者・仕事向け",
    ]
)

brand = st.text_input(
    "発信アカウント名（任意）",
    value="日めくり一言開運"
)

hashtags = st.text_input(
    "追加したいハッシュタグ（任意）",
    value="#今日の運勢 #開運 #日めくり"
)

if "result" not in st.session_state:
    st.session_state.result = None

if "wp_image_url" not in st.session_state:
    st.session_state.wp_image_url = None

if "ig_creation_id" not in st.session_state:
    st.session_state.ig_creation_id = None


# --------------------------------------------------
# AI読み取り
# --------------------------------------------------

if uploaded:
    image = ImageOps.exif_transpose(Image.open(uploaded))
    st.image(
        image,
        caption="アップロードした日めくり",
        width=420
    )

    if st.button(
        "AIで読み取り・投稿文を作る",
        type="primary"
    ):
        if not api_key:
            st.error(
                "先に OPENAI_API_KEY を設定してください。"
            )
            st.stop()

        # 新しい写真を読み取る時は、
        # 前回の投稿準備情報をリセット
        st.session_state.wp_image_url = None
        st.session_state.ig_creation_id = None

        b64 = base64.b64encode(
            uploaded.getvalue()
        ).decode("utf-8")

        mime = uploaded.type or "image/jpeg"

        prompt = f"""
あなたは「日めくり運勢」の編集者です。
添付画像を正確に読み取ってください。
読めない箇所は推測せず
「確認できません」としてください。

今日の日付は {date.today().isoformat()} です。
文章の雰囲気: {style}
発信名: {brand}

必ずJSONのみで返してください。
{{
  "calendar_date": "画像から確認できた日付",
  "original_fortune": "画像に書かれた運勢の原文。読めない部分は確認できません",
  "easy_explanation": "小学生でも意味がわかる、短く噛み砕いた説明",
  "today_action": [
    "今日やると良いこと1",
    "今日やると良いこと2",
    "今日気をつけること"
  ],
  "instagram_caption": "Instagram投稿文。絵文字は少なめ。200〜500字程度。最後に {hashtags} を自然に付ける",
  "note_draft": "note用の少し丁寧な記事。見出しを付けて600〜1000字程度",
  "short_story": "Instagramストーリーズ向け。50〜100字"
}}

重要:
- 占いの内容を勝手に追加・改変しない。
- 画像に書かれていない事実は作らない。
"""

        client = OpenAI(api_key=api_key)

        with st.spinner(
            "日めくりを読み取り、投稿文を作成しています..."
        ):
            response = client.responses.create(
                model=os.getenv(
                    "OPENAI_MODEL",
                    "gpt-5.6-luna"
                ),
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt
                            },
                            {
                                "type": "input_image",
                                "image_url":
                                    f"data:{mime};base64,{b64}"
                            }
                        ]
                    }
                ]
            )

        raw = response.output_text.strip()

        try:
            st.session_state.result = json.loads(raw)

        except json.JSONDecodeError:
            st.error(
                "AIの返答を整理できませんでした。"
                "もう一度実行してください。"
            )
            st.text_area(
                "AIの返答",
                raw,
                height=400
            )
            st.stop()


data = st.session_state.result


# --------------------------------------------------
# AI作成結果
# --------------------------------------------------

if data:
    st.success(
        "作成できました。内容を確認してください。"
    )

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📅 日めくりの内容")
        st.write(
            "**日付:**",
            data.get("calendar_date", "")
        )
        st.write(
            "**原文:**",
            data.get("original_fortune", "")
        )
        st.write(
            "**わかりやすく言うと:**",
            data.get("easy_explanation", "")
        )

    with c2:
        st.subheader("✅ 今日のポイント")

        for item in data.get(
            "today_action",
            []
        ):
            st.write("・", item)

    st.subheader("📸 Instagram投稿文")

    instagram_caption = st.text_area(
        "Instagram",
        value=data.get(
            "instagram_caption",
            ""
        ),
        height=260
    )

    st.subheader("📝 note用記事")

    st.text_area(
        "note",
        value=data.get(
            "note_draft",
            ""
        ),
        height=420
    )

    st.subheader("📱 ストーリーズ用")

    st.text_area(
        "Story",
        value=data.get(
            "short_story",
            ""
        ),
        height=120
    )

    export = json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    )

    st.download_button(
        "結果をJSONで保存",
        export,
        file_name=
            f"himekuri_{date.today().isoformat()}.json",
        mime="application/json"
    )

    # --------------------------------------------------
    # Instagram投稿
    # --------------------------------------------------

    st.divider()
    st.subheader("📤 Instagram投稿")

    st.info(
        "最初に「Instagram投稿の準備をする」を押してください。"
        "この段階ではInstagramには公開されません。"
        "内容を確認したあと、最後の公開ボタンを押した時だけ投稿されます。"
    )

    if st.button(
        "① Instagram投稿の準備をする"
    ):
        ig_token = os.getenv(
            "INSTAGRAM_ACCESS_TOKEN",
            ""
        )

        ig_user_id = os.getenv(
            "INSTAGRAM_USER_ID",
            ""
        )

        wp_url = os.getenv(
            "WORDPRESS_URL",
            ""
        )

        wp_username = os.getenv(
            "WORDPRESS_USERNAME",
            ""
        )

        wp_password = os.getenv(
            "WORDPRESS_APP_PASSWORD",
            ""
        )

        if uploaded is None:
            st.warning(
                "先に日めくり写真を選択してください。"
            )

        elif not ig_token or not ig_user_id:
            st.error(
                "Instagramの接続情報が不足しています。"
            )

        elif (
            not wp_url
            or not wp_username
            or not wp_password
        ):
            st.error(
                "WordPressの接続情報が不足しています。"
            )

        else:
            try:
                # ------------------------------
                # WordPressへ画像アップロード
                # ------------------------------

                with st.spinner(
                    "画像を準備しています..."
                ):
                    image_bytes = uploaded.getvalue()

                    content_type = (
                        uploaded.type
                        or "image/jpeg"
                    )

                    extension = os.path.splitext(
                        uploaded.name
                    )[1].lower()

                    if extension not in [
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".webp",
                    ]:
                        extension = ".jpg"

                    filename = (
                        "himekuri_"
                        f"{date.today().isoformat()}"
                        f"{extension}"
                    )

                    wp_response = requests.post(
                        f"{wp_url.rstrip('/')}"
                        "/wp-json/wp/v2/media",
                        auth=(
                            wp_username,
                            wp_password
                        ),
                        headers={
                            "Content-Disposition":
                                f'attachment; filename="{filename}"',
                            "Content-Type":
                                content_type,
                        },
                        data=image_bytes,
                        timeout=60,
                    )

                if wp_response.status_code != 201:
                    st.error(
                        "画像の準備に失敗しました。"
                    )
                    st.write(
                        "エラー番号:",
                        wp_response.status_code
                    )
                    st.stop()

                media = wp_response.json()

                image_url = media.get(
                    "source_url",
                    ""
                )

                if not image_url:
                    st.error(
                        "公開画像URLを取得できませんでした。"
                    )
                    st.stop()

                st.session_state.wp_image_url = (
                    image_url
                )

                # ------------------------------
                # Instagramメディアコンテナ作成
                # ここではまだ公開されない
                # ------------------------------

                with st.spinner(
                    "Instagram投稿を準備しています..."
                ):
                    container_response = (
                        requests.post(
                            "https://graph.instagram.com/"
                            f"{ig_user_id}/media",
                            data={
                                "image_url":
                                    image_url,
                                "caption":
                                    instagram_caption,
                                "access_token":
                                    ig_token,
                            },
                            timeout=60,
                        )
                    )

                container_data = (
                    container_response.json()
                )

                if (
                    container_response.ok
                    and container_data.get("id")
                ):
                    st.session_state.ig_creation_id = (
                        container_data["id"]
                    )

                    st.success(
                        "Instagram投稿の準備ができました。"
                    )

                    st.warning(
                        "まだInstagramには公開されていません。"
                        "下の内容を確認してから、"
                        "公開ボタンを押してください。"
                    )

                else:
                    st.error(
                        "Instagram投稿の準備に失敗しました。"
                    )

                    st.write(
                        container_data.get(
                            "error",
                            {}
                        ).get(
                            "message",
                            "詳細不明"
                        )
                    )

            except Exception as e:
                st.error(
                    "投稿準備中にエラーが発生しました。"
                )
                st.write(str(e))


    # --------------------------------------------------
    # 本当にInstagramへ公開
    # --------------------------------------------------

    if st.session_state.ig_creation_id:
        st.divider()

        st.success(
            "投稿準備済みです。"
        )

        st.write(
            "この下のボタンを押すと、"
            "Instagramに実際に公開されます。"
        )

        confirm = st.checkbox(
            "投稿する内容を確認しました"
        )

        if st.button(
            "② Instagramへ公開する",
            type="primary",
            disabled=not confirm
        ):
            ig_token = os.getenv(
                "INSTAGRAM_ACCESS_TOKEN",
                ""
            )

            ig_user_id = os.getenv(
                "INSTAGRAM_USER_ID",
                ""
            )

            creation_id = (
                st.session_state.ig_creation_id
            )

            try:
                with st.spinner(
                    "Instagramへ投稿しています..."
                ):
                    publish_response = (
                        requests.post(
                            "https://graph.instagram.com/"
                            f"{ig_user_id}/media_publish",
                            data={
                                "creation_id":
                                    creation_id,
                                "access_token":
                                    ig_token,
                            },
                            timeout=60,
                        )
                    )

                publish_data = (
                    publish_response.json()
                )

                if (
                    publish_response.ok
                    and publish_data.get("id")
                ):
                    st.success(
                        "Instagramへの投稿が完了しました！"
                    )

                    st.write(
                        "投稿ID:",
                        publish_data.get("id")
                    )

                    # 二重投稿防止
                    st.session_state.ig_creation_id = None
                    st.session_state.wp_image_url = None

                else:
                    st.error(
                        "Instagramへの投稿に失敗しました。"
                    )

                    st.write(
                        publish_data.get(
                            "error",
                            {}
                        ).get(
                            "message",
                            "詳細不明"
                        )
                    )

            except Exception as e:
                st.error(
                    "Instagram投稿中にエラーが発生しました。"
                )
                st.write(str(e))


# --------------------------------------------------
# Instagram接続確認
# --------------------------------------------------

st.divider()
st.subheader("🔗 Instagram接続確認")

if st.button(
    "Instagramの接続を確認する"
):
    ig_token = os.getenv(
        "INSTAGRAM_ACCESS_TOKEN",
        ""
    )

    ig_user_id = os.getenv(
        "INSTAGRAM_USER_ID",
        ""
    )

    if not ig_token or not ig_user_id:
        st.error(
            "Instagramの接続情報が設定されていません。"
        )

    else:
        try:
            response = requests.get(
                "https://graph.instagram.com/me",
                params={
                    "fields": "id,username",
                    "access_token":
                        ig_token,
                },
                timeout=20,
            )

            ig_data = response.json()

            if (
                response.ok
                and ig_data.get("id")
            ):
                st.success(
                    "Instagramに接続できました。"
                )

                st.write(
                    "Instagramユーザー名:",
                    ig_data.get(
                        "username",
                        "確認できませんでした"
                    )
                )

                st.write(
                    "ユーザーID一致:",
                    str(
                        ig_data.get("id")
                    )
                    ==
                    str(ig_user_id)
                )

            else:
                st.error(
                    "Instagramへの接続を"
                    "確認できませんでした。"
                )

                st.write(
                    ig_data.get(
                        "error",
                        {}
                    ).get(
                        "message",
                        "詳細不明"
                    )
                )

        except Exception as e:
            st.error(
                "接続確認中にエラーが発生しました。"
            )
            st.write(str(e))


# --------------------------------------------------
# 現在できること
# --------------------------------------------------

st.divider()

st.markdown(
    "### 現在できること\n"
    "1. iPhoneで日めくりを撮影・選択\n"
    "2. AIが内容を読み取る\n"
    "3. Instagram投稿文を自動作成\n"
    "4. 画像を自動で公開URL化\n"
    "5. 内容確認後、Instagramへ投稿\n\n"
    "※ Instagramへの実際の公開は、"
    "最後の「Instagramへ公開する」ボタンを"
    "押した時だけ行われます。"
)
