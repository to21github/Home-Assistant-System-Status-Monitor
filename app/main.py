"""Home Assistant 系统状态监控 — Flask 主应用。

提供仪表盘页面和 REST API（/api/stats、/api/health）。
通过 HA Ingress 在侧边栏中展示。"""

import json
import os
from flask import Flask, jsonify, render_template, request
import collector
import health

app = Flask(__name__)

# ---- 安全配置 ----
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())
app.logger.info("系统状态监控启动完成 (pid=%d)", os.getpid())

# Ingress 可信代理地址（HA Supervisor 反代来源），写操作仅信任该来源
INGRESS_PROXY_ADDRESS = "172.30.32.2"

def _is_trusted_proxy(address):
    """校验请求来源是否为 Ingress 可信代理（兼容 IPv6 映射前缀）"""
    return isinstance(address, str) and address.replace("::ffff:", "", 1) == INGRESS_PROXY_ADDRESS


@app.before_request
def _require_ingress_for_writes():
    # 写操作（POST）仅允许经 HA Ingress 可信代理转发；
    # 请求头特征可被伪造，故改用来源 IP 校验，防止同网络内直连端口调用
    if request.method == "POST" and not _is_trusted_proxy(request.remote_addr):
        return jsonify({"ok": False, "error": "仅允许通过 Home Assistant 入口访问该接口"}), 403
    return None

# ---- 业务配置（从 HA 加载项 options.json 读取）----
def _read_options():
    try:
        with open("/data/options.json") as f:
            return json.load(f)
    except Exception:
        return {}

_options = _read_options()
REFRESH_INTERVAL = int(_options.get("refresh_interval", 30))

@app.route("/")
def dashboard():
    """仪表盘主页"""
    return render_template("index.html", refresh_interval=REFRESH_INTERVAL)


@app.route("/api/stats")
def api_stats():
    """返回系统指标 JSON"""
    try:
        stats = collector.collect()
        return jsonify({"ok": True, "data": stats})
    except Exception as e:
        app.logger.error(f"采集系统指标失败: {e}")
        return jsonify({"ok": False, "error": "内部采集错误"}), 500


@app.route("/api/health")
def api_health():
    """返回健康评分 JSON"""
    try:
        stats = collector.collect()
        ha = collector.collect_ha_status()
        score = health.calculate(stats, ha)
        return jsonify({
            "ok": True,
            "data": {
                "score": score,
                "ha": ha,
            },
        })
    except Exception as e:
        app.logger.error(f"健康评分计算失败: {e}")
        return jsonify({"ok": False, "error": "健康评分计算错误"}), 500


# ---- 启动入口 ----
if __name__ == "__main__":
    port = int(os.environ.get("INGRESS_PORT", 8099))
    app.run(host="0.0.0.0", port=port, debug=False)
