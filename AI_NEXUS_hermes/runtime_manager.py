"""
每個帳號一個 hermes docker：跟 hermes-agent/runtime_manager.py 同一套已驗證邏輯，
逐字複製 + 改容器命名前綴（避免跟 hermes-agent-proxy 自己 clone 出來的
hermes-runtime-<user_id> 撞名）。

範圍跟使用者說的一致：這支只管「怎麼 ensure/建立容器」的邏輯，容器實際存在哪台機器、
docker.sock/volume 怎麼掛進來，是外部（部署這支服務的人）決定的，不是這支程式碼管的。

生命週期範圍（已知現況，跟正式 hermes-agent 一樣，不是這裡漏做）：
- ✅ ensure 冪等：重複呼叫同一個 user_id 不會重建，只會確認/喚醒既有容器。
- ✅ 容器意外停掉會自動重啟（restart_policy=always + ensure 呼叫時偵測到非 running 會 start()）。
- ❌ 閒置容器的自動關閉/刪除：還沒做，這在 hermes-agent/docs 也還是待決策項目，
  等實際流量規模出來、需要抓資源上限的時候再補。
"""
import os
import shutil
import socket
import time
from typing import Optional

import docker
from docker.errors import NotFound

from config import logger
import orchestrator_client

DOCKER_SOCK_URL = "unix://var/run/docker.sock"
READINESS_TIMEOUT_SECONDS = 30
CONTAINER_PREFIX = "ainexus-hermes"


def _get_docker_client() -> docker.DockerClient:
    return docker.DockerClient(base_url=DOCKER_SOCK_URL)


def _get_self_container(client: docker.DockerClient):
    return client.containers.get(socket.gethostname())


def _get_host_data_root(self_container) -> str:
    for mount in self_container.attrs.get("Mounts", []):
        if mount.get("Destination") == "/opt/data":
            return mount.get("Source")
    raise RuntimeError("找不到自身容器 /opt/data 的掛載來源，無法建立使用者專屬 Runtime")


def _build_child_volumes(self_container, user_host_path: str) -> dict:
    volumes = {}
    for mount in self_container.attrs.get("Mounts", []):
        source = mount.get("Source")
        dest = mount.get("Destination")
        if not source or not dest:
            continue
        if dest == "/var/run/docker.sock":
            continue
        if dest == "/opt/data":
            volumes[user_host_path] = {"bind": "/opt/data", "mode": "rw"}
        else:
            mode = "rw" if mount.get("RW", True) else "ro"
            volumes[source] = {"bind": dest, "mode": mode}
    return volumes


def _build_child_environment(self_container) -> dict:
    env_list = self_container.attrs.get("Config", {}).get("Env", [])
    env = {}
    for entry in env_list:
        if "=" in entry:
            key, _, value = entry.partition("=")
            env[key] = value
    return env


def _wait_until_ready(container_name: str, port: int = 8643, timeout_seconds: int = READINESS_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((container_name, port), timeout=1.5):
                return
        except OSError as e:
            last_error = e
            time.sleep(0.5)
    raise RuntimeError(f"使用者 Runtime 容器 {container_name} 在 {timeout_seconds} 秒內未就緒: {last_error}")


def _get_published_host_port(container) -> Optional[int]:
    """如果這個容器的 8643 有對外發布，回傳對應的 host port，方便直接開瀏覽器測 Swagger。"""
    container.reload()
    bindings = (container.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}).get("8643/tcp")
    if not bindings:
        return None
    return int(bindings[0]["HostPort"])


