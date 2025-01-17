from typing import List, Dict, Any, Optional
import json
import os
from pathlib import Path
import time
import logging
from src.core.tongyi_client import TongyiClient
from src.core.storage import Storage

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EpisodeCollector:
    """剧集收集器，负责扫描和收集未转写的剧集"""
    def __init__(self, storage: Storage):
        self.storage = storage
    
    def collect_untranscribed(self) -> List[Dict]:
        """收集所有未转写的剧集"""
        episodes = []
        episodes_dir = self.storage.get_episodes_dir()
        logger.info(f"开始扫描剧集目录: {episodes_dir}")
        
        # 扫描episodes目录下所有文件
        for file in episodes_dir.glob("*.json"):
            try:
                with file.open() as f:
                    data = json.load(f)
                    # 遍历所有episode条目
                    for eid, episode_data in data.items():
                        try:
                            # 从episode_data中提取所需字段
                            episode = {
                                'pid': episode_data.get('pid', ''),
                                'eid': episode_data.get('eid', ''),
                                'title': episode_data.get('title', ''),
                                'audio_url': episode_data.get('enclosure', {}).get('url', '')
                            }
                            # 检查是否已转写
                            if not self.storage.is_transcribed(episode):
                                episodes.append(episode)
                                logger.debug(f"找到未转写剧集: {episode['title']} ({episode['eid']})")
                        except Exception as ex:
                            logger.error(f"处理剧集数据时出错: {ex}")
                            continue
            except Exception as e:
                logger.error(f"读取文件 {file} 时出错: {e}")
                continue
        
        logger.info(f"共找到 {len(episodes)} 个未转写的剧集")
        return episodes

