"""
上下文压缩器：当对话过长时，将旧消息压缩为摘要，保留关键信息。

Alice 方法论 Ch.5：记忆分层——最近消息完整保留，早期消息压缩成摘要。
"""
import json
import logging

logger = logging.getLogger(__name__)


def compress_conversation(messages: list, keep_recent: int = 6, llm_config: dict = None) -> list:
    """
    压缩消息列表：保留最近 N 条，其余压缩为一条系统摘要。

    Args:
        messages: AutoGen 消息列表 [{"role": "...", "content": "...", "name": "..."}, ...]
        keep_recent: 保留最近几条消息不压缩
        llm_config: LLM 配置（用于生成摘要）。如果为 None，返回原列表。

    Returns:
        list: 压缩后的消息列表 = [摘要消息] + 最近 keep_recent 条
    """
    if len(messages) <= keep_recent + 4:
        return messages  # 还短，不需要压缩

    old = messages[:-keep_recent]
    recent = messages[-keep_recent:]

    summary = _generate_summary(old, llm_config)
    if summary is None:
        # 摘要生成失败，回退到简单截断
        logger.warning("summary generation failed, falling back to truncation")
        return recent

    summary_msg = {
        "role": "user",
        "name": "compressor",
        "content": f"【上下文摘要】之前的对话要点：\n{summary}",
    }

    compressed = [summary_msg] + recent
    logger.info(
        "context compressed: %d messages → %d (summary: %d chars)",
        len(messages), len(compressed), len(summary),
    )
    return compressed


def compress_groupchat(messages: list, keep_recent: int = 8, llm_config: dict = None) -> list:
    """
    压缩群聊消息列表。保留初始任务消息 + 最近 N 条，其余压缩为摘要。

    Args:
        messages: 群聊消息列表 [{"role": "...", "name": "...", "content": "..."}, ...]
        keep_recent: 保留最近几条
        llm_config: LLM 配置

    Returns:
        list: 压缩后的消息列表
    """
    if len(messages) <= keep_recent + 6:
        return messages

    # 保留第一条（通常是任务描述或用户消息）
    first = [messages[0]]
    old = messages[1:-keep_recent]
    recent = messages[-keep_recent:]

    summary = _generate_summary(old, llm_config)
    if summary is None:
        return first + recent

    summary_msg = {
        "role": "user",
        "name": "compressor",
        "content": (
            f"【群聊上文摘要】以下为早期讨论的要点，已帮你记住：\n\n{summary}\n\n"
            f"现在请继续基于上述信息和最近的对话进行协作。"
        ),
    }

    compressed = first + [summary_msg] + recent
    logger.info(
        "groupchat compressed: %d messages → %d", len(messages), len(compressed)
    )
    return compressed


def _generate_summary(messages: list, llm_config: dict = None) -> str | None:
    """
    用 LLM 生成对话摘要。

    Args:
        messages: 要摘要的消息列表
        llm_config: LLM 配置

    Returns:
        str | None: 摘要文本，失败返回 None
    """
    if not llm_config:
        return _simple_summary(messages)

    try:
        from autogen import ConversableAgent

        summarizer = ConversableAgent(
            name="summarizer",
            system_message="你是一个对话摘要工具。把给定的对话压缩成 3-5 句话的摘要，保留关键话题、决策和待办事项。用中文输出。",
            llm_config=llm_config,
            human_input_mode="NEVER",
        )

        transcript = _format_for_summary(messages)
        response = summarizer.generate_reply(
            messages=[{"role": "user", "content": f"请把以下对话压缩为 3-5 句摘要：\n\n{transcript}"}]
        )
        if isinstance(response, dict):
            response = response.get("content", str(response))
        return response.strip() if response else None

    except Exception as e:
        logger.error("summary generation failed: %s", e)
        return _simple_summary(messages)


def _simple_summary(messages: list) -> str:
    """简易摘要：提取每条消息的前 80 字符拼接。不调用 LLM。"""
    snippets = []
    for m in messages:
        content = m.get("content", "")
        name = m.get("name", m.get("role", "?"))
        snippet = content[:80].replace("\n", " ")
        snippets.append(f"[{name}]: {snippet}")
    return " | ".join(snippets)


def _format_for_summary(messages: list) -> str:
    """把消息列表格式化成适合 LLM 摘要的文本。"""
    lines = []
    for m in messages:
        name = m.get("name", m.get("role", "?"))
        content = m.get("content", "")
        # 截断每条消息以节省上下文
        short = content[:300].replace("\n", " ") if len(content) > 300 else content.replace("\n", " ")
        lines.append(f"{name}: {short}")
    return "\n".join(lines)
