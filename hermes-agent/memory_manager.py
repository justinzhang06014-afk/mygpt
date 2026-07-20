import os
import logging
from datetime import datetime
from config import PROFILES_BASE_DIR

logger = logging.getLogger("hermes-proxy.memory")

def get_all_available_agents() -> list[str]:
    """
    【掃描細胞庫】遍歷基礎目錄，撈出目前全平台所有可用的 agent_id 資料夾名稱
    """
    try:
        if not os.path.exists(PROFILES_BASE_DIR):
            return []
        # 僅撈出實體資料夾，且過濾掉隱藏檔案
        agents = [
            d for d in os.listdir(PROFILES_BASE_DIR)
            if os.path.isdir(os.path.join(PROFILES_BASE_DIR, d)) and not d.startswith(".")
        ]
        return sorted(agents)
    except Exception as e:
        logger.error(f"❌ 掃描全域 Agent 清單失敗: {str(e)}")
        return []


def parse_physical_file_to_json(agent_id: str, file_type: str) -> dict:
    """
    【雙軌制動態解析】依據 file_type ("memory" 或 "user") 讀取對應的實體 md 檔案，並結構化為大禮包。
    純樸平面顯示：hermes 本身沒有分類概念，不再用關鍵字猜測分類，每條記憶就是一條純文字事實。
    """
    f_type = "memory" if file_type.lower() == "memory" else "user"
    # 🐛 0716 修正：hermes 實際寫出來的檔名是大寫（MEMORY.md / USER.md），
    # 這裡原本組小寫檔名，在 Windows 掛載（大小寫不分）下能動，換到正式 Linux 主機會讀不到。
    filename = f"{f_type.upper()}.md"

    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    file_path = os.path.join(agent_dir, "memories", filename)

    facts = []
    result = {
        "status": "success",
        "meta": {
            "agent_id": agent_id,
            "file_type": f_type,
            "last_sync_time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "brain_saturation_percentage": 0,
            "max_allowed_facts": 20,
            "current_facts_count": 0
        },
        "memories": []
    }

    if not os.path.exists(file_path):
        return result

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        idx = 1
        for line in lines:
            clean_line = line.strip().lstrip("- ").lstrip("* ").strip()
            if not clean_line or clean_line.startswith("#"):
                continue

            facts.append({
                "id": f"{f_type}_fact_{str(idx).zfill(3)}",
                "text": clean_line,
                "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            })
            idx += 1

        result["memories"] = facts
        result["meta"]["current_facts_count"] = len(facts)
        result["meta"]["brain_saturation_percentage"] = int((len(facts) / 20) * 100)

    except Exception as e:
        logger.error(f"❌ 解析物理 {filename} 失敗: {str(e)}")

    return result


def write_json_memories_back_to_md(agent_id: str, file_type: str, text_list: list):
    """
    【雙軌制真理落盤】將純文字清單依據 file_type 壓回對應的 md 硬碟
    """
    f_type = "memory" if file_type.lower() == "memory" else "user"
    filename = f"{f_type.upper()}.md"

    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    memory_dir = os.path.join(agent_dir, "memories")
    os.makedirs(memory_dir, exist_ok=True)
    file_path = os.path.join(memory_dir, filename)
    
    title = "# Long Term Memory\n\n" if f_type == "memory" else "# User Profile & Preferences\n\n"
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(title)
            for text in text_list:
                clean_text = text.strip()
                if clean_text:
                    f.write(f"- {clean_text}\n")
        logger.info(f"💾 [File Flush] 成功同步重寫 Agent [{agent_id}] 的 {filename} 檔案。")
    except Exception as e:
        logger.error(f"❌ 寫入物理 {filename} 失敗: {str(e)}")


