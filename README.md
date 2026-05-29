# 百度资讯抓取 API

为 Coze 工作流提供百度资讯搜索和抓取服务。

## API 接口

### POST /search

搜索百度资讯。

**请求体：**

```json
{
  "keyword": "字节跳动",
  "days": 7,
  "max_pages": 3,
  "fetch_content": true,
  "content_length": 500
}
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| keyword | string | 必填 | 搜索关键词 |
| days | int | 7 | 搜索近 N 天 |
| max_pages | int | 3 | 最大翻页数（每页约 10 条） |
| fetch_content | bool | false | 是否抓取正文 |
| content_length | int | 500 | 正文最大长度（字符） |

**响应示例：**

```json
{
  "success": true,
  "keyword": "字节跳动",
  "days": 7,
  "count": 15,
  "items": [
    {
      "title": "字节跳动发布新产品",
      "url": "https://news.baidu.com/...",
      "source": "新华网",
      "time": "2小时前",
      "snippet": "摘要内容...",
      "content": "正文内容..."
    }
  ],
  "message": "成功获取 15 条资讯，耗时 45.2 秒"
}
```

## 本地测试

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python main.py

# 或
uvicorn main:app --reload

# 测试
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"keyword": "字节跳动", "days": 7}'
```
