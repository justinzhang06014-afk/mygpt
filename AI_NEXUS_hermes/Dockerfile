FROM python:3.11-slim

# 這支服務需要 docker.sock 才能 ensure/建立每個帳號的專屬容器（runtime_manager.py），
# 但 docker.sock 本身、/opt/data 的實體存放位置，都是「部署這支服務的人」用
# `docker run -v /var/run/docker.sock:/var/run/docker.sock -v <host路徑>:/opt/data`
# 掛進來的——不是這支 image 自己擁有或建立的基礎設施。
# 刻意不裝 OpenSSH server：那是 hermes-agent/Dockerfile 已知但尚未清理的風險
# （root 密碼寫死），這裡不需要遠端終端機（terminal.backend 固定是 local），不重蹈覆轍。
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

COPY . .

RUN mkdir -p /opt/data
EXPOSE 8643

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8643"]
