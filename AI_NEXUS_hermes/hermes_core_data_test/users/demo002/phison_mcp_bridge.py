#!/usr/bin/env python3
"""
Phison AINexus 動態專家路由 MCP Bridge。

背景：AINexus 平台的「動態推薦專家」是兩支 REST API（不是現成的 MCP endpoint）：
  1. POST {API_BASE}/tools/recommend-experts {query}      -> 依問題語意推薦最合適的專家清單
  2. POST {API_BASE}/tools/expert-response  {expertId, query} -> 實際呼叫該專家取得回答
hermes 只吃 MCP protocol，所以這支檔案是唯一負責把這兩支 REST API 包成一個 hermes
看得懂的 stdio MCP tool 的地方。真正的端點/欄位命名已經對照過使用者手動 curl
`GET {API_BASE}/capabilities?includeExperts=true` 拿到的真實回應（tools 陣列裡的
GetRecommendedExperts / GetExpertResponse），照原樣實作，不臆測欄位。

跟 hermes-agent/expert_catalog.py 是兩條不衝突的路：
  - expert_catalog.py 處理「已發布、固定的單一 agent」，直接掛成 MCP URL 常駐工具。
  - 這支檔案處理「不知道該問哪個專家，讓 AINexus 自己動態推薦」，每次呼叫都是即時決策。

認證：Token 一律從環境變數 PHISON_TOKEN 讀，不寫死在程式碼或任何設定檔裡；
呼叫端（services.py 的 config.yaml 產生邏輯）會把它接成 hermes 原生 mcp_servers
的 env 區塊，跟 mcp_services.py 幫一般 MCP 憑證做 ${MCP_<NAME>_<FIELD>} 是同一套機制。
"""
import os
import json
import requests
from mcp.server.fastmcp import FastMCP

API_BASE = os.getenv("PHISON_API_URL", "http://192.168.41.133:5155/api/v1/hermes/ainexus")
TOKEN = os.getenv("PHISON_TOKEN", "")
REQUEST_TIMEOUT_SECONDS = 30

mcp = FastMCP("Phison AINexus Expert Router")


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}",
        "accept": "application/json",
    }


@mcp.tool()
def query_phison_expert(query: str) -> str:
    """
    自動幫使用者的問題找到最合適的 Phison AINexus 專家並取得回答。
    內部執行兩步：GetRecommendedExperts 找專家 -> GetExpertResponse 問問題。
    """
    if not TOKEN:
        return "Error: PHISON_TOKEN 環境變數未設定，無法呼叫 AINexus。"

    try:
        rec_resp = requests.post(
            f"{API_BASE}/tools/recommend-experts",
            json={"query": query},
            headers=_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        rec_resp.raise_for_status()
        rec_data = rec_resp.json()
    except requests.exceptions.RequestException as e:
        return f"Network error while calling recommend-experts: {str(e)}"
    except Exception as e:
        return f"Unexpected error while parsing recommend-experts response: {str(e)}"

    experts = rec_data.get("experts", []) if isinstance(rec_data, dict) else []
    if not experts:
        return "No relevant experts found for this query."

    top_expert = experts[0]
    expert_id = top_expert.get("id")
    expert_name = top_expert.get("name", f"#{expert_id}")
    if expert_id is None:
        return f"Recommend-experts response missing an 'id' field: {json.dumps(rec_data, ensure_ascii=False)[:300]}"

    try:
        exec_resp = requests.post(
            f"{API_BASE}/tools/expert-response",
            json={"expertId": expert_id, "query": query},
            headers=_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        exec_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"Network error while calling expert-response (expert={expert_name}): {str(e)}"

    return f"[專家: {expert_name}]\n{exec_resp.text}"


@mcp.tool()
def get_recommended_experts(query: str) -> str:
    """
    取得 AINexus 推薦的專家清單（不直接呼叫專家，只回傳推薦結果）。
    使用者可以根據結果決定是否呼叫專家。
    """
    if not TOKEN:
        return "Error: PHISON_TOKEN 環境變數未設定，無法呼叫 AINexus。"

    try:
        rec_resp = requests.post(
            f"{API_BASE}/tools/recommend-experts",
            json={"query": query},
            headers=_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        rec_resp.raise_for_status()
        rec_data = rec_resp.json()
    except requests.exceptions.RequestException as e:
        return f"Network error while calling recommend-experts: {str(e)}"
    except Exception as e:
        return f"Unexpected error while parsing recommend-experts response: {str(e)}"

    experts = rec_data.get("experts", []) if isinstance(rec_data, dict) else []
    if not experts:
        return "No relevant experts found for this query."

    result = "推薦專家清單：\n"
    for i, expert in enumerate(experts[:5], 1):  # 只顯示前5個
        expert_id = expert.get("id", "unknown")
        expert_name = expert.get("name", f"#{expert_id}")
        expert_desc = expert.get("description", "無描述")
        result += f"{i}. {expert_name} (ID: {expert_id})\n   {expert_desc}\n"

    return result


@mcp.tool()
def get_expert_response(expert_id: str, query: str) -> str:
    """
    直接呼叫指定的 AINexus 專家取得回答。
    需要提供專家 ID (expert_id) 和問題 (query)。
    """
    if not TOKEN:
        return "Error: PHISON_TOKEN 環境變數未設定，無法呼叫 AINexus。"

    try:
        exec_resp = requests.post(
            f"{API_BASE}/tools/expert-response",
            json={"expertId": expert_id, "query": query},
            headers=_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        exec_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"Network error while calling expert-response: {str(e)}"

    return exec_resp.text


if __name__ == "__main__":
    mcp.run(transport="stdio")
