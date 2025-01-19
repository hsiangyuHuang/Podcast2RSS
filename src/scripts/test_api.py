#!/usr/bin/env python3
"""
测试小宇宙API返回的原始数据
"""

import json
import os
import sys
from pathlib import Path
from pprint import pprint

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "src"))

from core.podcast import PodcastClient

def main():
    """主函数"""
    # 初始化客户端
    client = PodcastClient()
    
    # 1. 获取播客列表
    print("\n=== 获取播客列表 ===")
    podcasts = client.get_podcast()
    if podcasts:
        print(f"\n获取到 {len(podcasts)} 个播客")
        print("\n第一个播客的完整数据：")
        print(json.dumps(podcasts[0], ensure_ascii=False, indent=2))
        
        # 2. 获取第一个播客的剧集
        pid = podcasts[0].get('pid')
        if pid:
            print(f"\n\n=== 获取播客 {podcasts[0].get('title')} 的剧集列表 ===")
            episodes = client.get_episodes(pid)
            if episodes:
                print(f"\n获取到 {len(episodes)} 个剧集")
                print("\n第一个剧集的完整数据：")
                print(json.dumps(episodes[0], ensure_ascii=False, indent=2))
            else:
                print("未获取到剧集")
    else:
        print("未获取到播客列表")

if __name__ == "__main__":
    main()
