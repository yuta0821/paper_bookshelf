# Paper Database
Qiitaへ投稿した記事で紹介したコードの全文です

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
