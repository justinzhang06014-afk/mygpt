import os
import socket
import time
import docker
from docker.errors import NotFound
from config import logger

DOCKER_SOCK_URL = "unix://var/run/docker.sock"
READINESS_TIMEOUT_SECONDS = 30


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


def _wait_until_ready(container_name: str, port: int = 8643, timeout_seconds: int = READINESS_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while time.monotonic() < deadline:
        try:
            # 這裡依然可以用內部容器名稱測試，因為 Provisioner 跟新容器在同一個 Docker 網路內
            with socket.create_connection((container_name, port), timeout=1.5):
                return
        except OSError as e:
            last_error = e
            time.sleep(0.5)
    raise RuntimeError(f"使用者 Runtime 容器 {container_name} 在 {timeout_seconds} 秒內未就緒: {last_error}")


def _build_child_environment(self_container) -> dict:
    env_list = self_container.attrs.get("Config", {}).get("Env", [])
    env = {}
    for entry in env_list:
        if "=" in entry:
            key, _, value = entry.partition("=")
            env[key] = value
    return env


def ensure_user_runtime(user_id: str) -> str:
    """
    確保 user_id 專屬的 Hermes Runtime 容器存在且正在運行。

    🛡️【已實測核對，修正過一次真實 bug】回傳的網址只會被 C# 後端拿去打(兩者都是
    container，同一個 Docker compose network 裡)，從來不會被瀏覽器直接呼叫——瀏覽器
    永遠只打 nginx/C# 後端，由後端內部轉發。所以這裡不需要、也不能用「宿主機 IP + 動態
    對外 Port」：之前的版本用 _get_internal_ip() 去 dial 8.8.8.8 探測「對外 IP」，但那支
    程式碼是在 hermes-agent-proxy 這個 container 裡執行，探測到的其實是它自己在 Docker
    bridge 網路上的內部 IP(如 172.18.0.4)，跟子容器對外映射的隨機 host port 兜在一起，
    兩者對不上號，會直接 Connection refused。正確做法是用 container 名稱(Docker 內部
    DNS)+ container 自己監聽的固定 8643 port，同網路的其他 container 本來就連得到，
    完全不需要對外發布 port，也更簡單可靠(不受 Docker 重啟後隨機 port 改變影響)。
    """
    container_name = f"hermes-runtime-{user_id}"
    client = _get_docker_client()

    try:
        existing = client.containers.get(container_name)
        if existing.status != "running":
            logger.info(f"🔄 [Runtime Provisioner] 使用者 {user_id} 的 Runtime 已存在但未啟動，重新啟動中...")
            existing.start()
        _wait_until_ready(container_name)
        return f"http://{container_name}:8643"

    except NotFound:
        pass

    logger.info(f"🚀 [Runtime Provisioner] 使用者 {user_id} 尚無專屬 Runtime，開始建立新容器...")

    self_container = _get_self_container(client)
    host_data_root = _get_host_data_root(self_container)
    user_host_path = os.path.join(host_data_root, "users", user_id).replace("\\", "/")

    image = self_container.image.id
    networks = list(self_container.attrs.get("NetworkSettings", {}).get("Networks", {}).keys())
    volumes = _build_child_volumes(self_container, user_host_path)
    environment = _build_child_environment(self_container)

    # 🔒 只需要接在內部 Docker network 上，不對外發布 port(不需要、也沒有瀏覽器會直接連它)
    container = client.containers.run(
        image=image,
        name=container_name,
        environment=environment,
        volumes=volumes,
        network=networks[0] if networks else None,
        detach=True,
        restart_policy={"Name": "always"},

        # 👇【關鍵新增：精準限制動態複製出來的 Hermes 帳號用量】👇
        # nano_cpus=1000000000,       # 限制最高 2.0 核 (10^9 nano_cpus = 1核)
        # mem_limit="1g",             # 限制最高記憶體為 2GB (天花板，過線會 OOM)
        # mem_reservation="0.5g",       # 保證分配 1GB 記憶體 (保底資源)
        # ipc_mode="host",             # 🚀 這行極重要！給予瀏覽器共享記憶體，防止 Chromium 報錯崩潰
    )

    for extra_network in networks[1:]:
        client.networks.get(extra_network).connect(container)

    _wait_until_ready(container_name)

    logger.info(f"✅ [Runtime Provisioner] 已為使用者 {user_id} 建立內部通道: http://{container_name}:8643")
    return f"http://{container_name}:8643"
