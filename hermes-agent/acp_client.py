"""
🆕 0716 新增：ACP（Agent Client Protocol）整合模組。

取代舊的「spawn `hermes chat -q` + 逐行讀終端機文字 + 正則表達式硬猜結構」的做法。
改用 hermes 官方提供、跟 VS Code/Zed/JetBrains 外掛同一套的結構化事件協定，
我們只是這個協定裡的一個「client」，實際的工具呼叫、危險指令判斷、記憶/技能寫入
審查，全部由 hermes 自己的 acp_adapter 完成——我們不猜、不重寫任何邏輯，只負責：
  1. 把使用者的訊息轉成 prompt 送進去
  2. 把 hermes 吐回來的結構化事件轉成我們自己的 SSE 標記格式往前端送
  3. 遇到 request_permission 就把完整的選項清單/真實指令內容丟給前端，
     等前端使用者選好，再把對應的 option_id 回傳給 hermes——不再用「塞 stdin 字元」
     這種土法煉鋼，是正式的 request/response。

已用本機 Ollama（llama3.1:8b）實測驗證過整條路徑，包含一次真正觸發 request_permission
（rm -rf 危險指令）、使用者核准後工具真的執行成功的完整往返。
"""
import asyncio
import json
import os
import time
import logging
from typing import AsyncIterator

import acp
from acp.schema import (
    ClientCapabilities,
    TextContentBlock,
    RequestPermissionResponse,
    AllowedOutcome,
    DeniedOutcome,
    PermissionOption,
)

logger = logging.getLogger("hermes-proxy.acp")

# 🔒 每個房間目前卡住等待使用者核准的狀態。
# room_id -> {"event": asyncio.Event, "options": [PermissionOption...], "decision_option_id": str|None}
# 跟舊版 active_processes 的角色一樣，只是現在存的是「等待核准的選項清單」而不是子進程物件本身。
pending_permission_requests: dict[str, dict] = {}

APPROVAL_TIMEOUT_SECONDS = 120.0  # 比舊版 30 秒寬鬆一點，因為選項變多了，使用者可能要多想一下


class HermesAcpClient:
    """
    實作 acp.Client 這個 Protocol 介面。hermes acp 子進程會透過 JSON-RPC
    呼叫這裡的方法——session_update 是單向通知（串流事件），request_permission
    是請求/回應（會卡住等我們回傳答案，這就是「一次性 subprocess 怎麼等使用者回應」
    的答案：不是我們在等，是 hermes 自己的 JSON-RPC 呼叫在等，我們的 subprocess
    全程都在跑，沒有中斷，只是它內部那一輪 prompt() 呼叫還沒返回而已）。
    """

    def __init__(self, room_id: str, event_queue: "asyncio.Queue"):
        self.room_id = room_id
        self.event_queue = event_queue

    async def session_update(self, session_id, update, **kwargs):
        await self.event_queue.put(update)

    async def request_permission(self, options: list[PermissionOption], session_id: str, tool_call, **kwargs):
        approve_event = asyncio.Event()
        pending_permission_requests[self.room_id] = {
            "event": approve_event,
            "options": options,
            "decision_option_id": None,
        }
        await self.event_queue.put({"__acp_permission_request__": True, "options": options, "tool_call": tool_call})

        try:
            logger.warning(f"🛡️ [ACP 核准攔截] 房間 {self.room_id} 觸發 request_permission，等待使用者選擇...")
            await asyncio.wait_for(approve_event.wait(), timeout=APPROVAL_TIMEOUT_SECONDS)
            chosen_id = pending_permission_requests[self.room_id]["decision_option_id"]
        except asyncio.TimeoutError:
            # 超時自癒：預設選第一個「拒絕一次」的選項，沒有就選清單最後一個，安全放行不卡死
            fallback = next((o for o in options if o.kind == "reject_once"), options[-1])
            chosen_id = fallback.optionId
            logger.warning(f"⏳ [ACP 超時自癒] 房間 {self.room_id} {APPROVAL_TIMEOUT_SECONDS}秒未回應，預設選擇: {chosen_id}")
        finally:
            pending_permission_requests.pop(self.room_id, None)

        chosen = next((o for o in options if o.optionId == chosen_id), options[-1])
        logger.info(f"👤 [ACP 人機協同] 房間 {self.room_id} 使用者選擇了: {chosen.name} ({chosen.optionId})")

        if chosen.kind.startswith("allow"):
            return RequestPermissionResponse(outcome=AllowedOutcome(optionId=chosen.optionId, outcome="selected"))
        return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))

    # 🚫 以下這些是給「編輯器整合」用的能力（讓 hermes 借用編輯器自己的終端機/檔案系統），
    # 我們不是編輯器，hermes 有自己內建的本機終端機/檔案工具（terminal.backend: local），
    # 不需要也不應該由我們代勞——明確回報「不支援」，讓 hermes 自動退回用它自己的內建機制，
    # 跟現有 `hermes chat` 模式下的行為完全一致，不是遺漏。
    async def create_terminal(self, *a, **kw):
        raise NotImplementedError("terminal ops 一律由 hermes 自己的 terminal.backend=local 處理")

    async def read_text_file(self, *a, **kw):
        raise NotImplementedError("file ops 一律由 hermes 自己的內建工具處理")

    async def release_terminal(self, *a, **kw):
        return None

    async def kill_terminal(self, *a, **kw):
        return None

    async def terminal_output(self, *a, **kw):
        raise NotImplementedError

    async def wait_for_terminal_exit(self, *a, **kw):
        raise NotImplementedError

    async def ext_method(self, method, params):
        return {}

    async def ext_notification(self, method, params):
        return None

    def on_connect(self, conn):
        pass


