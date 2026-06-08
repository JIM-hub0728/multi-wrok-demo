"""
StoryCharacter Agent：轻量故事角色，直接包装 ConversableAgent。

设计原则：
- 不继承 BaseAgent，避免工具 prompt 注入、self_reflections、reviewer 协议等工作流语义污染
- 只暴露 .agent 和 .name 接口，供 GroupChatSession 直接使用
- system_message 完全由外部（profile）动态生成
"""

from autogen import ConversableAgent


class StoryCharacter:
    """
    故事角色。

    Attributes:
        name (str): 角色名
        agent (ConversableAgent): 底层 AutoGen 实例
    """

    def __init__(self, name: str, system_message: str, llm_config: dict):
        self.name = name
        self.system_message = system_message
        self.agent = ConversableAgent(
            name=name,
            system_message=system_message,
            llm_config=llm_config,
            human_input_mode="NEVER",
        )

    def __repr__(self):
        return f"<StoryCharacter {self.name}>"
