# 懒猫微服专栏文章抓取器

从 [cloudsmithy.github.io](https://cloudsmithy.github.io) 自动抓取「懒猫微服」分类下的所有文章，生成静态站点。

## 功能

- 从 RSS 获取文章列表，逐篇抓取正文内容
- 自动识别分类（入门/进阶/开发/番外等）
- 生成带搜索和标签筛选的静态首页
- 文章页自动生成右侧目录导航
- 缓存机制，增量更新，不重复抓取
- HTML 文件丢失时自动重新抓取

## 快速开始

### 本地运行

```bash
pip install feedparser requests beautifulsoup4
python fetch.py
```

抓取完成后浏览器打开 `index.html`，或者起个本地服务：

```bash
python -m http.server 8888
# 访问 http://localhost:8888
```

### Docker 运行

```bash
docker compose up -d --build
# 访问 http://localhost:8080
```

容器启动后会立即抓取一次，之后每 12 小时自动更新。

## 配置

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `FETCH_INTERVAL` | `43200` | 抓取间隔（秒），默认 12 小时 |

## 项目结构

```
├── fetch.py           # 抓取脚本
├── style.css          # 页面样式
├── entrypoint.sh      # Docker 启动脚本
├── nginx.conf         # Nginx 配置
├── Dockerfile
├── docker-compose.yml
├── index.html         # 生成的首页（运行后）
├── articles.json      # 缓存文件（运行后）
└── articles/          # 文章 HTML（运行后）
```

## 清空重新抓取

```bash
rm -f articles.json
rm -f articles/*.html
python fetch.py
```
