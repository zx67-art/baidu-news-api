"""
百度资讯抓取 API - FastAPI 入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import time

from crawler import search_baidu_news, fetch_all_contents


# 创建 FastAPI 应用
app = FastAPI(
    title="百度资讯抓取 API",
    description="为 Coze 工作流提供百度资讯搜索和抓取服务",
    version="1.0.0",
)

# 允许跨域（Coze 调用需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
#  请求/响应模型
# ============================================

class SearchRequest(BaseModel):
    """搜索请求"""
    keyword: str                    # 搜索关键词
    days: int = 7                   # 搜索近 N 天
    max_pages: int = 10             # 最大翻页数（默认10页≈100条）
    fetch_content: bool = True      # 是否抓取正文（默认True）
    content_length: int = 500       # 正文最大长度


class NewsItem(BaseModel):
    """单条资讯"""
    title: str
    url: str
    source: str = ""
    time: str = ""
    snippet: str = ""
    content: Optional[str] = None


class SearchResponse(BaseModel):
    """搜索响应"""
    success: bool
    keyword: str
    days: int
    count: int
    items: List[NewsItem]
    message: str = ""


# ============================================
#  API 路由
# ============================================

@app.get("/")
def root():
    """根路径 - 健康检查"""
    return {
        "status": "ok",
        "service": "百度资讯抓取 API",
        "version": "1.0.0",
        "endpoints": {
            "POST /search": "搜索百度资讯",
            "GET /health": "健康检查",
        },
        "usage": {
            "keyword": "搜索关键词（必填）",
            "days": "搜索近 N 天，默认 7",
            "max_pages": "最大翻页数，默认 10（约 100 条）",
            "fetch_content": "是否抓取正文，默认 true",
            "content_length": "正文最大长度，默认 500"
        }
    }


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "healthy"}


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    """
    搜索百度资讯

    请求示例:
    {
        "keyword": "字节跳动",
        "days": 7,
        "max_pages": 10,
        "fetch_content": true,
        "content_length": 500
    }
    """
    start_time = time.time()

    try:
        # 搜索
        results = search_baidu_news(
            keyword=req.keyword,
            days=req.days,
            max_pages=req.max_pages
        )

        # 抓取正文
        if req.fetch_content and results:
            results = fetch_all_contents(results, req.content_length)

        elapsed = time.time() - start_time

        return SearchResponse(
            success=True,
            keyword=req.keyword,
            days=req.days,
            count=len(results),
            items=results,
            message=f"成功获取 {len(results)} 条资讯，耗时 {elapsed:.1f} 秒"
        )

    except Exception as e:
        return SearchResponse(
            success=False,
            keyword=req.keyword,
            days=req.days,
            count=0,
            items=[],
            message=f"搜索失败: {str(e)}"
        )


# ============================================
#  本地测试
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
