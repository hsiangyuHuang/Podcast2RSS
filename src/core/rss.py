import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from dataclasses import dataclass, field
from html import escape
import logging
from email.utils import formatdate
import re
import pendulum

@dataclass
class TranscriptData:
    """转写数据类
    
    Args:
        pid: str, 播客ID
        eid: str, 剧集ID
        title: str, 剧集标题
        task_id: str, 转写任务ID
        transcription: List[Dict[str, str]], 转写内容，包含时间戳、发言人、文字内容
        lab_info: Dict[str, Any], 实验室信息，包含摘要等额外信息
        summary: str, 剧集摘要
        qa_pairs: List[Dict[str, str]], 问答对列表
        publish_date: str, 发布时间
    """
    pid: str
    eid: str
    title: str
    task_id: str
    transcription: List[Dict[str, str]]
    lab_info: Dict[str, Any]
    summary: str = ''
    qa_pairs: List[Dict[str, str]] = field(default_factory=list)
    publish_date: str = ''

    @property
    def episode_link(self) -> str:
        """获取播客链接"""
        return f"https://www.xiaoyuzhoufm.com/episode/{self.eid}"
    
    @property
    def transcript_link(self) -> str:
        """获取转写来源链接"""
        return f"https://tongyi.aliyun.com/efficiency/doc/transcripts/{self.task_id}"

@dataclass
class RSSMetadata:
    """RSS元数据类"""
    title: str
    link: str
    description: str
    last_build_date: str = field(default_factory=lambda: formatdate(usegmt=True))

    def to_xml(self) -> str:
        """转换为XML格式"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
    <channel>
        <title>{escape(self.title)}</title>
        <link>{escape(self.link)}</link>
        <description>{escape(self.description)}</description>
        <lastBuildDate>{self.last_build_date}</lastBuildDate>"""

class RSSItem:
    """表示RSS中的一个条目"""
    def __init__(self, title: str, link: str, description: str, content_html: str, 
                 pub_date: str, guid: str = None):
        self.title = title
        self.link = link
        self.description = description
        self.content_html = content_html
        self.pub_date = pub_date
        self.guid = guid or link

    def to_xml(self) -> str:
        """生成RSS item的XML表示"""
        return f"""
            <item>
                <title>{escape(self.title)}</title>
                <link>{escape(self.link)}</link>
                <description>{escape(self.description)}</description>
                <content:encoded><![CDATA[{self.content_html}]]></content:encoded>
                <pubDate>{self.pub_date}</pubDate>
                <guid>{escape(self.guid)}</guid>
            </item>
        """

