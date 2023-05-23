import os
from typing import List

from save_db_utils import add_notion_db_page, write_notion_db_page
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError
from summarize_utils import get_pdf_text, get_sections, load_pdf, make_xml_file, write_markdown

# ボットトークンとソケットモードハンドラーを使ってアプリを初期化
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


def get_thread_messages(channel_id: str, thread_ts: List[str]) -> List[dict]:
    """
    指定したチャンネルの指定したスレッドのメッセージを取得します．
    Args:
        channel_id: チャンネルID
        thread_ts: スレッドのタイムスタンプ
    Returns:
        thread_messages: スレッドのメッセージ
    """
    try:
        result = app.client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
            limit=1000,
        )
        thread_messages = result["messages"]
    except SlackApiError as e:
        print(f"Error getting thread messages: {e}")

    return thread_messages


@app.event("app_mention")
def handle_app_mention_events(body, logger, say) -> None:
    """
    メンションされたときに発火して，Notionページに作成し，要約を書き込む
    Args:
        body: リクエストボディ
        logger: ロガー
        say: メッセージを送信する関数
    """
    logger.info(body)
    bot_user_id = body["authorizations"][0]["user_id"]
    text = body["event"]["text"]
    user = body["event"]["user"]

    channel_id = body["event"]["channel"]
    if "thread_ts" in body["event"].keys():
        thread_ts = body["event"]["thread_ts"]
        thread_messages = get_thread_messages(channel_id, thread_ts)
    else:
        thread_ts = body["event"]["ts"]
        thread_messages = [body["event"]]

    text = text.replace(f"<@{bot_user_id}>", "").strip()
    # デバック用
    if text == "ping":
        say(text=f"<@{user}> pong :robot_face:", thread_ts=thread_ts)
    # 指定されたチャンネル以外は処理しない
    elif channel_id not in ["<channel id>"]:
        say(text=f"<@{user}> this channel is not permitted", thread_ts=thread_ts)

    else:
        # PDFファイルを取得
        thread_text = thread_messages[0]["text"]
        pdf_file_name, pdf_file_path = load_pdf(thread_text)

        # セクション分割して，要約した文章を作成
        root = make_xml_file(pdf_file_name)
        sections = get_sections(root)
        pdf_text = get_pdf_text(pdf_file_path)
        markdown_text = write_markdown(sections, pdf_text.split(" "), pdf_file_name)

        # for debug
        # ここでtext類を保存する
        with open("./tmp.txt", mode="w") as f:
            f.write(thread_text)
        with open("./tmp_markdown.txt", mode="w") as f:
            f.write(markdown_text)

        with open("./tmp.txt", mode="r") as f:
            thread_text = f.read()
        with open("./tmp_markdown.txt", mode="r") as f:
            markdown_text = f.read()

        # Notionにページを作成し，要約を書き込む
        paper, database_id = add_notion_db_page(thread_text, is_debug=True)
        write_notion_db_page(markdown_text, paper, database_id, is_debug=True)

        # 要約をSlackのリプライに送信
        say(
            text=f"<@{user}>\n{markdown_text}",
            thread_ts=thread_ts,
        )


if __name__ == "__main__":
    # アプリを起動
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
