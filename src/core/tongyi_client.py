import json
import re
import time
import os
from pathlib import Path
from typing import List, Dict, Optional
from retrying import retry
import requests
from dotenv import load_dotenv
import traceback
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class TongyiClient:
    """通义千问API客户端，用于处理音频转写相关的API调用"""
    
    def __init__(self):
        cookie = os.getenv("TONGYI_COOKIE")
        if not cookie:
            raise ValueError("环境变量中未设置TONGYI_COOKIE")
            
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "content-type": "application/json",
            "origin": "https://tongyi.aliyun.com",
            "priority": "u=1, i",
            "referer": "https://tongyi.aliyun.com/efficiency/doc/transcripts/g2y8qeaoogbxnbeo?source=2",
            "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "x-b3-sampled": "1",
            "x-b3-spanid": "540e0d18e52cdf0d",
            "x-b3-traceid": "75a25320c048cde87ea3b710a65d196b",
            "x-tw-canary": "",
            "x-tw-from": "tongyi",
            "cookie": cookie
        }

    def create_dir(self, name):
        """创建文件夹，返回文件夹ID"""
        payload = {"dirName": name, "parentIdStr": -1}
        url = "https://qianwen.biz.aliyun.com/assistant/api/record/dir/add?c=tongyi-web"
        r = requests.post(url, headers=self.headers, json=payload)
        if r.ok:
            return r.json().get("data").get("focusDir").get("idStr")

    def get_dir(self):
        """获取已有文件夹信息"""
        url = (
            "https://qianwen.biz.aliyun.com/assistant/api/record/dir/list/get?c=tongyi-web"
        )
        response = requests.post(url, headers=self.headers)
        if response.ok:
            r = response.json()
            success = r.get("success")
            errorMsg = r.get("errorMsg")
            if success:
                return r.get("data")
            else:
                print(f"请求失败：{errorMsg}")
        else:
            print("请求失败：", response.status_code)

    def ensure_dir_exist(self, name):
        """输入文件夹名，确保文件夹存在，并返回文件夹ID"""
        dir_list = self.get_dir()
        for dir_item in dir_list:
            dir_info = dir_item.get('dir', {})
            if dir_info.get("dirName") == name:
                return dir_info.get("idStr")
        return self.create_dir(name)


    @retry(stop_max_attempt_number=3, wait_fixed=10000)
    def dir_list(self, dir_id="-1"):
        """获取文件夹内所有的转写任务和状态
        Args:
            dir_id: 文件夹ID，默认为根目录"-1"
        Returns:
            list: 转写任务列表，每个元素包含任务ID、记录ID、标题和状态
        """
        result = []
        pageNo = 1
        pageSize = 48
        
        while True:
            payload = {
                "dirIdStr": dir_id,
                "pageNo": pageNo,
                "pageSize": pageSize,
                "status": [20, 30, 40, 41],  #20 正在转 30是成功 40是失败
            }
            url = "https://qianwen.biz.aliyun.com/assistant/api/record/list?c=tongyi-web"
            response = requests.post(url, headers=self.headers, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                batch_records = data.get("data", {}).get("batchRecord", [])
                if not batch_records:
                    break
                for batch in batch_records:
                    records = batch.get("recordList", [])
                    for record in records:
                        result.append({
                            "taskId": record.get("genRecordId"),  # 任务ID，后续获取转写结果用
                            "recordId": record.get("recordId"),      # 记录ID，用于删除操作
                            "title": record.get("recordTitle"),   # 文件名也是任务名
                            "status": record.get("recordStatus")  # 任务状态20正在转 30成功 40失败
                        })
                        # print(f"找到转写记录: {record.get('recordTitle')} 状态: {record.get('recordStatus')}, 任务ID: {record.get('genRecordId')},记录ID：{record.get('recordId')}")
                pageNo += 1
            else:
                print(f"请求失败: {response.status_code}")
                break
        return result


    @retry(stop_max_attempt_number=5, wait_fixed=10000)
    def get_trans_result(self, taskId):
        """获取转写结果
        Args:
            taskId: 转写任务ID
        Returns:
            list: 转写结果列表，每个元素包含时间戳和文本内容
        """
        payload = {
            "action": "getTransResult",
            "version": "1.0",
            "transId": taskId,
        }
        url = "https://tw-efficiency.biz.aliyun.com/api/trans/getTransResult?c=tongyi-web"
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            if not response.ok:
                print(f"请求失败：{response.status_code}")
                raise Exception(f"HTTP请求失败: {response.status_code}")
            
            response_data = response.json()
            if not response_data.get("success"):
                print(f"API调用失败: {response_data.get('message', '未知错误')}")
                raise Exception(f"API调用失败: {response_data.get('message', '未知错误')}")
            
            # 获取用户信息
            user_dict = {}
            data = response_data.get("data", {})
            tag = data.get("tag", {})
            
            identify = tag.get("identify")
            if identify:
                user_info = json.loads(identify).get("user_info", {})
                for key, value in user_info.items():
                    user_dict[key] = value.get("name")
            
            # 解析转写结果
            result = data.get("result")
            if not result:
                raise Exception("未找到转写结果")
            
            # 解析段落
            results = []
            result_data = json.loads(result)
            paragraphs = result_data.get("pg", [])
            
            for paragraph in paragraphs:
                # 获取说话人信息
                uid = paragraph.get("ui")
                speaker = user_dict.get(uid, f"发言人{uid}")
                
                # 获取该段落的所有句子
                sentences = paragraph.get("sc", [])
                if not sentences:
                    continue
                
                # 获取时间戳和合并文本
                begin_time = sentences[0].get("bt")
                text = "".join(sentence.get("tc", "") for sentence in sentences)
                
                if text and begin_time is not None:
                    result_item = {
                        "time": self._format_time(begin_time),
                        "text": text.strip(),
                        "speaker": speaker
                    }
                    results.append(result_item)
            
            # 检查是否获取到有效结果
            if not results:
                raise Exception("未获取到有效的转写结果")
            
            return results
            
        except Exception as e:
            print(f"处理转写结果时出错：{str(e)}")
            raise  # 重新抛出异常以触发重试

    @retry(stop_max_attempt_number=5, wait_fixed=10000)
    def get_all_lab_info(self, taskId):
        """获取实验室信息（摘要、思维导图等）"""
        url = "https://tw-efficiency.biz.aliyun.com/api/lab/getAllLabInfo?c=tongyi-web"
        payload = {
            "action": "getAllLabInfo",
            "content": ["labInfo", "labSummaryInfo"],
            "transId": taskId,
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        if not response.ok:
            print(f"请求失败：{response.status_code}")
            return None
            
        try:
            result = {
                "summary": "",
                "qa_pairs": [],
                "chapters": [],
                "mindmap": None
            }
            
            data = response.json().get("data", {}).get("labCardsMap", {})
            lab_info = data.get("labInfo", []) + data.get("labSummaryInfo", [])
            
            for item in lab_info:
                name = item.get("basicInfo", {}).get("name")
                
                for content in item.get("contents", []):
                    for content_value in content.get("contentValues", []):
                        if name == "全文摘要":
                            result["summary"] = content_value.get("value", "")
                        elif name == "思维导图":
                            result["mindmap"] = content_value.get("json")
                        elif name == "议程":
                            chapter = {
                                "time": self._format_time(content_value.get("time")),
                                "title": content_value.get("value", ""),
                                "summary": content_value.get("summary", "")
                            }
                            result["chapters"].append(chapter)
                        elif name == "qa问答" and content_value.get("extensions"):
                            qa_pair = {
                                "question": content_value.get("title", ""),
                                "answer": content_value.get("value", ""),
                                "time": ""
                            }
                            
                            if sentence_info := content_value.get("extensions")[0].get("sentenceInfoOfAnswer"):
                                if begin_time := sentence_info[0].get("beginTime"):
                                    qa_pair["time"] = self._format_time(begin_time)
                            
                            result["qa_pairs"].append(qa_pair)
            
            # 检查是否获取到有效数据
            if not any([
                result["summary"],
                result["qa_pairs"],
                result["chapters"],
                result["mindmap"]
            ]):
                raise Exception("未获取到任何有效的实验室信息")
            
            return result
            
        except Exception as e:
            print(f"处理实验室信息时出错：{e}")
            raise  # 重新抛出异常以触发重试

    @retry(stop_max_attempt_number=10, wait_fixed=10000)
    def prepare_audio_file(self, eid,url: str) -> Optional[List[Dict]]:
        """准备音频文件信息
        Args:
            url: 音频URL
        Returns:
            Optional[List[Dict]]: 失败返回None。成功时返回列表，每个元素为：
            {
                "fileId": str,      # 文件ID
                "dirId": str,       # 文件夹ID
                "fileSize": int,    # 文件大小（字节）
                "tag": {
                    "fileType": "net_source",  # 文件类型
                    "showName": str,           # 显示名称
                    "lang": "cn",              # 语言
                    "roleSplitNum": int,       # 角色分割数
                    "translateSwitch": int,     # 翻译开关
                    "transTargetValue": int,    # 翻译目标值
                    "client": "web",           # 客户端类型
                    "originalTag": str         # 原始标签
                }
            }
        """
        try:
            # 1. 解析URL获取任务ID
            parse_payload = {
                "action": "parseNetSourceUrl",
                "version": "1.0",
                "url": url
            }
            parse_url = "https://tw-efficiency.biz.aliyun.com/api/trans/parseNetSourceUrl?c=tongyi-web"
            parse_response = requests.post(parse_url, headers=self.headers, json=parse_payload)
            
            if not parse_response.ok:
                print(f"解析URL请求失败：{parse_response.status_code}")
                return None
                
            parse_data = parse_response.json()
            if not parse_data.get("success"):
                print(f"解析URL失败：{parse_data.get('message', '未知错误')}")
                return None
                
            task_id = parse_data.get("data", {}).get("taskId")
            if not task_id:
                print("未获取到任务ID")
                return None
            
            # 2. 查询解析状态
            query_payload = {
                "action": "queryNetSourceParse",
                "version": "1.0",
                "taskId": task_id
            }
            query_url = "https://tw-efficiency.biz.aliyun.com/api/trans/queryNetSourceParse?c=tongyi-web"
            
            while True:
                query_response = requests.post(query_url, headers=self.headers, json=query_payload)
                if not query_response.ok:
                    print(f"查询状态请求失败：{query_response.status_code}")
                    return None
                    
                data = query_response.json().get("data")
                status = data.get("status")
                
                if status == 0:  # 成功
                    urls = data.get("urls", [])
                    if not urls:
                        print("解析结果为空")
                        return None
                    # 构造转写任务需要的文件信息
                    audio = urls[0]
                    return [{
                        "fileId": audio.get("fileId"),
                        "fileSize": audio.get("size", 0),
                        "tag": {
                            "fileType": "net_source",
                            "showName": eid,
                            "lang": "cn",
                            "roleSplitNum": 0,
                            "translateSwitch": 0,
                            "transTargetValue": 0,
                            "client": "web",
                            "originalTag": "",
                        }
                    }]
                elif status == -1:  # 处理中
                    print("解析处理中，等待重试...")
                    time.sleep(1)
                    continue
                else:  # 失败
                    print(f"解析失败，状态码: {status}")
                    return None
                    
        except Exception as e:
            print(f"准备音频文件时出错: {str(e)}")
            return None

    def start_transcription(self,files,dir_id="-1" ):
        """批量提交转写任务"""
        payload = {
            "dirIdStr": dir_id,
            "files": files,
            "taskType": "net_source",
            "bizTerminal": "web",
        }
        url = "https://qianwen.biz.aliyun.com/assistant/api/record/blog/start?c=tongyi-web"
        response = requests.post(url, headers=self.headers, json=payload)
        return response.ok

    @staticmethod
    def _format_time(milliseconds):
        """格式化时间（毫秒转时分秒）"""
        if milliseconds is None:
            return ""
        seconds = milliseconds // 1000
        minutes = seconds // 60
        hours = minutes // 60
        return f"{hours:02d}:{minutes%60:02d}:{seconds%60:02d}"

    def delete_task(self, record_id):
        """删除指定recordId的任务"""
        url = "https://qianwen.biz.aliyun.com/assistant/api/record/task/delete?c=tongyi-web"
        payload = {"recordIds": [record_id]}
        response = requests.post(url, headers=self.headers, json=payload)
        if response.status_code == 200:
            response_data = response.json()
            return response_data.get("success", False)
        return False

    # def is_transcribed_in_dir(self, dir_id: str, eid: str) -> bool:
    #     """检查指定播客目录下是否已有对应剧集的转写文件"""
    #     try:
    #         files = self.dir_list(dir_id)
            
    #         # 检查是否有以eid命名的文件
    #         for file in files:
    #             title = file.get('title', '')  # 使用title而不是showName
    #             if eid in title and file.get('status') == 30:  # 30表示转写成功
    #                 return True
                    
    #         return False
    #     except Exception as e:
    #         logger.error(f"检查转写状态时出错: {str(e)}")
    #         raise  # 重新抛出异常以便上层处理

if __name__ == "__main__":
    client = TongyiClient()
    files=client.dir_list(client.ensure_dir_exist('6022a180ef5fdaddc30bb101'))
    print(files)
