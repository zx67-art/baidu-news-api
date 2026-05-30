import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from typing import Tuple, List, Dict, Optional

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

BAIDU_HEADERS = {
    **BROWSER_HEADERS,
    "Referer": "https://www.baidu.com/",
}

TIME_PATTERNS = [
    r'刚刚',
    r'\d+分钟前',
    r'\d+小时前',
    r'昨天\d{0,2}:\d{0,2}',
    r'昨天',
    r'前天\d{0,2}:\d{0,2}',
    r'前天',
    r'\d+天前',
    r'\d{1,2}月\d{1,2}日',
    r'\d{4}年\d{1,2}月\d{1,2}日',
]


def is_valid_news_url(href: str) -> bool:
    if not href:
        return False

    # 百家号
    if "baijiahao.baidu.com" in href:
        return True

    # 百度跳转链接
    if "/link?" in href and "url=" in href:
        return True

    parsed = urlparse(href)

    # 过滤百度站内搜索/热榜/推荐
    if "baidu.com" in parsed.netloc:
        return False

    # 外部站点
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return True

    return False


def extract_time_and_source(text: str) -> Tuple[str, str]:
    if not text:
        return "", ""

    clean_text = re.sub(r'\s+', ' ', text).strip()

    for pattern in TIME_PATTERNS:
        match = re.search(pattern, clean_text)
        if match:
            time_str = match.group(0)
            source = clean_text.replace(time_str, "").strip(" -_|·")
            return time_str, source

    return "", clean_text


def extract_results_from_soup(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    results = []
    seen = set()

    # 只抓左侧主结果区
    content_left = soup.find("div", id="content_left")
    if not content_left:
        return results

    # 多种候选容器，尽量兼容百度资讯页不同块
    containers = []

    selectors = [
        'div.result',
        'div.result-op',
        'div.c-container',
        'div[data-log]',
    ]

    for selector in selectors:
        containers.extend(content_left.select(selector))

    # 去重容器，保留页面顺序
    deduped_containers = []
    container_seen = set()
    for c in containers:
        cid = id(c)
        if cid not in container_seen:
            container_seen.add(cid)
            deduped_containers.append(c)

    for container in deduped_containers:
        title = ""
        href = ""
        snippet = ""
        source = ""
        time_str = ""

        # 1. 优先找 h3 a
        a_tag = None
        h3 = container.find("h3")
        if h3:
            a_tag = h3.find("a", href=True)

        # 2. 如果没有 h3 a，再找第一个较像标题的链接
        if not a_tag:
            all_links = container.find_all("a", href=True)
            for link in all_links:
                txt = link.get_text(" ", strip=True)
                href_candidate = link.get("href", "")
                if len(txt) >= 8 and is_valid_news_url(href_candidate):
                    a_tag = link
                    break

        if not a_tag:
            continue

        href = a_tag.get("href", "").strip()
        title = a_tag.get_text(" ", strip=True).strip()

        if not title or len(title) < 5:
            continue

        if not is_valid_news_url(href):
            continue

        # 摘要提取
        snippet_candidates = []

        for sel in [
            'div.c-abstract',
            'span.content-right_8Zs40',
            'div.c-span9',
            'div.c-font-normal',
            'div[class*="summary"]',
            'p',
        ]:
            snippet_candidates.extend(container.select(sel))

        for elem in snippet_candidates:
            txt = elem.get_text(" ", strip=True)
            if txt and len(txt) > 20 and txt != title:
                snippet = txt
                break

        # 时间/来源提取
        meta_texts = []

        for sel in [
            'span',
            'a.c-showurl',
            'span.c-showurl',
            'span.source_1Vdap',
            'div[class*="source"]',
            'div[class*="time"]',
        ]:
            for elem in container.select(sel):
                txt = elem.get_text(" ", strip=True)
                if txt and len(txt) <= 40:
                    meta_texts.append(txt)

        # 去重保序
        uniq_meta = []
        meta_seen = set()
        for t in meta_texts:
            if t not in meta_seen:
                meta_seen.add(t)
                uniq_meta.append(t)

        for t in uniq_meta:
            found_time, found_source = extract_time_and_source(t)
            if found_time and not time_str:
                time_str = found_time
            if found_source and not source and found_source != time_str:
                source = found_source

        # 如果 source 还是空，但 snippet 开头像“昨天18:46 ...”
        if not time_str and snippet:
            found_time, found_source = extract_time_and_source(snippet[:40])
            if found_time:
                time_str = found_time
                if found_source and not source:
                    source = found_source

        key = (title, href)
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "title": title,
            "url": urljoin(base_url, href),
            "source": source,
            "time": time_str,
            "snippet": snippet,
        })

    return results


def is_within_days(time_str: str, days: int) -> bool:
    if not time_str:
        return True

    time_str = time_str.strip()

    if "刚刚" in time_str or "分钟前" in time_str or "小时前" in time_str:
        return True

    if "昨天" in time_str:
        return days >= 1

    if "前天" in time_str:
        return days >= 2

    m = re.search(r'(\d+)\s*天前', time_str)
    if m:
        return int(m.group(1)) <= days

    # 月日格式先保留
    if re.search(r'\d{1,2}月\d{1,2}日', time_str):
        return True

    return True


def search_baidu_news(keyword: str, days: int = 7, debug: bool = False) -> Tuple[List[Dict], Optional[Dict]]:
    baidu_url = f"https://www.baidu.com/s?wd={keyword}&tn=news&rtt=1&bsst=1&cl=2"

    debug_info = {
        "url": baidu_url,
        "page_title": None,
        "content_left_exists": False,
        "container_count": 0,
        "result_count": 0,
    }

    try:
        session = requests.Session()
        response = session.get(
            baidu_url,
            headers=BAIDU_HEADERS,
            timeout=20,
            allow_redirects=True,
        )
        response.encoding = response.apparent_encoding or "utf-8"

        if response.status_code != 200:
            return [], {"error": f"HTTP {response.status_code}", **debug_info}

        html = response.text
        soup = BeautifulSoup(html, "lxml")

        if "访问频率过高" in html or "验证码" in html:
            return [], {"error": "blocked", **debug_info}

        content_left = soup.find("div", id="content_left")

        if debug:
            debug_info["page_title"] = soup.title.string if soup.title else None
            debug_info["content_left_exists"] = content_left is not None
            if content_left:
                debug_info["container_count"] = len(content_left.find_all(["div"]))

        results = extract_results_from_soup(soup, baidu_url)

        if days > 0:
            results = [r for r in results if is_within_days(r.get("time", "") or r.get("source", ""), days)]

        if debug:
            debug_info["result_count"] = len(results)

        return results, debug_info

    except Exception as e:
        return [], {"error": str(e), **debug_info}
