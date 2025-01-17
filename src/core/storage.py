import json
from pathlib import Path
from typing import Iterator, Dict

class Storage:
    """存储类，负责管理音频文件和转写结果的存储"""
    
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            # 默认使用项目根目录下的data目录
            base_dir = Path(__file__).parent.parent.parent / "data"
        else:
            base_dir = Path(base_dir)
            
        self.base_dir = base_dir
        self.episodes_dir = base_dir / "episodes"
        self.transcripts_dir = base_dir / "transcripts"
        
        # 确保目录存在
        self.episodes_dir.mkdir(parents=True, exist_ok=True)
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        
    def get_episodes_dir(self) -> Path:
        """获取episodes目录路径"""
        return self.episodes_dir
        
    def get_transcripts_dir(self) -> Path:
        """获取transcripts目录路径"""
        return self.transcripts_dir
        
    def is_transcribed(self, episode: Dict) -> bool:
        """检查是否已转写"""
        return (self.transcripts_dir / f"{episode['eid']}.json").exists()
        
    def save_transcript(self, eid: str, transcript_data: dict):
        """保存转写结果"""
        with (self.transcripts_dir / f"{eid}.json").open('w', encoding='utf-8') as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=2)
            
    def load_episodes(self, episodes_file: Path) -> Iterator[Dict]:
        """加载需要处理的剧集信息"""
        with episodes_file.open('r') as f:
            data = json.load(f)
            pid = data.get('pid')
            if not pid:
                raise ValueError("缺少pid字段")
                
            for episode in data.get('episodes', []):
                yield {
                    'pid': pid,
                    'eid': str(episode.get('eid', '')),
                    'title': episode.get('title', ''),
                    'audio_url': episode.get('enclosure', {}).get('url', ''),
                    'date': str(episode.get('pubDate', ''))
                }
