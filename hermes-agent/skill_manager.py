"""
🆕【新增檔案】skill_manager.py

負責「私有 Skill 商店」＋「Skill 匯出/匯入 zip」這兩塊，全部是 hermes 目前沒有現成 CLI
可以直接殼一層的功能（hermes 官方只有 hub 上架用的 `hermes skills publish/install`，
沒有「從我們自己內部目錄安裝」或「zip 匯出匯入」這種用法），所以這裡是我們自己補的管理層。

設計原則（跟 memory_manager.py 一致）：
- 每個 agent 的 skills 都在自己私有的 profiles/<agent_id>/skills/ 底下，彼此互不相通。
- 「商店」目錄則是共用目錄（性質上是「有哪些可以安裝的目錄清單」，不是任何 agent 的私有資料）。
- 所有會員用 skill_id 當資料夾名稱，一律先做路徑檢查，避免 ../ 路徑穿越攻擊。
- 匯入 zip 有大小上限與解壓縮後總大小上限（防止惡意 zip 炸彈把硬碟塞爆）。
- SKILL.md 的驗證規則直接沿用 hermes 官方 skill 撰寫規範（frontmatter 起手式、name/description 必填等）。
"""
import os
import re
import io
import shutil
import tempfile
import zipfile
import yaml
from config import logger, GLOBAL_HERMES_DIR, PROFILES_BASE_DIR

# 🆕 私有 Skill 商店：放在 hermes 全域資料夾底下的一個共用目錄（不是任何 agent 的私有記憶）
SKILL_STORE_DIR = os.path.join(GLOBAL_HERMES_DIR, "skill_store")

# 🆕 匯入限制：壓縮檔本身大小上限，以及解壓縮後總大小上限（防 zip 炸彈）
MAX_IMPORT_ZIP_BYTES = 8 * 1024 * 1024       # 8MB
MAX_EXTRACTED_TOTAL_BYTES = 30 * 1024 * 1024  # 30MB

# 沿用 hermes 官方 skill 撰寫規範的驗證上限（見 hermes-agent-skill-authoring 這份官方 skill 文件）
MAX_DESCRIPTION_LENGTH = 1024
MAX_SKILL_CONTENT_CHARS = 100_000


class SkillTooLargeError(Exception):
    """匯入的 zip 太大，提醒使用者精簡或分次匯入"""
    pass


class SkillInvalidError(Exception):
    """zip 內容不是一個合法的 SKILL.md（不符合 hermes 官方驗證規則）"""
    pass


def _agent_skills_dir(agent_id: str) -> str:
    return os.path.join(PROFILES_BASE_DIR, agent_id, "skills")


