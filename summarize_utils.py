import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple
from xml.etree.ElementTree import Element

import arxiv
import fitz
import openai
from tqdm.auto import tqdm
from transformers import pipeline

# フォルダの作成
os.makedirs("./pdf", exist_ok=True)
os.makedirs("./xml", exist_ok=True)
os.makedirs("./pdf_images", exist_ok=True)

# OpenAIのAPIキーを設定
openai.api_key = os.environ.get("OPENAI_KEY")

MODEL_NAME = "gpt-3.5-turbo"
TEMPERATURE = 0.25
SYSTEM = """
### 指示 ###
論文の内容を理解した上で，重要なポイントを箇条書きで3点書いてください。

### 箇条書きの制約 ###
- 最大3個
- 日本語
- 箇条書き1個を100文字以内

### 対象とする論文の内容 ###
{text}

### 出力形式 ###
- 箇条書き1
- 箇条書き2
- 箇条書き3
"""


def get_text(element: Element) -> str:
    """
    XMLの要素からテキストを取得
    Args:
        element: XMLの要素
    Returns:
        text: テキスト
    """
    text = ""
    for elem in element.iter():
        if elem.text:
            text += elem.text
        if elem.tail:
            text += elem.tail
    return text


class Section:
    def __init__(self, title: str = "", body: str = "") -> None:
        """
        セクションのタイトルと本文を保持するクラス
        Args:
            title: セクションのタイトル
            body: セクションの本文
        """
        self.title = title
        self.body = body


def load_pdf(text: str) -> Tuple[str, str]:
    """
    テキストからarXivの論文を取得
    Args:
        text: テキスト
    Returns:
        pdf_file_name: PDFファイル名
        pdf_file_path: PDFファイルパス
    """
    arxiv_id = text.split("\n")[2].split("/")[-1]
    if arxiv_id[-1] == ">":
        arxiv_id = arxiv_id[:-1]

    paper = next(arxiv.Search(id_list=[arxiv_id]).results())
    pdf_file_name = paper.title.replace(" ", "_")

    os.makedirs(f"./pdf/{pdf_file_name}", exist_ok=True)
    pdf_file_path = paper.download_pdf(dirpath=f"./pdf/{pdf_file_name}", filename=f"{pdf_file_name}.pdf")
    return pdf_file_name, pdf_file_path


def make_xml_file(pdf_file_name: str, is_debug: bool = False) -> Element:
    """
    PDFファイルからXMLファイルを作成
    Args:
        pdf_file_name: PDFファイル名
        is_debug: デバッグモード
    Returns:
        root: XMLのルート
    """
    # /path/toの部分を書き換えてください
    cp = subprocess.run(
        f"java -Xmx4G -jar /path/to/grobid/grobid-0.7.2/grobid-core/build/libs/grobid-core-0.7.2-onejar.jar -gH /path/to/grobid/grobid-0.7.2/grobid-home -dIn /path/to/pdf/{pdf_file_name}/ -dOut /path/to/xml -exe processFullText",
        shell=True,
    )
    if is_debug:
        print(f"return code = {cp.returncode}")

    file_name = os.path.splitext(pdf_file_name)[0]
    xml_path = f"./xml/{file_name}.tei.xml"
    tree = ET.parse(xml_path)
    root = tree.getroot()
    return root


def get_sections(root: Element) -> List[Section]:
    """
    XMLファイルからセクションを取得
    Args:
        root: XMLのルート
    Returns:
        sections: セクションのリスト
    """
    sections = []
    for div in root[1][0]:
        section = Section("", "")
        for element in div:
            if element.tag == "{http://www.tei-c.org/ns/1.0}head":
                section.title = element.text
            if element.tag == "{http://www.tei-c.org/ns/1.0}p":
                section.body += get_text(element)

        if section.body != "":
            sections.append(section)

    return sections


def get_pdf_text(pdf_file_path: str) -> str:
    """
    PDFファイルからテキストを取得
    Args:
        pdf_file_path: PDFファイルパス
    Returns:
        pdf_text: PDFのテキスト
    """
    with fitz.open(pdf_file_path) as pdf_in:
        pdf_text = ""
        for page in pdf_in:
            page1 = page.get_text()
            page1 = page1.replace("-\n", "").replace("\n", " ")
            pdf_text += page1
        return pdf_text


def get_prefix(start: int, section: str, pdf_text_list: str) -> str:
    """
    セクションのタイトルの前に付ける#を取得
    Args:
        start: セクションの開始位置
        section: セクション
        pdf_text_list: PDFのテキストのリスト
    Returns:
        start: 更新後のセクションの開始位置
        prefix: セクションのタイトルの前に付ける#
    """
    idx = None
    for i in range(start, len(pdf_text_list)):
        is_same = True
        for j, title_word in enumerate(section.title.split(" ")):
            if pdf_text_list[i + j] != title_word:
                is_same = False
                break

        if is_same:
            start = i
            idx = i - 1
            break

    if idx is not None:
        prefix = f"\n\n{'#' * len(pdf_text_list[idx].split('.'))} " + f"{pdf_text_list[idx]} {section.title}"
    else:
        prefix = f"\n\n### {section.title}"
    return start, prefix


def write_markdown(sections: List[str], pdf_text_list: str, pdf_file_name: str) -> str:
    """
    Markdownファイルを作成
    Args:
        sections: セクションのリスト
        pdf_text_list: PDFのテキストのリスト
        pdf_file_name: PDFファイル名
    Returns:
        markdown_text: Markdownのテキスト
    """
    summarizer = pipeline("summarization", model="kworts/BARTxiv")
    translator = pipeline("translation", model="staka/fugumt-en-ja")
    img_dir = Path(".") / "xml" / f"{pdf_file_name}_assets"
    assert img_dir.exists(), f"{img_dir}"

    markdown_text = ""
    start = 0
    for section in tqdm(sections):
        start, prefix = get_prefix(start, section, pdf_text_list)
        markdown_text += prefix

        # 144文字以下の場合は，全文を翻訳する
        if len(section.body.split(" ")) < 144:
            translated_text = translator(section.body)[0]["translation_text"]

        # 144〜500文字の場合は，全文を踏まえて要約する
        elif len(section.body.split(" ")) < 500:
            summary = summarizer(section.body)[0]["summary_text"]
            translated_text = translator(summary)[0]["translation_text"]

        # 500文字以上の場合は，全文を踏まえて要約する
        else:
            response = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": section.body}],
                temperature=TEMPERATURE,
            )
            translated_text = translator(response["choices"][0]["message"]["content"])[0]["translation_text"]

        markdown_text += "\n" + translated_text

        if "conclusion" in section.title.lower():
            # *NOTE: 一旦画像は追加しない
            # path_list = sorted([tmp for tmp in img_dir.glob("*") if tmp.stem.split("image-")[-1].isdigit()], key=lambda x: int(x.stem.split("image-")[-1]))
            # for path in path_list:
            #     markdown_text += "\n\n" + f"<img alt='image' src={path} width=100>"
            break

    return markdown_text
