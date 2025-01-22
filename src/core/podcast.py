import json
import os
import pendulum
from retrying import retry
import requests
from pathlib import Path
import time
import logging
import yaml
from datetime import datetime

try:
    from .storage import Storage
except ImportError:
    from src.core.storage import Storage

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PodcastClient:
    """小宇宙播客客户端"""
    
    def __init__(self, storage):
        """初始化客户端
        
        Args:
            storage: Storage实例，用于管理数据存储
        """
        self.storage = storage
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
    def get_subscription(self):
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

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def get_podcast_info(self, pid):
        """获取单个播客的信息"""
        self.ensure_token()
        url = f"https://api.xiaoyuzhoufm.com/v1/podcast/get?pid={pid}"
        
        # 获取ISO格式的当前时间
        now = datetime.now()
        iso_time = now.strftime("%Y-%m-%dT%H:%M:%S%z")
        
        # 添加必要的请求头
        headers = {
            **self.headers,
            'User-Agent': 'Xiaoyuzhou/2.57.1 (build:1576; iOS 17.4.1)',
            'Market': 'AppStore',
            'App-BuildNo': '1576',
            'OS': 'ios',
            'Manufacturer': 'Apple',
            'BundleID': 'app.podcast.cosmos',
            'Model': 'iPhone14,2',
            'App-Version': '2.57.1',
            'OS-Version': '17.4.1',
            'Local-Time': iso_time,
            'Timezone': 'Asia/Shanghai',
            'Accept': '*/*',
            'Accept-Language': 'zh-Hant-HK;q=1.0, zh-Hans-CN;q=0.9'
        }

        resp = requests.get(url, headers=headers)

        if not resp.ok:
            if resp.status_code == 401:
                self.refresh_token()
                return self.get_podcast_info(pid)
            raise Exception(f"获取播客信息失败: {resp.text}")
            
        podcast = resp.json().get("data", {})
        if not podcast:
            raise Exception(f"未获取到播客信息: {pid}")
            
        # 只保留需要的字段
        filtered_podcast = {
            'latestEpisodePubDate': podcast.get('latestEpisodePubDate'),
            'pid': podcast.get('pid'),
            'title': podcast.get('title'),
            'brief': podcast.get('brief'),
            'episodeCount': podcast.get('episodeCount', 0),
            'description': podcast.get('description')
        }
        return filtered_podcast

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
                "payType": episode.get("payType", "FREE"),
                "shownotes": episode.get("shownotes", "")  # 添加 shownotes 字段
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
            # 1. 获取并保存指定播客信息
            total_episodes = 0
            results = []
            
            for pid in pids:
                # 获取并保存单个播客信息
                podcast = self.get_podcast_info(pid)
                results.append(podcast)
                total_episodes += podcast.get('episodeCount', 0)
                
                # 保存到独立文件
                podcast_file = self.storage.get_podcast_file(pid)
                with open(podcast_file, "w", encoding="utf-8") as f:
                    json.dump(podcast, f, ensure_ascii=False, indent=4)

            logger.info(f"更新播客信息完成")
            logger.info(f"所有播客历史总集数: {total_episodes}")

            # 2. 获取指定播客的剧集信息
            for index, pid in enumerate(pids, 1):
                try:
                    start_time = time.time()
                    logger.info(f"[{index}/{len(pids)}] 正在获取播客 {pid} 的剧集信息...")
                    episodes = self.get_episodes(pid)
                    if episodes:
                        self.save_episodes(episodes, pid)
                        logger.info(f"[{index}/{len(pids)}] 获取到 {len(episodes)} 个剧集")
                    else:
                        logger.warning(f"[{index}/{len(pids)}] 播客 {pid} 没有任何剧集")
                    process_time = time.time() - start_time
                    logger.info(f"[{index}/{len(pids)}] 处理完成: {pid}, 耗时: {process_time:.2f}秒")
                except Exception as e:
                    logger.error(f"[{index}/{len(pids)}] 处理失败: {pid}, 错误: {str(e)}")
        except Exception as e:
            logger.error(f"执行失败: {str(e)}")
            raise
