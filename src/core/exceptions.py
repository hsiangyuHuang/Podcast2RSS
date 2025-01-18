"""自定义异常类"""

class PodcastError(Exception):
    """播客处理相关错误"""
    pass

class TranscriptionError(Exception):
    """音频转写相关错误"""
    pass

class RSSError(Exception):
    """RSS生成相关错误"""
    pass
