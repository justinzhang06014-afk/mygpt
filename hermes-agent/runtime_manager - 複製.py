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
    # 容器 hostname 預設就是自己的 container ID
    return client.containers.get(socket.gethostname())


def _get_host_data_root(self_container) -> str:
    """從自己的掛載資訊反查 /opt/data 對應的 host 實體路徑，用來當作複製給新使用者容器的範本"""
    for mount in self_container.attrs.get("Mounts", []):
        if mount.get("Destination") == "/opt/data":
            return mount.get("Source")
    raise RuntimeError("找不到自身容器 /opt/data 的掛載來源，無法建立使用者專屬 Runtime")


def _build_child_volumes(self_container, user_host_path: str) -> dict:
    """複製自己身上的所有掛載給子容器，但排除 docker.sock，並把 /opt/data 換成該使用者專屬路徑"""
    volumes = {}
    for mount in self_container.attrs.get("Mounts", []):
        source = mount.get("Source")
        dest = mount.get("Destination")
        if not source or not dest:
            continue
        if dest == "/var/run/docker.sock":
            continue  # 子容器絕對不能繼承 docker.sock，否則失去隔離意義
        if dest == "/opt/data":
            volumes[user_host_path] = {"bind": "/opt/data", "mode": "rw"}
        else:
            mode = "rw" if mount.get("RW", True) else "ro"
            volumes[source] = {"bind": dest, "mode": mode}
    return volumes


def _wait_until_ready(container_name: str, port: int = 8643, timeout_seconds: int = READINESS_TIMEOUT_SECONDS) -> None:
    """
    容器剛 run 起來不代表裡面的 uvicorn 已經能接受連線，直接回傳網址給 backend 打過去
    會出現 Connection refused。這裡用最單純的 TCP 連線重試，等到真的能連上才回傳。
    """
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
    回傳可供 backend 呼叫的容器內部網址（同一個 Docker network 內用容器名稱互通）。
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

    container = client.containers.run(
        image=image,
        name=container_name,
        environment=environment,
        volumes=volumes,
        network=networks[0] if networks else None,
        detach=True,
        restart_policy={"Name": "always"},
    )

    # 若自己同時掛在多個 network 上，其餘的也一併接上，確保 backend 一定連得到
    for extra_network in networks[1:]:
        client.networks.get(extra_network).connect(container)

    # 容器 run 起來只代表行程已建立，裡面的 uvicorn 還需要幾秒鐘才能真正接受連線
    _wait_until_ready(container_name)

    logger.info(f"✅ [Runtime Provisioner] 已為使用者 {user_id} 建立專屬 Hermes Runtime 容器: {container_name}")
    return f"http://{container_name}:8643"
