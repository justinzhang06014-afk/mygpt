import asyncio
import json
import os
import time
from collections import deque

import docker
from config import logger

# 🔌 跟 runtime_manager.py 用同一種連法，不需要對外開 port
# DOCKER_SOCK_URL = "unix://var/run/docker.sock"
DOCKER_SOCK_URL = "npipe:////./pipe/docker_engine"
STATS_OUTPUT_PATH = "/opt/data/monitor_stats.json"
SAMPLE_INTERVAL_SECONDS = 10
ROLLING_WINDOW_SAMPLES = 30  # 30 筆 * 10 秒 = 5 分鐘

# container_name -> deque[dict]，各自獨立的滾動採樣歷史
_history: dict[str, deque] = {}

# container_name -> {cpu_percent: {min, max}, mem_usage_mb: {min, max}}
_peak: dict[str, dict] = {}

def _get_docker_client() -> docker.DockerClient:
    # 💡 讓 Docker 根據環境變數自動尋找最正確的連線方式
    return docker.from_env()

# def _get_docker_client() -> docker.DockerClient:
#     return docker.DockerClient(base_url=DOCKER_SOCK_URL)
# def _get_docker_client() -> docker.DockerClient:
#     # 💡 不要寫死 unix://，改成從環境變數載入，這樣才能支援 TCP 連線
#     return docker.from_env()


def _compute_cpu_percent(stats: dict) -> float:
    """標準 docker stats CPU 百分比算法：本輪 CPU 用量差 / 本輪系統時間差 * 核心數"""
    try:
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        online_cpus = stats["cpu_stats"].get("online_cpus") or len(
            stats["cpu_stats"].get("cpu_usage", {}).get("percpu_usage") or [1]
        )
        if system_delta > 0 and cpu_delta > 0:
            return round((cpu_delta / system_delta) * online_cpus * 100.0, 2)
    except (KeyError, ZeroDivisionError, TypeError):
        pass
    return 0.0


def _sample_container(container) -> dict:
    stats = container.stats(stream=False)
    mem_usage = stats.get("memory_stats", {}).get("usage", 0)
    mem_limit = stats.get("memory_stats", {}).get("limit", 0)

    networks = stats.get("networks") or {}
    net_rx = sum(n.get("rx_bytes", 0) for n in networks.values())
    net_tx = sum(n.get("tx_bytes", 0) for n in networks.values())

    blkio_entries = stats.get("blkio_stats", {}).get("io_service_bytes_recursive") or []
    block_read = sum(e["value"] for e in blkio_entries if e.get("op") == "Read")
    block_write = sum(e["value"] for e in blkio_entries if e.get("op") == "Write")

    return {
        "cpu_percent": _compute_cpu_percent(stats),
        "mem_usage_mb": round(mem_usage / (1024 * 1024), 2),
        "mem_limit_mb": round(mem_limit / (1024 * 1024), 2) if mem_limit else 0,
        "net_rx_mb": round(net_rx / (1024 * 1024), 2),
        "net_tx_mb": round(net_tx / (1024 * 1024), 2),
        "block_read_mb": round(block_read / (1024 * 1024), 2),
        "block_write_mb": round(block_write / (1024 * 1024), 2),
        # 🚧 先預留欄位：這台主機/這些 container 沒有 GPU passthrough，之後真的要採集
        # 再接 nvidia-smi 或類似工具，資料結構先留著不用再改一次
        "gpu": None,
    }


def _average_samples(samples: list) -> dict:
    if not samples:
        return {}
    keys = [k for k in samples[0].keys() if k != "gpu"]
    avg = {k: round(sum(s[k] for s in samples) / len(samples), 2) for k in keys}
    avg["gpu"] = None
    return avg


def _peak_update(name: str, cpu: float, mem_mb: float):
    """紀錄高峰/低峰（滾動視窗內）"""
    if name not in _peak:
        _peak[name] = {"cpu_percent": {"min": cpu, "max": cpu}, "mem_usage_mb": {"min": mem_mb, "max": mem_mb}}
    p = _peak[name]
    p["cpu_percent"]["min"] = min(p["cpu_percent"]["min"], cpu)
    p["cpu_percent"]["max"] = max(p["cpu_percent"]["max"], cpu)
    p["mem_usage_mb"]["min"] = min(p["mem_usage_mb"]["min"], mem_mb)
    p["mem_usage_mb"]["max"] = max(p["mem_usage_mb"]["max"], mem_mb)


def _peak_get(name: str) -> dict:
    if name not in _peak:
        return {}
    p = _peak[name]
    return {
        "min": {"cpu_percent": p["cpu_percent"]["min"], "mem_usage_mb": p["mem_usage_mb"]["min"]},
        "max": {"cpu_percent": p["cpu_percent"]["max"], "mem_usage_mb": p["mem_usage_mb"]["max"]},
    }


async def _monitor_loop():
    while True:
        try:
            client = _get_docker_client()
            try:
                containers = client.containers.list(filters={"name": "hermes-runtime-"})
                snapshot = {}
                for container in containers:
                    user_id = container.name.replace("hermes-runtime-", "", 1)
                    try:
                        current = _sample_container(container)
                    except Exception as e:
                        logger.warning(f"[監控] 採樣 {container.name} 失敗，略過本輪: {str(e)}")
                        continue

                    history = _history.setdefault(container.name, deque(maxlen=ROLLING_WINDOW_SAMPLES))
                    history.append(current)
                    _peak_update(container.name, current["cpu_percent"], current["mem_usage_mb"])

                    snapshot[user_id] = {
                        "container_name": container.name,
                        "current": current,
                        "avg_5min": _average_samples(list(history)),
                        "min": _peak_get(container.name).get("min", {}),
                        "max": _peak_get(container.name).get("max", {}),
                    }
            finally:
                client.close()

            output = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
                "containers": snapshot,
            }
            os.makedirs(os.path.dirname(STATS_OUTPUT_PATH), exist_ok=True)
            with open(STATS_OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"[監控] 採樣迴圈發生異常: {str(e)}")

        await asyncio.sleep(SAMPLE_INTERVAL_SECONDS)


def start_monitor_task():
    # asyncio.create_task(_monitor_loop())
    # logger.info(f"📊 資源監控背景迴圈已啟動，每 {SAMPLE_INTERVAL_SECONDS} 秒採樣一次，寫入 {STATS_OUTPUT_PATH}")
    logger.info(f"📊 資源監控已關閉，改用外部工具監看")