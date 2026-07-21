#!/usr/bin/env python3
"""
📊 終極懶人容器監控報表
讀取 monitor_stats.json，一次給你看：
  ✅ 即時值  ✅ 5分鐘加權平均  ✅ 最高峰  ✅ 最低峰  ✅ 記憶體條
用法：python monitor_dashboard.py                # 預設讀 /opt/data/monitor_stats.json
      python monitor_dashboard.py your_file.json  # 指定檔案
"""
import json
import sys
import re


def parse_mem_mb(s: str) -> float:
    """解析 '63.18MiB' → 63.18, '15.5GiB' → 15.5*1024"""
    s = s.strip()
    m = re.match(r'([\d.]+)\s*([A-Za-z]+)', s)
    if not m:
        return float(s)
    val = float(m.group(1))
    unit = m.group(2).upper()
    if unit == "GIB":
        val *= 1024
    elif unit == "GB":
        val *= 1000
    elif unit == "MIB":
        pass
    elif unit == "MB":
        pass
    elif unit in ("KB", "KIB"):
        val /= 1024
    elif unit == "TB":
        val *= 1024 * 1024
    elif unit == "B":
        val /= (1024 * 1024)
    return round(val, 2)


def parse_cpu(s: str) -> float:
    return float(s.strip().rstrip("%"))


def split_mem(s: str) -> tuple[float, float]:
    """'63.18MiB / 15.5GiB' → (63.18, 15.5*1024)"""
    parts = s.split(" / ")
    return parse_mem_mb(parts[0]), parse_mem_mb(parts[1])


def split_blkio(s: str) -> tuple[float, float]:
    """'80.4MB / 14.8MB' → (80.4, 14.8)"""
    parts = s.split(" / ")
    return parse_mem_mb(parts[0]), parse_mem_mb(parts[1])


def net_io_parse(s: str) -> float:
    """'5.45%' → 5.45"""
    return float(s.strip().rstrip("%"))


def make_bar(pct: float, width: int = 30) -> str:
    filled = min(width, max(0, int(width * pct / 100)))
    return "█" * filled + "░" * (width - filled)


def fmt_num(v, decimals=2):
    if v is None or v == "N/A":
        return "N/A"
    return f"{v:.{decimals}f}"


def print_dashboard(data: dict):
    containers = data.get("containers", {})
    ts = data.get("timestamp", "N/A")

    print()
    print("╔" + "═" * 90 + "╗")
    print("║" + " 📊  終極容器一眼報表  —  即時 / 5min 平均 / 高峰 / 低峰 ".center(88) + "║")
    print("║" + f"  取樣時間: {ts}".ljust(88) + "║")
    print("╚" + "═" * 90 + "╝")
    print()

    for cid, info in containers.items():
        name = info["container_name"]
        cur = info["current"]
        avg = info.get("avg_5min", {})
        mn = info.get("min", {})
        mx = info.get("max", {})

        cur_cpu = parse_cpu(cur["cpu_percent"])
        mem_usage, mem_limit = split_mem(cur["mem_usage"])
        mem_pct = (mem_usage / mem_limit * 100) if mem_limit > 0 else 0
        bar = make_bar(mem_pct, 40)

        net_rx = net_io_parse(cur["net_io"]) if " / " not in cur.get("net_io", "") else 0
        blkio = cur.get("block_io", "N/A")
        blk_read, blk_write = split_blkio(blkio) if " / " in blkio else (0, 0)

        print(f"  🐳 {name}")
        print()
        print(f"  ┌{'─' * 14}┬{'─' * 10}┬{'─' * 12}┬{'─' * 12}┬{'─' * 12}┐")
        print(f"  │ 指標        │ 即時值    │ 5min 平均  │ 最高峰      │ 最低峰      │")
        print(f"  ├{'─' * 14}┼{'─' * 10}┼{'─' * 12}┼{'─' * 12}┼{'─' * 12}┤")

        # CPU
        avg_cpu = avg.get("cpu_percent", 0) if avg else 0
        max_cpu = mx.get("cpu_percent", "N/A")
        min_cpu = mn.get("cpu_percent", "N/A")
        print(f"  │ CPU(%)      │ {fmt_num(cur_cpu, 2):>9}% │ {fmt_num(avg_cpu, 2):>10}% │ {fmt_num(max_cpu):>10} │ {fmt_num(min_cpu):>10} │")

        # Mem MB
        avg_mem = avg.get("mem_usage_mb", 0) if avg else 0
        max_mem = mx.get("mem_usage_mb", "N/A")
        min_mem = mn.get("mem_usage_mb", "N/A")
        print(f"  │ 記憶體(MB)  │ {fmt_num(mem_usage, 1):>9} │ {fmt_num(avg_mem, 1):>10} │ {fmt_num(max_mem):>10} │ {fmt_num(min_mem):>10} │")

        # Mem %
        print(f"  │ 記憶體使用率 │ {fmt_num(mem_pct, 1):>8}% │              │              │              │")
        print(f"  │              │ │{bar}|              │              │              │")

        # Disk I/O
        print(f"  │ 磁碟讀(MB)  │ {fmt_num(blk_read, 1):>9} │ {'N/A':>10} │ {'N/A':>10} │ {'N/A':>10} │")
        print(f"  │ 磁碟寫(MB)  │ {fmt_num(blk_write, 1):>9} │ {'N/A':>10} │ {'N/A':>10} │ {'N/A':>10} │")

        # Net
        avg_net = avg.get("net_io") if avg else 0
        print(f"  │ 網路(%)     │ {fmt_num(net_rx, 2):>9} │ {fmt_num(avg_net, 2):>10} │ {'N/A':>10} │ {'N/A':>10} │")

        print(f"  └{'─' * 14}┴{'─' * 10}┴{'─' * 12}┴{'─' * 12}┴{'─' * 12}┘")
        print()

    # 底部摘要
    print()
    print("  ┌─── 快速摘要 ─────────────────────────────────────────────────────────┐")
    total_mem = 0
    total_cpu = 0
    for cid, info in containers.items():
        cur = info["current"]
        mem_u, mem_l = split_mem(cur["mem_usage"])
        total_mem += mem_u
        total_cpu += parse_cpu(cur["cpu_percent"])
    print(f"  │  總 CPU 使用:   {fmt_num(total_cpu, 2)}%")
    print(f"  │  總記憶體使用:  {fmt_num(total_mem, 1)} MB")
    print(f"  └──────────────────────────────────────────────────────────────────────┘")
    print()


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "/opt/data/monitor_stats.json"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到檔案: {filepath}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析錯誤: {e}")
        sys.exit(1)

    print_dashboard(data)