def ensure_user_runtime(user_id: str, agent_dir: str = None) -> dict:
    """
    確保 user_id 專屬的 AI_NEXUS_hermes 容器存在且正在運行，回傳其內部 base_url。
    這個 base_url 只給同一個 Docker network 裡的其他服務（對接的前後端）直接呼叫，
    之後的每一輪對話都直接打這個 base_url，不需要再經過這支 ensure 服務。

    📍 有設定 ORCHESTRATOR_URL 環境變數，就整個委派給 orchestrator_client.py——
    同事的服務負責實際建容器，這裡只負責轉發跟拿回位址。沒設定就照舊走下面
    docker.sock 那條路（本機測試/還沒接同事服務時用）。

    #0722修正：當使用 orchestrator 時，會回傳 externalBaseUrl（如果啟用），
    允許透過對方主機的 External Access Proxy 存取容器服務。

    🧪 PUBLISH_CHILD_PORTS=true（只建議測試用，只在走 docker.sock 這條路才有效）：
    額外把子容器的 8643 發布到一個隨機 host port，回傳的 swagger_url 可以直接拿去
    瀏覽器開——正式環境不要開這個，子容器應該只給同網路的其他服務內部呼叫。
    
    Args:
        user_id: 使用者 ID
        agent_dir: 本地 agent 目錄（僅遠端模式需要）
    """
    if orchestrator_client.is_enabled():
        return orchestrator_client.ensure_user_runtime(user_id, agent_dir)

    container_name = f"{CONTAINER_PREFIX}-{user_id}"
    client = _get_docker_client()
    publish_ports = os.getenv("PUBLISH_CHILD_PORTS", "").lower() in ("1", "true", "yes")

    try:
        existing = client.containers.get(container_name)
        if existing.status != "running":
            logger.info(f"🔄 [Runtime] 使用者 {user_id} 的容器已存在但未啟動，重新啟動中...")
            existing.start()
        _wait_until_ready(container_name)
        host_port = _get_published_host_port(existing)
        result = {"status": "existing", "container_name": container_name, "base_url": f"http://{container_name}:8643"}
        if host_port:
            result["swagger_url"] = f"http://localhost:{host_port}/docs"
        return result

    except NotFound:
        pass

    logger.info(f"🚀 [Runtime] 使用者 {user_id} 尚無專屬容器，開始建立...")

    self_container = _get_self_container(client)
    host_data_root = _get_host_data_root(self_container)
    user_host_path = os.path.join(host_data_root, "users", user_id).replace("\\", "/")

    image = self_container.image.id
    networks = list(self_container.attrs.get("NetworkSettings", {}).get("Networks", {}).keys())
    volumes = _build_child_volumes(self_container, user_host_path)
    environment = _build_child_environment(self_container)

    container = client.containers.run(
        image=image,
        name=container_name,
        environment=environment,
        volumes=volumes,
        network=networks[0] if networks else None,
        ports={"8643/tcp": None} if publish_ports else None,
        detach=True,
        restart_policy={"Name": "always"},
    )

    for extra_network in networks[1:]:
        client.networks.get(extra_network).connect(container)

    _wait_until_ready(container_name)

    logger.info(f"✅ [Runtime] 已為使用者 {user_id} 建立容器: http://{container_name}:8643")
    result = {"status": "created", "container_name": container_name, "base_url": f"http://{container_name}:8643"}
    if publish_ports:
        host_port = _get_published_host_port(container)
        if host_port:
            result["swagger_url"] = f"http://localhost:{host_port}/docs"
    return result


def _describe_container(container) -> dict:
    name = container.name
    user_id = name[len(CONTAINER_PREFIX) + 1:] if name.startswith(CONTAINER_PREFIX + "-") else name
    info = {
        "user_id": user_id,
        "container_name": name,
        "status": container.status,
        "base_url": f"http://{name}:8643",
    }
    host_port = _get_published_host_port(container)
    if host_port:
        info["swagger_url"] = f"http://localhost:{host_port}/docs"
    return info


def list_user_runtimes() -> list[dict]:
    """
    列出目前這台機器上所有使用者的容器（Read - 列表），供 CRUD 的 GET /api/users 用。
    走 orchestrator 模式時還沒有對應的「列表」端點可以委派（草案沒定義），先明確
    報錯而不是假裝有結果——等同事那邊有等效端點，在這裡加委派邏輯就好。
    """
    if orchestrator_client.is_enabled():
        raise RuntimeError("走 orchestrator 模式時尚未支援列出使用者，請跟同事確認等效端點後在 runtime_manager.py 補上")
    client = _get_docker_client()
    containers = client.containers.list(all=True, filters={"name": f"{CONTAINER_PREFIX}-"})
    return [_describe_container(c) for c in containers]


def get_user_runtime(user_id: str) -> Optional[dict]:
    """查詢單一使用者的容器狀態（Read - 單筆），不存在回傳 None。"""
    if orchestrator_client.is_enabled():
        raise RuntimeError("走 orchestrator 模式時尚未支援查詢單一使用者，請跟同事確認等效端點後在 runtime_manager.py 補上")
    client = _get_docker_client()
    try:
        container = client.containers.get(f"{CONTAINER_PREFIX}-{user_id}")
    except NotFound:
        return None
    return _describe_container(container)


def delete_user_runtime(user_id: str, wipe_data: bool = False) -> bool:
    """
    刪除一個使用者：停止並移除容器（Delete）。找不到容器回傳 False。
    wipe_data=True 才會連 host 上的 profile 資料夾一起刪掉——預設不刪，避免手滑
    誤刪使用者的記憶/設定，這是刻意的安全預設值，不是漏做。
    """
    if orchestrator_client.is_enabled():
        raise RuntimeError("走 orchestrator 模式時尚未支援刪除使用者，請跟同事確認等效端點後在 runtime_manager.py 補上")
    client = _get_docker_client()
    container_name = f"{CONTAINER_PREFIX}-{user_id}"
    try:
        container = client.containers.get(container_name)
    except NotFound:
        return False

    container.remove(force=True)
    logger.info(f"🗑️ [Runtime] 已刪除使用者 {user_id} 的容器 {container_name}")

    if wipe_data:
        try:
            self_container = _get_self_container(client)
            host_data_root = _get_host_data_root(self_container)
            user_host_path = os.path.join(host_data_root, "users", user_id)
            shutil.rmtree(user_host_path, ignore_errors=True)
            logger.info(f"🗑️ [Runtime] 已清除使用者 {user_id} 的資料夾: {user_host_path}")
        except Exception as e:
            logger.warning(f"⚠️ [Runtime] 清除使用者 {user_id} 資料夾失敗（容器已刪除，只是資料留著）: {str(e)}")

    return True
