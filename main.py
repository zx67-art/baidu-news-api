from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import time
import requests
from crawler import search_baidu_news

app = FastAPI(title="Baidu News API", version="3.0")

FC_FETCH_URL = "https://baidu-news-api-bhlnsujzen.cn-hangzhou.fcapp.run/fetch-content"


class SearchRequest(BaseModel):
    keyword: str
    days: int = 7
    fetch_content: bool = True
    debug: bool = False


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    time: str
    snippet: str
    content: Optional[str] = None
    content_status: Optional[str] = None


class SearchResponse(BaseModel):
    success: bool
    keyword: str
    days: int
    count: int
    search_status: str
    items: List[NewsItem]
    message: str
    debug_info: Optional[dict] = None


@app.get("/")
async def root():
    return {"message": "Baidu News API v3.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


def fetch_content_via_fc(url: str):
    try:
        resp = requests.post(
            FC_FETCH_URL,
            json={"url": url},
            timeout=30
        )
        if resp.status_code != 200:
            return "[内容获取失败，请访问原文链接]", "failed"

        data = resp.json()
        return data.get("content", "[内容获取失败，请访问原文链接]"), data.get("content_status", "failed")
    except Exception:
        return "[内容获取失败，请访问原文链接]", "failed"


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    start_time = time.time()

    results, debug_info = search_baidu_news(
        keyword=request.keyword,
        days=request.days,
        debug=request.debug
    )

    # 可选：先限制前10条，避免太慢
    results = results[:10]

    if debug_info and debug_info.get("error"):
        if debug_info["error"] == "blocked":
            search_status = "blocked"
        else:
            search_status = "error"
    elif len(results) == 0:
        search_status = "empty"
    else:
        search_status = "success"

    items = []
    success_count = 0
    failed_count = 0

    for r in results:
        item = NewsItem(
            title=r["title"],
            url=r["url"],
            source=r.get("source", ""),
            time=r.get("time", ""),
            snippet=r.get("snippet", ""),
        )

        if request.fetch_content:
            content, status = fetch_content_via_fc(r["url"])
            item.content = content
            item.content_status = status
            if status == "success":
                success_count += 1
            else:
                failed_count += 1
        else:
            item.content = None
            item.content_status = "skipped"

        items.append(item)

    elapsed = time.time() - start_time

    if request.fetch_content:
        message = f"成功获取 {len(items)} 条资讯（{success_count} 条正文成功，{failed_count} 条正文失败），耗时 {elapsed:.1f} 秒"
    else:
        message = f"成功获取 {len(items)} 条资讯，耗时 {elapsed:.1f} 秒"

    return SearchResponse(
        success=search_status == "success",
        keyword=request.keyword,
        days=request.days,
        count=len(items),
        search_status=search_status,
        items=items,
        message=message,
        debug_info=debug_info if request.debug else None
    )
