import json
from pathlib import Path
from typing import Iterator, Dict
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.config.paths import DATA_DIR

class Storage:
    """存储类，负责管理音频文件和转写结果的存储"""
    
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else DATA_DIR
        self.episodes_dir = self.base_dir / "episodes"
        self.transcripts_dir = self.base_dir / "transcripts"
        self.rss_dir = self.base_dir / "rss"
        self.podcasts_dir = self.base_dir / "podcasts"
        
        # 确保目录存在
        self._ensure_directories()
        
    def _ensure_directories(self):
        """确保所有存储目录存在"""
        directories = [
            self.episodes_dir,
            self.transcripts_dir,
            self.rss_dir,
            self.podcasts_dir
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
    def get_episodes_dir(self) -> Path:
        """获取episodes目录路径"""
        return self.episodes_dir
        
    def is_transcribed(self, pid: str, eid: str) -> bool:
        """检查是否已转写"""
        return (self.transcripts_dir / pid / f"{eid}.json").exists()
        
    def save_transcript(self, pid: str, eid: str, transcript_data: dict):
        """保存转写结果"""
        # 确保播客转写目录存在
        podcast_transcript_dir = self.transcripts_dir / pid
        podcast_transcript_dir.mkdir(parents=True, exist_ok=True)
        # 保存转写结果
        with (podcast_transcript_dir / f"{eid}.json").open('w', encoding='utf-8') as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=2)

    def save_rss(self, pid: str, rss_data: dict):
        # 确保播客转写目录存在
        podcast_rss_dir = self.rss_dir / pid
        podcast_rss_dir.mkdir(parents=True, exist_ok=True)
        # 保存转写结果
        with (podcast_rss_dir / f"{pid}.xml").open('w', encoding='utf-8') as f:
            f.write(rss_data)
            
    def save_rss(self, pid: str, rss_content: str):
        """保存 RSS 内容到文件"""
        rss_file = self.rss_dir / f"{pid}.xml"
        with rss_file.open('w', encoding='utf-8') as f:
            f.write(rss_content)
            
    def get_podcast_file(self, pid: str) -> Path:
        """获取播客信息文件路径"""
        return self.podcasts_dir / f"{pid}.json"
        
    def get_episodes_file(self, pid: str) -> Path:
        """获取播客剧集文件路径"""
        return self.episodes_dir / f"{pid}.json"
        
    def load_transcript(self, pid: str, eid: str) -> dict:
        """加载转写文件内容"""
        transcript_file = self.transcripts_dir / pid / f"{eid}.json"
        if not transcript_file.exists():
            raise FileNotFoundError(f"转写文件不存在: {transcript_file}")
            
        with transcript_file.open('r', encoding='utf-8') as f:
            return json.load(f)