"""
健康评分引擎 — 完全遵循 README.md 中的评分规则。

规则摘要（100 分制，从 100 开始扣分）：

| 维度       | 条件                       | 扣分  |
|------------|----------------------------|-------|
| CPU        | > 90%                      | −25   |
|            | > 75%                      | −15   |
|            | > 50%                      | −5    |
| 内存       | > 90%                      | −25   |
|            | > 75%                      | −15   |
|            | > 50%                      | −5    |
| 磁盘       | > 90% (每块盘)             | −25   |
|            | > 75%                      | −15   |
|            | > 50%                      | −5    |
| 系统负载   | > 2× CPU 核心数            | −15   |
|            | > 1× CPU 核心数            | −10   |
| CPU温度    | > 80 °C                    | −15   |
|            | > 70 °C                    | −8    |
| 响应延迟   | > 500ms                    | −25   |
|            | > 200ms                    | −15   |
|            | > 100ms                    | −5    |
"""


def _dim_score(percent, thresholds):
    """通用的维度扣分：thresholds = [(>值, 扣分), ...]，返回 (扣分, 等级)"""
    for gt, penalty in thresholds:
        if percent > gt:
            return penalty, _level(penalty)
    return 0, "ok"


def _level(penalty):
    if penalty >= 20:
        return "critical"
    if penalty >= 10:
        return "warning"
    if penalty > 0:
        return "mild"
    return "ok"


def calculate(stats, ha_status):
    """
    计算综合健康评分。

    参数:
        stats:      来自 collector.collect() 的系统指标字典
        ha_status:  来自 collector.collect_ha_status() 的 HA 状态字典

    返回:
        {
            "total": int,            # 0-100
            "level": str,            # critical | warning | mild | ok
            "dimensions": [...],     # 每个维度详情
        }
    """
    dimensions = []
    total_penalty = 0

    # ---- CPU ----
    cpu_pct = stats["cpu"]["percent"]
    penalty, level = _dim_score(cpu_pct, [(90, 25), (75, 15), (50, 5)])
    total_penalty += penalty
    dimensions.append({
        "name": "CPU",
        "icon": "cpu",
        "value": cpu_pct,
        "unit": "%",
        "penalty": penalty,
        "sub_score": max(0, 100 - penalty),
        "level": level,
    })

    # ---- 内存 ----
    mem_pct = stats["memory"]["percent"]
    penalty, level = _dim_score(mem_pct, [(90, 25), (75, 15), (50, 5)])
    total_penalty += penalty
    dimensions.append({
        "name": "内存",
        "icon": "memory",
        "value": mem_pct,
        "unit": "%",
        "penalty": penalty,
        "sub_score": max(0, 100 - penalty),
        "level": level,
    })

    # ---- 磁盘（取 / 和 /data 中最差的）----
    disk_penalty = 0
    disk_worst = {"percent": 0, "mount": ""}
    if stats["disks"]:
        for d in stats["disks"]:
            p, _ = _dim_score(d["percent"], [(90, 25), (75, 15), (50, 5)])
            if p > disk_penalty:
                disk_penalty = p
                disk_worst = {"percent": d["percent"], "mount": d["mount"]}
    total_penalty += disk_penalty
    disk_display_value = disk_worst["percent"] if stats["disks"] else None
    dimensions.append({
        "name": "磁盘",
        "icon": "harddisk",
        "value": disk_display_value,
        "unit": "%",
        "penalty": disk_penalty,
        "sub_score": max(0, 100 - disk_penalty),
        "level": _level(disk_penalty),
        "detail": disk_worst["mount"] or "/",
    })

    # ---- 系统负载 ----
    load1 = stats["load"]["load1"]
    cpu_count = stats["cpu"]["count"]
    penalty = 0
    if cpu_count > 0 and load1 > 2 * cpu_count:
        penalty = 15
    elif cpu_count > 0 and load1 > cpu_count:
        penalty = 10
    level = _level(penalty)
    total_penalty += penalty
    load_ratio = round(load1 / cpu_count, 1) if cpu_count else 0
    dimensions.append({
        "name": "系统负载",
        "icon": "load",
        "value": load_ratio,
        "unit": "×",
        "penalty": penalty,
        "sub_score": max(0, 100 - penalty),
        "level": level,
        "detail": f"load1={load1}, cores={cpu_count}",
    })

    # ---- CPU温度 ----
    temp = stats.get("temperature")
    temp_penalty = 0
    if temp is not None:
        if temp > 80:
            temp_penalty = 15
        elif temp > 70:
            temp_penalty = 8
    level = _level(temp_penalty)
    total_penalty += temp_penalty
    dimensions.append({
        "name": "CPU温度",
        "icon": "thermometer",
        "value": temp,
        "unit": "°C",
        "penalty": temp_penalty,
        "sub_score": max(0, 100 - temp_penalty),
        "level": level,
    })

    # ---- 响应延迟 ----
    latency = ha_status.get("latency_ms")
    ha_penalty = 0
    if latency is not None:
        if latency > 500:
            ha_penalty = 25
        elif latency > 200:
            ha_penalty = 15
        elif latency > 100:
            ha_penalty = 5
    level = _level(ha_penalty)
    total_penalty += ha_penalty
    dimensions.append({
        "name": "响应延迟",
        "icon": "latency",
        "value": latency,
        "unit": "ms",
        "penalty": ha_penalty,
        "sub_score": max(0, 100 - ha_penalty),
        "level": level,
        "detail": f"延迟 {latency}ms" if latency else "无数据",
    })

    # ---- 汇总 ----
    total = max(0, min(100, 100 - total_penalty))
    if total >= 80:
        overall = "ok"
    elif total >= 60:
        overall = "mild"
    elif total >= 40:
        overall = "warning"
    else:
        overall = "critical"

    preferred_order = ["CPU", "CPU温度", "系统负载", "响应延迟", "内存", "磁盘"]
    dimensions_by_name = {item["name"]: item for item in dimensions}

    return {
        "total": total,
        "level": overall,
        "dimensions": [dimensions_by_name[name] for name in preferred_order if name in dimensions_by_name],
    }
