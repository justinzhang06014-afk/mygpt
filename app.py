import os
import yaml
import logging
import shutil
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Profile 的基礎路徑
PROFILES_BASE_DIR = "/opt/data/profiles"
HERMES_CORE_URL = os.getenv("HERMES_CORE_URL", "http://independent_hermes_core:8642/v1/chat/completions")
API_SERVER_KEY = os.getenv("API_SERVER_KEY", "my-local-test-token")

app = FastAPI()

class ChatRequest(BaseModel):
    agent_id: str
    room_id: str
    message: str
    system_prompt: str = ""

def verify_and_init_profile(agent_id: str, system_prompt: str = "") -> str:
    """
    Initialize agent profile - same as hermes.is_new_agent() + hermes.initialize_agent()
    """
    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    memories_dir = os.path.join(agent_dir, "memories")

    soul_path = os.path.join(agent_dir, "SOUL.md")
    config_path = os.path.join(agent_dir, "config.yaml")
    memory_md_path = os.path.join(memories_dir, "memory.md")
    user_md_path = os.path.join(memories_dir, "user.md")

    try:
        # Check if new agent (equivalent to hermes.is_new_agent())
        if not os.path.exists(agent_dir):
            logger.info(f"Detecting new Agent [{agent_id}], creating profile sandbox...")
            os.makedirs(memories_dir, exist_ok=True)

            # Initialize default config
            default_config = {
                "memory": {
                    "memory_enabled": True,
                    "user_profile_enabled": True,
                    "provider": "built-in"
                }
            }
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(default_config, f, allow_unicode=True)

            with open(memory_md_path, "w", encoding="utf-8") as f:
                f.write("# Agent Memory\n")
            with open(user_md_path, "w", encoding="utf-8") as f:
                f.write("# User Profile\n")

            logger.info(f"Agent [{agent_id}] Profile created.")

        # Set or update system prompt (equivalent to hermes.set_system_prompt())
        if system_prompt:
            with open(soul_path, "w", encoding="utf-8") as f:
                f.write(system_prompt)
            logger.info(f"Agent [{agent_id}] SOUL.md updated successfully")

        return agent_dir

    except Exception as e:
        logger.error(f"Failed to initialize Agent [{agent_id}] Profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def load_soul_prompt(agent_id: str) -> str:
    soul_path = os.path.join(PROFILES_BASE_DIR, agent_id, "SOUL.md")
    if os.path.exists(soul_path):
        with open(soul_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

@app.post("/api/agent/chat")
async def agent_chat(payload: ChatRequest):
    # Ensure agent profile exists
    verify_and_init_profile(payload.agent_id, payload.system_prompt)

    # Read soul prompt
    soul_prompt = load_soul_prompt(payload.agent_id)

    messages = []
    if soul_prompt:
        messages.append({
            "role": "system",
            "content": soul_prompt
        })

    # Include room info in conversation context (keep as is)
    agent_context = f"[Agent: {payload.agent_id}] [Room: {payload.room_id}]"
    messages.append({
        "role": "user",
        "content": f"{agent_context} {payload.message}"
    })

    core_payload = {
        "model": os.getenv("LLM_MODEL", "Qwen/Qwen3.6-27B"),
        "messages": messages
    }

    # 🎯 CORRECT IMPLEMENTATION:
    # Use ONLY agent_id for profile switching
    # This allows same agent across rooms to share memory
    profile_name = payload.agent_id  # ✅ KEY CHANGE: Only agent_id, no room_id

    headers = {
        "X-Hermes-Session-Id": profile_name,  # ✅ Use profile name as session ID
        "X-Hermes-Agent-Id": payload.agent_id,
        "Authorization": f"Bearer {API_SERVER_KEY}",
        "Content-Type": "application/json"
    }

    logger.info(f"Forwarding request to Hermes Core. Profile: {profile_name}")

    async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
        try:
            response = await client.post(HERMES_CORE_URL, json=core_payload, headers=headers)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            core_json = response.json()
            try:
                reply_content = core_json["choices"][0]["message"]["content"]
                return {"reply": reply_content}
            except (KeyError, IndexError):
                return core_json

        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

@app.delete("/api/agent/{agent_id}")
async def reset_agent(agent_id: str):
    agent_dir = os.path.join(PROFILES_BASE_DIR, agent_id)
    if not os.path.exists(agent_dir):
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        shutil.rmtree(agent_dir)
        return {"status": "success", "message": f"Agent [{agent_id}] memory reset."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))