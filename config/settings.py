"""
配置模块：集中管理 API Key、模型参数等。
把配置和代码分离，以后换模型或换 Key 不用到处改。
"""
import os

class Settings:
    """
    应用全局配置类。

    TODO:
        1. 在 __init__ 中读取环境变量或直接填写你的 API Key
        2. 实现 get_llm_config()，返回 AutoGen 需要的 llm_config 字典格式
    """

    def __init__(self):
        # TODO: 填写你的 OpenAI API Key、模型名、base_url 等
        # 建议优先从环境变量读取：os.getenv("OPENAI_API_KEY")
        self.api_key = os.getenv("API_KEY", "sk-your-api-key-here")
        self.model = os.getenv("API_MODEL", "deepseek-v4-pro")
        self.base_url = os.getenv("API_BASE_URL")

    def get_llm_config(self):
        """
        返回 AutoGen 需要的 llm_config 字典。

        标准格式示例：
            {
                "config_list": [
                    {
                        "model": "gpt-4o-mini",
                        "api_key": "sk-...",
                        "base_url": "https://..."  # 可选
                    }
                ],
                "temperature": 0.7,
                "timeout": 120
            }
        Returns:
            dict: 符合 AutoGen 要求的配置字典
        """
        # TODO: 构造并返回 llm_config 字典
        if not self.api_key:
             raise ValueError("API_KEY 环境变量未设置，请先配置 API Key")
        
        config_list = [
            {
                "model": self.model,
                "api_key":self.api_key,
                "price": [0, 0],  # 告诉 AutoGen 跳过价格估算
            }
        ]
        if self.base_url:
            config_list[0]["base_url"] = self.base_url
        
        return {
            "config_list":config_list,
            "temperature":0.7,  #0~1，越高回答越有变化
            "timeout":120,   #请求超时时间
        }
