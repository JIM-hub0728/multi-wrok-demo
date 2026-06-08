"""
私聊管理模块：处理用户与单个 Agent 的一对一对话。

设计原则：
    返回字符串而不是直接 print，这样以后接前端时可以直接复用，不用改逻辑。
"""

from autogen import UserProxyAgent
from tools.tool_registry import execute_all_tools
from core.context_compressor import compress_conversation


class PrivateChatManager:
    """
    私聊管理器：维护用户与各个 Agent 的独立会话。

    Attributes:
        agents (dict): 所有可聊天的 agent，格式 {name: agent_instance}
        user (UserProxyAgent): 代表用户的 AutoGen agent
    """

    def __init__(self, agents_dict, max_history=20, llm_config=None):
        """
        初始化私聊管理器。

        Args:
            agents_dict (dict): 从 AgentFactory.create_all() 拿到的角色字典
            max_history (int): 最多保留的对话轮数，默认 20
            llm_config (dict): LLM 配置，用于上下文摘要压缩
        """
        self.agents = agents_dict
        self.max_history = max_history
        self.llm_config = llm_config
        # 创建一个代表用户的 agent，不自动回复，只负责把用户消息转发给目标 agent
        self.user = UserProxyAgent(
            name="User",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=0,
            code_execution_config={"use_docker": False},
        )
        # 记录和每个 agent 的会话是否已建立
        # key=agent_name, value=bool
        self._active_chats = {}

    def chat_with(self, agent_name, user_message):
        """
        用户与指定 agent 进行一对一聊天。支持工具调用循环。

        Args:
            agent_name (str): 要聊天的 agent 名字，如 "Manager"
            user_message (str): 用户发送的消息内容

        Returns:
            dict: {"content": str, "files": list[dict]}
                content: Agent 的回复内容
                files: 工具调用过程中创建的文件列表

        Raises:
            KeyError: 如果 agent_name 不存在
        """
        if agent_name not in self.agents:
            raise KeyError(f"Agent '{agent_name}' 不存在")
        agent = self.agents[agent_name]

        agent.enter_private_mode()
        all_created_files = []
        try:
            if agent_name not in self._active_chats:
                result = self.user.initiate_chat(
                    agent.agent,
                    message=user_message,
                    max_turns=1,
                    silent=True,
                )
                self._active_chats[agent_name] = True
                self._trim_history(agent)
                reply = result.chat_history[-1]["content"]
            else:
                self.user.send(user_message, agent.agent, request_reply=True, silent=True)
                self._trim_history(agent)
                reply = agent.agent.last_message(self.user)["content"]

            # 工具调用循环：如果 Agent 回复里有 [TOOL:，执行工具并让 Agent 继续
            for _ in range(3):  # 最多 3 轮工具调用
                if "[TOOL:" not in reply:
                    break
                combined, created_files = execute_all_tools(reply)
                if combined is None:
                    break
                all_created_files.extend(created_files)
                short_result = combined[:3000] if len(combined) > 3000 else combined
                self.user.send(
                    f"【系统消息】你刚才调用的工具返回了以下结果。"
                    f"请把结果翻译/总结成用户能看懂的格式回复给用户，不要再重复调用同样的工具：\n\n{short_result}",
                    agent.agent,
                    request_reply=True,
                    silent=True,
                )
                self._trim_history(agent)
                msgs = agent.agent.chat_messages.get(self.user, [])
                reply = msgs[-1].get("content", "") if msgs else reply

            return {"content": reply, "files": all_created_files}
        finally:
            agent.exit_private_mode()

    def _trim_history(self, agent):
        """保留最近 max_history 轮对话，超出部分压缩为摘要而非丢弃。"""
        messages = self.user.chat_messages.get(agent.agent, [])
        limit = self.max_history * 2
        if len(messages) > limit:
            compressed = compress_conversation(
                messages, keep_recent=limit, llm_config=self.llm_config
            )
            self.user.chat_messages[agent.agent] = compressed

    def get_history(self, agent_name):
        """
        获取用户与某个 agent 的历史聊天记录。

        Args:
            agent_name (str): Agent 名字

        Returns:
            list[dict]: 聊天记录，格式 [{"speaker": "...", "content": "..."}, ...]
        """
        if agent_name not in self.agents:
            raise KeyError(f"Agent '{agent_name}' 不存在")
        return self.agents[agent_name].get_history()

    def list_agents(self):
        """
        列出所有可私聊的 agent 名字。

        Returns:
            list[str]: Agent 名称列表
        """
        return list(self.agents.keys())
