#!/usr/bin/env python3
"""懒猫微服专栏文章抓取器
从 cloudsmithy.github.io 抓取懒猫微服分类下的所有文章
"""
import feedparser
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime
from urllib.parse import unquote
import re
import time
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

RSS_URL = "https://cloudsmithy.github.io/atom.xml"
BASE_DIR = Path("/data") if Path("/data").exists() else Path(__file__).parent
ARTICLES_DIR = BASE_DIR / "articles"
FILTER_CATEGORY = "懒猫微服"
META_FILE = BASE_DIR / "articles.json"
INDEX_FILE = BASE_DIR / "index.html"
STYLE_FILE = BASE_DIR / "style.css"


def clean_filename(title):
    cleaned = re.sub(r'[<>:"/\\|?*]', '', title)
    return cleaned[:80]


def load_meta():
    if META_FILE.exists():
        try:
            with open(META_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"元数据文件损坏，重新创建: {e}")
    return {}


def save_meta(meta):
    tmp = META_FILE.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    tmp.replace(META_FILE)


def fetch_article(url, retries=3):
    """抓取文章，返回 (content_html, main_category, sub_category)"""
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 LanmaoFetcher/1.0'
            })
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            main_cat, sub_cat = '', ''

            # 从文章元信息区域提取分类
            # 结构: <span class="level-item"><a href="/categories/懒猫微服/">懒猫微服</a><span>/</span><a href="/categories/懒猫微服/入门/">入门</a></span>
            # 注意：不能用 p.categories，那是侧边栏"最新文章"的分类
            for scope in [soup.find('div', class_='article-meta'), soup.find('article')]:
                if not scope:
                    continue
                for span in scope.find_all('span', class_='level-item'):
                    cat_links = span.find_all('a', href=re.compile(r'/categories/'))
                    if not cat_links:
                        continue
                    # 遍历所有分类链接，取最深层级的路径
                    for a in cat_links:
                        href = a.get('href', '')
                        parts = [unquote(p) for p in href.strip('/').split('/') if p and p != 'categories']
                        if len(parts) >= 1:
                            main_cat = parts[0]
                        if len(parts) >= 2:
                            sub_cat = parts[1]
                    break
                if main_cat:
                    break

            article = soup.find('article')
            if not article:
                return None, main_cat, sub_cat

            content_div = article.find('div', class_='content')
            if not content_div:
                return None, main_cat, sub_cat

            for tag in content_div.find_all(['script', 'style']):
                tag.decompose()

            # 处理代码块
            for figure in content_div.find_all('figure'):
                lang = ''
                for c in figure.get('class', []):
                    if c.startswith('highlight'):
                        parts = c.split('-')
                        if len(parts) > 1:
                            lang = parts[1]
                        break

                code_text = ''
                table = figure.find('table')
                if table:
                    tds = table.find_all('td')
                    if len(tds) >= 2:
                        code_pre = tds[1].find('pre')
                        if code_pre:
                            code_text = '\n'.join(
                                line.get_text() for line in code_pre.find_all('span', class_='line')
                            ) or code_pre.get_text()

                if not code_text:
                    pre = figure.find('pre')
                    if pre:
                        code_text = '\n'.join(
                            line.get_text() for line in pre.find_all('span', class_='line')
                        ) or pre.get_text()

                if code_text:
                    new_pre = soup.new_tag('pre')
                    new_code = soup.new_tag('code')
                    if lang:
                        new_code['class'] = f'language-{lang}'
                    new_code.string = code_text.strip()
                    new_pre.append(new_code)
                    figure.replace_with(new_pre)

            # 清理多余属性
            for tag in content_div.find_all(True):
                if tag.name == 'a':
                    tag.attrs = {'href': tag.get('href', '')}
                elif tag.name == 'img':
                    tag.attrs = {'src': tag.get('src', ''), 'alt': tag.get('alt', '')}
                elif tag.name == 'code' and tag.get('class'):
                    tag.attrs = {'class': ' '.join(tag.get('class', []))}
                else:
                    tag.attrs = {}

            html = ''.join(str(child) for child in content_div.children)
            return html.strip(), main_cat, sub_cat

        except Exception as e:
            log.warning(f"抓取失败 ({attempt+1}/{retries}): {url} - {e}")
            if attempt < retries - 1:
                time.sleep(3)
    return None, '', ''


