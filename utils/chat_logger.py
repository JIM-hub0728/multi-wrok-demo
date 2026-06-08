"""
日志模块：记录所有私聊和群聊的聊天记录，方便调试和复盘。

支持按日期或会话维度保存到本地文件。
"""

import os
from datetime import datetime


class ChatLogger:
    """
    聊天记录管理器。

    Attributes:
        log_dir (str): 日志文件存放目录，默认 "logs"
    """

    def __init__(self, log_dir="logs"):
        """
        初始化日志器。

        Args:
            log_dir (str): 日志存放目录路径
        """
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def log_private(self, agent_name, user_msg, agent_reply):
        """
        记录一次私聊对话。

        Args:
            agent_name (str): 对话的 agent 名称
            user_msg (str): 用户发送的消息
            agent_reply (str): Agent 的回复
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = f"[{timestamp}] User: {user_msg}\n[{timestamp}] {agent_name}: {agent_reply}\n\n"
        filename = f"private_{agent_name}_{datetime.now().strftime('%Y%m%d')}.txt"
        self.save_to_file(filename, content)

    def log_group(self, transcript):
        """
        记录一次完整的群聊记录。

        Args:
            transcript (list[dict]): 群聊记录列表
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"group_{timestamp}.txt"
        lines = []
        for msg in transcript:
            speaker = msg.get("speaker", "Unknown")
            content = msg.get("content", "")
            lines.append(f"{speaker}: {content}")
        content = "\n".join(lines) + "\n\n"
        self.save_to_file(filename, content)

    def save_to_file(self, filename, content):
        """
        通用方法：将内容保存到日志目录下的指定文件。

        Args:
            filename (str): 文件名（不含目录）
            content (str): 要保存的文本内容
        """
        filepath = os.path.join(self.log_dir, filename)
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(content)
