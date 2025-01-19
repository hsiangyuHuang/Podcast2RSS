#!/usr/bin/env python3
"""
分析特定播客的所有剧集数据
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "src"))

from core.podcast import PodcastClient

def save_to_markdown(data: dict, output_file: Path):
    """保存分析结果到Markdown文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        # 写入标题
        f.write("# 播客分析报告\n\n")
        f.write(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 写入播客基本信息
        podcast = data['podcast']
        f.write("## 播客信息\n\n")
        f.write(f"- 标题：{podcast.get('title', 'N/A')}\n")
        f.write(f"- ID：{podcast.get('pid', 'N/A')}\n")
        f.write(f"- 作者：{podcast.get('author', 'N/A')}\n")
        f.write(f"- 简介：{podcast.get('description', 'N/A')}\n\n")
        
        # 分析剧集付费情况
        episodes = data['episodes']
        payment_stats = analyze_payment_fields(episodes)
        
        # 写入付费分析结果
        f.write("## 付费情况分析\n\n")
        
        f.write("### isPrivateMedia 字段分布\n")
        for value, count in payment_stats['isPrivateMedia'].items():
            f.write(f"- {value}: {count} 个剧集\n")
        f.write("\n")
        
        f.write("### source_mode 字段分布\n")
        for value, count in payment_stats['source_mode'].items():
            f.write(f"- {value}: {count} 个剧集\n")
        f.write("\n")
        
        f.write("### payType 字段分布\n")
        for value, count in payment_stats['payType'].items():
            f.write(f"- {value}: {count} 个剧集\n")
        f.write("\n")
        
        f.write(f"- 总剧集数：{payment_stats['total_episodes']}\n")
        f.write(f"- 免费剧集：{payment_stats['free_episodes']}\n")
        f.write(f"- isPrivateMedia付费：{payment_stats['paid_episodes']['isPrivateMedia']}\n")
        f.write(f"- source_mode付费：{payment_stats['paid_episodes']['source_mode']}\n")
        f.write(f"- payType付费：{payment_stats['paid_episodes']['payType']}\n")
        f.write("\n")
        
        # 写入示例数据
        f.write("## 示例数据\n\n")
        f.write("第一个剧集的原始数据：\n\n")
        f.write("```json\n")
        if isinstance(episodes, dict):
            first_episode = next(iter(episodes.values()))
        else:
            first_episode = episodes[0]
        f.write(json.dumps(first_episode, ensure_ascii=False, indent=2))
        f.write("\n```\n")

def analyze_payment_fields(episodes):
    """分析付费相关字段"""
    stats = {
        'isPrivateMedia': {
            'False': 0,  # 免费
            'True': 0    # 付费
        },
        'source_mode': {
            'PUBLIC': 0,  # 免费
            'PRIVATE': 0  # 付费
        },
        'payType': {
            'FREE': 0,         # 免费
            'PAY_EPISODE': 0   # 付费
        },
        'total_episodes': 0,
        'paid_episodes': {
            'isPrivateMedia': 0,
            'source_mode': 0,
            'payType': 0
        },
        'free_episodes': 0
    }
    
    # 如果episodes是字典，转换为列表
    if isinstance(episodes, dict):
        episodes = episodes.values()
    
    for episode in episodes:
        stats['total_episodes'] += 1
        
        # 记录每个字段的付费状态
        is_paid = {
            'isPrivateMedia': False,
            'source_mode': False,
            'payType': False
        }
        
        # 检查isPrivateMedia字段
        is_private = episode.get('isPrivateMedia', False)
        if is_private:
            stats['isPrivateMedia']['True'] += 1
            is_paid['isPrivateMedia'] = True
            stats['paid_episodes']['isPrivateMedia'] += 1
        else:
            stats['isPrivateMedia']['False'] += 1
        
        # 检查media.source.mode字段
        media = episode.get('media', {})
        if isinstance(media, dict):
            media_source = media.get('source', {})
            if isinstance(media_source, dict):
                mode = media_source.get('mode', 'PUBLIC')
                if mode == 'PRIVATE':
                    stats['source_mode']['PRIVATE'] += 1
                    is_paid['source_mode'] = True
                    stats['paid_episodes']['source_mode'] += 1
                elif mode == 'PUBLIC':
                    stats['source_mode']['PUBLIC'] += 1
        
        # 检查payType字段
        pay_type = episode.get('payType', 'FREE')
        if pay_type == 'FREE':
            stats['payType']['FREE'] += 1
        elif pay_type == 'PAY_EPISODE':
            stats['payType']['PAY_EPISODE'] += 1
            is_paid['payType'] = True
            stats['paid_episodes']['payType'] += 1
        
        # 如果所有字段都显示免费，则计入免费剧集
        if not any(is_paid.values()):
            stats['free_episodes'] += 1
    
    return stats

def analyze_all_podcasts(client):
    """分析所有播客的付费情况"""
    results = {}
    
    # 获取所有播客
    podcasts = client.get_podcast()
    
    for podcast in podcasts:
        pid = podcast.get('pid')
        if not pid:
            continue
            
        print(f"\n正在分析播客：{podcast.get('title', 'Unknown')}")
        
        # 获取播客的剧集列表
        episodes = client.get_episodes(pid)
        if not episodes:
            print(f"未获取到播客 {pid} 的剧集列表")
            continue
            
        # 分析付费情况
        stats = analyze_payment_fields(episodes)
        
        results[pid] = {
            'title': podcast.get('title', 'Unknown'),
            'stats': stats
        }
    
    return results

def save_all_podcasts_analysis(results, output_file):
    """保存所有播客的分析结果"""
    with open(output_file, 'w', encoding='utf-8') as f:
        # 写入标题和时间
        f.write("# 小宇宙播客付费情况分析报告\n\n")
        f.write(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 写入总体统计
        total_episodes = sum(podcast_stats['stats']['total_episodes'] for podcast_stats in results.values())
        total_free = sum(podcast_stats['stats']['free_episodes'] for podcast_stats in results.values())
        
        # 计算每个字段标记的付费剧集总数
        total_paid = {
            'isPrivateMedia': sum(podcast_stats['stats']['paid_episodes']['isPrivateMedia'] for podcast_stats in results.values()),
            'source_mode': sum(podcast_stats['stats']['paid_episodes']['source_mode'] for podcast_stats in results.values()),
            'payType': sum(podcast_stats['stats']['paid_episodes']['payType'] for podcast_stats in results.values())
        }
        
        f.write("## 总体统计\n\n")
        f.write("| 指标 | 数值 |\n")
        f.write("|------|------|\n")
        f.write(f"| 播客总数 | {len(results)} |\n")
        f.write(f"| 剧集总数 | {total_episodes} |\n")
        f.write(f"| 免费剧集 | {total_free} |\n")
        f.write("\n### 各字段标记的付费剧集数\n\n")
        f.write("| 字段名称 | 付费剧集数 | 付费比例 |\n")
        f.write("|----------|------------|----------|\n")
        for field, count in total_paid.items():
            ratio = count / total_episodes * 100 if total_episodes > 0 else 0
            f.write(f"| {field} | {count} | {ratio:.1f}% |\n")
        f.write("\n")
        
        # 写入各播客详细统计
        f.write("## 各播客详细统计\n\n")
        f.write("| 播客名称 | 总剧集数 | 免费剧集 | isPrivateMedia付费 | source_mode付费 | payType付费 |\n")
        f.write("|----------|-----------|-----------|-------------------|----------------|--------------|\n")
        
        # 按照总剧集数排序
        sorted_results = sorted(results.items(), key=lambda x: x[1]['stats']['total_episodes'], reverse=True)
        
        for podcast_name, data in sorted_results:
            stats = data['stats']
            paid = stats['paid_episodes']
            f.write(f"| {data['title']} | {stats['total_episodes']} | {stats['free_episodes']} | ")
            f.write(f"{paid['isPrivateMedia']} | {paid['source_mode']} | {paid['payType']} |\n")
        
        f.write("\n## 付费字段值分布\n\n")
        for podcast_name, data in sorted_results:
            f.write(f"### {data['title']}\n\n")
            stats = data['stats']
            
            # 合并所有字段的分布到一个表格
            f.write("| 字段 | 值 | 数量 |\n")
            f.write("|------|-----|------|\n")
            
            for field, values in [
                ('isPrivateMedia', stats['isPrivateMedia']),
                ('source_mode', stats['source_mode']),
                ('payType', stats['payType'])
            ]:
                for value, count in values.items():
                    f.write(f"| {field} | {value} | {count} |\n")
            
            f.write("\n---\n\n")

def main():
    """主函数"""
    # 初始化客户端
    client = PodcastClient()
    
    try:
        # 分析单个播客
        pid = "65257ff6e8ce9deaf70a65e9"
        print("正在获取播客信息...")
        podcasts = client.get_podcast()
        target_podcast = None
        for podcast in podcasts:
            if podcast.get('pid') == pid:
                target_podcast = podcast
                break
                
        if not target_podcast:
            print("未找到目标播客")
            return
            
        print(f"正在获取播客 {target_podcast.get('title')} 的剧集列表...")
        episodes = client.get_episodes(pid)
        if not episodes:
            print("未获取到剧集列表")
            return
            
        data = {
            'podcast': target_podcast,
            'episodes': episodes
        }
        
        # 保存单个播客分析
        output_dir = project_root / "docs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"podcast_{pid}_analysis.md"
        
        print(f"正在生成单播客分析报告...")
        save_to_markdown(data, output_file)
        
        # 保存原始数据
        raw_data_file = output_dir / f"podcast_{pid}_raw.json"
        with open(raw_data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        # 分析所有播客
        print("正在分析所有播客...")
        all_results = analyze_all_podcasts(client)
        all_podcasts_report = output_dir / "all_podcasts_analysis.md"
        save_all_podcasts_analysis(all_results, all_podcasts_report)
        print(f"所有播客分析报告已保存到：{all_podcasts_report}")
        
    except Exception as e:
        print(f"分析过程出错: {e}")
        raise

if __name__ == "__main__":
    main()