# 文章模板 - style.css 在上级目录
ARTICLE_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <link rel="stylesheet" href="../style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
</head>
<body>
    <nav class="toc" id="toc"></nav>
    <div class="article-page">
        <a class="back" href="../index.html">← 返回列表</a>
        <div class="meta">{date} · {sub_cat} · <a href="{link}">原文链接</a></div>
        <h1>{title}</h1>
        <div class="content">{content}</div>
    </div>
    <script>
        hljs.highlightAll();
        // 生成目录
        (function() {{
            const content = document.querySelector('.content');
            const toc = document.getElementById('toc');
            const headings = content.querySelectorAll('h2, h3');
            if (headings.length < 2) {{ toc.style.display = 'none'; return; }}
            let html = '<div class="toc-title">目录</div><ul>';
            headings.forEach((h, i) => {{
                const id = 'heading-' + i;
                h.id = id;
                const cls = h.tagName === 'H3' ? ' class="toc-sub"' : '';
                html += '<li' + cls + '><a href="#' + id + '">' + h.textContent + '</a></li>';
            }});
            html += '</ul>';
            toc.innerHTML = html;
            // 滚动高亮
            const links = toc.querySelectorAll('a');
            const observer = new IntersectionObserver(entries => {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) {{
                        links.forEach(a => a.classList.remove('active'));
                        const active = toc.querySelector('a[href="#' + entry.target.id + '"]');
                        if (active) active.classList.add('active');
                    }}
                }});
            }}, {{ rootMargin: '0px 0px -70% 0px' }});
            headings.forEach(h => observer.observe(h));
        }})();
    </script>
</body>
</html>'''


def parse_date(entry):
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6])
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6])
    return datetime.now()


def generate_index(articles, all_tags):
    """生成静态首页 HTML"""
    # 统计每个标签的文章数
    tag_counts = {}
    for art in articles:
        sc = art.get('sub_cat', '')
        if sc:
            tag_counts[sc] = tag_counts.get(sc, 0) + 1

    tags_html = '<button class="tag-btn active" data-tag="all">全部</button>\n'
    for tag in sorted(all_tags):
        cnt = tag_counts.get(tag, 0)
        tags_html += f'            <button class="tag-btn" data-tag="{tag}">{tag} <span class="tag-count">{cnt}</span></button>\n'

    items_html = ''
    for art in articles:
        sub_cat = art.get('sub_cat', '')
        items_html += f'''            <li class="article-item" data-title="{art['title'].lower()}" data-tag="{sub_cat}">
                <div class="article-info">
                    <a href="articles/{art['filename']}">{art['title']}</a>{f' <span class="article-tag">{sub_cat}</span>' if sub_cat else ''}
                </div>
                <span class="article-date">{art.get('date', '')}</span>
            </li>
'''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>懒猫微服专栏</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="hero">
        <div class="hero-content">
            <h1>懒猫微服专栏</h1>
            <p class="subtitle">手把手带你玩转懒猫微服</p>
            <div class="stats">
                <div class="stat-box"><span class="stat-num">{len(articles)}</span><span class="stat-label">篇文章</span></div>
                <div class="stat-box"><span class="stat-num">{len(all_tags)}</span><span class="stat-label">个分类</span></div>
            </div>
        </div>
    </div>
    <div class="main-container">
        <div class="search-box">
            <input type="text" id="search" placeholder="搜索文章标题..." autocomplete="off" aria-label="搜索文章">
        </div>
        <div class="tag-filter">
            {tags_html}
            <button class="tag-btn sort-btn" id="sortBtn" data-order="desc">🕐 最新优先</button>
        </div>
        <ul class="article-list" id="article-list">
{items_html}        </ul>
        <div class="site-footer">
            <p>数据来源 <a href="https://cloudsmithy.github.io" target="_blank">cloudsmithy.github.io</a></p>
        </div>
    </div>
    <script>
        const searchInput = document.getElementById('search');
        const tagBtns = document.querySelectorAll('.tag-btn:not(.sort-btn)');
        const sortBtn = document.getElementById('sortBtn');
        const list = document.getElementById('article-list');
        const items = Array.from(document.querySelectorAll('.article-item'));
        let currentTag = 'all';
        let sortOrder = 'desc';

        function filterArticles() {{
            const query = searchInput.value.toLowerCase();
            let count = 0;
            items.forEach(item => {{
                const title = item.getAttribute('data-title');
                const tag = item.getAttribute('data-tag');
                const matchSearch = title.includes(query);
                const matchTag = currentTag === 'all' || tag === currentTag;
                const show = matchSearch && matchTag;
                item.style.display = show ? '' : 'none';
                if (show) count++;
            }});
        }}

        function sortArticles() {{
            const sorted = [...items].sort((a, b) => {{
                const da = a.querySelector('.article-date').textContent;
                const db = b.querySelector('.article-date').textContent;
                return sortOrder === 'desc' ? db.localeCompare(da) : da.localeCompare(db);
            }});
            sorted.forEach(item => list.appendChild(item));
        }}

        searchInput.addEventListener('input', filterArticles);
        tagBtns.forEach(btn => {{
            btn.addEventListener('click', function() {{
                tagBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                currentTag = this.getAttribute('data-tag');
                filterArticles();
            }});
        }});
        sortBtn.addEventListener('click', function() {{
            sortOrder = sortOrder === 'desc' ? 'asc' : 'desc';
            this.textContent = sortOrder === 'desc' ? '🕐 最新优先' : '🕐 最早优先';
            sortArticles();
            filterArticles();
        }});
    </script>
</body>
</html>'''


