FROM python:3.11-slim

WORKDIR /app

# 安装依赖
RUN pip install --no-cache-dir feedparser requests beautifulsoup4

# 复制脚本
COPY fetch.py .

# 创建输出目录
RUN mkdir -p /data/articles

# 复制样式文件（如果存在）
COPY articles/style.css /data/articles/style.css

# 创建定时任务脚本
RUN echo '#!/bin/sh\n\
echo "$(date): 开始抓取文章..."\n\
python /app/fetch.py\n\
echo "$(date): 抓取完成"' > /app/run.sh && chmod +x /app/run.sh

# 创建 cron 任务（每小时执行一次）
RUN echo "0 * * * * /app/run.sh >> /var/log/cron.log 2>&1" > /etc/cron.d/fetch-cron \
    && chmod 0644 /etc/cron.d/fetch-cron

# 安装 cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# 启动脚本
RUN echo '#!/bin/sh\n\
# 首次运行\n\
python /app/fetch.py\n\
# 启动 cron\n\
cron\n\
# 保持容器运行，同时提供 HTTP 服务\n\
cd /data/articles && python -m http.server 80' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 80

CMD ["/app/start.sh"]
