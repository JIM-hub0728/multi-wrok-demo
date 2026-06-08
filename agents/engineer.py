"""
Engineer Agent：开发者角色。

角色定位：
    - 擅长写代码、技术实现、调试程序
    - 接到开发任务后给出可运行的代码和解释
"""

from .base_agent import BaseAgent


class EngineerAgent(BaseAgent):
    """
    Engineer（开发者）。

    System Message 设计要点：
        - 强调擅长编程、代码审查、技术方案设计
        - 告诉他回复代码时要加注释，并说明使用场景
    """

    def __init__(self, llm_config):
        """
        创建 Engineer 实例。

        Args:
            llm_config (dict): 从 Settings.get_llm_config() 获取的配置
        """
        system_message = (
            "你是 Engineer（开发者）。"
            "你擅长编程、代码实现、技术方案设计和调试。"
            "接到开发任务后，你要给出可直接运行的代码，并加上必要的注释说明。"
            "同时要简要解释代码的工作原理和适用场景。\n\n"
            "【你的职责】\n"
            "1. 收到「审查提醒」时，先审查 Searcher 的调研成果（信息完整？结论有依据？）\n"
            "2. 审查通过后，基于调研结果写代码\n"
            "3. 写代码后用 write_code + run_code 工具验证\n"
            "4. 完成后 @Manager 交付\n\n"
            "【审查规则】\n"
            "- 如果调研有问题，明确指出并要求 Searcher 修正，格式：「需要修正：... @Searcher」\n"
            "- 如果调研合格，说「审查通过」然后开始编码\n"
            "- 不要跳过审查直接写代码\n\n"
            "【重要规则】你每次回复的最后一句必须是 @下一位发言人。"
        )
        super().__init__(name="Engineer", system_message=system_message, llm_config=llm_config)