def _sanitize_skill_id(raw_id: str) -> str:
    """把任意字串收斂成安全的資料夾名稱：只留小寫英數字與 -，其餘一律換成 -"""
    cleaned = re.sub(r"[^a-z0-9-]", "-", (raw_id or "").strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "untitled-skill"


def _safe_join(base_dir: str, skill_id: str) -> str:
    """
    🛡️【路徑穿越防線】不管 skill_id 傳進來的是什麼，一律先清洗成安全字元，
    再確認最終路徑真的落在 base_dir 底下，避免 ../../.. 逃出去動到其他 agent 或系統檔案。
    """
    safe_id = _sanitize_skill_id(skill_id)
    base_abs = os.path.abspath(base_dir)
    target_abs = os.path.abspath(os.path.join(base_abs, safe_id))
    if os.path.commonpath([base_abs, target_abs]) != base_abs:
        raise SkillInvalidError("非法的 skill 識別碼")
    return target_abs


def _parse_skill_frontmatter(skill_md_path: str) -> dict:
    """解析 SKILL.md 最前面的 YAML frontmatter，回傳 {name, description}"""
    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---"):
        raise SkillInvalidError("SKILL.md 必須以 --- 開頭 (frontmatter)")
    if len(content) > MAX_SKILL_CONTENT_CHARS:
        raise SkillInvalidError(f"SKILL.md 內容超過 {MAX_SKILL_CONTENT_CHARS} 字元上限")

    match = re.search(r"\n---\s*\n", content[3:])
    if not match:
        raise SkillInvalidError("SKILL.md frontmatter 沒有正確以 \\n---\\n 結尾")

    frontmatter_text = content[3:match.start() + 3]
    try:
        frontmatter = yaml.safe_load(frontmatter_text) or {}
    except Exception as e:
        raise SkillInvalidError(f"SKILL.md frontmatter 不是合法的 YAML: {e}")

    if not isinstance(frontmatter, dict) or "name" not in frontmatter or "description" not in frontmatter:
        raise SkillInvalidError("SKILL.md frontmatter 缺少必填的 name / description 欄位")
    if len(str(frontmatter["description"])) > MAX_DESCRIPTION_LENGTH:
        raise SkillInvalidError(f"description 超過 {MAX_DESCRIPTION_LENGTH} 字元上限")

    body = content[match.end() + 3:]
    if not body.strip():
        raise SkillInvalidError("SKILL.md 的 frontmatter 之後必須要有實際內容")

    return {"name": str(frontmatter["name"]), "description": str(frontmatter["description"])}


def _list_skills_in_dir(base_dir: str) -> list[dict]:
    if not os.path.isdir(base_dir):
        return []
    entries = []
    for skill_id in sorted(os.listdir(base_dir)):
        skill_dir = os.path.join(base_dir, skill_id)
        skill_md = os.path.join(skill_dir, "SKILL.md")
        if not os.path.isdir(skill_dir) or not os.path.isfile(skill_md):
            continue
        try:
            meta = _parse_skill_frontmatter(skill_md)
            entries.append({"id": skill_id, "name": meta["name"], "description": meta["description"]})
        except SkillInvalidError as e:
            logger.warning(f"⚠️ [Skill 掃描] 略過格式不合法的 skill 資料夾 {skill_id}: {e}")
    return entries


def list_agent_skills(agent_id: str) -> list[dict]:
    """該 agent 私有 skills 資料夾底下，目前已安裝的 skill 清單"""
    return _list_skills_in_dir(_agent_skills_dir(agent_id))


def list_store_skills() -> list[dict]:
    """共用的 Skill 商店目錄底下，目前可供安裝的 skill 清單"""
    return _list_skills_in_dir(SKILL_STORE_DIR)


def _get_skill_detail_in_dir(base_dir: str, skill_id: str) -> dict:
    """
    🆕 讀出某個 skill 完整的 SKILL.md 內容（不只是 frontmatter），
    給「商店卡片點進去看說明」「已安裝清單點進去看使用方式」共用。
    body 直接回傳原始 markdown，前端用既有的 marked 渲染即可。
    """
    skill_dir = _safe_join(base_dir, skill_id)
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        raise SkillInvalidError(f"找不到 skill: {skill_id}")

    meta = _parse_skill_frontmatter(skill_md)
    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"\n---\s*\n", content[3:])
    body = content[match.end() + 3:].strip() if match else content

    return {"id": skill_id, "name": meta["name"], "description": meta["description"], "body": body}


def get_store_skill_detail(store_skill_id: str) -> dict:
    return _get_skill_detail_in_dir(SKILL_STORE_DIR, store_skill_id)


def get_agent_skill_detail(agent_id: str, skill_id: str) -> dict:
    return _get_skill_detail_in_dir(_agent_skills_dir(agent_id), skill_id)


