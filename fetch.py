#!/usr/bin/env python3
import feedparser
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime
from urllib.parse import unquote
import re
import time
import json

RSS_URL = "https://airag.click/atom.xml"
OUTPUT_DIR = Path("/data/articles") if Path("/data").exists() else Path(__file__).parent / "articles"
FILTER_CATEGORY = "懒猫微服"
META_FILE = "articles.json"

def clean_filename(title):
    cleaned = re.sub(r'[<>:"/\\|?*]', '', title)
    return cleaned[:80]

def load_meta():
    meta_path = OUTPUT_DIR / META_FILE
    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_meta(meta):
    with open(OUTPUT_DIR / META_FILE, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def fetch_article(url):
    """抓取文章，返回 (content_html, main_category, sub_category)"""
    try:
        resp = requests.get(url, timeout=30)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 获取分类 - 从 p.categories 或 level-item 里找
        main_cat = ''
        sub_cat = ''
        
        # 方法1: 从 p.categories 找（包含完整路径）
        cat_p = soup.find('p', class_='categories')
        if cat_p:
            links = cat_p.find_all('a', href=re.compile(r'/categories/'))
            for a in links:
                href = a.get('href', '')
                parts = [unquote(p) for p in href.strip('/').split('/') if p and p != 'categories']
                if len(parts) >= 1 and not main_cat:
                    main_cat = parts[0]
                if len(parts) >= 2:
                    sub_cat = parts[1]
                    break
        
        # 方法2: 从 level-item 找（备用）
        if not main_cat:
            for span in soup.find_all('span', class_='level-item'):
                a = span.find('a', href=re.compile(r'/categories/'))
                if a:
                    href = a.get('href', '')
                    parts = [unquote(p) for p in href.strip('/').split('/') if p and p != 'categories']
                    if len(parts) >= 1:
                        main_cat = parts[0]
                    if len(parts) >= 2:
                        sub_cat = parts[1]
                    break
        
        # 获取文章内容
        article = soup.find('article')
        if not article:
            return None, main_cat, sub_cat
        
        content_div = article.find('div', class_='content')
        if not content_div:
            return None, main_cat, sub_cat
        
        # 清理
        for tag in content_div.find_all(['script', 'style']):
            tag.decompose()
        
        # 处理代码块
        for figure in content_div.find_all('figure'):
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
        return html.strip(), main_cat, sub_cat
        
    except Exception as e:
        print(f"  错误: {e}")
        return None, '', ''

def generate_index(articles, all_tags):
    """生成文章列表首页（带搜索和标签筛选）"""
    
    # 标签按钮 HTML
    tags_html = '<button class="tag-btn active" data-tag="all">全部</button>\n'
    for tag in sorted(all_tags):
        tags_html += f'            <button class="tag-btn" data-tag="{tag}">{tag}</button>\n'
    
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
        <div class="tag-filter">
            ''' + tags_html + '''
        </div>
        <ul class="article-list" id="article-list">
'''
    for art in articles:
        date_str = art.get('date', '')
        sub_cat = art.get('sub_cat', '')
        html += f'''            <li class="article-item" data-title="{art['title'].lower()}" data-tag="{sub_cat}">
                <div class="article-info">
                    <a href="{art['filename']}">{art['title']}</a>
                    <span class="article-tag">{sub_cat}</span>
                </div>
                <span class="article-date">{date_str}</span>
            </li>
'''
    html += '''        </ul>
    </div>
    <script>
        const searchInput = document.getElementById('search');
        const tagBtns = document.querySelectorAll('.tag-btn');
        const items = document.querySelectorAll('.article-item');
        
        let currentTag = 'all';
        
        function filterArticles() {
            const query = searchInput.value.toLowerCase();
            items.forEach(item => {
                const title = item.getAttribute('data-title');
                const tag = item.getAttribute('data-tag');
                const matchSearch = title.includes(query);
                const matchTag = currentTag === 'all' || tag === currentTag;
                item.style.display = (matchSearch && matchTag) ? '' : 'none';
            });
        }
        
        searchInput.addEventListener('input', filterArticles);
        
        tagBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                tagBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                currentTag = this.getAttribute('data-tag');
                filterArticles();
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
        <a class="back" href="../index.html">← 返回列表</a>
        <div class="meta">{date} · {sub_cat} · <a href="{link}">原文链接</a></div>
        <h1>{title}</h1>
        <div class="content">{content}</div>
    </div>
    <script>hljs.highlightAll();</script>
</body>
</html>'''

def parse_date(entry):
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
    
    meta = load_meta()
    articles = []
    all_tags = set()
    
    for entry in feed.entries:
        title = entry.title
        link = entry.link
        filename = clean_filename(title) + ".html"
        filepath = OUTPUT_DIR / filename
        pub_date = parse_date(entry)
        date_str = pub_date.strftime('%Y-%m-%d')
        
        # 检查缓存
        if filename in meta:
            cached = meta[filename]
            if cached.get('main_cat') == FILTER_CATEGORY:
                sub_cat = cached.get('sub_cat', '')
                if sub_cat:
                    all_tags.add(sub_cat)
                articles.append({
                    'title': title,
                    'filename': filename,
                    'date': date_str,
                    'sub_cat': sub_cat,
                    'timestamp': pub_date.timestamp()
                })
            continue
        
        print(f"检查: {title[:40]}...")
        content, main_cat, sub_cat = fetch_article(link)
        
        # 记录元数据
        meta[filename] = {
            'title': title,
            'link': link,
            'date': date_str,
            'main_cat': main_cat,
            'sub_cat': sub_cat
        }
        
        # 过滤分类
        if main_cat != FILTER_CATEGORY:
            print(f"  跳过 (分类: {main_cat})")
            continue
        
        if not content:
            print(f"  跳过 (无内容)")
            continue
        
        print(f"  保存 ✓ [{sub_cat}]")
        
        if sub_cat:
            all_tags.add(sub_cat)
        
        html = ARTICLE_TEMPLATE.format(
            title=title, 
            link=link, 
            content=content,
            date=date_str,
            sub_cat=sub_cat or '其他'
        )
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        # 每保存一篇就更新 JSON，让前端能实时看到
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
    
    print(f"[{datetime.now()}] 完成，共 {len(articles)} 篇懒猫微服文章，{len(all_tags)} 个标签")

if __name__ == "__main__":
    fetch()
