"""
基础 Agent 模块：封装 AutoGen 的 ConversableAgent，为所有角色提供通用能力。

为什么要封装一层？
    AutoGen 的 ConversableAgent 功能很全，但我们需要在上面加自己的逻辑
    （比如记录日志、格式化输出、限制轮数）。直接继承或包装比到处调原生 API 干净。
"""

import json
import os

from autogen import ConversableAgent


class BaseAgent:
    """
    所有 Agent 的父类。

    Attributes:
        name (str): Agent 的名字，如 "Manager"
        agent (ConversableAgent): 底层 AutoGen 实例
    """

    MEMORY_DIR = "memory/history"
    PROFILE_DIR = "memory/agents"
    MAX_MEMORY_ROUNDS = 5
    MAX_CONTEXT_ROUNDS = 15

    def __init__(self, name, system_message, llm_config):
        """
        初始化 Agent。

        Args:
            name (str): Agent 名称，会在对话中作为身份标识
            system_message (str): 系统提示词，定义这个角色的行为和能力
            llm_config (dict): AutoGen 需要的 LLM 配置字典，从 Settings.get_llm_config() 获取
        """
        self.name = name
        self.system_message = system_message
        self.raw_system_message = system_message
        self.profile = self._load_profile()
        enriched_system_message = self._build_system_message(system_message)

        self.agent = ConversableAgent(
            name=name,
            system_message=enriched_system_message,
            llm_config=llm_config,
            human_input_mode="NEVER",
        )
        self._inject_memory()

    def chat(self, message, recipient=None):
        """
        发送一条消息。

        Args:
            message (str): 要发送的消息内容
            recipient (BaseAgent, optional): 接收方 Agent。如果是 None，可以理解为对外广播或回复用户

        Returns:
            str: 对方的回复内容
        """
        if recipient is not None:
            try:
                chat_result = self.agent.initiate_chat(
                    recipient.agent,
                    message=message,
                    max_turns=1,
                    silent=True,
                )
                self._trim_context()
                return chat_result.chat_history[-1]["content"]
            except Exception as e:
                return f"[系统提示] 对话服务暂时异常，请稍后再试。详情: {str(e)}"
        raise NotImplementedError("recipient 为 None 的情况后续在 PrivateChatManager 中实现")

    def _load_profile(self):
        """
        从本地文件加载 Agent 画像。如果文件不存在，返回空字典。
        """
        filepath = os.path.join(self.PROFILE_DIR, f"{self.name}_profile.json")
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _build_system_message(self, base_message):
        """
        将原始 system_message 与画像信息合并，构建注入画像后的完整 system_message。
        画像信息追加在末尾，作为上下文注入层（中等变化频率）。
        """
        if not self.profile:
            return base_message

        parts = [base_message]
        profile_sections = []

        if "communication_style" in self.profile:
            profile_sections.append(f"你的沟通风格: {self.profile['communication_style']}")
        if "collaboration_experience" in self.profile:
            exp = self.profile["collaboration_experience"]
            lines = [f"  - {k}: {v}" for k, v in exp.items()]
            profile_sections.append("你对其他 Agent 的了解:\n" + "\n".join(lines))
        if "self_reflections" in self.profile and self.profile["self_reflections"]:
            recent = self.profile["self_reflections"][-3:]
            lines = [f"  - [{r.get('date', '?')}] {r.get('improvement', r.get('summary', ''))}" for r in recent]
            profile_sections.append("你最近的自我反思:\n" + "\n".join(lines))

        if profile_sections:
            parts.append("\n【你的画像与经验】\n" + "\n".join(profile_sections))

        return "\n".join(parts)

    def enter_private_mode(self):
        """进入私聊模式：移除群聊特有的 @规则，避免私聊时乱@其他Agent。"""
        private_suffix = (
            "\n\n【当前模式：私聊】\n"
            "你现在正在与用户进行一对一私聊。\n"
            "- 直接回答用户的问题，不要@任何其他Agent\n"
            "- 不要使用 @Manager / @Searcher / @Engineer 等格式\n"
            "- 你的回复应该完整、独立，不需要转交给任何人\n"
            "- 如果用户要求你写代码，请使用 [TOOL: write_code(filename, code)] 格式调用工具保存文件"
        )
        private_msg = self._build_system_message(self.raw_system_message) + private_suffix
        self.agent.update_system_message(private_msg)

    def exit_private_mode(self):
        """退出私聊模式：恢复原始 system_message。"""
        self.agent.update_system_message(self._build_system_message(self.raw_system_message))

    def save_profile(self):
        """
        将当前画像保存到本地文件。
        """
        os.makedirs(self.PROFILE_DIR, exist_ok=True)
        filepath = os.path.join(self.PROFILE_DIR, f"{self.name}_profile.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.profile, f, ensure_ascii=False, indent=2)

    def _trim_context(self):
        """
        截断过长的上下文，每个对话对象独立保留最近 MAX_CONTEXT_ROUNDS 轮。
        _oai_messages 是 defaultdict(list)，key 是对话对象名。
        """
        max_msgs = self.MAX_CONTEXT_ROUNDS * 2
        for key in self.agent._oai_messages:
            msgs = self.agent._oai_messages[key]
            if len(msgs) > max_msgs:
                self.agent._oai_messages[key] = msgs[-max_msgs:]

    def _inject_memory(self):
        """
        从本地文件恢复历史对话记录，注入到 agent 的上下文中。
        只恢复最近 MAX_MEMORY_ROUNDS 轮，防止上下文过长。
        """
        filepath = os.path.join(self.MEMORY_DIR, f"{self.name}.json")
        if not os.path.exists(filepath):
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        if not history:
            return

        # 将历史消息注入 _oai_messages（defaultdict(list)，key 是对话对象名）
        # 还原到已有对话的 key 中；如果还没有任何会话，默认用 "User"
        existing_keys = [k for k in self.agent._oai_messages.keys() if self.agent._oai_messages[k]]
        target_key = existing_keys[0] if existing_keys else "User"

        for entry in history[-self.MAX_MEMORY_ROUNDS:]:
            speaker = entry.get("speaker", "User")
            content = entry.get("content", "")
            role = "assistant" if speaker == self.name else "user"
            msg = {"role": role, "content": content}
            if role == "user":
                msg["name"] = speaker
            self.agent._oai_messages[target_key].append(msg)
        self._trim_context()

    def save_history(self):
        """
        将当前对话历史保存到本地文件，实现会话级持久化。
        """
        os.makedirs(self.MEMORY_DIR, exist_ok=True)
        history = self.get_history()
        filepath = os.path.join(self.MEMORY_DIR, f"{self.name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def get_history(self):
        """
        返回这个 agent 参与过的所有聊天记录。

        Returns:
            list[dict]: 聊天记录列表，每条格式为 {"speaker": "...", "content": "..."}
        """
        all_messages = []
        for recipient, messages in self.agent.chat_messages.items():
            for msg in messages:
                all_messages.append({
                    "speaker": msg.get("name", self.name),
                    "content": msg.get("content", ""),
                })
        return all_messages
