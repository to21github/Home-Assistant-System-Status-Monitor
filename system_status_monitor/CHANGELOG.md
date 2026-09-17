# 更新日志

## 1.1.2

- 新增：镜像发布至 GitHub Container Registry，更新时直接拉取镜像，不再需要设备本地构建
- 修复：插件商店更新日志缺失提示

## 1.1.1

- 修正插件仓库地址
- 移除无效的端口配置项（Ingress 模式下端口由 Home Assistant 自动管理）
- 同步文档中磁盘数据来源说明

## 1.1.0

- 磁盘采集改为 statvfs 直查 /data 数据分区，不再依赖 Supervisor API 版本
- 失败时自动回退 Supervisor API 及本地挂载点读取

## 1.0.6

- 初始功能版本
