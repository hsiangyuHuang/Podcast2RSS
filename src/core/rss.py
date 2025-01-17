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

    def _generate_episode_link(self, eid: str) -> str:
        """生成播客链接"""
        return f"https://www.xiaoyuzhoufm.com/episode/{eid}"
    
    def _generate_podcast_link(self, pid: str) -> str:
        """生成播客主页链接"""
        return f"https://www.xiaoyuzhoufm.com/podcast/{pid}"
    
    def _generate_transcript_link(self, task_id: str) -> str:
        """生成转写任务链接"""
        return f"https://tongyi.aliyun.com/efficiency/doc/transcripts/{task_id}"

    def _parse_date(self, date_str: Union[str, int]) -> datetime:
        """解析日期字符串或时间戳为datetime对象"""
        if isinstance(date_str, int):
            return datetime.fromtimestamp(date_str)
            
        if not date_str:
            return datetime.now()
            
        date_str = str(date_str).strip()
        try:
            return pendulum.parse(date_str)
        except Exception as e:
            self.logger.warning(f"日期解析失败: {date_str}, 错误: {e}")
            return datetime.now()

    def _format_channel_xml(self, channel_info: dict) -> str:
        """生成RSS频道的XML头部"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
    <channel>
        <title>{escape(channel_info['title'])}</title>
        <link>{escape(channel_info['link'])}</link>
        <description>{escape(channel_info['description'])}</description>
        <lastBuildDate>{formatdate(usegmt=True)}</lastBuildDate>"""

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

    def _format_transcript(self, transcript_data: dict) -> str:
        """格式化转写文稿为HTML格式"""
        try:
            result = []
            
            # 1. 转写链接
            result.append('<h1>转写链接</h1>')
            result.append(f'<link>{self._generate_transcript_link(transcript_data["task_id"])}</link><br>')
            
            # 2. 摘要部分
            if transcript_data.get('summary'):
                result.append('<h1>节目摘要</h1>')
                result.append(f'<div class="summary">{escape(transcript_data["summary"])}</div><br>')
            
            # 3. 章节部分
            chapters = transcript_data.get('lab_info', {}).get('chapters', [])
            if chapters:
                result.append('<h1>章节速览</h1>')
                result.append('<div class="chapters">')
                for chapter in chapters:
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
            result.append('<h1>节目文稿</h1>')
            for item in transcript_data.get('transcription', []):
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
            return transcript_data.get('title', '')

    def _read_transcript(self, eid: str) -> Optional[Dict]:
        """读取转写文件"""
        try:
            transcript_file = self.transcripts_dir / f"{eid}.json"
            if not transcript_file.exists():
                self.logger.error(f"转写文件不存在: {transcript_file}")
                return None
                
            with transcript_file.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证必要字段
            if not data.get('title') or not data.get('transcription'):
                self.logger.error(f"转写文件缺少必要字段: {eid}")
                return None
                
            # 添加eid字段
            data['eid'] = eid
            
            # 处理实验室信息
            lab_info = data.get('lab_info', {})
            if lab_info:
                # 提取摘要和问答
                data['summary'] = lab_info.get('summary', '')
                data['qa_pairs'] = [
                    qa for qa in lab_info.get('qa_pairs', [])
                    if 'question' in qa and 'answer' in qa
                ]
            
            return data
            
        except Exception as e:
            self.logger.error(f"读取转写文件失败: {eid}, 错误: {e}")
            return None

    def _read_podcast_info(self, podcast_file: str) -> Dict[str, Any]:
        """读取播客信息"""
        try:
            # 1. 从episodes文件获取pid
            with open(podcast_file, 'r', encoding='utf-8') as f:
                episodes_data = json.load(f)
                
            if not isinstance(episodes_data, list) or not episodes_data:
                raise ValueError(f"播客文件 {podcast_file} 格式错误或为空")
            
            pid = episodes_data[0].get('pid')
            if not pid:
                raise ValueError(f"播客文件中的剧集缺少pid字段")
            
            # 2. 从subscribe_podcasts.json获取播客信息
            subscribe_file = Path(self.rss_materials_dir).parent / "podcasts" / "subscribe_podcasts.json"
            if not subscribe_file.exists():
                raise ValueError(f"订阅信息文件不存在: {subscribe_file}")
                
            with open(subscribe_file, 'r', encoding='utf-8') as f:
                podcasts = json.load(f)
            
            # 查找对应的播客信息
            podcast_info = next((p for p in podcasts if p.get('pid') == pid), None)
            if not podcast_info:
                raise ValueError(f"在订阅列表中未找到播客信息: {pid}")
            
            return {
                'pid': pid,
                'title': podcast_info.get('title', ''),
                'link': self._generate_podcast_link(pid),
                'description': podcast_info.get('description', '') or podcast_info.get('brief', ''),
                'episodes': episodes_data
            }
            
        except Exception as e:
            self.logger.error(f"读取播客信息失败: {podcast_file}, 错误: {e}")
            raise

    def generate_rss(self, podcast_info: dict, transcript_data_list: List[dict], output_file: str):
        """生成RSS文件"""
        try:
            # 生成RSS头部
            rss_content = self._format_channel_xml(podcast_info)

            # 处理每个单集
            for transcript_data in transcript_data_list:
                try:
                    # 生成HTML内容
                    html_content = self._format_transcript(transcript_data)
                    
                    # 创建RSS条目
                    item_info = {
                        'title': transcript_data['title'],
                        'link': self._generate_episode_link(transcript_data['eid']),
                        'description': transcript_data.get('summary', '') or transcript_data['title'],
                        'content_html': html_content,
                        'pub_date': formatdate(
                            self._parse_date(transcript_data.get('publish_date', '')).timestamp(),
                            usegmt=True
                        ),
                        'guid': transcript_data['eid']
                    }
                    rss_content += self._format_item_xml(item_info)
                    
                except Exception as e:
                    self.logger.error(f"处理单集失败: {transcript_data.get('eid')}, 错误: {e}")
                    continue

            # 添加结束标签
            rss_content += """
    </channel>
</rss>"""

            # 写入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(rss_content)
                
            self.logger.info(f"生成RSS文件成功: {output_file}")
            
        except Exception as e:
            self.logger.error(f"生成RSS文件失败: {output_file}, 错误: {e}")
            raise

    def process_single(self, podcast_file: str, output_file: str):
        """处理单个播客的所有剧集并生成RSS"""
        try:
            # 1. 读取播客信息和剧集列表
            podcast_info = self._read_podcast_info(podcast_file)
            
            # 2. 处理每个剧集的转写文件
            transcript_data_list = []
            for episode in podcast_info['episodes']:
                try:
                    eid = episode['eid']
                    transcript_data = self._read_transcript(eid)
                    if not transcript_data:
                        continue
                        
                    # 确保转写文件属于正确的播客
                    if transcript_data.get('pid') != podcast_info['pid']:
                        self.logger.warning(f"转写文件 {eid} 的pid与目标播客不匹配")
                        continue
                    
                    # 使用episode中的信息补充转写数据
                    transcript_data.update({
                        'title': episode['title'],
                        'description': episode.get('description', ''),
                        'publish_date': episode.get('pubDate', ''),
                        'lab_info': {
                            **transcript_data.get('lab_info', {}),
                            'description': episode.get('description', ''),
                            'shownotes': episode.get('shownotes', ''),
                            'duration': episode.get('duration', 0),
                        }
                    })
                    
                    transcript_data_list.append(transcript_data)
                    self.logger.info(f"处理剧集: {episode['title']}")
                    
                except Exception as e:
                    self.logger.error(f"处理转写文件失败: {eid}, 错误: {e}")
                    continue
            
            if not transcript_data_list:
                raise ValueError(f"没有找到播客 {podcast_info['pid']} 的有效转写文件")
                
            self.logger.info(f"找到 {len(transcript_data_list)} 个有效转写文件")
            
            # 3. 生成RSS
            self.generate_rss(podcast_info, transcript_data_list, output_file)
            
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
        podcast_file="/Users/hsiangyu/Inbox/Podcast2RSS/data/episodes/63b7dd49289d2739647d9587.json",
        output_file="/Users/hsiangyu/Inbox/Podcast2RSS/data/rss/63b7dd49289d2739647d9587_3.xml"
    )
