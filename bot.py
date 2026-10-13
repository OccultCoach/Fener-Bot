name: Fenerbahçe Bot

on:
  workflow_dispatch:

permissions:
  contents: write

jobs:
  run:
    runs-on: ubuntu-latest

    steps:
      - name: Kodu indir
        uses: actions/checkout@v4

      - name: Python 3.12 kur
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Bağımlılıkları kur
        run: pip install -r requirements.txt

      - name: Botu çalıştır
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          CHAT_ID: ${{ secrets.CHAT_ID }}
          GIST_ID: ${{ secrets.GIST_ID }}
          GIST_TOKEN: ${{ secrets.GIST_TOKEN }}
        run: python bot.py
