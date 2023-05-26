# Paper Bookshelf
Qiitaへ投稿した記事で紹介したコードの全文です

[毎日の論文サーベイを手軽に！ChatGPTを活用したSlackへの3行要約通知とNotionデータベース連携](https://qiita.com/yuta0821/items/2edf338a92b8a157af37)

# Usage
## Install
Dockerfileを用意しているので，そちらから環境構築してください

また環境構築後，grobidのinstallを実施してください
```bash
wget https://github.com/kermitt2/grobid/archive/0.7.2.zip
unzip 0.7.2.zip
cd grobid/grobid-0.7.2
./gradlew clean install
```

最後に環境変数の設定をしてください
```bash
export $(cat .env| grep -v "#" | xargs)
```

以下でアプリが起動します
```bash
python app.py
```
