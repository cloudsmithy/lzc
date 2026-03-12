#!/bin/sh
set -e

INTERVAL=${FETCH_INTERVAL:-43200}  # 默认 12 小时 = 43200 秒

echo "=== 懒猫微服文章抓取服务 ==="
echo "抓取间隔: ${INTERVAL} 秒"

# 首次抓取
python /app/fetch.py

# 后台定时抓取
(
    while true; do
        sleep "$INTERVAL"
        echo "--- 定时抓取开始 ---"
        python /app/fetch.py || echo "抓取出错，等待下次重试"
    done
) &

# 启动 nginx（前台运行）
exec nginx -g "daemon off;"
