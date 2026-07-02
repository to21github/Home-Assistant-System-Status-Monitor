"""系统指标采集模块。

负责读取宿主机 CPU / 内存 / 磁盘 / 网络 / 温度 / 负载 等硬件指标，
以及通过 Supervisor API 获取 Home Assistant 连接状态。
所有采集函数内置缓存以减轻重复请求压力。
"""

import logging
import os
import time
import psutil
import requests

_log = logging.getLogger(__name__)
# 提示：默认日志级别为 WARNING，若需查看 DEBUG 日志（如传感器读取失败），
# 请在 gunicorn 启动时添加 --log-level debug

# ---- 常量 ----
SUPERVISOR_URL = "http://supervisor"
SUPERVISOR_HOST_INFO_URL = f"{SUPERVISOR_URL}/host/info"
_BYTE_GB = 1024 ** 3
_KB_GB = 1024 ** 2

# ---- 采集缓存（避免并行请求重复采集）----
# 注意：此处使用模块级变量做简易缓存，依赖 gunicorn sync worker 单线程模型。
# 若改用 gthread/gevent 等多线程 worker，需添加 threading.Lock 保护。
_cache = None
_cache_time = 0
_CACHE_TTL = 2  # 秒

_ha_cache = None
_ha_cache_time = 0
_HA_CACHE_TTL = 10  # 秒（HA 状态变化慢，可长缓存）

def _get_cpu_temp():
    """获取 CPU 温度，依次尝试 psutil → /sys/class/thermal → 返回 None"""
    # 1) psutil sensors_temperatures（过滤 CPU 相关传感器）
    try:
        temps = psutil.sensors_temperatures()
        cpu_keys = {"coretemp", "k10temp", "cpu_thermal", "acpitz", "zenpower"}
        if temps:
            for name, entries in temps.items():
                if name not in cpu_keys:
                    continue
                for e in entries:
                    if e.current and e.current > 0:
                        return round(e.current, 1)
    except Exception:
        _log.debug("psutil sensors_temperatures 失败", exc_info=True)
        pass

    # 2) /sys/class/thermal 回退
    try:
        for root, dirs, _ in os.walk("/sys/class/thermal"):
            for d in dirs:
                if d.startswith("thermal_zone"):
                    tz_dir = os.path.join(root, d)
                    type_file = os.path.join(tz_dir, "type")
                    temp_file = os.path.join(tz_dir, "temp")
                    if os.path.isfile(type_file) and os.path.isfile(temp_file):
                        with open(type_file) as f:
                            ttype = f.read().strip()
                        if ttype in ("cpu-thermal", "x86_pkg_temp", "acpitz", "k10temp"):
                            with open(temp_file) as f:
                                val = int(f.read().strip()) / 1000.0
                            if 10 < val < 150:
                                return round(val, 1)
    except Exception:
        _log.debug("/sys/class/thermal 读取失败", exc_info=True)
        pass

    return None


def _round_gb_from_kb(value_kb):
    return round(value_kb / _KB_GB, 1)


def _read_memory_from_meminfo(path="/proc/meminfo"):
    """从 /proc/meminfo 读取真实内存使用量，按 total - available 计算已用。"""
    fields = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            key, _, rest = line.partition(":")
            if not rest:
                continue
            parts = rest.strip().split()
            if not parts:
                continue
            try:
                fields[key] = int(parts[0])
            except ValueError:
                continue

    total_kb = fields.get("MemTotal")
    available_kb = fields.get("MemAvailable")
    if not total_kb or available_kb is None:
        return None

    used_kb = max(0, total_kb - available_kb)
    percent = round((used_kb / total_kb) * 100, 1)
    return {
        "total": _round_gb_from_kb(total_kb),
        "used": _round_gb_from_kb(used_kb),
        "free": _round_gb_from_kb(available_kb),
        "percent": percent,
        "source": "proc_meminfo",
    }


def _collect_memory():
    try:
        memory = _read_memory_from_meminfo()
        if memory:
            return memory
    except Exception:
        _log.debug("/proc/meminfo 读取失败，回退 psutil", exc_info=True)

    mem = psutil.virtual_memory()
    total = mem.total
    available = mem.available
    used = max(0, total - available)
    return {
        "total": round(total / _BYTE_GB, 1),
        "used": round(used / _BYTE_GB, 1),
        "free": round(available / _BYTE_GB, 1),
        "percent": round((used / total) * 100, 1) if total else 0,
        "source": "psutil",
    }


