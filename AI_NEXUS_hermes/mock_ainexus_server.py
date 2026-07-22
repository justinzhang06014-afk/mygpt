#!/usr/bin/env python3
"""
本機測試專用：模擬 AINexus 的 recommend-experts / expert-response 兩支 REST API。

背景：這台機器連不到 Phison 內網（192.168.41.133），所以 phison_mcp_bridge.py
沒辦法直接對真實 AINexus 測試。這支檔案用 response_1784630885607.json 裡真實的
experts 清單當假資料，跑一個結構一模一樣的本機 REST server，讓 phison_mcp_bridge.py
可以指向 PHISON_API_URL=http://<this-host>:9500/api/v1/hermes/ainexus 做端到端驗證
（兩段 REST 呼叫串接、hermes MCP 是否正確收到並顯示結果），跑完之後把 PHISON_API_URL
換回真實內網位址即可，不用改 phison_mcp_bridge.py 一行程式碼。

不驗證真實網路/真實 Token 是否有效——那部分只能等連得到 Phison 內網的環境再測。
"""
import json
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Mock AINexus Server (local test only)")

RESPONSE_JSON_PATH = Path(__file__).parent.parent / "response_1784630885607.json"
with open(RESPONSE_JSON_PATH, "r", encoding="utf-8") as f:
    _catalog = json.load(f)

EXPERTS = _catalog.get("experts", [])
FAKE_TOKEN = os.getenv("MOCK_EXPECTED_TOKEN", "")  # 空字串 = 不檢查 token，方便本機測試


def _check_auth(authorization: str | None):
    if not FAKE_TOKEN:
        return
    if not authorization or authorization != f"Bearer {FAKE_TOKEN}":
        raise HTTPException(status_code=401, detail="invalid token")


class RecommendRequest(BaseModel):
    query: str


class ExpertResponseRequest(BaseModel):
    expertId: int
    query: str


@app.post("/api/v1/hermes/ainexus/tools/recommend-experts")
def recommend_experts(body: RecommendRequest, authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    q = body.query.lower()
    # 極簡假推薦邏輯：query 字串出現在 name/description 就算命中，命中不到就回第一個已 isAdded 的專家
    matched = [
        e for e in EXPERTS
        if q in e.get("name", "").lower() or q in e.get("description", "").lower()
    ]
    if not matched:
        matched = [e for e in EXPERTS if e.get("isAdded")] or EXPERTS[:1]
    return {"experts": matched[:5]}


@app.post("/api/v1/hermes/ainexus/tools/expert-response")
def expert_response(body: ExpertResponseRequest, authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    expert = next((e for e in EXPERTS if e.get("id") == body.expertId), None)
    if not expert:
        raise HTTPException(status_code=404, detail=f"expert {body.expertId} not found")
    return (
        f"(模擬回答 / 本機 mock server，不是真的 AINexus 推論結果)\n"
        f"專家「{expert.get('name')}」收到問題：{body.query}\n"
        f"專家簡介：{expert.get('description', '')[:200]}"
    )


if __name__ == "__main__":
    port = int(os.getenv("MOCK_PORT", "9500"))
    print(f"Mock AINexus server: {len(EXPERTS)} experts loaded from {RESPONSE_JSON_PATH}")
    uvicorn.run(app, host="0.0.0.0", port=port)
