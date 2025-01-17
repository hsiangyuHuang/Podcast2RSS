import os
import logging
from pathlib import Path
from dotenv import load_dotenv
import requests
import time
import json
from datetime import datetime

# 加载环境变量
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

def get_podcast():
    results = []
    url = "https://api.xiaoyuzhoufm.com/v1/subscription/list"
    data = {
        "limit": 25,
        "sortBy": "subscribedAt",
        "sortOrder": "desc",
    }
    loadMoreKey = ""
    
    # 确保有有效的token
    ensure_token()
    
    print(f"使用的headers: {headers}")  # 添加调试信息
    while loadMoreKey is not None:
        if loadMoreKey:
            data["loadMoreKey"] = loadMoreKey
        try:
            resp = requests.post(url, json=data, headers=headers)
            print(f"API响应状态码: {resp.status_code}")  # 添加调试信息
            if resp.ok:
                loadMoreKey = resp.json().get("loadMoreKey")
                results.extend(resp.json().get("data"))
            else:
                print(f"刷新token前的错误响应: {resp.text}")  # 添加调试信息
                refresh_token()
                raise Exception(f"Error {data} {resp.text}")
        except Exception as e:
            print(f"请求发生异常: {str(e)}")  # 添加调试信息
            raise
    return results

def ensure_token():
    """确保token有效"""
    if "x-jike-access-token" not in headers:
        refresh_token()

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

def save_podcasts_to_json(podcasts, output_dir):
    """将播客数据保存为JSON文件"""
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 使用时间戳作为文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"podcasts_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # 保存数据
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(podcasts, f, ensure_ascii=False, indent=2)
    
    print(f"播客数据已保存到: {filepath}")
    return filepath

if __name__ == "__main__":
    headers = {
        "host": "api.xiaoyuzhoufm.com",
        "applicationid": "app.podcast.cosmos",
        "x-jike-refresh-token": os.getenv("REFRESH_TOKEN").strip(),
        "x-jike-device-id": "5070e349-ba04-4c7b-a32e-13eb0fed01e7",
    }
    
    # 获取播客数据
    podcasts = get_podcast()
    
    # 保存到JSON文件
    output_dir = "/Users/hsiangyu/Inbox/Podcast2RSS/data/podcasts"
    save_podcasts_to_json(podcasts, output_dir)