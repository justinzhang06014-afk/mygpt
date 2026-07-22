"""
呼叫同事的外部 orchestrator 服務，取代 runtime_manager.py 自己用 docker.sock 建容器
那條路——同事的服務負責「空間/儲存/容器怎麼跑」，我們（這支服務）還是全權負責
hermes config.yaml/mcp_servers 產生跟 ACP 對話執行，範圍沒有變。

設計成「開關式」：設定 ORCHESTRATOR_URL 環境變數才會啟用這條路；沒設定就照舊用
runtime_manager.py 自己的 docker.sock 邏輯（本機測試/沒有同事服務時還能用）。
main.py 完全不用知道現在走哪一條路，兩條路都回傳同樣格式的 dict。

⚠️ 這裡的 payload/回應欄位名稱是根據 hermes_dockerPOST架構.txt 草案寫的最佳猜測，
不是同事確認過的正式規格——hermes-agent/docs/01_orchestrator_split_plan.md 已經列出
好幾個當時沒問清楚的地方（per-user vs per-agent granularity、環境變數命名對不上、
CRUD API 要不要走），這幾個問題現在還是一樣沒解。等你跟同事對齊實際規格後，
只要改這支檔案的 payload 組裝跟回應解析，main.py/runtime_manager.py 都不用動。
"""
import os
import requests

from config import logger

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "").rstrip("/")
ORCHESTRATOR_TIMEOUT_SECONDS = int(os.getenv("ORCHESTRATOR_TIMEOUT_SECONDS", "30"))


def is_enabled() -> bool:
    """有設定 ORCHESTRATOR_URL 才走外部 orchestrator，這是唯一的開關。"""
    return bool(ORCHESTRATOR_URL)


def _extract_base_url(data: dict) -> str | None:
    """
    📍 回應欄位名稱是猜的，同事的真實規格可能用別的 key——先照 hermes_dockerPOST架構.txt
    最像的幾種寫法都試著抓一次，抓不到就讓呼叫端自己報錯，不要默默回傳錯的網址。
    """
    for key in ("base_url", "baseUrl", "url"):
        if data.get(key):
            return data[key]
    host = data.get("host") or data.get("container_name") or data.get("containerName")
    port = data.get("port")
    if host and port:
        return f"http://{host}:{port}"
    return None


def ensure_user_runtime(user_id: str) -> dict:
    """
    📍 這裡是跟同事對接的地方。目前的 payload 對照 hermes_dockerPOST架構.txt 草案：
      - userId：對齊
      - agentId：故意不帶——容器是 per-user 不是 per-agent（docs 裡已經建議維持這樣，
        除非同事那邊真的要 per-agent，再加這個欄位）
      - environment：草案原本寫 AINEXUS_API_KEY，這裡改用真正在用的 PHISON_API_KEY，
        跟同事對齊環境變數命名時注意這裡
      - resource_limits：草案有這個欄位，這裡先沒帶，同事的服務需要的話在這裡加
    回傳格式跟 runtime_manager.py 自己 docker.sock 那條路完全一樣：
    {"status": "created"|"existing", "base_url": "http://..."}（不會有 swagger_url，
    那是本機測試專用的 docker.sock 開發便利功能，走 orchestrator 時不適用）。
    """
    if not is_enabled():
        raise RuntimeError("ORCHESTRATOR_URL 未設定，不應該呼叫這個函式（main.py 應該先檢查 is_enabled()）")

    payload = {
        "userId": user_id,
        "environment": {
            "PHISON_API_KEY": os.getenv("PHISON_API_KEY", ""),
        },
    }

    try:
        resp = requests.post(
            f"{ORCHESTRATOR_URL}/api/v1/workers",
            json=payload,
            timeout=ORCHESTRATOR_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ [Orchestrator] 呼叫 {ORCHESTRATOR_URL} 建立使用者 {user_id} 的 Runtime 失敗: {str(e)}")
        raise RuntimeError(f"呼叫 orchestrator 失敗: {str(e)}")

    base_url = _extract_base_url(data)
    if not base_url:
        raise RuntimeError(f"Orchestrator 回應沒有可辨識的位址欄位（base_url/baseUrl/url/host+port）: {data}")

    status = data.get("status", "created")
    logger.info(f"✅ [Orchestrator] 使用者 {user_id} 的 Runtime: {status} -> {base_url}")
    return {"status": status, "base_url": base_url}
