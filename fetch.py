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
FILTER_CATEGORY = "懒猫微服"  # 只抓这个分类

def clean_filename(title):
    cleaned = re.sub(r'[<>:"/\\|?*]', '', title)
    return cleaned[:80]

def fetch_article(url):
    """抓取文章，返回 (content_html, categories)"""
    try:
        resp = requests.get(url, timeout=30)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 获取分类
        categories = []
        for a in soup.find_all('a', href=re.compile(r'/categories/')):
            cat = a.get_text().strip()
            if cat:
                categories.append(cat)
        
        # 获取文章内容 - 在 article 里找 class="content" 的 div
        article = soup.find('article')
        if not article:
            return None, categories
        
        content_div = article.find('div', class_='content')
        if not content_div:
            return None, categories
        
        # 清理
        for tag in content_div.find_all(['script', 'style']):
            tag.decompose()
        
        # 处理代码块
        for figure in content_div.find_all('figure'):
            table = figure.find('table')
            if table:
                tds = table.find_all('td')
                if len(tds) >= 2:
                    code_pre = tds[1].find('pre')
                    if code_pre:
                        new_pre = soup.new_tag('pre')
                        # 保留换行符
                        code_text = '\n'.join(line.get_text() for line in code_pre.find_all('span', class_='line'))
                        if not code_text:
                            code_text = code_pre.get_text()
                        new_pre.string = code_text.strip()
                        figure.replace_with(new_pre)
                        continue
            pre = figure.find('pre')
            if pre:
                new_pre = soup.new_tag('pre')
                # 保留换行符
                code_text = '\n'.join(line.get_text() for line in pre.find_all('span', class_='line'))
                if not code_text:
                    code_text = pre.get_text()
                new_pre.string = code_text.strip()
                figure.replace_with(new_pre)
        
        # 清理属性
        for tag in content_div.find_all(True):
            if tag.name == 'a':
                tag.attrs = {'href': tag.get('href', '')}
            elif tag.name == 'img':
                tag.attrs = {'src': tag.get('src', ''), 'alt': tag.get('alt', '')}
            else:
                tag.attrs = {}
        
        # 获取内容 HTML
        html = ''.join(str(child) for child in content_div.children)
        return html.strip(), categories
        
    except Exception as e:
        print(f"  错误: {e}")
        return None, []

def generate_index(articles):
    """生成文章列表首页"""
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
        <ul class="article-list">
'''
    for art in articles:
        html += f'''            <li class="article-item">
                <a href="{art['filename']}">{art['title']}</a>
            </li>
'''
    html += '''        </ul>
    </div>
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
</head>
<body>
    <div class="container">
        <a class="back" href="index.html">← 返回列表</a>
        <div class="meta">来源: <a href="{link}">{link}</a></div>
        <h1>{title}</h1>
        <div class="content">{content}</div>
    </div>
</body>
</html>'''

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
    
    articles = []
    for entry in feed.entries:
        title = entry.title
        link = entry.link
        
        # 检查是否已存在
        filename = clean_filename(title) + ".html"
        filepath = OUTPUT_DIR / filename
        
        if filepath.exists():
            # 已存在，检查是否是目标分类（读取缓存）
            articles.append({'title': title, 'filename': filename, 'date': ''})
            continue
        
        print(f"检查: {title[:40]}...")
        content, categories = fetch_article(link)
        
        # 过滤分类
        if FILTER_CATEGORY not in categories:
            print(f"  跳过 (分类: {categories})")
            continue
        
        if not content:
            print(f"  跳过 (无内容)")
            continue
        
        print(f"  保存 ✓")
        
        html = ARTICLE_TEMPLATE.format(title=title, link=link, content=content)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        articles.append({'title': title, 'filename': filename, 'date': ''})
        time.sleep(0.5)
    
    # 生成首页
    index_html = generate_index(articles)
    with open(OUTPUT_DIR / 'index.html', 'w', encoding='utf-8') as f:
        f.write(index_html)
    
    print(f"[{datetime.now()}] 完成，共 {len(articles)} 篇懒猫微服文章")

if __name__ == "__main__":
    fetch()
