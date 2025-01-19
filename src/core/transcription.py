import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

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
            
            # 将数据转换为列表并按发布时间排序
            episode_list = []
            for eid, episode_data in data.items():
                # 构建episode信息
                episode = {
                    'pid': pid,
                    'eid': eid,  # 直接使用key作为eid
                    'title': episode_data.get('title'),
                    'duration': episode_data.get('duration'),
                    'audio_url': episode_data.get('enclosure', {}).get('url'),
                    'published_at': episode_data.get('pubDate'),  # 添加发布时间
                    'payType': episode_data.get('payType')  # 添加付费类型
                }
                episode_list.append(episode)
            
            # 按发布时间降序排序并只取最新的50集
            episode_list.sort(key=lambda x: x.get('published_at', ''), reverse=True)
            episode_list = episode_list[:50]
            
            # 处理排序后的剧集
            for episode in episode_list:
                # 检查必要字段
                if not all([episode['pid'], episode['eid'], episode['title'], episode['duration'], episode['audio_url']]):
                    logger.warning(f"剧集数据不完整: {episode}")
                    continue
                
                # 检查是否付费单集
                if episode.get('payType') == 'PAY_EPISODE':
                    logger.info(f"付费剧集，跳过转写: {episode['title']} ({episode['eid']})")
                    continue

                # 检查时长限制
                duration = episode.get('duration')
                if not duration:
                    continue
                if duration < 180:  # 3分钟以下的单集跳过
                    logger.info(f"剧集时长低于3分钟，跳过转写: {episode['title']} ({episode['eid']}), 时长: {duration/60:.1f}分钟")
                    continue
                if duration > 18000:  # 超过5小时的单集跳过
                    logger.info(f"剧集时长超过5小时，跳过转写: {episode['title']} ({episode['eid']}), 时长: {duration/3600:.1f}小时")
                    continue
                    
                # 检查是否已转写
                if not self.storage.is_transcribed(pid, episode['eid']):
                    episodes.append(episode)
                    logger.debug(f"找到未转写剧集: {episode['title']} ({episode['eid']})")
                    
        except Exception as e:
            logger.error(f"处理文件 {episode_file} 时出错: {e}")
            
        logger.info(f"播客 {pid} 共找到 {len(episodes)} 个未转写的剧集")
        return episodes