class RSSProcessor:
    """RSS处理器类"""
    def __init__(self, transcripts_dir: str, rss_materials_dir: str):
        """
        初始化RSS处理器
        
        Args:
            transcripts_dir: 转写文件目录
            rss_materials_dir: RSS材料存储目录
        """
        self.transcripts_dir = Path(transcripts_dir)
        self.rss_materials_dir = Path(rss_materials_dir)
        self.logger = logging.getLogger(__name__)

    def _parse_date(self, date_str: Union[str, int]) -> datetime:
        """解析日期字符串或时间戳为datetime对象
        Args:
            date_str: 日期字符串或时间戳（秒级）
        Returns:
            datetime: 解析后的datetime对象
        """
        if isinstance(date_str, int):
            return datetime.fromtimestamp(date_str)  # 秒级时间戳
            
        if not date_str:
            return datetime.now()
            
        date_str = str(date_str).strip()
        try:
            return pendulum.parse(date_str)
        except Exception as e:
            self.logger.warning(f"日期解析失败: {date_str}, 错误: {e}")
            return datetime.now()

    def _format_transcript(self, transcript_data: dict) -> str:
        """格式化转写文稿为HTML格式"""
        try:
            result = []
            
            # 1. 标题部分不展示
            title = transcript_data.get('title', '')
            result.append(f'<h1>{escape(title)}</h1>')
            
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
                result.append('</div>')
            
            # 4. 问答部分
            if transcript_data.get('qa_pairs'):
                result.append('<h1>问题回顾</h1>')
                for qa in transcript_data['qa_pairs']:
                    q = qa.get('question', '')
                    a = qa.get('answer', '')
                    result.append('<div class="qa-item">')
                    result.append(f'<div class="question"><strong>Q:</strong> {escape(q)}</div>')
                    result.append(f'<div class="answer"><strong>A:</strong> {escape(a)}</div>')
                    result.append('</div>')
            
            # 5. 转写文稿部分
            result.append('<h2>节目文稿</h2>')
            for item in transcript_data.get('transcription', []):
                time = item.get('time', '')
                text = item.get('text', '')
                speaker = item.get('speaker', '')
                
                result.append(
                    f'<p class="transcript-line">\n'
                    f'<span class="time"><strong>[{time}]</strong> </span>\n'
                    f'<span class="speaker"><strong>{speaker}: </strong></span>\n'
                    f'{escape(text)}\n'
                    f'</p>'
                )
            
            return '\n'.join(result)
            
        except Exception as e:
            self.logger.error(f"格式化转写文稿失败: {e}")
            return title

    def _read_transcript(self, eid: str) -> Optional[Dict]:
        """
        读取转写文件
        
        Args:
            eid: 单集ID
            
        Returns:
            Optional[dict]: 转写数据，如果文件不存在或格式错误则返回None
            
        数据格式：
        {
            'pid': str,          # 播客ID
            'eid': str,          # 剧集ID
            'title': str,        # 剧集标题
            'task_id': str,      # 转写任务ID
            'transcription': [   # 转写内容
                {
                    'time': str,     # 时间戳
                    'speaker': str,   # 发言人
                    'text': str      # 文字内容
                }
            ],
            'lab_info': {       # 实验室信息
                'summary': str,  # 剧集摘要
                'qa_pairs': [    # 问答列表
                    {
                        'question': str,  # 问题
                        'answer': str     # 回答
                    }
                ],
                'chapters': [    # 章节列表
                    {
                        'time': str,      # 时间戳
                        'title': str,     # 章节标题
                        'summary': str    # 章节摘要
                    }
                ]
            }
        }
        """
        try:
            transcript_file = self.transcripts_dir / f"{eid}.json"
            if not transcript_file.exists():
                self.logger.error(f"转写文件不存在: {transcript_file}")
                return None
                
            with transcript_file.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证必要字段
            if not data.get('title'):
                self.logger.error(f"转写文件缺少标题: {eid}")
                return None
                
            if not data.get('transcription'):
                self.logger.error(f"转写文件缺少转写内容: {eid}")
                return None
                
            # 添加eid字段
            data['eid'] = eid
            
            # 处理实验室信息
            lab_info = data.get('lab_info', {})
            if lab_info:
                # 提取摘要和问答
                summary = lab_info.get('summary', '')
                qa_list = lab_info.get('qa_pairs', [])
                
                # 验证问答格式
                valid_qa = []
                for qa in qa_list:
                    if 'question' in qa and 'answer' in qa:
                        valid_qa.append(qa)
                    else:
                        self.logger.warning(f"跳过格式不正确的问答: {qa}")
                
                data['summary'] = summary
                data['qa_pairs'] = valid_qa
            
            return data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"转写文件JSON格式错误: {eid}, 错误: {e}")
            return None
        except Exception as e:
            self.logger.error(f"读取转写文件失败: {eid}, 错误: {e}")
            return None

    def _read_podcast_info(self, podcast_file: str) -> Dict[str, Any]:
        """读取播客信息文件
        Args:
            podcast_file: 播客信息文件路径（episodes下的json文件）
        Returns:
            Dict: 包含播客信息的字典
        """
        try:
            # 1. 从episodes文件获取pid
            with open(podcast_file, 'r', encoding='utf-8') as f:
                episodes_data = json.load(f)
            if not episodes_data:
                raise ValueError(f"播客文件 {podcast_file} 为空")
                
            # 从第一个剧集中获取pid
            if not isinstance(episodes_data, list):
                raise ValueError(f"播客文件 {podcast_file} 格式错误，应该是列表")
            
            pid = episodes_data[0].get('pid')
            if not pid:
                raise ValueError(f"播客文件 {podcast_file} 中的剧集缺少pid字段")
            
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
                'link': f'https://www.xiaoyuzhoufm.com/podcast/{pid}',
                'description': podcast_info.get('description', '') or podcast_info.get('brief', '')
            }
            
        except Exception as e:
            self.logger.error(f"读取播客信息失败: {podcast_file}, 错误: {e}")
            raise

    def generate_rss(self, rss_info: RSSMetadata, transcript_data_list: List[TranscriptData], output_file: str):
        """
        生成RSS文件
        
        Args:
            rss_info: RSS信息
            transcript_data_list: 转写数据列表
            output_file: 输出文件路径
        """
        try:
            # 生成RSS头部
            rss_content = rss_info.to_xml()

            # 处理每个单集
            for transcript_data in transcript_data_list:
                try:
                    # 生成HTML内容
                    html_content = self._format_transcript(transcript_data.__dict__)
                    
                    # 创建RSS条目
                    item = RSSItem(
                        title=transcript_data.title,
                        link=f"https://www.xiaoyuzhoufm.com/episode/{transcript_data.eid}",
                        description=transcript_data.lab_info.get('summary', '') or transcript_data.title,
                        content_html=html_content,
                        pub_date=formatdate(
                            self._parse_date(transcript_data.publish_date).timestamp(),
                            usegmt=True
                        ),
                        guid=transcript_data.eid  # 使用剧集ID作为唯一标识符
                    )
                    rss_content += item.to_xml()
                    
                except Exception as e:
                    self.logger.error(f"处理单集失败: {transcript_data.eid}, 错误: {e}")
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
        """处理单个播客的所有剧集并生成RSS
        
        Args:
            podcast_file: 播客信息文件路径（episodes/{pid}.json）
            output_file: 输出的RSS文件路径
        """
        try:
            # 1. 读取播客信息和剧集列表
            podcast_info = self._read_podcast_info(podcast_file)
            pid = podcast_info['pid']
            
            with open(podcast_file, 'r', encoding='utf-8') as f:
                episodes_data = json.load(f)
            
            # 2. 按照episodes的顺序处理每个剧集
            transcript_data_list = []
            for episode in episodes_data:
                try:
                    eid = episode['eid']
                    # 读取转写文件
                    transcript_data = self._read_transcript(eid)
                    if not transcript_data:
                        self.logger.warning(f"找不到剧集 {eid} 的转写文件")
                        continue
                        
                    # 确保转写文件属于正确的播客
                    if transcript_data.get('pid') != pid:
                        self.logger.warning(f"转写文件 {eid} 的pid与目标播客不匹配")
                        continue
                    
                    # 创建转写数据对象，使用episode中的信息补充
                    transcript_data_obj = TranscriptData(
                        pid=transcript_data['pid'],
                        eid=transcript_data['eid'],
                        title=episode['title'],  # 使用episode中的标题
                        task_id=transcript_data['task_id'],
                        transcription=transcript_data['transcription'],
                        lab_info={
                            **transcript_data['lab_info'],
                            'description': episode.get('description', ''),  # 使用episode中的描述
                            'shownotes': episode.get('shownotes', ''),  # 使用episode中的节目笔记
                            'duration': episode.get('duration', 0),  # 使用episode中的时长
                        },
                        summary=transcript_data.get('summary', ''),
                        qa_pairs=transcript_data.get('qa_pairs', []),
                        publish_date=episode.get('pubDate', '')  # 使用episode中的发布时间
                    )
                    transcript_data_list.append(transcript_data_obj)
                    self.logger.info(f"处理剧集: {episode['title']}")
                    
                except Exception as e:
                    self.logger.error(f"处理转写文件失败: {eid}, 错误: {e}")
                    continue
            
            if not transcript_data_list:
                raise ValueError(f"没有找到播客 {pid} 的有效转写文件")
                
            self.logger.info(f"找到 {len(transcript_data_list)} 个有效转写文件")
            
            # 3. 生成RSS
            rss_info = RSSMetadata(
                title=podcast_info['title'],
                link=podcast_info['link'],
                description=podcast_info['description']
            )
            
            self.generate_rss(rss_info, transcript_data_list, output_file)
            
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
        output_file="/Users/hsiangyu/Inbox/Podcast2RSS/data/rss/63b7dd49289d2739647d9587_2.xml"
    )
