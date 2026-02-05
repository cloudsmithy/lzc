#!/usr/bin/env python3
import feedparser
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime
import re
import time
import json

RSS_URL = "https://airag.click/atom.xml"
OUTPUT_DIR = Path("/data/articles") if Path("/data").exists() else Path(__file__).parent / "articles"
FILTER_CATEGORY = "懒猫微服"
META_FILE = "articles.json"  # 文章元数据缓存

def clean_filename(title):
    cleaned = re.sub(r'[<>:"/\\|?*]', '', title)
    return cleaned[:80]

def load_meta():
    """加载文章元数据"""
    meta_path = OUTPUT_DIR / META_FILE
    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_meta(meta):
    """保存文章元数据"""
    with open(OUTPUT_DIR / META_FILE, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def fetch_article(url):
    """抓取文章，返回 (content_html, categories)"""
    try:
        resp = requests.get(url, timeout=30)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 获取分类（只取文章头部 level-item 里的，排除侧边栏 tags）
        categories = []
        for span in soup.find_all('span', class_='level-item'):
            a = span.find('a', href=re.compile(r'/categories/'))
            if a:
                cat = a.get_text().strip()
                if cat:
                    categories.append(cat)
        
        # 获取文章内容
        article = soup.find('article')
        if not article:
            return None, categories
        
        content_div = article.find('div', class_='content')
        if not content_div:
            return None, categories
        
        # 清理
        for tag in content_div.find_all(['script', 'style']):
            tag.decompose()
        
        # 处理代码块，提取语言类型
        for figure in content_div.find_all('figure'):
            # 获取语言类型
            lang = ''
            fig_class = figure.get('class', [])
            for c in fig_class:
                if c.startswith('highlight'):
                    parts = c.split('-')
                    if len(parts) > 1:
                        lang = parts[1]
                    break
            
            table = figure.find('table')
            if table:
                tds = table.find_all('td')
                if len(tds) >= 2:
                    code_pre = tds[1].find('pre')
                    if code_pre:
                        new_pre = soup.new_tag('pre')
                        new_code = soup.new_tag('code')
                        if lang:
                            new_code['class'] = f'language-{lang}'
                        code_text = '\n'.join(line.get_text() for line in code_pre.find_all('span', class_='line'))
                        if not code_text:
                            code_text = code_pre.get_text()
                        new_code.string = code_text.strip()
                        new_pre.append(new_code)
                        figure.replace_with(new_pre)
                        continue
            pre = figure.find('pre')
            if pre:
                new_pre = soup.new_tag('pre')
                new_code = soup.new_tag('code')
                if lang:
                    new_code['class'] = f'language-{lang}'
                code_text = '\n'.join(line.get_text() for line in pre.find_all('span', class_='line'))
                if not code_text:
                    code_text = pre.get_text()
                new_code.string = code_text.strip()
                new_pre.append(new_code)
                figure.replace_with(new_pre)
        
        # 清理属性
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
        return html.strip(), categories
        
    except Exception as e:
        print(f"  错误: {e}")
        return None, []

def generate_index(articles):
    """生成文章列表首页（带搜索）"""
    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>懒猫微服文章</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <h1>懒猫微服</h1>
        <p class="subtitle">共 ''' + str(len(articles)) + ''' 篇文章</p>
        <div class="search-box">
            <input type="text" id="search" placeholder="搜索文章..." autocomplete="off">
        </div>
        <ul class="article-list" id="article-list">
'''
    for art in articles:
        date_str = art.get('date', '')
        html += f'''            <li class="article-item" data-title="{art['title'].lower()}">
                <a href="{art['filename']}">{art['title']}</a>
                <span class="article-date">{date_str}</span>
            </li>
'''
    html += '''        </ul>
    </div>
    <script>
        document.getElementById('search').addEventListener('input', function(e) {
            const query = e.target.value.toLowerCase();
            document.querySelectorAll('.article-item').forEach(item => {
                const title = item.getAttribute('data-title');
                item.style.display = title.includes(query) ? '' : 'none';
            });
        });
    </script>
</body>
</html>'''
    return html

ARTICLE_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <link rel="stylesheet" href="style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
</head>
<body>
    <div class="container">
        <a class="back" href="index.html">← 返回列表</a>
        <div class="meta">{date} · <a href="{link}">原文链接</a></div>
        <h1>{title}</h1>
        <div class="content">{content}</div>
    </div>
    <script>hljs.highlightAll();</script>
</body>
</html>'''

def parse_date(entry):
    """解析 RSS 日期"""
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6])
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6])
    return datetime.now()

def fetch():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"[{datetime.now()}] 开始抓取...")
    resp = requests.get(RSS_URL, timeout=30)
    resp.encoding = 'utf-8'
    feed = feedparser.parse(resp.text)
    
    if not feed.entries:
        print("RSS 解析失败")
        return
    
    print(f"RSS 共 {len(feed.entries)} 篇，过滤分类: {FILTER_CATEGORY}")
    
    # 加载已有元数据
    meta = load_meta()
    articles = []
    
    for entry in feed.entries:
        title = entry.title
        link = entry.link
        filename = clean_filename(title) + ".html"
        filepath = OUTPUT_DIR / filename
        pub_date = parse_date(entry)
        date_str = pub_date.strftime('%Y-%m-%d')
        
        # 检查缓存：已确认是目标分类的文章
        if filename in meta:
            cached = meta[filename]
            # 检查缓存的分类列表是否包含目标分类
            cached_cats = cached.get('categories', [])
            if FILTER_CATEGORY in cached_cats:
                articles.append({
                    'title': title,
                    'filename': filename,
                    'date': date_str,
                    'timestamp': pub_date.timestamp()
                })
            continue
        
        print(f"检查: {title[:40]}...")
        content, categories = fetch_article(link)
        
        # 记录元数据（保存所有分类）
        meta[filename] = {
            'title': title,
            'link': link,
            'date': date_str,
            'categories': categories
        }
        
        # 过滤分类
        if FILTER_CATEGORY not in categories:
            print(f"  跳过 (分类: {categories})")
            continue
        
        if not content:
            print(f"  跳过 (无内容)")
            continue
        
        print(f"  保存 ✓")
        
        html = ARTICLE_TEMPLATE.format(
            title=title, 
            link=link, 
            content=content,
            date=date_str
        )
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        articles.append({
            'title': title,
            'filename': filename,
            'date': date_str,
            'timestamp': pub_date.timestamp()
        })
        time.sleep(0.5)
    
    # 保存元数据
    save_meta(meta)
    
    # 按时间排序（最新在前）
    articles.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
    
    # 生成首页
    index_html = generate_index(articles)
    with open(OUTPUT_DIR / 'index.html', 'w', encoding='utf-8') as f:
        f.write(index_html)
    
    print(f"[{datetime.now()}] 完成，共 {len(articles)} 篇懒猫微服文章")

if __name__ == "__main__":
    fetch()
