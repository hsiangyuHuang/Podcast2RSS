# RSS生成系统需求文档

## 1. 项目概述

### 1.1 项目目的
基于已有的播客转写数据，生成RSS feed，使用户可以通过RSS阅读器订阅和阅读播客文字内容。

### 1.2 项目背景
- 已完成播客内容获取和转写
- 需要构建RSS feed展示文字内容
- 需要部署到Railway平台

## 2. 功能需求

### 2.1 数据源说明

#### 目录结构
```
data/
├── episodes/           # 单集基本信息
│   └── {eid}.json     # 例：63b7dd49289d2739647d9587.json
├── transcripts/        # 转写文件
│   └── {eid}.json     # 例：63ca932c78910ae65ca92644.json
└── rss/               # RSS输出目录
    ├── html/          # HTML文件输出
    │   └── {eid}.html # 单集HTML文件
    └── feed.xml       # RSS Feed文件
```

#### 数据格式
1. **单集信息** (`data/episodes/{eid}.json`)
```json
{
    "{eid}": {
        "title": "单集标题",
        "publish_date": "发布日期",
        "duration": "时长"
    }
}
```

2. **转写数据** (`data/transcripts/{eid}.json`)
```json
{
    "pid": "播客ID",
    "eid": "单集ID",
    "title": "单集标题",
    "task_id": "转写任务ID",
    "transcription": [
        {
            "time": "时间戳（格式：HH:MM:SS）",
            "speaker": "说话人标识",
            "text": "说话内容"
        }
    ],
    "lab_info": {
        "summary": "节目摘要（AI生成）",
        "qa_pairs": [
            {
                "question": "问题",
                "answer": "答案",
                "time": "问题在音频中的时间点"
            }
        ],
        "chapters": [
            {
                "time": "章节开始时间",
                "title": "章节标题",
                "summary": "章节摘要"
            }
        ],
        "mindmap": {
            "content": "思维导图主题",
            "children": [
                {
                    "content": "子主题",
                    "children": []
                }
            ]
        }
    }
}
```

### 2.2 RSS生成
- **内容格式化**
  - 转写文本格式化
  - 摘要内容处理
  - 问答内容处理
  - HTML样式美化

- **RSS Feed要求**
  - 符合RSS 2.0标准
  - 支持HTML内容
  - 清晰的文章结构


## 3. 技术架构

### 3.1 代码结构
```
src/
└── rss.py  # RSS生成核心代码
    - 转写数据处理
    - RSS生成
    - 格式化工具
```

### 3.2 数据流
```
输入:
  episodes/*.json    # 单集信息
  transcripts/*.json # 转写内容

处理:
  TranscriptData ← 读取并验证数据
  ↓
  格式化内容 → HTML/RSS内容

输出:
  rss/html/*.html # 单集HTML
  rss/feed.xml    # RSS Feed
