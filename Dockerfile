# 使用官方 Python 3.11.7 
FROM python:3.11.7-slim

# 設定容器內的工作目錄為 /app，後續的指令都會在此目錄下執行
WORKDIR /app

# 設定環境變數：禁止 Python 產生 .pyc 快取檔案，減少容器內的空間佔用
ENV PYTHONDONTWRITEBYTECODE=1

# 設定環境變數：強制將 Python 的標準輸出與錯誤直接印出（不進行快取），確保能即時看到 Log
ENV PYTHONUNBUFFERED=1

# 設定環境變數：關閉 Hugging Face 的高速傳輸模式（若有使用 HF 套件，可避免特定網路環境下的下載錯誤）
ENV HF_HUB_ENABLE_HF_TRANSFER=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 將本地的套件清單 requirements.txt 複製到容器內的工作目錄
COPY requirements.txt .

# 升級 pip 並依據清單安裝套件；使用 --no-cache-dir 參數可以避免暫存安裝檔，確保映像檔最輕量化
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 將本地的應用程式主程式 app.py 複製到容器內的工作目錄
COPY app.py .

# 宣告容器運行時會監聽的網路連接埠（Port）為 8000
EXPOSE 8000

# 容器啟動時執行的預設指令：使用 uvicorn 啟動 app.py 裡的 app 實例，監聽所有 IP 並綁定 8000 埠
# CMD "uvicorn", "app:app", "--host", "0.0.0.0", "--
CMD uvicorn app:app --host 0.0.0.0 --port 8000
