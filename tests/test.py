import logging
from src.core.tongyi_client import TongyiClient

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    client = TongyiClient()
    all_tasks = client.dir_list()
    if all_tasks:
        logger.info(f"开始清理平台上的{len(all_tasks)}个任务...")
        for task in all_tasks:
            try:
                if client.delete_task(task["recordId"]):
                    logger.info(f"成功删除任务: {task['title']}")
                else:
                    logger.warning(f"删除任务时出错: {task['title']}")
            except Exception as e:
                logger.error(f"删除任务时发生异常: {task['title']}, 错误: {str(e)}")
        logger.info("平台任务清理完成")
    else:
        logger.info("平台上没有需要清理的任务")