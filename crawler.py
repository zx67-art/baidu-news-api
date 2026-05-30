cat << 'ENDOFFILE' > /Users/bytedance/projects/baidu-news-api/crawler.py
"""
百度资讯抓取 - 核心爬虫模块
"""

import requests
from bs4 import BeautifulSoup
import time
import random
from datetime import datetime, timedelta
from urllib.parse import quote


USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


def get_random_headers():
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
    delay = random.uniform(min_sec, max_sec)
    if random.random() < 0.1:
        delay += random.uniform(3, 8)
    time.sleep(delay)


def is_blocked(html):
    html_lower = html.lower()
    signals = [
        "验证码",
        "安全验证",
        "百度安全验证",
        "captcha",
        "abnormal",
        "请输入验证码",
        "访问过于频繁",
        "verify",
    ]
    return any(s.lower() in html_lower for s in signals)


def extract_page_title(soup):
    if soup.title:
        return soup.title.get_text(strip=True)
    return ""


def extract_results_from_soup(soup):
    results = []
    seen_urls = set()
    containers = []

    selectors = [
        "div.result",
        "div.result-op",
        "div.c-container",
        "div[data-log]",
    ]

    for selector in selectors:
        found = soup.select(selector)
        if found:
            containers.extend(found)

    unique_containers = []
    seen_ids = set()
    for item in containers:
        marker = str(item)[:200]
        if marker not in seen_ids:
            seen_ids.add(marker)
            unique_containers.append(item)

    for item in unique_containers:
        try:
            title_elem = item.select_one("h3 a, h3.t a, h3.c-title a, a")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            result_url = title_elem.get("href", "").strip()

            if not title or not result_url:
                continue

            if result_url.startswith("javascript:"):
                continue

            if result_url in seen_urls:
                continue
            seen_urls.add(result_url)

            source = ""
            pub_time = ""
            snippet = ""

            author_elem = item.select_one(
                "span.c-color-gray, span.f-author, p.c-author, div.c-summary span, div.c-color-text"
            )
            if author_elem:
                author_text = author_elem.get_text(" ", strip=True).replace("\xa0", " ")
                parts = author_text.split()
                if len(parts) >= 2:
                    source = parts[0]
                    pub_time = " ".join(parts[1:])
                elif parts:
                    source = parts[0]

            snippet_elem = item.select_one(
                "div.c-abstract, span.c-font-normal, span.c-color-text, div.c-summary, div.content-right_8Zs40"
            )
            if snippet_elem:
                snippet = snippet_elem.get_text(" ", strip=True)[:200]

            results.append({
                "title": title[:200],
                "url": result_url,
                "source": source[:100],
                "time": pub_time[:100],
                "snippet": snippet,
                "content_status": "success",
            })

        except Exception:
            continue

    return results


def search_baidu_news(keyword: str, days: int = 7, max_pages: int = 3, debug: bool = False):
    session = requests.Session()
    session.headers.update(get_random_headers())

    debug_info = {
        "keyword": keyword,
        "days": days,
        "max_pages": max_pages,
        "pages": [],
        "total_results": 0,
    }

    try:
        warmup_resp = session.get("https://www.baidu.com", timeout=10)
        if debug:
            debug_info["warmup"] = {
                "status_code": warmup_resp.status_code,
                "final_url": warmup_resp.url,
            }
        time.sleep(random.uniform(1, 2))
    except Exception as e:
        if debug:
            debug_info["warmup_error"] = str(e)

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    start_ts = int(start_time.timestamp())
    end_ts = int(end_time.timestamp())

    all_results = []
    all_seen_urls = set()

    print(f"🔍 开始搜索: 「{keyword}」| 近 {days} 天 | 最多 {max_pages} 页")

    for page in range(max_pages):
        session.headers["User-Agent"] = random.choice(USER_AGENTS)

        encoded_keyword = quote(keyword)
        url = (
            f"https://www.baidu.com/s?"
            f"wd={encoded_keyword}&tn=news"
            f"&rtt=4&bsst=1&cl=2&medium=0"
            f"&gpc=stf%3D{start_ts}%2C{end_ts}%7Cstftype%3D2"
            f"&pn={page * 10}"
        )

        page_debug = {
            "page": page + 1,
            "request_url": url,
        }

        try:
            resp = session.get(url, timeout=15, allow_redirects=True)
            resp.encoding = resp.apparent_encoding or "utf-8"

            soup = BeautifulSoup(resp.text, "lxml")
            page_title = extract_page_title(soup)
            blocked = is_blocked(resp.text)

            raw_results = extract_results_from_soup(soup)

            page_results = []
            for item in raw_results:
                if item["url"] in all_seen_urls:
                    continue
                all_seen_urls.add(item["url"])
                page_results.append(item)

            page_debug.update({
                "status_code": resp.status_code,
                "final_url": resp.url,
                "page_title": page_title,
                "blocked": blocked,
                "result_div_count": len(soup.select("div.result")),
                "container_count": len(soup.select("div.result, div.result-op, div.c-container, div[data-log]")),
                "h3_link_count": len(soup.select("h3 a")),
                "parsed_count": len(page_results),
                "html_preview": resp.text[:500],
            })

            if blocked:
                print(f"⚠️ 第 {page + 1} 页疑似被拦截，页面标题: {page_title}")
                if debug:
                    debug_info["pages"].append(page_debug)
                if page < max_pages - 1:
                    time.sleep(random.uniform(15, 30))
                continue

            all_results.extend(page_results)
            print(f"📄 第 {page + 1} 页: {len(page_results)} 条（累计 {len(all_results)} 条）")

            if debug:
                debug_info["pages"].append(page_debug)

            if page < max_pages - 1:
                random_delay(3, 6)

        except requests.RequestException as e:
            page_debug["request_error"] = str(e)
            print(f"❌ 第 {page + 1} 页请求失败: {e}")
            if debug:
                debug_info["pages"].append(page_debug)
            time.sleep(random.uniform(5, 10))

        except Exception as e:
            page_debug["parse_error"] = str(e)
            print(f"❌ 第 {page + 1} 页解析失败: {e}")
            if debug:
                debug_info["pages"].append(page_debug)

    debug_info["total_results"] = len(all_results)
    print(f"✅ 搜索完成，共 {len(all_results)} 条")

    return all_results, debug_info if debug else None


def fetch_article_content(url: str, max_length: int = 500):
    headers = {"User-Agent": random.choice(USER_AGENTS)}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = resp.apparent_encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "lxml")

        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
            tag.decompose()

        paragraphs = soup.find_all("p")
        content = "\n".join([
            p.get_text(strip=True)
            for p in paragraphs
            if len(p.get_text(strip=True)) > 20
        ])

        if len(content) < 50:
            body = soup.find("body")
            if body:
                content = body.get_text(strip=True)[:max_length]

        if content:
            return content[:max_length], "success"
        else:
            return "", "failed"

    except Exception:
        return "", "failed"


def fetch_all_contents(results: list, max_length: int = 500):
    total = len(results)
    print(f"📥 开始抓取正文（共 {total} 条）...")

    for i, item in enumerate(results):
        print(f"  [{i + 1}/{total}] {item['title'][:30]}...")
        content, status = fetch_article_content(item["url"], max_length)
        item["content"] = content
        item["content_status"] = status

        if i < total - 1:
            random_delay(1, 3)

    print("✅ 正文抓取完成")
    return results
ENDOFFILE