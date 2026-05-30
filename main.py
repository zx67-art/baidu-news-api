"""
百度资讯抓取 API - FastAPI 入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time

from crawler import search_baidu_news, fetch_all_contents


app = FastAPI(
    title="百度资讯抓取 API",
    description="为 Coze 工作流提供百度资讯搜索和抓取服务",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    keyword: str
    days: int = 7
    max_pages: int = 10
    fetch_content: bool = True
    content_length: int = 500
    debug: bool = False


class NewsItem(BaseModel):
    title: str
    url: str
    source: str = ""
    time: str = ""
    snippet: str = ""
    content: Optional[str] = None
    content_status: str = "success"


class SearchResponse(BaseModel):
    success: bool
    keyword: str
    days: int
    count: int
    search_status: str = "success"
    items: List[NewsItem]
    message: str = ""
    debug_info: Optional[Dict[str, Any]] = None


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "百度资讯抓取 API",
        "version": "2.0.0",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    start_time = time.time()

    try:
        results, debug_info = search_baidu_news(
            keyword=req.keyword,
            days=req.days,
            max_pages=req.max_pages,
            debug=req.debug
        )

        search_status = "success"
        blocked_pages = 0

        if debug_info and debug_info.get("pages"):
            for page_info in debug_info["pages"]:
                if page_info.get("blocked"):
                    blocked_pages += 1

            total_pages = len(debug_info["pages"])
            if blocked_pages == total_pages and len(results) == 0:
                search_status = "blocked"
            elif blocked_pages > 0:
                search_status = "partial"
            elif len(results) == 0:
                search_status = "empty"
        elif len(results) == 0:
            search_status = "empty"

        if req.fetch_content and results:
            results = fetch_all_contents(results, req.content_length)
        elif not req.fetch_content:
            for item in results:
                item["content_status"] = "skipped"

        elapsed = time.time() - start_time

        if search_status == "blocked":
            message = f"搜索被百度拦截，未能获取资讯。请稍后重试或更换网络环境。耗时 {elapsed:.1f} 秒"
        elif search_status == "partial":
            success_count = len([i for i in results if i.get("content_status") != "failed"])
            failed_count = len([i for i in results if i.get("content_status") == "failed"])
            message = f"部分页面被拦截，获取 {len(results)} 条资讯（{success_count} 条正文成功，{failed_count} 条正文失败），耗时 {elapsed:.1f} 秒"
        elif search_status == "empty":
            message = f"未找到相关资讯。可能原因：百度页面结构变化或被拦截。耗时 {elapsed:.1f} 秒"
        else:
            success_count = len([i for i in results if i.get("content_status") == "success"])
            failed_count = len([i for i in results if i.get("content_status") == "failed"])
            if req.fetch_content and failed_count > 0:
                message = f"成功获取 {len(results)} 条资讯（{success_count} 条正文成功，{failed_count} 条正文失败），耗时 {elapsed:.1f} 秒"
            else:
                message = f"成功获取 {len(results)} 条资讯，耗时 {elapsed:.1f} 秒"

        return SearchResponse(
            success=search_status != "blocked",
            keyword=req.keyword,
            days=req.days,
            count=len(results),
            search_status=search_status,
            items=results,
            message=message,
            debug_info=debug_info if req.debug else None
        )

    except Exception as e:
        return SearchResponse(
            success=False,
            keyword=req.keyword,
            days=req.days,
            count=0,
            search_status="error",
            items=[],
            message=f"搜索失败: {str(e)}",
            debug_info={"error": str(e)} if req.debug else None
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
