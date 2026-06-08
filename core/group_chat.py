"""
群聊管理模块：多 Agent 协作的核心，让用户能看到 Agent 之间的讨论过程。

核心设计：
    基于 AutoGen 的 GroupChat + GroupChatManager，
    但封装一层以便自定义发言规则（让 Alice 做主持人决定谁说话）。
"""

import threading
import queue

from autogen import GroupChat, GroupChatManager, UserProxyAgent


def custom_speaker_selection(last_speaker, groupchat):
    """
    自定义发言选择函数：解析最后一条消息中的 @AgentName，
    决定下一个发言的 Agent。

    Args:
        last_speaker: 上一个发言的 Agent
        groupchat: GroupChat 实例

    Returns:
        ConversableAgent or None: 指定的下一个 Agent，None 表示用默认策略
    """
    import re

    messages = groupchat.messages
    if not messages:
        return None

    # 取最后一条消息的内容
    last_msg = messages[-1]
    content = last_msg.get("content", "")

    # 解析 @AgentName（支持 @Ken: 或 @Ken 格式）
    match = re.search(r"@(\w+)", content)
    if not match:
        return None

    target_name = match.group(1)

    # 在群聊的所有 agent 中查找目标
    for agent in groupchat.agents:
        if agent.name == target_name:
            return agent

    return None