def fetch():
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    log.info("开始抓取 RSS...")
    try:
        resp = requests.get(RSS_URL, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 LanmaoFetcher/1.0'
        })
        resp.encoding = 'utf-8'
        feed = feedparser.parse(resp.text)
    except Exception as e:
        log.error(f"RSS 获取失败: {e}")
        return False

    if not feed.entries:
        log.error("RSS 解析失败，无文章")
        return False

    log.info(f"RSS 共 {len(feed.entries)} 篇，过滤分类: {FILTER_CATEGORY}")

    meta = load_meta()
    articles = []
    all_tags = set()
    new_count = 0

    for entry in feed.entries:
        title = entry.title
        link = entry.link
        filename = clean_filename(title) + ".html"
        pub_date = parse_date(entry)
        date_str = pub_date.strftime('%Y-%m-%d')

        # 已缓存的直接用（但要确认 HTML 文件存在）
        if filename in meta:
            cached = meta[filename]
            if cached.get('main_cat') == FILTER_CATEGORY:
                sub_cat = cached.get('sub_cat', '')
                html_exists = (ARTICLES_DIR / filename).exists()
                if sub_cat:
                    all_tags.add(sub_cat)
                if html_exists:
                    articles.append({
                        'title': title,
                        'filename': filename,
                        'date': date_str,
                        'sub_cat': sub_cat,
                        'timestamp': pub_date.timestamp()
                    })
                    continue
                else:
                    # HTML 文件丢失，需要重新抓取
                    log.info(f"重新抓取(文件丢失): {title[:50]}...")
                    del meta[filename]
            else:
                continue

        log.info(f"检查: {title[:50]}...")
        content, main_cat, sub_cat = fetch_article(link)

        meta[filename] = {
            'title': title,
            'link': link,
            'date': date_str,
            'main_cat': main_cat,
            'sub_cat': sub_cat
        }

        if main_cat != FILTER_CATEGORY:
            log.info(f"  跳过 (分类: {main_cat})")
            continue

        if not content:
            log.info("  跳过 (无内容)")
            continue

        log.info(f"  保存 ✓ [{sub_cat}]")
        new_count += 1

        if sub_cat:
            all_tags.add(sub_cat)

        html = ARTICLE_TEMPLATE.format(
            title=title, link=link, content=content,
            date=date_str, sub_cat=sub_cat or '其他'
        )
        with open(ARTICLES_DIR / filename, 'w', encoding='utf-8') as f:
            f.write(html)

        save_meta(meta)
        articles.append({
            'title': title,
            'filename': filename,
            'date': date_str,
            'sub_cat': sub_cat,
            'timestamp': pub_date.timestamp()
        })
        time.sleep(0.5)

    save_meta(meta)

    # 按日期倒序
    articles.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

    # 生成静态首页到根目录
    index_html = generate_index(articles, all_tags)
    tmp_index = INDEX_FILE.with_suffix('.html.tmp')
    with open(tmp_index, 'w', encoding='utf-8') as f:
        f.write(index_html)
    tmp_index.replace(INDEX_FILE)

    log.info(f"完成! 新增 {new_count} 篇，共 {len(articles)} 篇文章")
    return True


if __name__ == "__main__":
    fetch()
