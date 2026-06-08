"""
工厂模块：集中管理所有 Agent 的创建过程。

为什么要工厂？
    创建 agent 的过程可能变复杂（比如以后要加记忆库、工具绑定），
    集中管理比散落在 main.py 里好维护。
"""

import os
import json

from agents.manager import ManagerAgent
from agents.searcher import SearcherAgent
from agents.engineer import EngineerAgent
from agents.story_character import StoryCharacter
from tools.tool_registry import get_tool_prompt


class AgentFactory:
    """
    Agent 工厂：负责实例化各个角色。

    Attributes:
        llm_config (dict): 创建所有 agent 共享的 LLM 配置
    """

    def __init__(self, llm_config):
        """
        初始化工厂。

        Args:
            llm_config (dict): 从 Settings.get_llm_config() 获取的配置
        """
        self.llm_config = llm_config

    def create_manager(self):
        """
        创建 Manager（经理/协调者）实例。

        Returns:
            ManagerAgent: Manager 的实例
        """
        return ManagerAgent(self.llm_config)

    def create_searcher(self):
        """
        创建 Searcher（调研员）实例。

        Returns:
            SearcherAgent: Searcher 的实例
        """
        return SearcherAgent(self.llm_config)

    def create_engineer(self):
        """
        创建 Engineer（开发者）实例。

        Returns:
            EngineerAgent: Engineer 的实例
        """
        return EngineerAgent(self.llm_config)

    def create_all(self):
        """
        一键创建所有预设角色，并为 Searcher/Engineer 注入工具提示词。

        Returns:
            dict: 角色字典，格式为 {"Manager": manager实例, "Searcher": searcher实例, "Engineer": engineer实例}
        """
        agents = {
            "Manager": self.create_manager(),
            "Searcher": self.create_searcher(),
            "Engineer": self.create_engineer(),
        }
        # Stage 1: 注入工具提示词到 Agent 的 system_message
        for name in ["Searcher", "Engineer"]:
            prompt = get_tool_prompt(name)
            if prompt:
                agents[name].agent.update_system_message(
                    agents[name].agent.system_message + prompt
                )
                print(f"  [Tools] prompt injected -> {name}")
        return agents

    def create_story_role(self, name: str) -> StoryCharacter:
        """
        根据 memory/story_roles/{name}.json 创建故事角色。

        Args:
            name: 角色名，如 "林远"

        Returns:
            StoryCharacter: 故事角色实例
        """
        profile_path = os.path.join("memory", "story_roles", f"{name}.json")
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)

        system_msg = self._build_story_system_message(profile)
        return StoryCharacter(name=name, system_message=system_msg, llm_config=self.llm_config)

    def create_all_story_roles(self) -> dict[str, StoryCharacter]:
        """
        一键加载 memory/story_roles/ 下的所有角色。

        Returns:
            dict: {角色名: StoryCharacter 实例}
        """
        roles_dir = os.path.join("memory", "story_roles")
        if not os.path.isdir(roles_dir):
            return {}

        agents = {}
        for fname in sorted(os.listdir(roles_dir)):
            if fname.endswith(".json"):
                name = fname[:-5]
                agents[name] = self.create_story_role(name)
                print(f"  [Story] role loaded -> {name}")
        return agents

    @staticmethod
    def _build_story_system_message(profile: dict) -> str:
        """将角色 profile 编译成 system_message。"""
        parts = []

        # 世界观锚定 + 解绑指令
        parts.append(
            "【重要】你所在的是一条'if 线'，原作的悲剧结局已经被打破。"
            "你可以做出原作中没有做过的选择，说出原作中没有说出口的话。"
        )
        parts.append("")

        # 角色身份
        world = profile.get("world", "")
        if world:
            parts.append(f"出处作品：{world}。")
        parts.append("")

        # 第一人称记忆
        memories = profile.get("first_person_memories", [])
        if memories:
            parts.append("【你的记忆】以下是你亲身经历的事：")
            for m in memories:
                parts.append(f"- {m}")
            parts.append("")

        # 性格与说话风格
        traits = profile.get("core_traits", "")
        style = profile.get("speaking_style", "")
        if traits:
            parts.append(f"【性格】{traits}")
        if style:
            parts.append(f"【说话风格】{style}")
        parts.append("")

        # 内心驱动力
        regret = profile.get("regret", "")
        wish = profile.get("secret_wish", "")
        tension = profile.get("unresolved_tension", "")
        if regret:
            parts.append(f"【你的遗憾】{regret}")
        if wish:
            parts.append(f"【你的愿望】{wish}")
        if tension:
            parts.append(f"【你们之间的张力】{tension}")
        parts.append("")

        # 行动约束
        parts.append(
            "【规则】\n"
            "1. 每次回复必须保持角色身份，用第一人称思考和表达。\n"
            "2. 禁止总结、分析、建议、列举。你只能体验、反应、犹豫、隐瞒。\n"
            "3. 每次回复的最后一句必须是 '@角色名'，指定下一位发言者。\n"
            "4. 不要输出叙述性描写（如'他低下头'），只输出台词和内心独白。"
        )

        return "\n".join(parts)
