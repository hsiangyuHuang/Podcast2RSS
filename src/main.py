import logging
import os
import time
import yaml
from pathlib import Path
from core.podcast import PodcastClient
from core.transcription import transcribe_podcast
from core.rss import RSSProcessor
from core.exceptions import PodcastError, TranscriptionError, RSSError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """主程序入口"""
    start_time = time.time()
    # 1. 读取配置
    config_path = Path(__file__).parent.parent / "config" / "podcasts.yml"
    with open(config_path) as f:
        podcasts = yaml.safe_load(f)['podcasts']
        
    total_podcasts = len(podcasts)
    logger.info(f"共有 {total_podcasts} 个播客需要处理")
    
    try:
        # 2. 初始化处理器
        client = PodcastClient()
        rss_processor = RSSProcessor()
        
        logger.info("开始更新播客订阅数据...")
        pids = [p['pid'] for p in podcasts if 'pid' in p]
        client.update_all(pids)
        
        # 3. 处理每个播客
        for index, podcast in enumerate(podcasts, 1):
            pid = podcast.get('pid')
            name = podcast.get('name')
            if not pid or not name:
                logger.error(f"播客配置错误: {podcast}")
                continue
                
            logger.info(f"[{index}/{total_podcasts}] 开始处理播客：{name}")
            podcast_start_time = time.time()
            
            try:
                # 3.1 获取播客数据
                logger.info(f"正在获取播客数据...")
                episodes = client.get_episodes(pid)
                if episodes:
                    client.save_episodes(episodes, pid)
                    logger.info(f"获取到 {len(episodes)} 个剧集")
                
                # 3.2 处理音频转写
                logger.info(f"正在处理音频转写...")
                try:
                    transcribe_podcast(pid)
                except TranscriptionError as e:
                    logger.error(f"音频转写失败: {str(e)}")
                    
                # 3.3 生成RSS
                logger.info(f"正在生成RSS...")
                try:
                    rss_processor.generate_rss(pid)
                except RSSError as e:
                    logger.error(f"RSS生成失败: {str(e)}")
                
                podcast_time = time.time() - podcast_start_time
                logger.info(f"播客 {name} 处理完成，耗时：{podcast_time:.2f}秒")
                
            except Exception as e:
                logger.error(f"处理播客 {name} 时发生错误：{str(e)}")
                continue
        
        total_time = time.time() - start_time
        logger.info(f"所有播客处理完成，总耗时：{total_time:.2f}秒")
        
    except Exception as e:
        logger.error(f"程序执行出错：{str(e)}")
        raise

if __name__ == "__main__":
    main()