class GroupChatSession:
    """
    群聊会话：管理一次多 Agent 协作任务。

    Attributes:
        agents (dict): 参与群聊的所有 agent
        llm_config (dict): GroupChatManager 需要的 LLM 配置
        max_round (int): 最大对话轮数，防止无限循环
        transcript (list): 完整的群聊记录
        _observers (list): 订阅者回调函数列表
    """

    def __init__(self, agents_dict, llm_config, max_round=20, mode="work"):
        """
        初始化群聊会话。

        Args:
            agents_dict (dict): 所有参与群聊的 agent，包含 Alice、Ken、Yu 等
            llm_config (dict): LLM 配置，用于创建 GroupChatManager
            max_round (int): 单轮任务最多允许的对话轮数，默认 20
            mode (str): "work" 为工作协作模式（含工具拦截、reviewer、压缩），
                        "story" 为故事模式（纯净对话，无工具/reviewer/压缩干扰）
        """
        self.agents = agents_dict
        self.llm_config = llm_config
        self.max_round = max_round
        self.mode = mode
        self.transcript = []
        self._observers = []
        # 创建一个代表用户的 proxy，用于直接发起群聊
        self.user_proxy = UserProxyAgent(
            name="User",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=0,
            code_execution_config={"use_docker": False},
        )

    def start(self, task_description, selected_names=None):
        """
        启动一次群聊协作任务。

        流程：
            1. 根据 selected_names 筛选进群的 agent（None 表示全部）
            2. 创建 AutoGen 的 GroupChat
            3. 用 GroupChatManager 管理对话流程
            4. 由 Alice 发起讨论
            5. 每产生一条消息，调用 _notify_observers() 通知订阅者

        Args:
            task_description (str): 任务描述，例如 "帮我调研一下多 agent 框架的优缺点"
            selected_names (list[str], optional): 指定进群的 agent 名字列表，None 表示全部

        Returns:
            list[dict]: 完整的群聊记录
        """
        if selected_names is None:
            selected_agents = list(self.agents.values())
        else:
            selected_agents = []
            for name in selected_names:
                if name in self.agents:
                    selected_agents.append(self.agents[name])
                else:
                    print(f"[警告] Agent '{name}' 不存在，已跳过")

        if not selected_agents:
            raise ValueError("没有有效的 Agent 被选中，无法启动群聊")

        autogen_agents = [agent.agent for agent in selected_agents]
        groupchat = GroupChat(
            agents=autogen_agents,
            messages=[],
            max_round=self.max_round,
            speaker_selection_method=custom_speaker_selection,
        )
        manager = GroupChatManager(
            groupchat=groupchat,
            llm_config=self.llm_config,
        )
        # 由用户直接发起群聊，而不是通过某个 agent 传话
        try:
            self.user_proxy.initiate_chat(manager, message=task_description, silent=True)
        except Exception as e:
            return [{"speaker": "System", "content": f"群聊服务暂时异常，请稍后再试。详情: {str(e)}"}]

        self.transcript = []
        for msg in groupchat.messages:
            entry = {
                "speaker": msg.get("name", "Unknown"),
                "content": msg.get("content", ""),
            }
            self.transcript.append(entry)
            self._notify_observers(entry)
        return self.transcript

    def get_transcript(self):
        """
        获取当前群聊的完整聊天记录。

        Returns:
            list[dict]: 群聊记录，格式 [{"speaker": "Alice", "content": "..."}, ...]
        """
        return self.transcript

    def get_summary_transcript(self, recent_rounds=10):
        """
        获取摘要版群聊记录。早期讨论折叠成一行摘要，只保留最近轮数的完整内容。

        Args:
            recent_rounds (int): 保留完整内容的最近轮数，默认 10

        Returns:
            list[dict]: 摘要版群聊记录
        """
        full = self.get_transcript()
        if len(full) <= recent_rounds:
            return full

        early = full[:-recent_rounds]
        recent = full[-recent_rounds:]

        speakers = sorted(set(m.get("speaker", "Unknown") for m in early))
        summary = [{
            "speaker": "System",
            "content": f"【早期讨论摘要】共 {len(early)} 轮，参与者: {', '.join(speakers)}。详细内容已折叠。"
        }]

        return summary + recent

    def subscribe(self, callback):
        """
        订阅群聊消息（观察者模式）。

        每有一条新消息产生，就会调用 callback(message)。
        以后做实时展示时，前端可以"流式"看到他们在聊什么。

        Args:
            callback (callable): 回调函数，签名应为 fn(message_dict) -> None
        """
        self._observers.append(callback)

    def _notify_observers(self, message):
        """
        内部方法：通知所有订阅者有一条新消息。

        Args:
            message (dict): 消息字典，格式 {"speaker": "...", "content": "..."}
        """
        for callback in self._observers:
            callback(message)

    def start_streaming(self, task_description, selected_names=None):
        """
        流式启动群聊，每生成一条消息立刻 yield。

        原理：
            用 speaker_selection_method 钩子捕获消息——AutoGen 每生成一条
            新消息后就会调用这个钩子选择下一位发言人。我们在钩子里把最新消息
            推入 Queue，主线程立刻 yield 给前端，实现真正的实时流式。

            后台线程跑同步的 initiate_chat，主线程消费 Queue。

        Args:
            task_description (str): 任务描述
            selected_names (list[str], optional): 指定进群的 agent 名字列表

        Yields:
            dict: 单条消息 {"speaker": "...", "content": "..."}
        """
        if selected_names is None:
            selected_agents = list(self.agents.values())
        else:
            selected_agents = []
            for name in selected_names:
                if name in self.agents:
                    selected_agents.append(self.agents[name])
                else:
                    yield {"speaker": "System", "content": f"[警告] Agent '{name}' 不存在，已跳过"}

        if not selected_agents:
            return

        from core.reviewer import reset_review_counts
        reset_review_counts()

        autogen_agents = [a.agent for a in selected_agents]
        msg_queue = queue.Queue()
        file_queue = queue.Queue()  # 工具创建的文件信息队列
        yielded_idx = [0]  # 闭包不能直接赋值 nonlocal，用 list 包装

        def _capture_messages(last_speaker, groupchat):
            """每次选发言人时触发：把新消息送入队列 + 拦截工具调用 + 解析 @AgentName。"""
            import re

            # 1. 把新消息送入队列（实时流式）
            while yielded_idx[0] < len(groupchat.messages):
                msg = groupchat.messages[yielded_idx[0]]
                msg_queue.put({
                    "speaker": msg.get("name", "Unknown"),
                    "content": msg.get("content", ""),
                })
                yielded_idx[0] += 1

            # 2. 检测最后一条消息是否包含工具调用（支持多条同时调用）
            #    story 模式下跳过工具拦截，保持对话纯净
            if self.mode != "story" and groupchat.messages:
                last_msg = groupchat.messages[-1]
                content = last_msg.get("content", "")
                if "[TOOL:" in content:
                    from tools.tool_registry import execute_all_tools
                    combined, created_files = execute_all_tools(content)
                    # 将创建的文件信息送入队列
                    for f in created_files:
                        file_queue.put(f)
                    if combined is not None:
                        # 判断工具调用中是否有失败项
                        has_error = '"success": false' in combined.lower() or "error" in combined.lower()

                        if has_error:
                            instruction = (
                                "【系统消息】你刚才调用的工具执行失败。"
                                "请仔细阅读下方的错误信息，分析问题原因，修复后重新调用工具。"
                                "不要直接跳过或假装成功。"
                            )
                        else:
                            instruction = (
                                "【系统消息】你刚才调用的工具已成功执行。"
                                "请把结果翻译/总结后回复给用户，不要再重复调用同样的工具。"
                            )

                        tool_msg = {
                            "role": "user",
                            "name": "tool_result",
                            "content": f"{instruction}\n\n{combined}",
                        }
                        groupchat.messages.append(tool_msg)
                        # 让同一个 Agent 继续发言，处理工具结果
                        return last_speaker

            # 3. 上下文压缩：群聊消息超过阈值时压缩旧消息
            #    story 模式下跳过压缩，保留完整对话
            if self.mode != "story":
                compress_threshold = self.max_round * 2
                if len(groupchat.messages) > compress_threshold:
                    from core.context_compressor import compress_groupchat
                    compressed = compress_groupchat(
                        list(groupchat.messages),
                        keep_recent=10,
                        llm_config=self.llm_config,
                    )
                    groupchat.messages.clear()
                    groupchat.messages.extend(compressed)

            # 4. 解析 @AgentName 找下一位发言人
            if not groupchat.messages:
                return None
            last_msg = groupchat.messages[-1]
            content = last_msg.get("content", "")
            last_name = last_msg.get("name", "")
            match = re.search(r"@(\w+)", content)
            if not match:
                # story 模式下无 @ 时自动轮询另一角色，兜底保证对话不中断
                if self.mode == "story":
                    for agent in groupchat.agents:
                        if agent.name != last_name:
                            return agent
                return None
            target_name = match.group(1)
            # 找到目标 Agent
            target_agent = None
            for agent in groupchat.agents:
                if agent.name == target_name:
                    target_agent = agent
                    break
            if target_agent is None:
                return None

            # 5. 审查注入（Stage 4）：Agent 交接时先审查再继续
            #    story 模式下跳过审查，保持对话自然
            if self.mode != "story":
                from core.reviewer import should_inject_review, build_review_message
                if should_inject_review(content, last_name, target_name):
                    review_msg = build_review_message(last_name, target_name)
                    groupchat.messages.append(review_msg)
                    # 审查者就是被 @ 的人，先审查再干活
                    return target_agent

            return target_agent

        groupchat = GroupChat(
            agents=autogen_agents,
            messages=[],
            max_round=self.max_round,
            speaker_selection_method=_capture_messages,
        )
        manager = GroupChatManager(
            groupchat=groupchat,
            llm_config=self.llm_config,
        )

        def _run():
            try:
                self.user_proxy.initiate_chat(manager, message=task_description, silent=True)
                # 补捞遗漏消息（如最后一条没有被 speaker_selection 触发）
                while yielded_idx[0] < len(groupchat.messages):
                    msg = groupchat.messages[yielded_idx[0]]
                    msg_queue.put({
                        "speaker": msg.get("name", "Unknown"),
                        "content": msg.get("content", ""),
                    })
                    yielded_idx[0] += 1
            except Exception as e:
                msg_queue.put({"speaker": "System", "content": f"群聊异常: {str(e)}"})
            finally:
                msg_queue.put(None)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        while True:
            msg = msg_queue.get()
            if msg is None:
                break
            # 收集与该消息关联的文件（在消息产生后、yield前，从file_queue中取出）
            msg_files = []
            while not file_queue.empty():
                try:
                    msg_files.append(file_queue.get_nowait())
                except queue.Empty:
                    break
            if msg_files:
                msg["files"] = msg_files
            yield msg

        thread.join()
