import os
from typing import Tuple

import arxiv
import requests

DATABASE_ID_DICT = {
    "<Page Name>": "<Database ID>",
}

HEADERS = {
    "Authorization": "Bearer " + os.environ.get("NOTION_TOKEN"),
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

CATEGORY_LABELS = {
    "<カテゴリー ラベル>": "説明",
}

PROPERTIES = {
    "Name": {
        "title": [
            {
                "text": {
                    "content": "",  # ここを変える
                }
            }
        ]
    },
    "Published": {
        "date": {
            "start": "",  # ここを変える
        }
    },
    "URL": {
        "url": "",  # ここを変える
    },
    "Author": {
        "rich_text": [
            {
                "text": {
                    "content": "",  # ここを変える
                },
            }
        ],
    },
    "read": {
        "checkbox": False,  # ここは固定
    },
    "tag": {
        "multi_select": [],  # 辞書を追加
    },
    "Summary": {
        "rich_text": [
            {
                "text": {
                    "content": "",
                },
            }
        ],
    },
    "Abstract": {
        "rich_text": [
            {
                "text": {
                    "content": "",
                },
            }
        ],
    },
}

CREATE_URL = "https://api.notion.com/v1/pages"


def get_paper(text: str) -> arxiv.Result:
    """
    テキストからarXivの論文を取得
    Args:
        text: テキスト
    returns:
        paper: arXivの論文
    """
    arxiv_id = text.split("\n")[2].split("/")[-1]
    if arxiv_id[-1] == ">":
        arxiv_id = arxiv_id[:-1]
    paper = next(arxiv.Search(id_list=[arxiv_id]).results())
    return paper


def get_summary(text: str) -> str:
    """
    テキストから3行要約を取得
    Args:
        text: テキスト
    Returns:
        summary: 3行要約
    """
    # 3行要約の抽出
    summary = ""
    for sentence in text.split("-")[-3:]:
        summary += f"- {sentence}"

    if summary[-2:] == "\n":
        # 最後の\nを除去
        summary = summary[:-2]

    return summary


def get_database_id(text: str) -> str:
    """
    テキストからデータベースIDを取得
    Args:
        text: テキスト
    Returns:
        database_id: データベースID
    """
    for key, database_id in DATABASE_ID_DICT.items():
        if key in text.split("\n")[0].lower():
            return database_id


def create_page(paper: arxiv.Result, summary: str, database_id: str, is_debug: bool = False) -> None:
    """
    Notionにページを作成
    Args:
        paper: arXivの論文
        summary: 3行要約
        database_id: データベースID
        is_debug: デバッグモード
    """
    # プロパティの設定
    PROPERTIES["Name"]["title"][0]["text"]["content"] = paper.title
    PROPERTIES["Published"]["date"]["start"] = paper.published.strftime("%Y-%m-%d")
    PROPERTIES["URL"]["url"] = paper.entry_id
    PROPERTIES["Author"]["rich_text"][0]["text"]["content"] = ", ".join([author.name for author in paper.authors])
    PROPERTIES["tag"]["multi_select"] = [
        {"name": CATEGORY_LABELS[category]} for category in paper.categories if category in CATEGORY_LABELS
    ]
    PROPERTIES["Summary"]["rich_text"][0]["text"]["content"] = summary
    PROPERTIES["Abstract"]["rich_text"][0]["text"]["content"] = paper.summary

    payload = {"parent": {"database_id": database_id}, "properties": PROPERTIES}
    response = requests.post(CREATE_URL, headers=HEADERS, json=payload)
    if is_debug:
        assert response.status_code == 200, f"{response.content}"


def get_page_id(title: str, database_id: str) -> str:
    """
    タイトルからページIDを取得
    Args:
        title: タイトル
        database_id: データベースID
    Returns:
        page_id: ページID
    """
    # タイトルを検索して，ページIDを取得
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    payload = {"filter": {"property": "Name", "rich_text": {"equals": title}}}
    response = requests.post(url, json=payload, headers=HEADERS)
    page_id = response.json()["results"][0]["id"]
    return page_id


def write_to_notion_page(markdown_text: str, paper: arxiv.Result, page_id: str, is_debug: bool = False) -> None:
    """
    Notionのページに書き込み
    Args:
        markdown_text: Markdown形式のテキスト
        paper: arXivの論文
        page_id: ページID
        is_debug: デバッグモード
    """
    payload = {"children": []}
    for sentence in markdown_text.split("\n"):
        if "#" in sentence:
            n_head = len(sentence.split(" ")[0])
            if n_head >= 4:
                payload["children"].append(
                    {"paragraph": {"rich_text": [{"text": {"content": " ".join(sentence.split(" ")[1:])}}]}}
                )
            else:
                payload["children"].append(
                    {f"heading_{n_head}": {"rich_text": [{"text": {"content": " ".join(sentence.split(" ")[1:])}}]}}
                )
        else:
            payload["children"].append({"paragraph": {"rich_text": [{"text": {"content": sentence}}]}})

    # 元論文のPDFを追加
    payload["children"].append({"heading_1": {"rich_text": [{"text": {"content": "元論文"}}]}})
    payload["children"].append(
        {"pdf": {"type": "external", "external": {"url": f"https://arxiv.org/pdf/{paper.entry_id.split('/')[-1]}.pdf"}}}
    )

    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    response = requests.patch(url, json=payload, headers=HEADERS)
    if is_debug:
        assert response.status_code == 200, f"{response.content}"


def add_notion_db_page(text: str, is_debug: bool = False) -> Tuple[arxiv.Result, str]:
    """
    テキストからNotionのページを作成
    Args:
        text: テキスト
        is_debug: デバッグモード
    Returns:
        paper: arXivの論文
        database_id: データベースID
    """
    paper = get_paper(text)
    summary = get_summary(text)
    database_id = get_database_id(text)
    create_page(paper, summary, database_id, is_debug=is_debug)
    return paper, database_id


def write_notion_db_page(markdown_text: str, paper: arxiv.Result, database_id: str, is_debug: bool = False) -> None:
    """
    Notionのページに書き込み
    Args:
        markdown_text: Markdown形式のテキスト
        paper: arXivの論文
        database_id: データベースID
        is_debug: デバッグモード
    """
    page_id = get_page_id(paper.title, database_id)
    write_to_notion_page(markdown_text, paper, page_id, is_debug=is_debug)
