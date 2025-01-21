# Podcast2RSS

一个将小宇宙播客转换为RSS的工具，集成通义听悟实现音频转文字功能。

## 项目结构

## 运行流程

1. **配置加载**
   - 从 `config/podcasts.yml` 读取需要处理的播客列表
   - 每个播客包含 `pid` 和 `name` 信息

2. **逐个播客处理**
   对每个播客执行以下完整流程：

   a. **播客数据获取** (`podcast.py`)
      - 获取播客的元数据信息
      - 获取所有单集信息
      - 保存到 `data/podcasts/[pid].json` 和 `data/episodes/[pid].json`

   b. **音频转写处理** (`transcription.py`)
      - 检查未转写的单集
      - 提交音频转写任务
      - 监控转写状态
      - 保存转写结果到 `data/transcripts/[pid]/`

   c. **RSS生成** (`rss.py`)
      - 读取播客元数据
      - 读取单集信息
      - 读取转写内容
      - 生成RSS并保存到 `data/rss/[pid].xml`

3. **数据存储结构**
   ```
   data/
   ├── podcasts/                 # 播客元数据
   │   └── [pid].json           # 每个播客一个文件
   ├── episodes/                 # 单集信息
   │   └── [pid].json           # 每个播客的所有单集
   ├── transcripts/             # 转写内容
   │   └── [pid]/               # 每个播客一个目录
   │       └── [episode_id].json # 单集的转写结果
   └── rss/                     # 生成的RSS文件
       └── [pid].xml            # 每个播客的RSS文件
   ```

## 数据流
小宇宙API → 本地数据存储 → 通义听悟转写 → RSS Feed生成

## 环境变量
- `TONGYI_COOKIE`: 通义听悟的Cookie，用于API认证
- `REFRESH_TOKEN`: 小宇宙的刷新令牌
- `STORAGE_PATH`: 数据存储路径（可选）

## 使用说明
1. 配置环境变量
2. 在 `config/podcasts.yml` 中配置需要处理的播客
3. 运行 `python src/main.py`