def submit_permission_decision(room_id: str, option_id: str) -> bool:
    """
    approve-write 端點呼叫這個函式，把使用者在前端點的選項 id 灌回去，
    喚醒卡在 request_permission 裡的 await。
    """
    ctx = pending_permission_requests.get(room_id)
    if not ctx:
        return False
    valid_ids = {o.optionId for o in ctx["options"]}
    if option_id not in valid_ids:
        raise ValueError(f"不合法的 option_id: {option_id}，合法選項: {sorted(valid_ids)}")
    ctx["decision_option_id"] = option_id
    ctx["event"].set()
    return True


async def run_acp_turn(
    agent_dir: str,
    room_id: str,
    message: str,
    env: dict,
    resume_session_id: str | None,
) -> AsyncIterator[dict]:
    """
    開一次 `hermes acp` 連線，跑一輪對話，把過程中收到的每一個結構化事件
    透過 async generator yield 出去。呼叫端（main.py）負責把這些事件轉成 SSE。

    最後一個 yield 會是 {"__acp_turn_complete__": True, "session_id": ...}，
    帶回這輪對話的 session_id，讓呼叫端存進 session_mapping.json 給下次 resume 用
    （跟舊版 --resume 機制共用同一份映射檔案，不用另外設計）。
    """
    event_queue: asyncio.Queue = asyncio.Queue()
    client = HermesAcpClient(room_id, event_queue)

    proc = await asyncio.create_subprocess_exec(
        "hermes", "acp",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    async def _drain_stderr():
        # hermes acp 把所有人類可讀的日誌都導向 stderr（stdout 保留給 JSON-RPC），
        # 這裡只寫進伺服器自己的 log，不會混進使用者看到的內容
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            logger.debug(f"[hermes acp stderr] {line.decode(errors='ignore').rstrip()}")

    stderr_task = asyncio.create_task(_drain_stderr())
    agent = None

    try:
        agent = acp.connect_to_agent(client, proc.stdin, proc.stdout)
        await agent.initialize(protocol_version=acp.PROTOCOL_VERSION, client_capabilities=ClientCapabilities())

        if resume_session_id:
            try:
                sess = await agent.resume_session(cwd="/workspace", session_id=resume_session_id)
                # 🛡️ 檢查回傳物件中是否有 session_id，沒有就代表雖然沒噴 exception 但內容是失敗的
                if not hasattr(sess, "session_id") or not sess.session_id:
                    logger.warning(f"[ACP] resume_session 回傳格式異常，可能新模型不支援此會話，改開新 session")
                    sess = await agent.new_session(cwd="/workspace")
            except Exception as e:
                logger.warning(f"[ACP] resume_session 失敗（{e}），改開新 session")
                sess = await agent.new_session(cwd="/workspace")
        else:
            sess = await agent.new_session(cwd="/workspace")

        # 🐛 0716 修正：resume_session() 內部會把歷史對話透過 session_update 重播一次，
        # 這些通知跟這輪真正的新事件共用同一個 event_queue，先前沒有丟棄，
        # 導致使用者回報「每次都先看到上一輪內容」——resume 完、開始新 prompt 前，
        # 把目前已經堆積在佇列裡的重播事件全部丟棄，只留下這輪 prompt() 之後才進來的事件。
        discarded = 0
        while not event_queue.empty():
            event_queue.get_nowait()
            discarded += 1
        if discarded:
            logger.info(f"[ACP] resume_session 丟棄了 {discarded} 個重播事件")

        # 🛡️ 安全獲取 session_id，如果連 new_session 都因為新模型壞掉而沒拿到，就主動拋出有意義的錯誤
        session_id = getattr(sess, "session_id", None)
        if not session_id:
            raise RuntimeError(f"❌ 無法從 ACP 獲取有效的 session_id！請檢查新模型是否啟動成功、API Key 是否正確。收到回傳: {sess}")

        prompt_task = asyncio.create_task(
            agent.prompt(session_id=session_id, prompt=[TextContentBlock(text=message, type="text")])
        )

        while not prompt_task.done():
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=0.3)
                yield event
            except asyncio.TimeoutError:
                continue

        # prompt 已經結束，把佇列裡剩下還沒消化的事件（例如最後的 UsageUpdate）也送完
        while not event_queue.empty():
            yield event_queue.get_nowait()

        await prompt_task  # 讓例外（如果有）在這裡正確拋出

        yield {"__acp_turn_complete__": True, "session_id": session_id}

    finally:
        # 🐛 0716 修正：光 terminate 子進程不夠，acp 連線物件自己還開了背景的
        # Sender/Dispatcher loop（實測時在 log 看到 "Task was destroyed but it is
        # pending!"），要先正式關閉連線本身，背景任務才會乾淨收掉，不會變成孤兒任務。
        if agent is not None:
            try:
                await agent.close()
            except Exception:
                pass
        stderr_task.cancel()
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