# =====================================================================
# 🆕【尚未驗證・待你接手確認】把 skill 的啟用狀態同步進該 agent 的 config.yaml。
#
# 目前 hermes 官方文件裡有 `hermes skills config`（依平台啟用/停用 skill）跟
# `/reload-skills`（重新掃描 skills 資料夾），但實際 config.yaml 底下
# skill 啟用清單長怎樣、欄位叫什麼名字，我這邊沒有真的能跑的 hermes
# 環境可以實測驗證（submodule 原始碼那份也是空的），所以下面這個函式
# 是「最保守的猜測寫法」：在 config.yaml 加一個 skills.installed 清單。
#
# 你之後在真環境測試時，麻煩：
#   1. 手動用 `hermes skills config` 開一個 skill 看它實際寫出的 config.yaml 長怎樣
#   2. 把下面 config_data["skills"] 這段改成跟真實格式一致
#   3. 如果 hermes 其實只靠「skills 資料夾裡有沒有這個資料夾」就自動生效
#      （不需要 config.yaml 額外記錄），那這個函式可以直接刪掉不用呼叫
# =====================================================================
def _sync_skill_activation_to_config(agent_id: str, skill_id: str, enabled: bool):
    import yaml  # 延遲載入，避免影響其他不需要 yaml 的函式

    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    config_path = os.path.join(agent_dir, "config.yaml")
    if not os.path.exists(config_path):
        return  # profile 還沒建立過，這裡先不處理，等第一次對話建檔時再說

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    skills_cfg = config_data.setdefault("skills", {})
    installed = set(skills_cfg.get("installed", []))
    if enabled:
        installed.add(skill_id)
    else:
        installed.discard(skill_id)
    skills_cfg["installed"] = sorted(installed)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config_data, f, default_flow_style=False)

    logger.info(f"⚡ [Skill 開通] Agent {agent_id} 的 config.yaml 已同步 skill '{skill_id}' 啟用狀態 = {enabled}（欄位格式待你用真環境驗證）")


def install_skill_from_store(agent_id: str, store_skill_id: str) -> list[dict]:
    """把商店裡的某個 skill 複製一份到該 agent 私有的 skills 資料夾（不同 agent 各自獨立一份，互不影響）"""
    source_dir = _safe_join(SKILL_STORE_DIR, store_skill_id)
    if not os.path.isdir(source_dir) or not os.path.isfile(os.path.join(source_dir, "SKILL.md")):
        raise SkillInvalidError(f"商店裡找不到 skill: {store_skill_id}")

    dest_dir = _safe_join(_agent_skills_dir(agent_id), store_skill_id)
    os.makedirs(os.path.dirname(dest_dir), exist_ok=True)
    shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)
    logger.info(f"⚡ [Skill 商店] Agent {agent_id} 已安裝商店 skill: {store_skill_id}")

    # 🆕 依決議 3a：main.py 這條路徑要負責去「開通」這個 skill —— 實際寫法待你用真環境驗證，見上方函式註解
    _sync_skill_activation_to_config(agent_id, store_skill_id, enabled=True)

    return list_agent_skills(agent_id)


def uninstall_agent_skill(agent_id: str, skill_id: str) -> list[dict]:
    """從該 agent 私有的 skills 資料夾移除一個 skill（只影響這個 agent 自己）"""
    target_dir = _safe_join(_agent_skills_dir(agent_id), skill_id)
    if os.path.isdir(target_dir):
        shutil.rmtree(target_dir)
        logger.info(f"🗑️ [Skill 管理] Agent {agent_id} 已移除 skill: {skill_id}")
    _sync_skill_activation_to_config(agent_id, skill_id, enabled=False)
    return list_agent_skills(agent_id)


def export_skill_zip_bytes(agent_id: str, skill_id: str) -> tuple[bytes, str]:
    """把該 agent 私有的某個 skill 資料夾打包成 zip bytes，回傳 (zip內容, 建議檔名)"""
    source_dir = _safe_join(_agent_skills_dir(agent_id), skill_id)
    if not os.path.isdir(source_dir):
        raise SkillInvalidError(f"找不到 skill: {skill_id}")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(source_dir):
            for filename in files:
                abs_path = os.path.join(root, filename)
                rel_path = os.path.join(skill_id, os.path.relpath(abs_path, source_dir))
                zf.write(abs_path, arcname=rel_path)

    return buffer.getvalue(), f"{skill_id}.zip"


