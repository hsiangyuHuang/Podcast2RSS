import json
import os
import pendulum
from retrying import retry
import requests
from pathlib import Path
from dotenv import load_dotenv
import time
import logging
import yaml

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# 配置数据存储路径
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PODCASTS_DIR = DATA_DIR / "podcasts"
EPISODES_DIR = DATA_DIR / "episodes"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
PODCAST_CONFIG = CONFIG_DIR / "podcasts.yml"

# 创建必要的目录
DATA_DIR.mkdir(exist_ok=True)
PODCASTS_DIR.mkdir(exist_ok=True)
EPISODES_DIR.mkdir(exist_ok=True)
TRANSCRIPTS_DIR.mkdir(exist_ok=True)
CONFIG_DIR.mkdir(exist_ok=True)

headers = {
    "host": "api.xiaoyuzhoufm.com",
    "applicationid": "app.podcast.cosmos",
    "x-jike-refresh-token": os.getenv("REFRESH_TOKEN").strip(),
    "x-jike-device-id": "5070e349-ba04-4c7b-a32e-13eb0fed01e7",
}

def ensure_token():
    """确保token有效"""
    if "x-jike-access-token" not in headers:
        refresh_token()

@retry(stop_max_attempt_number=3, wait_fixed=5000)
def refresh_token():
    """刷新访问令牌"""
    url = "https://api.xiaoyuzhoufm.com/app_auth_tokens.refresh"
    resp = requests.post(url, headers=headers)
    if not resp.ok:
        raise Exception(f"刷新令牌失败: {resp.text}")
    token = resp.json().get("x-jike-access-token")
    if not token:
        raise Exception("未获取到有效的访问令牌")
    headers["x-jike-access-token"] = token
    # 等待token生效
    time.sleep(1)

@retry(stop_max_attempt_number=3, wait_fixed=5000)
def get_podcast():
    results = []
    url = "https://api.xiaoyuzhoufm.com/v1/subscription/list"
    data = {
        "limit": 25,
        "sortBy": "subscribedAt",
        "sortOrder": "desc",
    }
    loadMoreKey = ""
    while loadMoreKey is not None:
        if loadMoreKey:
            data["loadMoreKey"] = loadMoreKey
        resp = requests.post(url, json=data, headers=headers)
        if resp.ok:
            loadMoreKey = resp.json().get("loadMoreKey")
            results.extend(resp.json().get("data"))
        else:
            refresh_token()
            raise Exception(f"Error {data} {resp.text}")
    return results

@retry(stop_max_attempt_number=3, wait_fixed=5000)
def get_episodes(pid):
    """获取播客剧集列表"""
    ensure_token()
    url = "https://api.xiaoyuzhoufm.com/v1/episode/list"
    episodes = []
    load_more_key = None
    
    while True:
        data = {
            "limit": 25,
            "pid": pid,
        }
        if load_more_key:
            data["loadMoreKey"] = load_more_key
            
        resp = requests.post(url, json=data, headers=headers)
        if not resp.ok:
            if resp.status_code == 401:
                refresh_token()
                continue
            raise Exception(f"获取剧集列表失败: {resp.text}")
            
        resp_data = resp.json()
        new_episodes = resp_data.get("data", [])
        if not new_episodes:
            break
            
        episodes.extend(new_episodes)
        load_more_key = resp_data.get("loadMoreKey")
        if not load_more_key:
            break
            
    return episodes


