# FROM python:3.11-slim

# USER root

# RUN apt-get update && apt-get install -y ca-certificates curl \
#     && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
#     && apt-get install -y nodejs \
#     && apt-get clean && rm -rf /var/lib/apt/lists/*

# # 安裝執行官方 CLI 所需的系統基本套件
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     curl git \
#     && rm -rf /var/lib/apt/lists/*

# WORKDIR /app

# # 安裝 Python 依賴與官方 hermes-agent CLI 工具
# # 🔌 [mcp] extras：MCP client 函式庫（streamable-http/sse/stdio 傳輸層），不裝會導致 MCP 連線失敗
# # 🔌 [acp] extras（0716 新增）：Agent Client Protocol，讓我們的中繼站可以用官方結構化事件
# # 協定跟 hermes 溝通（跟 VS Code/Zed/JetBrains 外掛同一套機制），取代舊的文字流猜測法
# RUN pip install --no-cache-dir --default-timeout=1000 fastapi uvicorn pydantic httpx pyyaml docker "hermes-agent[mcp,acp]"

# COPY . .

# RUN mkdir -p /opt/data && chmod 777 /opt/data
# EXPOSE 8643

# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8643"]
FROM python:3.11-slim

# 1. 所有系統套件同一層安裝
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    openssh-server \
    openssh-client \
    sudo \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. SSH 伺服器端設定
RUN mkdir -p /var/run/sshd && \
    echo 'root:hermespass' | chpasswd && \
    sed -i 's/^#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/^ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config

# 3. 【全新修正】在絕對不會被覆蓋的 /root/.ssh 生成金鑰並授權
RUN mkdir -p /root/.ssh && \
    ssh-keygen -t rsa -b 2048 -f /root/.ssh/id_rsa -N "" && \
    cp /root/.ssh/id_rsa.pub /root/.ssh/authorized_keys && \
    chmod 700 /root/.ssh && \
    chmod 600 /root/.ssh/id_rsa && \
    chmod 600 /root/.ssh/authorized_keys

# 4. 設定 SSH 客戶端預設參數（防止第一次連線時跳出 yes/no 提問而卡死）
RUN mkdir -p /etc/ssh && \
    echo "Host *" >> /etc/ssh/ssh_config && \
    echo "    StrictHostKeyChecking no" >> /etc/ssh/ssh_config && \
    echo "    UserKnownHostsFile /dev/null" >> /etc/ssh/ssh_config

WORKDIR /app

# 5. Python 依賴
RUN pip install --no-cache-dir --default-timeout=1000 \
    fastapi uvicorn pydantic httpx pyyaml docker \
    "hermes-agent[mcp,acp]"

COPY . .

EXPOSE 8643 22

# 6. 【關鍵修正】啟動時，強制把金鑰複製到會被共享的 /opt/data 中，確保 Python 讀得到
RUN mkdir -p /opt/data
CMD ["/bin/bash", "-c", "mkdir -p /opt/data && cp -f /root/.ssh/id_rsa* /opt/data/ && chmod 600 /opt/data/id_rsa && service ssh start && sleep 2 && uvicorn main:app --host 0.0.0.0 --port 8643"]



