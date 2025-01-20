#!/usr/bin/env python3
import yaml
import json
from pathlib import Path

def load_config():
    """加载现有的播客配置"""
    config_path = Path(__file__).parent.parent.parent / "config" / "podcasts.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_config(config):
    """保存更新后的配置"""
    config_path = Path(__file__).parent.parent.parent / "config" / "podcasts.yml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)

def load_subscribed_podcasts():
    """从本地 JSON 文件加载订阅的播客信息"""
    json_path = Path(__file__).parent.parent.parent / "data" / "podcasts" / "subscribe_podcasts.json"
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def update_podcast_list():
    # 获取现有配置
    config = load_config()
    existing_pids = {podcast["pid"] for podcast in config["podcasts"]}

    # 从本地文件获取订阅列表
    try:
        subscribed_podcasts = load_subscribed_podcasts()
    except Exception as e:
        print(f"读取订阅列表失败：{e}")
        return

    # 添加新的播客
    for podcast in subscribed_podcasts:
        if podcast["pid"] not in existing_pids:
            config["podcasts"].append({
                "pid": podcast["pid"],
                "name": podcast["title"]
            })
            print(f"添加新播客：{podcast['title']}")

    # 保存更新后的配置
    save_config(config)
    print("配置文件已更新")

if __name__ == "__main__":
    update_podcast_list()
