import json
import os
import pendulum
from retrying import retry
import requests
from pathlib import Path
import time
import logging
import yaml

try:
    from .storage import Storage
except ImportError:
    from src.core.storage import Storage

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PodcastClient:
    """小宇宙API客户端"""
    
    def __init__(self):
        # 初始化存储
        self.storage = Storage()
        
        # 初始化headers
        self.headers = {
            "host": "api.xiaoyuzhoufm.com",
            "applicationid": "app.podcast.cosmos",
            "x-jike-refresh-token": os.getenv("REFRESH_TOKEN"),
            "x-jike-device-id": "5070e349-ba04-4c7b-a32e-13eb0fed01e7",
        }
        
        # 检查必要的环境变量
        self._check_environment()

    def _check_environment(self):
        """检查必要的环境变量"""
        if not os.getenv("REFRESH_TOKEN"):
            raise Exception("缺少必要的环境变量: REFRESH_TOKEN")

    def ensure_token(self):
        """确保token有效"""
        if "x-jike-access-token" not in self.headers:
            self.refresh_token()

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def refresh_token(self):
        """刷新访问令牌"""
        url = "https://api.xiaoyuzhoufm.com/app_auth_tokens.refresh"
        resp = requests.post(url, headers=self.headers)
        if not resp.ok:
            raise Exception(f"刷新令牌失败: {resp.text}")
        token = resp.json().get("x-jike-access-token")
        if not token:
            raise Exception("未获取到有效的访问令牌")
        self.headers["x-jike-access-token"] = token
        # 等待token生效
        time.sleep(1)

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_podcast(self):
        """获取订阅的播客列表"""
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
            resp = requests.post(url, json=data, headers=self.headers)
            if resp.ok:
                loadMoreKey = resp.json().get("loadMoreKey")
                results.extend(resp.json().get("data"))
            else:
                self.refresh_token()
                raise Exception(f"Error {data} {resp.text}")
        return results

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_episodes(self, pid):
        """获取播客剧集列表"""
        self.ensure_token()
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
                
            resp = requests.post(url, json=data, headers=self.headers)
            if not resp.ok:
                if resp.status_code == 401:
                    self.refresh_token()
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

    def save_episodes(self, episodes, pid):
        """保存播客剧集到文件"""
        filepath = self.storage.get_episodes_file(pid)
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
                "duration": episode.get("duration"),
                "enclosure": {
                    "url": episode.get("enclosure", {}).get("url"),
                    "type": "audio/mpeg",
                    "length": episode.get("media", {}).get("size", 0)
                },
                "pubDate": pendulum.parse(episode.get("pubDate")).in_tz("UTC").int_timestamp if episode.get("pubDate") else None,
                "author": episode.get("podcast", {}).get("author"),
                "explicit": episode.get("explicit", False),
                "payType": episode.get("payType", "FREE")
            }
            
            existing_episodes[episode_id] = episode_data
        
        # 保存到文件
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(existing_episodes, f, ensure_ascii=False, indent=2)
        
        logger.info(f"保存了 {len(episodes)} 个剧集到: {filepath}")

    def update_all(self, pids=None):
        """更新所有播客数据
        
        Args:
            pids: 要更新的播客ID列表，如果为None则更新所有订阅的播客
        """
        try:
            # 1. 获取并保存订阅的播客信息
            results = self.get_podcast()
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
                
                # 将单个播客信息保存为独立的JSON文件
                pid = filtered_podcast['pid']
                podcast_file = self.storage.get_podcast_file(pid)
                with open(podcast_file, "w", encoding="utf-8") as f:
                    json.dump(filtered_podcast, f, ensure_ascii=False, indent=4)
                
            # 将所有播客信息存储为JSON文件
            output_file = self.storage.podcasts_dir / "subscribe_podcasts.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(filtered_results, f, ensure_ascii=False, indent=4)
            logger.info(f"更新订阅信息")
            logger.info(f"所有播客总集数: {total_episodes}")
            
            # 2. 获取指定播客的剧集信息
            if pids:
                for pid in pids:
                    try:
                        start_time = time.time()
                        episodes = self.get_episodes(pid)
                        if episodes:
                            self.save_episodes(episodes, pid)
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