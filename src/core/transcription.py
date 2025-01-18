import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from src.core.storage import Storage
from src.core.tongyi_client import TongyiClient
from src.core.exceptions import TranscriptionError

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EpisodeCollector:
    """剧集收集器，负责扫描和收集未转写的剧集"""
    def __init__(self, storage: Storage):
        self.storage = storage
    
    def collect_untranscribed(self, pid: str) -> List[Dict]:
        """收集指定播客的未转写剧集
        Args:
            pid: 播客ID
        Returns:
            List[Dict]: 未转写剧集列表
        """
        episodes = []
        episodes_dir = self.storage.get_episodes_dir()
        episode_file = episodes_dir / f"{pid}.json"
        
        if not episode_file.exists():
            logger.error(f"播客剧集文件不存在: {episode_file}")
            return episodes
            
        try:
            with episode_file.open() as f:
                data = json.load(f)
            
            for eid, episode_data in data.items():
                # 构建episode信息
                episode = {
                    'pid': pid,
                    'eid': eid,  # 直接使用key作为eid
                    'title': episode_data.get('title'),
                    'duration': episode_data.get('duration'),
                    'audio_url': episode_data.get('enclosure', {}).get('url')
                }
                
                # 检查必要字段
                if not all(episode.values()):
                    logger.warning(f"剧集数据不完整: {episode}")
                    continue
                
                # 检查时长限制
                duration = episode.get('duration')
                if duration and duration > 18000:  # 超过5小时的单集跳过
                    logger.info(f"剧集时长超过5小时，跳过转写: {episode['title']} ({eid}), 时长: {duration/3600:.1f}小时")
                    continue
                    
                # 检查是否已转写
                if not self.storage.is_transcribed(pid, eid):
                    episodes.append(episode)
                    logger.debug(f"找到未转写剧集: {episode['title']} ({eid})")
                    
        except Exception as e:
            logger.error(f"处理文件 {episode_file} 时出错: {e}")
            
        logger.info(f"播客 {pid} 共找到 {len(episodes)} 个未转写的剧集")
        return episodes