class TranscriptionProcessor:
    """转写处理器"""
    def __init__(self, tongyi_client: TongyiClient, pid: str, storage: Storage = None, batch_size: int = 10):
        self.client = tongyi_client
        self.pid = pid
        self.batch_size = batch_size
        self.storage = storage or Storage()
        self.error_records = {}  # 记录每个剧集的错误原因
        self.dir_id = self.client.ensure_dir_exist(pid)  # 初始化时就获取目录ID
        logger.info(f"初始化转写处理器，播客ID: {pid}, 目录ID: {self.dir_id}")

    def process_transcription(self, episodes: List[dict]) -> None:
        """处理转写任务的主流程
        
        Args:
            episodes: 需要处理的剧集列表
        """
        if not episodes:
            logger.info("没有需要处理的剧集")
            return
            
        # 提交任务
        tasks = self._prepare_and_submit_tasks(episodes, self.dir_id)
        if not tasks:
            logger.error("没有成功提交的任务")
            return
            
        # 监控任务状态
        task_status = self._monitor_task_status(tasks, self.dir_id)
        
        # 清理失败的任务
        self._cleanup_failed_tasks(task_status, self.dir_id)
        
        # 保存转写结果
        self._save_transcription_results(task_status)

    def process_in_batches(self, episodes: List[Dict]) -> None:
        """分批处理所有剧集"""
        # 检查已有任务
        episodes_to_process, existing_tasks = self._check_existing_tasks(episodes)
        
        # 处理已有任务的结果
        if existing_tasks:
            logger.info(f"发现 {len(existing_tasks)} 个已有任务，开始获取结果...")
            existing_task_status = {}
            
            for eid, task_info in existing_tasks.items():
                existing_task_status[eid] = {
                    'status': 'completed',
                    'task_id': task_info['task']['taskId'],  # 直接使用保存的任务信息
                    'episode': task_info['episode']
                }
            
            if existing_task_status:
                self._save_transcription_results(existing_task_status)
        
        # 分批处理新任务
        total_episodes = len(episodes_to_process)
        if total_episodes > 0:
            logger.info(f"开始分批处理 {total_episodes} 个新任务...")
            for i in range(0, total_episodes, self.batch_size):
                batch = episodes_to_process[i:i + self.batch_size]
                logger.info(f"处理第 {i//self.batch_size + 1} 批，共 {len(batch)} 个任务")
                self.process_transcription(batch)

    def _prepare_and_submit_tasks(self, episodes: List[dict], dir_id: str) -> List[dict]:
        """准备音频文件并提交转写任务
        
        Args:
            episodes: 需要处理的剧集列表
            dir_id: 目录ID
            
        Returns:
            List[dict]: 提交成功的任务列表
        """
        tasks = []
        for episode in episodes:
            try:
                file_list = self.client.prepare_audio_file(
                    episode['eid'],
                    episode['audio_url']
                )
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
            return []
            
        # 提交所有任务
        file_infos = [t["file_info"] for t in tasks]
        if not self.client.start_transcription(file_infos, dir_id):
            logger.error("提交转写任务失败")
            return []
            
        logger.info(f"成功提交 {len(file_infos)} 个转写任务")
        return tasks

    def _monitor_task_status(self, tasks: List[dict], dir_id: str) -> Dict[str, dict]:
        """监控任务状态直到完成
        
        Args:
            tasks: 任务列表
            dir_id: 目录ID
            
        Returns:
            Dict[str, dict]: 任务状态字典，键为eid
        """
        MAX_WAIT_TIME = 3600  # 最大等待1小时
        start_time = time.time()
        task_status = {}
        
        while True:
            if time.time() - start_time > MAX_WAIT_TIME:
                logger.error("等待任务完成超时")
                break
                
            all_tasks = self.client.dir_list(dir_id)
            completed = failed = running = 0
            
            for task in tasks:
                episode = task["episode"]
                eid = episode["eid"]
                
                matching_record = next(
                    (record for record in all_tasks 
                     if record["title"] == eid),
                    None
                )
                
                if matching_record:
                    status = matching_record["status"]
                    if status == 30:  # 成功
                        completed += 1
                        task_status[eid] = {
                            'status': 'completed',
                            'task_id': matching_record["taskId"],  # 从目录中获取taskId
                            'record_id': matching_record["recordId"],
                            'episode': episode
                        }
                    elif status in (40, 41):  # 失败
                        failed += 1
                        task_status[eid] = {
                            'status': 'failed',
                            'record_id': matching_record["recordId"],
                            'episode': episode
                        }
                        self.error_records[eid] = f"转写失败(状态码: {status})"
                    else:
                        running += 1
                else:
                    running += 1
            
            # 输出进度
            total = len(tasks)
            progress = (completed + failed) / total * 100 if total > 0 else 0
            logger.info(f"批次进度 {progress:.1f}% - 完成: {completed}, 失败: {failed}, 运行中: {running}")
            
            if running == 0:
                break
                
            time.sleep(60)
            
        return task_status

    def _cleanup_failed_tasks(self, task_status: Dict[str, dict], dir_id: str) -> None:
        """清理失败的任务
        
        Args:
            task_status: 任务状态字典
            dir_id: 目录ID
        """
        current_dir_tasks = self.client.dir_list(dir_id)
        failed_tasks = [
            task for task in task_status.values()
            if task['status'] == 'failed'
            and any(dt['recordId'] == task['record_id'] 
                   for dt in current_dir_tasks)
        ]
        
        if not failed_tasks:
            return
            
        logger.info(f"开始清理 {len(failed_tasks)} 个失败任务...")
        for task in failed_tasks:
            try:
                if self.client.delete_task(task['record_id']):
                    logger.info(f"成功删除任务: {task['episode']['title']}")
                else:
                    logger.warning(f"删除任务失败: {task['episode']['title']}")
            except Exception as e:
                logger.error(f"删除任务出错: {task['episode']['title']}, 错误: {str(e)}")

    def _save_transcription_results(self, task_status: Dict[str, dict]) -> None:
        """保存转写结果
        
        Args:
            task_status: 任务状态字典
        """
        for eid, task in task_status.items():
            if task['status'] != 'completed':
                continue
                
            try:
                # 获取转写结果
                trans_result = self.client.get_trans_result(task['task_id'])
                if not trans_result:
                    logger.error(f"获取转写结果失败: {task['episode']['title']}")
                    continue
                    
                # 获取实验室信息
                lab_info = self.client.get_all_lab_info(task['task_id'])
                if not lab_info:
                    logger.error(f"获取标注信息失败: {task['episode']['title']}")
                    continue
                
                # 保存结果
                result = {
                    "pid": task['episode']['pid'],
                    "eid": eid,
                    "title": task['episode']['title'],
                    "task_id": task['task_id'],
                    "transcription": trans_result,
                    "lab_info": lab_info
                }
                
                self.storage.save_transcript(
                    task['episode']['pid'], 
                    eid, 
                    result
                )
                logger.info(f"成功保存转写结果: {task['episode']['title']}")
                
            except Exception as e:
                logger.error(f"保存结果时出错: {task['episode']['title']}, 错误: {e}")
                self.error_records[eid] = f"保存结果失败: {str(e)}"

    def _check_existing_tasks(self, episodes: List[dict]) -> Tuple[List[dict], Dict[str, dict]]:
        """检查已有任务并返回需要处理的剧集和已存在的任务
        Args:
            episodes: 需要处理的剧集列表
            
        Returns:
            Tuple[List[dict], Dict[str, dict]]: 
                - 需要处理的剧集列表
                - 已存在任务的字典，键为eid，值包含episode和task信息
        """
        existing_tasks = {}
        episodes_to_process = []
        
        # 获取目录中的所有任务
        all_tasks = self.client.dir_list(self.dir_id)
        
        for episode in episodes:
            eid = episode['eid']
            # 在目录中查找对应的任务
            task = next((t for t in all_tasks if t['title'] == eid), None)
            if task:
                logger.info(f"剧集已有转写文件，跳过: {episode['title']}")
                existing_tasks[eid] = {
                    'episode': episode,
                    'task': task  # 保存完整的任务信息
                }
            else:
                episodes_to_process.append(episode)
                
        return episodes_to_process, existing_tasks

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
        need_transcribe = len(untranscribed_episodes)
        logger.info(f"找到 {need_transcribe} 个未转写的剧集")
        
        if not untranscribed_episodes:
            logger.info("没有需要转写的剧集")
            return False
            
        # 开始处理转写任务
        processor = TranscriptionProcessor(tongyi_client=tongyi_client, pid=pid, storage=storage)
        processor.process_in_batches(untranscribed_episodes)
        
        # 重新检查转写结果
        transcribed_count = 0
        failed_episodes = []
        for episode in untranscribed_episodes:
            if storage.is_transcribed(pid, episode['eid']):
                transcribed_count += 1
            else:
                error_msg = processor.error_records.get(episode['eid'], "未知原因")
                failed_episodes.append((episode['title'], episode['eid'], error_msg))
        
        # 输出统计
        logger.info(f"\n转写任务统计:")
        logger.info(f"需要转写: {need_transcribe}")
        logger.info(f"成功转写: {transcribed_count}")
        if failed_episodes:
            logger.info("未成功的剧集:")
            for title, eid, error in failed_episodes:
                logger.info(f"- {title} (eid: {eid}) - {error}")
                
        return True
    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}")
        raise TranscriptionError(f"转写失败: {str(e)}")

if __name__ == "__main__":
    pid="6022a180ef5fdaddc30bb101"
    transcribe_podcast(pid)