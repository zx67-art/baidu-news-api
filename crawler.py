"""
百度资讯抓取 - 核心爬虫模块
"""

import requests
from bs4 import BeautifulSoup
import time
import random
from datetime import datetime, timedelta
from urllib.parse import quote


# User-Agent 池
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


def get_random_headers():
    """生成随机请求头"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.baidu.com/",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }


def random_delay(min_sec=2, max_sec=5):
    """随机延迟，模拟人类行为"""
    delay = random.uniform(min_sec, max_sec)
    # 10% 概率长停顿
    if random.random() < 0.1:
        delay += random.uniform(3, 8)
    time.sleep(delay)


def is_blocked(html):
    """检测是否被拦截"""
    signals = ["验证码", "安全验证", "百度安全验证", "captcha", "abnormal"]
    return any(s in html.lower() for s in signals)


def search_baidu_news(keyword: str, days: int = 7, max_pages: int = 3):
    """
    搜索百度资讯

    参数:
        keyword: 搜索关键词
        days: 搜索近 N 天
        max_pages: 最大翻页数

    返回:
        list: 资讯列表，每条包含 title, url, source, time, snippet
    """
    # 创建 Session
    session = requests.Session()
    session.headers.update(get_random_headers())

    # 预热：先访问百度首页
    try:
        session.get("https://www.baidu.com", timeout=10)
        time.sleep(random.uniform(1, 2))
    except:
        pass

    # 计算时间范围
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    start_ts = int(start_time.timestamp())
    end_ts = int(end_time.timestamp())

    all_results = []
    seen_urls = set()

    print(f"🔍 开始搜索: 「{keyword}」| 近 {days} 天 | 最多 {max_pages} 页")

    for page in range(max_pages):
        # 每页轮换 UA
        session.headers["User-Agent"] = random.choice(USER_AGENTS)

        # 构造搜索 URL
        encoded_keyword = quote(keyword)
        url = (
            f"https://www.baidu.com/s?"
            f"wd={encoded_keyword}&tn=news"
            f"&rtt=4&bsst=1&cl=2&medium=0"
            f"&gpc=stf%3D{start_ts}%2C{end_ts}%7Cstftype%3D2"
            f"&pn={page * 10}"
        )

        try:
            resp = session.get(url, timeout=15)
            resp.encoding = "utf-8"

            # 检测拦截
            if is_blocked(resp.text):
                print(f"⚠️ 第 {page + 1} 页被拦截，跳过")
                time.sleep(random.uniform(30, 60))
                continue

            # 解析结果
            soup = BeautifulSoup(resp.text, "lxml")
            page_results = []

            for item in soup.select("div.result"):
                try:
                    # 标题和 URL
                    title_elem = item.select_one("h3 a, h3.t a")
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    result_url = title_elem.get("href", "")

                    # 去重
                    if result_url in seen_urls:
                        continue
                    seen_urls.add(result_url)

                    # 来源和时间
                    source = ""
                    pub_time = ""
                    author_elem = item.select_one("span.c-color-gray, span.f-author, p.c-author")
                    if author_elem:
                        author_text = author_elem.get_text(strip=True).replace("\xa0", " ")
                        parts = author_text.split()
                        if len(parts) >= 2:
                            source = parts[0]
                            pub_time = " ".join(parts[1:])
                        elif parts:
                            source = parts[0]

                    # 摘要
                    snippet = ""
                    snippet_elem = item.select_one("div.c-abstract, span.c-font-normal, span.c-color-text")
                    if snippet_elem:
                        snippet = snippet_elem.get_text(strip=True)[:200]

                    page_results.append({
                        "title": title,
                        "url": result_url,
                        "source": source,
                        "time": pub_time,
                        "snippet": snippet,
                    })

                except Exception:
                    continue

            all_results.extend(page_results)
            print(f"📄 第 {page + 1} 页: {len(page_results)} 条（累计 {len(all_results)} 条）")

            # 翻页延迟
            if page < max_pages - 1:
                random_delay(3, 6)

        except requests.RequestException as e:
            print(f"❌ 第 {page + 1} 页请求失败: {e}")
            time.sleep(random.uniform(10, 30))

    print(f"✅ 搜索完成，共 {len(all_results)} 条")
    return all_results


def fetch_article_content(url: str, max_length: int = 500):
    """
    抓取文章正文

    参数:
        url: 文章 URL
        max_length: 最大返回长度

    返回:
        str: 正文内容（截断）
    """
    headers = {"User-Agent": random.choice(USER_AGENTS)}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = resp.apparent_encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "lxml")

        # 移除无关标签
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
            tag.decompose()

        # 提取正文
        paragraphs = soup.find_all("p")
        content = "\n".join([
            p.get_text(strip=True)
            for p in paragraphs
            if len(p.get_text(strip=True)) > 20
        ])

        if len(content) < 50:
            # 备选：直接提取 body
            body = soup.find("body")
            if body:
                content = body.get_text(strip=True)[:max_length]

        return content[:max_length] if content else ""

    except Exception:
        return ""


def fetch_all_contents(results: list, max_length: int = 500):
    """
    批量抓取正文

    参数:
        results: 搜索结果列表
        max_length: 每条正文最大长度

    返回:
        list: 添加了 content 字段的结果列表
    """
    total = len(results)
    print(f"📥 开始抓取正文（共 {total} 条）...")

    for i, item in enumerate(results):
        print(f"  [{i + 1}/{total}] {item['title'][:30]}...")
        item["content"] = fetch_article_content(item["url"], max_length)

        # 延迟
        if i < total - 1:
            random_delay(1, 3)

    print(f"✅ 正文抓取完成")
    return results
