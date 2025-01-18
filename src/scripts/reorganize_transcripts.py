#!/usr/bin/env python3
import json
import shutil
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def reorganize_transcripts():
    """重组转写文稿目录结构，将文件按照 pid/eid.json 的结构存储"""
    try:
        # 1. 设置路径
        base_dir = Path(__file__).parent.parent.parent
        old_transcripts_dir = base_dir / "data" / "transcripts"
        new_transcripts_dir = base_dir / "data" / "transcripts_new"
        
        # 2. 创建新目录
        new_transcripts_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. 遍历所有转写文件
        for file in old_transcripts_dir.glob("*.json"):
            try:
                # 读取文件内容
                with file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 获取 pid 和 eid
                eid = file.stem  # 文件名就是 eid
                pid = None
                
                # 从 episodes 目录查找对应的 pid
                episodes_dir = base_dir / "data" / "episodes"
                for episode_file in episodes_dir.glob("*.json"):
                    with episode_file.open('r', encoding='utf-8') as f:
                        episodes_data = json.load(f)
                        if eid in episodes_data:
                            pid = episodes_data[eid].get('pid')
                            break
                
                if not pid:
                    logger.warning(f"找不到文件 {file.name} 对应的 pid，跳过处理")
                    continue
                
                # 创建新的目录结构
                new_podcast_dir = new_transcripts_dir / pid
                new_podcast_dir.mkdir(parents=True, exist_ok=True)
                
                # 复制文件到新位置
                new_file = new_podcast_dir / file.name
                with new_file.open('w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"已处理文件: {file.name} -> {pid}/{file.name}")
                
            except Exception as e:
                logger.error(f"处理文件 {file} 时出错: {e}")
        
        # 4. 确认所有文件都已处理
        old_count = len(list(old_transcripts_dir.glob("*.json")))
        new_count = sum(len(list(d.glob("*.json"))) for d in new_transcripts_dir.iterdir() if d.is_dir())
        
        logger.info(f"处理完成！原始文件数: {old_count}, 新文件数: {new_count}")
        
        # 5. 如果确认无误，可以替换原目录
        if old_count == new_count:
            backup_dir = base_dir / "data" / "transcripts_backup"
            shutil.move(old_transcripts_dir, backup_dir)
            shutil.move(new_transcripts_dir, old_transcripts_dir)
            logger.info(f"目录替换完成！原目录已备份到: {backup_dir}")
        else:
            logger.warning("文件数量不匹配，请手动检查后再替换目录")
            
    except Exception as e:
        logger.error(f"重组过程中出错: {e}")
        raise

if __name__ == "__main__":
    reorganize_transcripts()
