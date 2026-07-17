---
name: web-search
description: Web search capability using multiple search engines. Enables real-time information retrieval for any topic.
version: 1.0.0
---

# Web Search Skill

使用多個搜尋引擎進行聯網搜索。

## 安裝

```bash
pip install tavily-python duckduckgo-search
```

## 使用

```python
from tavily import TavilyClient
client = TavilyClient(api_key="your-api-key")
response = client.qna_search(query="your question")
```

## 注意事項

- 免費層有每日搜索限制
- 需要 API Key
