#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
from src.core.tongyi_client import TongyiClient
import time

# 创建通义千问客户端实例
client = TongyiClient()

TONGYI_COOKIE='_samesite_flag_=true; aliyun_site=CN; login_aliyunid_csrf=_csrf_tk_1286724295705333; currentRegionId=cn-shanghai; help_csrf=2Z3APxJQTH8zsHE3eY8TA%2F92DAOcnkJEezqM5VdvjPLm5GG%2Bmx4RaLdTiakklhitzzFBAUEIgcdFjv8%2BUQppOt79w3eXA9G0qYiSAZIuGByu9Kx6HZW7Kf7ci2x8qxW6Z5UfNKu1IhrvHN7qyGccPw%3D%3D; cr_token=5e23b882-a056-44b2-a604-881b363d7ec8; XSRF-TOKEN=8739ff99-0ee6-45fb-be03-17c7e7e01ab4; cookie2=103f1df916804d76e75d15b7bfff8869; t=0cb5df3b5a20ce483724ff3fb10344cf; _tb_token_=e335e87e310b7; sca=aaaa56a5; cna=UxjUH93nkiwCAd9K89JfzQEh; UM_distinctid=193c846ddc46e-018f90cbd4ee11-1e525636-1fa400-193c846ddc5566; CNZZDATA1281115298=1098181948-1734231908-https%253A%252F%252Fwww.google.com%252F%7C1734232436; login_aliyunid_ticket=N4KgG*eGC2vf0buxQEF1wZYgQ5_2k2YShf8FrrSf_ENpoU_BOTwChTBoNM1ZJeedfK9zxYnbN5hossqIZCr6t7SGxRigm2Cb4fGaCdBZWIzmgdHq6sXXZQg4KFWufyvpeV*0*Cm58slMT1tJw3_v$$FL0; login_aliyunid_csrf=_csrf_tk_1663436601709451; login_aliyunid_pk=1694143888672648; login_current_pk=1694143888672648; hssid=103f1df916804d76e75d15b7bfff8869; hsite=6; aliyun_country=CN; aliyun_site=CN; aliyun_lang=zh; login_aliyunid_pks=BG+ebu5LphJ/6GW6BZCtONI/LurdbBmkJvaa0itxeSWCvM=; login_aliyunid=hsia****; yunpk=1694143888672648; tongyi_sso_ticket=$oyWIfIvKGKqV1ey8jnOJzg_uQ53adQf3Nfitqub*kYRBfb*zzp_8Gn1gsBy1ogROHqapzX0Ccdj0; cnaui=1736920645334945233; aui=1736920645334945233; CNZZDATA1281397965=570966109-1734509812-https%253A%252F%252Fwww.google.com%252F%7C1736920672; atpsida=a76e6b9e4b72978c802b74a4_1736920729_8; isg=BPLyKUe2wYoWWf8SsWg9ceQWQz7Ug_Ydm_Gw47zLHqWQT5JJpBNGLfisP-tzP261; tfstk=gx_S0AchI9QqcTehmTV2CwyhqbTQQSzZpXOds63r9ULJ996fIb5Pwe8Bp6CpUBJF9eNCU_iyY6eldw9Ae7mUq68Cdt66ee8PzysBHtpPUg5FcX1Gh9t3ZpJpd95d4Sza7_fk-eBQQPzZsGs6Ka9KLeLkkGEFN74a7_fJ-eeaQP7rKi2XUpLp2HKvDKAneeKp9S9vOCmKe9BdMSOpNv3K2edvkBdWJpBpJS1vnBTp9UyK1BZWE_N7epbn-cNNNKgKJZO8KdCWhIAclQtWBnpjJ__XN39OaaVYUAOCXNtlB-oyeGsFCCWzk461wTs9XaHYhefVf9O1y5n6dTfAznQ8TcAD-gI9ywwsesK1ka8lcRgwBifdRnCuCcAVv17PATymJLS1MttNuxuwka65ynTO4RgwCMc-AjtiJI9aGSinx8b5IPCj-9nv2IAW0SNjeMxJiIsYGSinx3dDguFbGYIh.'

# 通义千问API相关配置
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": TONGYI_COOKIE  
}
def dir_list(dir_id="-1"):
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
        response = requests.post(url, headers=headers, json=payload)
        
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
                    print(f"找到转写记录: {record.get('recordTitle')} 状态: {record.get('recordStatus')}, 任务ID: {record.get('genRecordId')},记录ID：{record.get('recordId')}")
            pageNo += 1
        else:
            print(f"请求失败: {response.status_code}")
            break
    return result

def create_dir(name):
    """创建文件夹，返回文件夹ID"""
    payload = {"dirName": name, "parentIdStr": -1}
    url = "https://qianwen.biz.aliyun.com/assistant/api/record/dir/add?c=tongyi-web"
    r = requests.post(url, headers=headers, json=payload)
    if r.ok:
        return r.json().get("data").get("focusDir").get("idStr")

def get_dir():
    """获取已有文件夹信息"""
    url = (
        "https://qianwen.biz.aliyun.com/assistant/api/record/dir/list/get?c=tongyi-web"
    )
    response = requests.post(url, headers=headers)
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

def ensure_dir_exist(name):
    """确保文件夹存在"""
    dir_list = get_dir()
    for dir in dir_list:
        if dir.get("dirName") == name:
            return dir.get("idStr")
    return create_dir(name)

def prepare_audio_file(url):
    """准备音频文件信息
    Args:
        url: 音频URL
        dir_id: 文件夹ID，默认为根目录"-1"
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
        parse_response = requests.post(parse_url, headers=headers, json=parse_payload)
        
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
            query_response = requests.post(query_url, headers=headers, json=query_payload)
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
                        "showName": audio.get("showName"),
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

def start_transcription(files,dir_id):
    """批量提交转写任务"""
    payload = {
        "dirIdStr": dir_id,
        "files": files,
        "taskType": "net_source",
        "bizTerminal": "web"
    }
    url = "https://qianwen.biz.aliyun.com/assistant/api/record/blog/start?c=tongyi-web"
    response = requests.post(url, headers=headers, json=payload)
    return response.ok

def delete_task(record_id):
    """删除指定recordId的任务"""
    url = "https://qianwen.biz.aliyun.com/assistant/api/record/task/delete?c=tongyi-web"
    payload = {"recordIds": [record_id]}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        response_data = response.json()
        return response_data.get("success", False)
    return False


if __name__ == "__main__":
    result=ensure_dir_exist("再试试就再试试")
    print(result)
    # 开始实验
    # client = TongyiClient()
    # audio_url = "https://media.xyzcdn.net/ljKxn3MVatfroeSl04E1B4c2mtSc.m4a"
    # dir_id=1817382656225053696
    # files = prepare_audio_file(audio_url)
    # start_transcription(files,dir_id) 