def _supervisor_headers():
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _number_or_none(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _collect_host_disks():
    """优先通过 Supervisor 读取宿主机磁盘容量。"""
    try:
        resp = requests.get(
            SUPERVISOR_HOST_INFO_URL,
            headers=_supervisor_headers(),
            timeout=5,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        _log.debug("Supervisor host/info 读取失败，回退本地挂载点", exc_info=True)
        return []

    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    total = _number_or_none(data.get("disk_total"))
    used = _number_or_none(data.get("disk_used"))
    free = _number_or_none(data.get("disk_free"))
    if total is None or total <= 0:
        return []
    if used is None and free is not None:
        used = max(0, total - free)
    if free is None and used is not None:
        free = max(0, total - used)
    if used is None:
        return []

    percent = round((used / total) * 100, 1)
    return [{
        "mount": "host",
        "total": round(total, 1),
        "used": round(used, 1),
        "free": round(free, 1) if free is not None else None,
        "percent": percent,
        "source": "supervisor_host_info",
    }]


def _collect_mount_disks():
    disks = []
    for mp in ["/", "/config", "/data"]:
        try:
            usage = psutil.disk_usage(mp)
            disks.append({
                "mount": mp,
                "total": round(usage.total / _BYTE_GB, 1),
                "used": round(usage.used / _BYTE_GB, 1),
                "free": round(usage.free / _BYTE_GB, 1),
                "percent": usage.percent,
                "source": "psutil_disk_usage",
            })
        except Exception:
            _log.debug("磁盘 %s 读取失败", mp, exc_info=True)
            pass
    return disks


def _collect_disks():
    return _collect_host_disks() or _collect_mount_disks()


def collect():
    """采集所有系统指标（带 2s 缓存），返回字典"""
    global _cache, _cache_time
    now = time.time()
    if _cache is not None and (now - _cache_time) < _CACHE_TTL:
        return _cache

    try:
        return _do_collect()
    except Exception:
        # 采集失败时返回过期缓存，避免单次异常导致前端空白
        if _cache is not None:
            return _cache
        raise


def _do_collect():
    """实际采集逻辑，失败时由 collect() 兜底"""
    global _cache, _cache_time
    now = time.time()

    # --- CPU ---
    cpu_percent = psutil.cpu_percent(interval=0.2)
    cpu_count = psutil.cpu_count(logical=True)
    cpu_count_physical = psutil.cpu_count(logical=False)

    # --- 内存 ---
    memory = _collect_memory()

    # --- 磁盘（优先读取宿主机，失败回退 / 和 /data）---
    disks = _collect_disks()

    # --- 负载 ---
    load1, load5, load15 = psutil.getloadavg()

    # --- 温度 ---
    cpu_temp = _get_cpu_temp()

    # --- 启动时间 ---
    boot_time = psutil.boot_time()
    uptime_seconds = int(time.time() - boot_time)

    _cache = {
        "cpu": {
            "percent": cpu_percent,
            "count": cpu_count,
            "count_physical": cpu_count_physical,
        },
        "memory": memory,
        "disks": disks,
        "load": {
            "load1": round(load1, 2),
            "load5": round(load5, 2),
            "load15": round(load15, 2),
        },
        "temperature": cpu_temp,
        "uptime": uptime_seconds,
        "timestamp": int(time.time()),
    }
    _cache_time = now
    return _cache


def collect_ha_status():
    """采集 Home Assistant 连接状态（带 10s 缓存）"""
    global _ha_cache, _ha_cache_time
    now = time.time()
    if _ha_cache is not None and (now - _ha_cache_time) < _HA_CACHE_TTL:
        return _ha_cache

    result = {
        "core_connected": False,
        "latency_ms": None,
        "supervisor_healthy": None,
    }

    headers = _supervisor_headers()

    # ---- HA Core 状态 & 延迟 ----
    latencies = []
    for _ in range(3):
        try:
            t0 = time.monotonic()
            resp = requests.get(
                f"{SUPERVISOR_URL}/core/api/",
                headers=headers,
                timeout=5,
            )
            lat = (time.monotonic() - t0) * 1000
            if resp.status_code in (200, 401):
                latencies.append(lat)
                result["core_connected"] = True
        except Exception:
            _log.debug("HA 延迟探测失败", exc_info=True)
            pass
        if len(latencies) < 3:
            time.sleep(0.3)

    if latencies:
        result["latency_ms"] = round(sum(latencies) / len(latencies), 1)

    _ha_cache = result
    _ha_cache_time = now
    return result
