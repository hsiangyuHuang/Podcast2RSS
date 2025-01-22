#!/usr/bin/env python3
import re
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import glob

def parse_rss_files(rss_dir):
    """从 RSS XML 文件中解析播客信息"""
    podcasts = []
    rss_files = glob.glob(os.path.join(rss_dir, '*.xml'))
    
    for rss_file in rss_files:
        try:
            tree = ET.parse(rss_file)
            root = tree.getroot()
            channel = root.find('channel')
            
            if channel is not None:
                title = channel.find('title').text
                link = channel.find('link').text
                
                # 构建 RSS URL
                pid = os.path.basename(rss_file).replace('.xml', '')
                rss_url = f'https://hsiangyuhuang.github.io/Podcast2RSS/{pid}.xml'
                
                podcasts.append({
                    'title': title,
                    'xmlUrl': rss_url,
                    'htmlUrl': link
                })
                print(f'已解析: {title}')
        except Exception as e:
            print(f'解析文件 {rss_file} 时出错: {str(e)}')
    
    return podcasts

def generate_opml(podcasts, output_path):
    """生成 OPML 文件"""
    # 创建根元素
    root = ET.Element('opml', version='1.0')
    
    # 添加 head 元素
    head = ET.SubElement(root, 'head')
    title = ET.SubElement(head, 'title')
    title.text = '小宇宙播客订阅列表'
    date_created = ET.SubElement(head, 'dateCreated')
    date_created.text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
    
    # 添加 body 元素
    body = ET.SubElement(root, 'body')
    
    # 创建一个播客分组
    outline = ET.SubElement(body, 'outline', text='小宇宙播客', title='小宇宙播客')
    
    # 添加每个播客
    for podcast in podcasts:
        ET.SubElement(outline, 'outline',
                     type='rss',
                     text=podcast['title'],
                     title=podcast['title'],
                     xmlUrl=podcast['xmlUrl'],
                     htmlUrl=podcast['htmlUrl'])
    
    # 格式化 XML
    xml_str = minidom.parseString(ET.tostring(root, encoding='unicode')).toprettyxml(indent='  ')
    
    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_str)

def main():
    rss_dir = 'data/rss'  # RSS 文件目录
    output_path = 'podcasts.opml'
    
    print('正在解析 RSS 文件...')
    podcasts = parse_rss_files(rss_dir)
    print(f'找到 {len(podcasts)} 个播客')
    
    print('正在生成 OPML 文件...')
    generate_opml(podcasts, output_path)
    print(f'OPML 文件已生成: {output_path}')

if __name__ == '__main__':
    main()
