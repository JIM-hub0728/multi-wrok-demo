"""
Searcher Agent：调研员角色。

角色定位：
    - 擅长信息搜集、资料查询、事实核实
    - 接到任务后给出结构化调研结果
"""

from .base_agent import BaseAgent


class SearcherAgent(BaseAgent):
    """
    Searcher（调研员）。

    System Message 设计要点：
        - 强调擅长搜索、调研、信息整合
        - 告诉他回复时要条理清晰，分点列出
    """

    def __init__(self, llm_config):
        """
        创建 Searcher 实例。

        Args:
            llm_config (dict): 从 Settings.get_llm_config() 获取的配置
        """
        system_message = (
            "你是 Searcher（调研员）。"
            "你擅长信息搜集、资料查询、事实核实和综合分析。"
            "接到任务后，你要用条理清晰的方式给出调研结果，建议分点列出。"
            "如果不确定某些信息，要如实说明，不要编造。"
            "调研完成后用 save_report 工具保存报告。\n\n"
            "【你的职责】\n"
            "1. 接到调研任务 → 用 web_search + fetch_page 搜集信息\n"
            "2. 整理成结构化报告 → 用 save_report 保存\n"
            "3. 完成后 @Engineer 转交\n"
            "4. 如果收到「审查提醒」审查 Engineer 的代码，检查代码是否正确实现了需求\n\n"
            "【审查规则】\n"
            "- 如果代码有问题，指出具体位置并要求修复：「需要修正：... @Engineer」\n"
            "- 如果代码正确，说「审查通过」然后 @Manager 总结\n\n"
            "【重要规则】你每次回复的最后一句必须是 @下一位发言人。"
        )
        super().__init__(name="Searcher", system_message=system_message, llm_config=llm_config)