class TranscriptionProcessor:
    """转写处理器"""
    def __init__(self, tongyi_client: TongyiClient, storage: Storage = None, batch_size: int = 20):
        self.client = tongyi_client
        self.batch_size = batch_size
        self.storage = storage or Storage()
        
    def process_all(self, episodes: List[Dict]):
        """处理所有剧集"""
        if not episodes:
            logger.info("没有需要处理的剧集")
            return
            
        # 1. 构建任务列表
        tasks = []
        for episode in episodes:
            try:
                # 解析URL获取任务ID
                parse_result = self.client.parse_net_source_url(episode['audio_url'])
                if not parse_result:
                    logger.error(f"解析URL失败: {episode['audio_url']}")
                    continue
                    
                episode['task_id'] = parse_result["taskId"]
                
                # 获取任务内容
                file_list = self.client.query_net_source_parse(episode['task_id'])
                if not file_list:
                    logger.error(f"获取任务内容失败: {episode['audio_url']}")
                    episode['task_id'] = None
                    continue
                    
                tasks.append({
                    "episode": episode,
                    "task": file_list[0]
                })
                logger.info(f"成功准备任务: {episode['title']}")
                
            except Exception as e:
                logger.error(f"处理任务时出错: {episode['title']}, 错误: {e}")
                episode['task_id'] = None
                
        # 2. 过滤出准备好的任务
        valid_tasks = [t for t in tasks if t["episode"].get('task_id')]
        if not valid_tasks:
            logger.warning("没有有效的任务")
            return
            
        # 3. 提交转写任务
        task_contents = [t["task"] for t in valid_tasks]
        if not self.client.start_transcription(task_contents):
            logger.error("提交转写任务失败")
            return
            
        # 4. 等待任务完成
        MAX_WAIT_TIME = 3600  # 最大等待1小时
        start_time = time.time()
        while True:
            # 1. 检查是否超时
            if time.time() - start_time > MAX_WAIT_TIME:
                logger.error("等待任务完成超时")
                break
            # 2. 获取所有任务状态（临时表）
            all_tasks = self.client.dir_list()
            # 3. 更新任务状态
            completed = failed = running = 0
            found_tasks = set()  # 用于记录找到的任务
            
            # 通过文件名匹配更新任务状态
            for task in valid_tasks:
                episode = task["episode"]
                task_file_name = task["task"]["tag"]["showName"]
                # 在临时表中查找对应任务
                matching_record = next(
                    (record for record in all_tasks if record["title"] == task_file_name),
                    None
                )
                if matching_record:
                    found_tasks.add(task_file_name)
                    status = matching_record["status"]
                    if status == 30:  # 成功
                        completed += 1
                        episode['task_id'] = matching_record["taskId"]
                        episode['record_id'] = matching_record["recordId"]
                        logger.info(f"任务完成: {episode['title']}")
                    elif status in (40, 41):  # 失败
                        failed += 1
                        episode['task_id'] = None
                        episode['record_id'] = matching_record["recordId"]  # 保存记录ID用于后续清理
                        logger.error(f"任务失败: {episode['title']}")
                    elif status == 20:  # 正在转写
                        running += 1
                        episode['task_id'] = matching_record["taskId"]
                        episode['record_id'] = matching_record["recordId"]
                        logger.info(f"任务进行中: {episode['title']}")
                else:
                    # 任务未找到，可能正在初始化
                    running += 1
                    logger.info(f"任务可能正在初始化: {episode['title']}")
            
            # 4. 输出进度
            total_tasks = len(valid_tasks)
            progress = (completed + failed) / total_tasks * 100 if total_tasks > 0 else 0
            logger.info(f"批次进度 {progress:.1f}% - 完成: {completed}, 失败: {failed}, 运行中: {running}, 总数: {total_tasks}")
            
            # 5. 检查是否全部完成（没有正在运行的任务）
            if running == 0:
                break
                
            # 等待30秒后继续检查
            time.sleep(30)
            
        # 6. 清理失败的任务
        failed_tasks = [task for task in valid_tasks if task["episode"].get("task_id") is None and task["episode"].get("record_id")]
        if failed_tasks:
            logger.info(f"开始清理{len(failed_tasks)}个失败的任务...")
            for task in failed_tasks:
                record_id = task["episode"].get("record_id")
                try:
                    if self.client.delete_task(record_id):
                        logger.info(f"成功删除失败的任务: {task['episode']['title']}")
                    else:
                        logger.warning(f"删除失败任务时出错: {task['episode']['title']}")
                except Exception as e:
                    logger.error(f"删除任务时发生异常: {task['episode']['title']}, 错误: {str(e)}")
            
        # 7. 获取并保存结果
        for task in valid_tasks:
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
                
                # 构建完整结果
                result = {
                    "pid": episode['pid'],
                    "eid": episode['eid'],
                    "title": episode['title'],
                    "task_id": episode['task_id'],
                    "transcription": trans_result,
                    "lab_info": lab_info
                }
                
                # 保存到文件
                self.storage.save_transcript(episode['eid'], result)
                logger.info(f"成功保存转写结果: {episode['title']}")
                
            except Exception as e:
                logger.error(f"保存结果时出错: {episode['title']}, 错误: {e}")

    def process_in_batches(self, episodes: List[Dict]):
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
            self.process_all(batch)
            logger.info(f"第 {batch_num}/{total_batches} 批处理完成")

        logger.info("所有批次处理完成")

if __name__ == "__main__":
    try:
        # 1. 初始化组件
        storage = Storage()  # 使用默认的数据目录
        tongyi_client = TongyiClient()
        collector = EpisodeCollector(storage)
        
        # 2. 收集未转写的剧集
        untranscribed_episodes = collector.collect_untranscribed()
        logger.info(f"找到 {len(untranscribed_episodes)} 个未转写的剧集")
        
        if not untranscribed_episodes:
            logger.info("没有需要转写的剧集")
            exit(0)
            
        # 3. 初始化转写处理器
        processor = TranscriptionProcessor(
            tongyi_client=tongyi_client,
            storage=storage,
            batch_size=20  
        )
        
        # 4. 开始处理转写任务
        processor.process_in_batches(untranscribed_episodes)
        
        logger.info("所有转写任务处理完成")
        
    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}")
        raise