def _safe_extract_zip(zf: zipfile.ZipFile, dest_root: str):
    """
    🛡️【zip slip 防線】不能直接呼叫 zf.extractall()，必須逐一檢查每個項目解壓後的
    實際路徑是否仍落在 dest_root 底下，避免惡意 zip 內夾帶 ../../ 之類的路徑逃出解壓目錄。
    """
    dest_root_abs = os.path.abspath(dest_root)
    for info in zf.infolist():
        target_path = os.path.abspath(os.path.join(dest_root_abs, info.filename))
        if os.path.commonpath([dest_root_abs, target_path]) != dest_root_abs:
            raise SkillInvalidError(f"zip 內含有非法路徑，已拒絕解壓縮: {info.filename}")
    zf.extractall(dest_root_abs)


def import_skill_zip(agent_id: str, zip_bytes: bytes) -> list[dict]:
    """
    匯入一個使用者上傳的 zip 檔，驗證通過後安裝到該 agent 私有的 skills 資料夾。
    - 太大：丟 SkillTooLargeError，由上層 API 轉成提醒訊息回給使用者。
    - 格式不合法（沒有 SKILL.md / frontmatter 缺欄位）：丟 SkillInvalidError。
    """
    if len(zip_bytes) > MAX_IMPORT_ZIP_BYTES:
        raise SkillTooLargeError(
            f"壓縮檔 {len(zip_bytes) / 1024 / 1024:.1f}MB，超過 {MAX_IMPORT_ZIP_BYTES / 1024 / 1024:.0f}MB 上限，"
            f"請精簡內容（例如移除多餘的圖片/範例檔）或拆成多個 skill 分次匯入。"
        )

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise SkillInvalidError("上傳的檔案不是合法的 zip 壓縮檔")

    total_uncompressed = sum(info.file_size for info in zf.infolist())
    if total_uncompressed > MAX_EXTRACTED_TOTAL_BYTES:
        raise SkillTooLargeError(
            f"解壓縮後總大小約 {total_uncompressed / 1024 / 1024:.1f}MB，"
            f"超過 {MAX_EXTRACTED_TOTAL_BYTES / 1024 / 1024:.0f}MB 上限，請精簡內容後再匯入。"
        )

    # 在 zip 裡找出「離根目錄最近」的那個 SKILL.md，把它所在的資料夾當成這個 skill 的根目錄
    skill_md_entries = [n for n in zf.namelist() if os.path.basename(n) == "SKILL.md"]
    if not skill_md_entries:
        raise SkillInvalidError("zip 內找不到 SKILL.md，不是合法的 skill 封裝")
    skill_md_entry = min(skill_md_entries, key=lambda n: n.count("/"))
    skill_root_in_zip = os.path.dirname(skill_md_entry)

    tmp_dir = tempfile.mkdtemp(prefix="hermes_skill_import_")
    try:
        _safe_extract_zip(zf, tmp_dir)

        extracted_skill_md = os.path.join(tmp_dir, skill_md_entry.replace("/", os.sep))
        meta = _parse_skill_frontmatter(extracted_skill_md)

        extracted_skill_dir = os.path.join(tmp_dir, skill_root_in_zip.replace("/", os.sep)) if skill_root_in_zip else tmp_dir

        # 目的地資料夾名稱以 SKILL.md 內的 name 欄位為準（跟官方規範一致：小寫 + 連字號）
        skill_id = _sanitize_skill_id(meta["name"])
        dest_dir = _safe_join(_agent_skills_dir(agent_id), skill_id)
        os.makedirs(os.path.dirname(dest_dir), exist_ok=True)
        if os.path.isdir(dest_dir):
            shutil.rmtree(dest_dir)  # 同名視為更新覆蓋，而不是無限堆疊重複資料夾
        shutil.copytree(extracted_skill_dir, dest_dir)

        logger.info(f"📥 [Skill 匯入] Agent {agent_id} 成功匯入 skill: {skill_id}")
        _sync_skill_activation_to_config(agent_id, skill_id, enabled=True)
        return list_agent_skills(agent_id)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