def save_episodes(episodes, pid):
    """保存播客剧集到文件
    
    Args:
        episodes: 剧集列表
        pid: 播客ID
    """
    EPISODES_DIR.mkdir(exist_ok=True)
    
    filepath = EPISODES_DIR / f"{pid}.json"
    existing_episodes = {}
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            existing_episodes = json.load(f)
    
    # 更新数据
    for episode in episodes:
        episode_id = episode.get("eid")
        if not episode_id:
            logger.warning(f"剧集缺少eid: {episode.get('title')}")
            continue
        
        # 只保留RSS Feed需要的字段
        episode_data = {
            "eid": episode_id,
            "pid": episode.get("pid"),
            "title": episode.get("title"),
            "description": episode.get("description"),
            # "shownotes": episode.get("shownotes"),  # 保留完整的节目笔记
            "duration": episode.get("duration"),  # 音频时长（秒）
            "enclosure": {
                "url": episode.get("enclosure", {}).get("url"),
                "type": "audio/mpeg",  # RSS Feed通常使用mp3格式
                "length": episode.get("media", {}).get("size", 0)  # 文件大小
            },
            "pubDate": pendulum.parse(episode.get("pubDate")).in_tz("UTC").int_timestamp if episode.get("pubDate") else None,
            "author": episode.get("podcast", {}).get("author"),
            "explicit": episode.get("explicit", False)
        }
        
        existing_episodes[episode_id] = episode_data
    
    # 保存到文件
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(existing_episodes, f, ensure_ascii=False, indent=2)
    
    logger.info(f"保存了 {len(episodes)} 个剧集到: {filepath}")


def load_podcast_config():
    """加载播客配置"""
    with open(PODCAST_CONFIG) as f:
        config = yaml.safe_load(f)
    return config['podcasts']


def check_environment():
    """检查必要的环境变量"""
    required_vars = {
        "REFRESH_TOKEN": os.getenv("REFRESH_TOKEN"),
        "STORAGE_PATH": os.getenv("STORAGE_PATH"),
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        raise Exception(f"缺少必要的环境变量: {', '.join(missing_vars)}")
    return required_vars


def main():
    """主函数"""
    try:
        # 1. 获取并保存订阅的播客信息
        results = get_podcast()
        # 只保留指定字段
        filtered_results = []
        total_episodes = 0
        for podcast in results:
            episode_count = podcast.get('episodeCount', 0)
            total_episodes += episode_count
            filtered_podcast = {
                'latestEpisodePubDate': podcast.get('latestEpisodePubDate'),
                'pid': podcast.get('pid'),
                'title': podcast.get('title'),
                'brief': podcast.get('brief'),
                'episodeCount': episode_count,
                'description': podcast.get('description')
            }
            filtered_results.append(filtered_podcast)
            logger.info(f"播客 {filtered_podcast['title']}: {episode_count} 集")
            
            # 将单个播客信息保存为独立的JSON文件
            pid = filtered_podcast['pid']
            podcast_file = PODCASTS_DIR / f"{pid}.json"
            with open(podcast_file, "w", encoding="utf-8") as f:
                json.dump(filtered_podcast, f, ensure_ascii=False, indent=4)
            logger.info(f"保存播客信息到: {podcast_file}")
            
        # 将所有播客信息存储为JSON文件
        output_file = PODCASTS_DIR / "subscribe_podcasts.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(filtered_results, f, ensure_ascii=False, indent=4)
        logger.info(f"更新订阅信息")
        logger.info(f"所有播客总集数: {total_episodes}")
        
        # 2. 获取指定播客的剧集信息
        podcasts = load_podcast_config()
        for podcast in podcasts:
            pid = podcast.get('pid')
            if not pid:
                logger.error(f"播客配置缺少pid字段: {podcast}")
                continue
                
            try:
                start_time = time.time()
                episodes = get_episodes(pid)  # 直接调用get_episodes
                if episodes:
                    save_episodes(episodes, pid)  # 直接调用save_episodes
                    logger.info(f"获取到 {len(episodes)} 个剧集")
                else:
                    logger.warning(f"播客 {pid} 没有任何剧集")
                process_time = time.time() - start_time
                logger.info(f"处理完成: {pid}, 耗时: {process_time:.2f}秒")
            except Exception as e:
                logger.error(f"处理失败: {pid}, 错误: {str(e)}")
    except Exception as e:
        logger.error(f"执行失败: {str(e)}")
        raise


if __name__ == "__main__":
    main()