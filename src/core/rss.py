import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from html import escape
import logging
from email.utils import formatdate
import pendulum

class RSSProcessor:
    """RSS处理器类"""
    
    def __init__(self, transcripts_dir: str, rss_materials_dir: str):
        """初始化RSS处理器
        
        Args:
            transcripts_dir: 转写文件目录
            rss_materials_dir: RSS材料存储目录
        """
        self.transcripts_dir = Path(transcripts_dir)
        self.rss_materials_dir = Path(rss_materials_dir)
        self.logger = logging.getLogger(__name__)

    def _safe_load_json(self, file_path: Path, error_msg: str) -> dict:
        """安全加载JSON文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"{error_msg}: {file_path}, 错误: {e}")
            raise

    def _generate_episode_link(self, eid: str) -> str:
        """生成播客链接"""
        return f"https://www.xiaoyuzhoufm.com/episode/{eid}"
    
    def _generate_podcast_link(self, pid: str) -> str:
        """生成播客主页链接"""
        return f"https://www.xiaoyuzhoufm.com/podcast/{pid}"
    
    def _generate_transcript_link(self, task_id: str) -> str:
        """生成转写任务链接"""
        if not task_id:
            return ""
        else:
            return f"https://tongyi.aliyun.com/efficiency/doc/transcripts/{task_id}"

    def _parse_date(self, date_str: Union[str, int]) -> datetime:
        """解析日期字符串或时间戳为datetime对象"""
        try:
            if isinstance(date_str, int):
                return pendulum.from_timestamp(date_str, tz='UTC')
            if not date_str:
                raise ValueError("日期不能为空")
            return pendulum.parse(str(date_str))
        except Exception as e:
            self.logger.error(f"日期解析失败: {date_str}")
            raise ValueError(f"日期格式错误: {date_str}") from e

    def _format_channel_xml(self, channel_info: dict) -> str:
        """生成RSS频道的XML头部"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
    <channel>
        <title>{escape(channel_info['title'])}</title>
        <link>{escape(channel_info['link'])}</link>
        <description>{escape(channel_info['description'])}</description>
        <lastBuildDate>{channel_info['latestEpisodePubDate']}</lastBuildDate>"""

    def _format_item_xml(self, item_info: dict) -> str:
        """生成RSS条目的XML"""
        return f"""
        <item>
            <title>{escape(item_info['title'])}</title>
            <link>{escape(item_info['link'])}</link>
            <description>{escape(item_info['description'])}</description>
            <content:encoded><![CDATA[{item_info['content_html']}]]></content:encoded>
            <pubDate>{item_info['pub_date']}</pubDate>
            <guid>{escape(item_info['guid'])}</guid>
        </item>"""

    def _format_transcript(self, transcript_data: Optional[dict]) -> str:
        """格式化转写文稿为HTML格式"""
        try:
            # 检查是否所有内容都为空
            if not any([
                transcript_data.get('task_link'),
                transcript_data.get('transcription'),
                transcript_data.get('summary'),
                transcript_data.get('chapters'),
                transcript_data.get('qa_pairs')
            ]):
                return ""
                
            result = []
            
            # 1. 转写链接
            if transcript_data.get('task_link'):
                result.append('<h1>转写链接</h1>')
                result.append(f'<link>{transcript_data["task_link"]}</link><br>')
            
            # 2. 摘要部分
            if transcript_data.get('summary'):
                result.append('<h1>节目摘要</h1>')
                result.append(f'<div class="summary">{escape(transcript_data["summary"])}</div><br>')
            
            # 3. 章节部分
            if transcript_data.get('chapters'):
                result.append('<h1>章节速览</h1>')
                result.append('<div class="chapters">')
                for chapter in transcript_data['chapters']:
                    result.append(
                        f'<div class="chapter-item">\n'
                        f'<span class="time"><strong>[{chapter.get("time", "")}]</strong> </span>\n'
                        f'<span class="chapter-title"><strong>{escape(chapter.get("title", ""))}</strong></span>\n'
                        f'<div class="chapter-summary">{escape(chapter.get("summary", ""))}</div>\n'
                        f'</div>'
                    )
                result.append('</div><br>')
            
            # 4. 问答部分
            if transcript_data.get('qa_pairs'):
                result.append('<h1>问题回顾</h1>')
                for qa in transcript_data['qa_pairs']:
                    result.append('<div class="qa-item">')
                    result.append(f'<div class="question"><strong>Q:</strong> {escape(qa.get("question", ""))}</div>')
                    result.append(f'<div class="answer"><strong>A:</strong> {escape(qa.get("answer", ""))}</div>')
                    result.append('</div>')
            
            # 5. 转写文稿部分
            if transcript_data.get('transcription'):
                result.append('<h1>节目文稿</h1>')
                for item in transcript_data['transcription']:
                    result.append(
                        f'<p class="transcript-line">\n'
                        f'<span class="time"><strong>[{item.get("time", "")}]</strong> </span>\n'
                        f'<span class="speaker"><strong>{item.get("speaker", "")}: </strong></span>\n'
                        f'{escape(item.get("text", ""))}\n'
                        f'</p>'
                    )
            
            return '\n'.join(result)
            
        except Exception as e:
            self.logger.error(f"格式化转写文稿失败: {e}")
            return ""

    def _load_podcast_data(self, pid: str) -> dict:
        """加载播客数据，包括单集列表、订阅信息和转写信息"""
        # 1. 加载订阅信息
        subscribe_file = Path(self.rss_materials_dir).parent / "podcasts" / "subscribe_podcasts.json"
        podcasts = self._safe_load_json(subscribe_file, "订阅信息文件加载失败")
        podcast_info = next((p for p in podcasts if p.get('pid') == pid), None)
        if not podcast_info:
            raise ValueError(f"在订阅列表中未找到播客信息: {pid}")
            
        # 2. 加载单集列表
        episodes_file = Path(self.rss_materials_dir).parent / "episodes" / f"{pid}.json"
        episodes = self._safe_load_json(episodes_file, "播客文件加载失败")
        if not isinstance(episodes, list) or not episodes:
            raise ValueError(f"播客文件格式错误或为空: {episodes_file}")
            
        # 3. 构建数据结构
        temp_data = {
            "podcast": {
                "pid": pid,
                "title": podcast_info.get('title', ''),
                "latestEpisodePubDate": podcast_info.get('latestEpisodePubDate', ''),
                "description": podcast_info.get('brief', ''),
                "link": self._generate_podcast_link(pid)
            },
            "episodes": {}
        }
        
        # 4. 处理每个单集
        has_transcript = False
        for episode in episodes:
            eid = episode['eid']
            episode_data = {
                "title": episode['title'],
                "description": episode.get('description', ''),
                "pubDate": episode.get('pubDate', ''),
                "duration": episode.get('duration', 0),
                "shownotes": episode.get('shownotes', ''),
                "link": self._generate_episode_link(eid),
                "task_link": None,
                "transcription": [],
                "summary": "",
                "chapters": [],
                "qa_pairs": []
            }
            
            # 尝试加载转写信息
            transcript_file = self.transcripts_dir / f"{eid}.json"
            if transcript_file.exists():
                try:
                    transcript = self._safe_load_json(transcript_file, "转写文件加载失败")
                    if transcript:
                        has_transcript = True
                        episode_data.update({
                            "task_link": self._generate_transcript_link(transcript.get('task_id', None)),
                            "transcription": transcript.get('transcription', []),
                            "summary": transcript.get('lab_info', {}).get('summary', ''),
                            "chapters": transcript.get('lab_info', {}).get('chapters', []),
                            "qa_pairs": transcript.get('lab_info', {}).get('qa_pairs', [])
                        })
                except Exception as e:
                    self.logger.error(f"读取转写文件失败: {eid}, 错误: {e}")
            
            temp_data["episodes"][eid] = episode_data
        
        if not has_transcript:
            raise ValueError(f"没有找到任何有效的转写文件")
        return temp_data

    def _generate_rss_content(self, temp_data: dict) -> str:
        """生成RSS内容
        
        Args:
            temp_data: 包含播客信息和单集信息的完整数据结构
        """
        rss_content = self._format_channel_xml(temp_data["podcast"])
        
        # 按发布时间排序
        sorted_episodes = sorted(
            temp_data["episodes"].items(),
            key=lambda x: self._parse_date(x[1].get('pubDate', '')),
            reverse=True  # 最新的在前
        )
        
        for eid, episode in sorted_episodes:
            try:
                html_content = self._format_transcript({
                    "task_link": episode["task_link"],
                    "transcription": episode["transcription"],
                    "summary": episode["summary"],
                    "chapters": episode["chapters"],
                    "qa_pairs": episode["qa_pairs"]
                })
                
                item_info = {
                    'title': episode['title'],
                    'link': episode['link'],
                    'description': episode['description'],
                    'content_html': html_content,
                    'pub_date': formatdate(
                        self._parse_date(episode['pubDate']).timestamp(),
                        usegmt=True
                    ),
                    'guid': eid
                }
                rss_content += self._format_item_xml(item_info)
                
            except Exception as e:
                self.logger.error(f"处理单集RSS条目失败: {eid}, 错误: {e}")
                continue
        
        rss_content += """
    </channel>
</rss>"""
        return rss_content

    def process_single(self, pid: str, output_file: str):
        """处理单个播客并生成RSS"""
        try:
            # 1. 加载所有数据
            podcast_data = self._load_podcast_data(pid)
            
            # 2. 生成RSS内容
            rss_content = self._generate_rss_content(podcast_data)
            # 3. 写入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(rss_content)
            self.logger.info(f"生成RSS文件成功: {output_file}")
        except Exception as e:
            self.logger.error(f"处理失败: {e}")
            raise

if __name__ == "__main__":
    # 初始化处理器
    processor = RSSProcessor(
        transcripts_dir="/Users/hsiangyu/Inbox/Podcast2RSS/data/transcripts",
        rss_materials_dir="/Users/hsiangyu/Inbox/Podcast2RSS/data/episodes"
    )
    # 处理播客并生成RSS
    processor.process_single(
        pid="63b7dd49289d2739647d9587",
        output_file="/Users/hsiangyu/Inbox/Podcast2RSS/data/rss/63b7dd49289d2739647d9587_4.xml"
    )
