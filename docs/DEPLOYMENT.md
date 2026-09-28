# 服务器部署与更新

以下记录来自已有部署交接，未在本次仓库发布过程中连接或修改服务器。

## 现有配置

- ECS：`39.96.206.228`，Ubuntu，Python 3.10.12。
- 代码：`/var/www/group-chronicle`。
- 生产数据库：`/var/lib/group-chronicle/archive.sqlite3`。
- systemd 服务及专用用户：`group-chronicle`。
- 启动命令：`/usr/bin/python3 /var/www/group-chronicle/server.py --port 8765 --database /var/lib/group-chronicle/archive.sqlite3`。
- Python 服务绑定 `127.0.0.1:8765`，Nginx 计划在 8081 端口代理。
- Nginx 文件：`/etc/nginx/conf.d/group-chronicle.conf`。
- 计划公网入口：`http://39.96.206.228:8081/`。交接时内部服务已验证，公网验收尚未确认。
- 产品设定为公开查看和新增，无账号密码。

## 更新代码

1. 先备份生产数据库。可使用 Python 的 SQLite backup API 在线备份，或停止本服务后复制数据库文件。
2. 短暂停止 `group-chronicle` 服务。
3. 上传本次变更的代码文件到 `/var/www/group-chronicle`，保留专用用户和文件权限。
4. 启动 `group-chronicle`，检查服务状态与日志。
5. 验收页面、查询与 Excel 导出；若需要验证新增，请使用实际要录入的新团名。

本次 Excel 导出功能需要更新 `server.py`、`dist/index.html`、`dist/app.js`、`dist/style.css`，不需要数据库迁移。

部署时使用服务器已有生产数据库，不要用仓库内的本地快照覆盖它。不要重新导入初始记录。代码与数据库分开部署，可以保留服务器上已经新增的记录。

仅操作 `group-chronicle` 服务；同机其他项目使用 3000/3001、3100、80 和 8080 等端口，保持不变。

## 反向代理注意事项

Nginx 将 8081 转发到 `127.0.0.1:8765`，需保留 `Host $http_host`，限制请求体为 `8k`。现有服务的 POST Origin 校验使用 `http://Host`；若后续改用 HTTPS，需要同步适配该校验。

GitHub 仓库用于存放项目。GitHub Pages 仅能托管静态页面，不能直接运行这个 Python/SQLite 应用。
