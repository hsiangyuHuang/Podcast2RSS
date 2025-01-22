import logging
import os
import time
import yaml
import json
from pathlib import Path
from core.podcast import PodcastClient
from core.transcription import transcribe_podcast
from core.rss import RSSProcessor
from core.storage import Storage
from core.exceptions import PodcastError, TranscriptionError, RSSError

def setup_logging():
    """配置日志处理器"""
    # 创建logs目录
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # 生成日志文件名，包含时间戳
    log_file = log_dir / f"podcast_rss_{time.strftime('%Y%m%d_%H%M%S')}.log"
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建并配置文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # 创建并配置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # 移除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    # 添加新的处理器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return log_file

def main():
    """主程序入口"""
    # 设置日志
    log_file = setup_logging()
    logger = logging.getLogger(__name__)
    logger.info(f"日志将保存到: {log_file}")
    
    start_time = time.time()
    # 初始化存储
    storage = Storage()
    
    try:
        # 1. 读取配置
        config_path = Path(__file__).parent.parent / "config" / "podcasts.yml"
        with open(config_path) as f:
            podcasts = yaml.safe_load(f)['podcasts']
            
        if not podcasts:
            logger.error("配置文件为空")
            return
            
        total_podcasts = len(podcasts)
        logger.info(f"共有 {total_podcasts} 个指定播客需要处理")
        
        # 2. 初始化处理器
        client = PodcastClient(storage)
        rss_processor = RSSProcessor()
        
        logger.info("开始更新播客与剧集数据...")
        pids = [p['pid'] for p in podcasts if 'pid' in p]
        client.update_all(pids)
        logger.info("完成更新播客与剧集数据...")

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
                # 3. 获取播客数据和转写
                logger.info(f"正在处理播客: {pid}")
                
                # 3.1 从文件中读取剧集信息
                episodes_file = storage.get_episodes_file(pid)
                with open(episodes_file, 'r', encoding='utf-8') as f:
                    episodes = json.load(f)
                logger.info(f"从文件读取到 {len(episodes)} 个剧集")
                
                # 3.2 处理音频转写
                logger.info(f"正在处理音频转写...")
                has_new_transcripts = False
                try:
                    has_new_transcripts = transcribe_podcast(pid)
                    if not has_new_transcripts:
                        logger.info("没有新的转写内容，跳过RSS生成")
                        continue
                except TranscriptionError as e:
                    logger.error(f"音频转写失败: {str(e)}")
                    continue

                # 3.3 生成RSS
                logger.info(f"检测到新的转写内容，正在生成RSS...")
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