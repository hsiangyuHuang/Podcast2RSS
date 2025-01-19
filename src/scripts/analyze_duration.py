#!/usr/bin/env python
import json
import logging
from pathlib import Path
from collections import defaultdict

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_duration_distribution():
    """分析所有播客剧集的时长分布"""
    episodes_dir = Path("data/episodes")
    if not episodes_dir.exists():
        logger.error("episodes目录不存在")
        return

    # 统计数据
    total_episodes = 0
    total_duration = 0
    duration_ranges = defaultdict(int)
    long_episodes = []  # 存储超长剧集信息
    short_episodes = {  # 存储短剧集信息
        '1min': [],    # 1分钟以下
        '2min': [],    # 1-2分钟
        '3min': [],    # 2-3分钟
        '5min': []     # 3-5分钟
    }

    # 遍历所有播客文件
    for episode_file in episodes_dir.glob("*.json"):
        try:
            with open(episode_file) as f:
                episodes = json.load(f)
            
            # 处理每个剧集
            for eid, episode in episodes.items():
                duration = episode.get('duration', 0)
                if duration > 0:
                    total_episodes += 1
                    total_duration += duration

                    # 记录短剧集
                    minutes = duration / 60
                    episode_info = {
                        'title': episode.get('title'),
                        'duration': minutes,
                        'podcast': episode_file.stem,
                        'eid': eid
                    }
                    
                    if minutes <= 1:
                        short_episodes['1min'].append(episode_info)
                    elif minutes <= 2:
                        short_episodes['2min'].append(episode_info)
                    elif minutes <= 3:
                        short_episodes['3min'].append(episode_info)
                    elif minutes <= 5:
                        short_episodes['5min'].append(episode_info)

                    # 按时长范围统计
                    hours = duration / 3600
                    if hours <= 0.5:
                        duration_ranges['0-30分钟'] += 1
                    elif hours <= 1:
                        duration_ranges['30-60分钟'] += 1
                    elif hours <= 1.5:
                        duration_ranges['1-1.5小时'] += 1
                    elif hours <= 2:
                        duration_ranges['1.5-2小时'] += 1
                    elif hours <= 3:
                        duration_ranges['2-3小时'] += 1
                    else:
                        duration_ranges['3小时以上'] += 1
                        # 记录超长剧集
                        long_episodes.append({
                            'title': episode.get('title'),
                            'duration': hours,
                            'podcast': episode_file.stem
                        })

        except Exception as e:
            logger.error(f"处理文件 {episode_file} 时出错: {e}")

    # 输出统计结果
    logger.info("\n时长分布统计:")
    logger.info(f"总剧集数: {total_episodes}")
    logger.info(f"总时长: {total_duration/3600:.1f}小时")
    logger.info(f"平均时长: {(total_duration/total_episodes/60):.1f}分钟")
    
    # 输出短剧集统计
    logger.info("\n短剧集统计:")
    logger.info(f"1分钟以下: {len(short_episodes['1min'])} 集")
    logger.info(f"1-2分钟: {len(short_episodes['2min'])} 集")
    logger.info(f"2-3分钟: {len(short_episodes['3min'])} 集")
    logger.info(f"3-5分钟: {len(short_episodes['5min'])} 集")
    
    # 输出短剧集详情
    for duration, episodes in short_episodes.items():
        if episodes:
            if duration == '1min':
                logger.info("\n1分钟以下的剧集:")
            elif duration == '2min':
                logger.info("\n1-2分钟的剧集:")
            elif duration == '3min':
                logger.info("\n2-3分钟的剧集:")
            else:
                logger.info("\n3-5分钟的剧集:")
                
            for ep in sorted(episodes, key=lambda x: x['duration']):
                logger.info(f"- [{ep['podcast']}] {ep['title']}: {ep['duration']:.1f}分钟")
    
    logger.info("\n各时长范围分布:")
    for range_name, count in sorted(duration_ranges.items()):
        percentage = count / total_episodes * 100
        logger.info(f"{range_name}: {count} 集 ({percentage:.1f}%)")

    if long_episodes:
        logger.info("\n超长剧集(3小时以上):")
        for ep in sorted(long_episodes, key=lambda x: x['duration'], reverse=True):
            logger.info(f"- [{ep['podcast']}] {ep['title']}: {ep['duration']:.1f}小时")

if __name__ == "__main__":
    analyze_duration_distribution()