class TranscriptionProcessor:
    """转写处理器"""
    def __init__(self, tongyi_client: TongyiClient, storage: Storage = None, batch_size: int = 10):
        self.client = tongyi_client
        self.batch_size = batch_size
        self.storage = storage or Storage()
        
    def process_transcription(self, episodes, pid):
        """处理单一播客的剧集转写任务
        
        处理流程：
        1. 准备音频文件信息
        2. 创建或获取目录
        3. 提交转写任务
        4. 监控任务状态
        5. 获取并保存结果
        """
        if not episodes:
            logger.info("没有需要处理的剧集")
            return
            
        # 1. 准备音频文件信息
        tasks = []
        for episode in episodes:
            try:
                file_list = self.client.prepare_audio_file(episode['audio_url'])
                if not file_list:
                    logger.error(f"获取音频文件信息失败: {episode['title']}")
                    continue
                
                tasks.append({
                    "episode": episode,
                    "file_info": file_list[0]
                })
                logger.info(f"成功准备任务: {episode['title']}")
            except Exception as e:
                logger.error(f"处理任务时出错: {episode['title']}, 错误: {e}")
                continue
                
        if not tasks:
            logger.warning("没有有效的任务")
            return
            
        try:
            # 2. 创建或获取目录
            dir_id = self.client.ensure_dir_exist(pid)
            if not dir_id:
                logger.error(f"无法创建或获取目录: {pid}")
                return
                
            # 3. 提交转写任务
            file_infos = [t["file_info"] for t in tasks]
            if not self.client.start_transcription(file_infos, dir_id):
                logger.error("提交转写任务失败")
                return
                
            logger.info(f"成功提交 {len(file_infos)} 个转写任务")
            
            # 4. 监控任务状态
            MAX_WAIT_TIME = 3600  # 最大等待1小时
            start_time = time.time()
            
            while True:
                if time.time() - start_time > MAX_WAIT_TIME:
                    logger.error("等待任务完成超时")
                    break
                    
                all_tasks = self.client.dir_list(dir_id)
                completed = failed = running = 0
                
                # 更新每个任务的状态
                for task in tasks:
                    episode = task["episode"]
                    file_info = task["file_info"]
                    task_file_name = file_info.get("tag", {}).get("showName", "")
                    
                    # 查找对应的任务记录
                    matching_record = next(
                        (record for record in all_tasks if record["title"] == task_file_name),
                        None
                    )
                    
                    if matching_record:
                        status = matching_record["status"]
                        task["record"] = matching_record  # 保存任务记录以便后续使用
                        
                        if status == 30:  # 成功
                            completed += 1
                            episode['task_id'] = matching_record["taskId"]
                            episode['record_id'] = matching_record["recordId"]
                            logger.info(f"任务完成: {episode['title']}")
                        elif status in (40, 41):  # 失败
                            failed += 1
                            episode['task_id'] = None
                            episode['record_id'] = matching_record["recordId"]
                            logger.error(f"任务失败: {episode['title']}")
                        else:  # 正在转写
                            running += 1
                            episode['task_id'] = matching_record["taskId"]
                            episode['record_id'] = matching_record["recordId"]
                            # logger.info(f"任务进行中: {episode['title']}")
                    else:
                        running += 1
                        logger.info(f"任务可能正在初始化: {episode['title']}")
                
                # 输出进度
                total = len(tasks)
                progress = (completed + failed) / total * 100 if total > 0 else 0
                logger.info(f"批次进度 {progress:.1f}% - 完成: {completed}, 失败: {failed}, 运行中: {running}, 总数: {total}")
                
                if running == 0:
                    break
                    
                time.sleep(60)  # 等待60秒后继续检查
            logger.info(f"批次转写耗时: {time.time() - start_time:.1f}秒")
            # 5. 清理未完成和失败的任务
            # 只清理当前文件夹内的任务
            current_dir_tasks = self.client.dir_list(dir_id)
            tasks_to_clean = [
                task["record"] for task in tasks 
                if task.get("record") and task["record"]["status"] in (20, 40, 41)
                and any(dt["recordId"] == task["record"]["recordId"] for dt in current_dir_tasks)
            ]
            
            if tasks_to_clean:
                logger.info(f"开始清理当前文件夹中的 {len(tasks_to_clean)} 个无效任务...")
                for task in tasks_to_clean:
                    try:
                        if self.client.delete_task(task["recordId"]):
                            logger.info(f"成功删除任务: {task['title']}")
                        else:
                            logger.warning(f"删除任务失败: {task['title']}")
                    except Exception as e:
                        logger.error(f"删除任务出错: {task['title']}, 错误: {str(e)}")
            
            # 6. 获取并保存结果
            for task in tasks:
                try:
                    episode = task["episode"]
                    if not episode.get('task_id'):  # 跳过失败的任务
                        continue
                        
                    # 获取转写结果
                    trans_result = self.client.get_trans_result(episode['task_id'])
                    if not trans_result:
                        logger.error(f"获取转写结果失败: {episode['title']}")
                        continue
                        
                    # 获取实验室信息
                    lab_info = self.client.get_all_lab_info(episode['task_id'])
                    if not lab_info:
                        logger.error(f"获取标注信息失败: {episode['title']}")
                        continue
                    
                    # 保存结果
                    result = {
                        "pid": episode['pid'],
                        "eid": episode['eid'],
                        "title": episode['title'],
                        "task_id": episode['task_id'],
                        "transcription": trans_result,
                        "lab_info": lab_info
                    }
                    
                    self.storage.save_transcript(episode['pid'], episode['eid'], result)
                    logger.info(f"成功保存转写结果: {episode['title']}")
                    
                except Exception as e:
                    logger.error(f"保存结果时出错: {episode['title']}, 错误: {e}")
                    
        except Exception as e:
            logger.error(f"处理转写任务时出错: {str(e)}")
            return

    def process_in_batches(self, episodes: List[Dict], pid: str):
        """分批处理所有剧集"""
        if not episodes:
            logger.info("没有需要处理的剧集")
            return

        total_episodes = len(episodes)
        for i in range(0, total_episodes, self.batch_size):
            batch = episodes[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (total_episodes + self.batch_size - 1) // self.batch_size
            logger.info(f"开始处理第 {batch_num}/{total_batches} 批，包含 {len(batch)} 个剧集")
            self.process_transcription(batch, pid)
            logger.info(f"第 {batch_num}/{total_batches} 批处理完成")

        logger.info("所有批次处理完成")


def transcribe_podcast(pid):
    """处理播客的音频转写
    
    Args:
        pid: 播客ID
        
    Returns:
        bool: 如果有新的转写内容返回True，否则返回False
        
    Raises:
        TranscriptionError: 转写过程中出现错误
    """
    try:
        # 初始化必要的对象
        storage = Storage()
        tongyi_client = TongyiClient()
        
        # 收集任务
        collector = EpisodeCollector(storage)
        untranscribed_episodes = collector.collect_untranscribed(pid)
        logger.info(f"找到 {len(untranscribed_episodes)} 个未转写的剧集")
        if not untranscribed_episodes:
            logger.info("没有需要转写的剧集")
            return False
            
        # 开始处理转写任务
        processor = TranscriptionProcessor(tongyi_client=tongyi_client, storage=storage)
        processor.process_in_batches(untranscribed_episodes, pid)
        logger.info(f"播客 {pid} 的转写任务处理完成")
        return True
    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}")
        raise TranscriptionError(f"转写失败: {str(e)}")

if __name__ == "__main__":
    pid="658057ae3d1caa927acbaf60"
    transcribe_podcast(pid)