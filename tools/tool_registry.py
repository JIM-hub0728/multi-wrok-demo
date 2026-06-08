"""
工具注册 & 调用拦截。

Alice 方法论 Ch.4：工具设计要让 AI 可靠调用。
这里用 prompt-based 方式替代 AutoGen 原生的 function calling：
1. Agent 的 system_message 里写清可用工具和调用格式
2. Agent 在回复中用 [TOOL: name(args)] 格式请求工具
3. group_chat.py 的 _capture_messages 拦截并执行
4. 执行结果注入 conversation，同一 Agent 继续回复

为什么要绕开 AutoGen 原生 function calling？
AutoGen 0.7 的 GroupChat + register_for_llm 存在消息链同步 bug：
LLM 返回 tool_calls 后 AutoGen 未正确插入 tool result 消息，
导致 DeepSeek API 报 "insufficient tool messages" 错误。
"""
import re
import json
import logging
import os

logger = logging.getLogger(__name__)

# ─── 工具函数引用 ───
from .searcher_tools import web_search, fetch_page, save_report
from .engineer_tools import write_code, run_code

# ─── 工具名 → (函数, 简要签名) ───
TOOL_MAP = {
    "web_search": (web_search, 'web_search(query: str, max_results: int = 5)'),
    "fetch_page": (fetch_page, 'fetch_page(url: str)'),
    "save_report": (save_report, 'save_report(filename: str, content: str)'),
    "write_code": (write_code, 'write_code(filename: str, code: str)'),
    "run_code": (run_code, 'run_code(filename: str)'),
}

# ─── 各 Agent 的系统提示词注入（追加到 system_message 末尾）───

SEARCHER_TOOL_PROMPT = """
【你的工具】
你可以使用以下工具来完成调研任务。需要时，请在回复中插入工具调用：
格式：[TOOL: function_name(args)]

可用的工具：
1. web_search(query, max_results=5) — 搜索互联网，返回标题、URL 和摘要
   示例：[TOOL: web_search("Python asyncio vs trio", max_results=3)]

2. fetch_page(url) — 抓取指定网页的纯文本内容
   示例：[TOOL: fetch_page("https://example.com")]

3. save_report(filename, content) — 将调研报告保存为 deliverables/research/ 下的 Markdown 文件
   示例：[TOOL: save_report("async_comparison.md", "# 报告标题\n\n## 调研结果\n...")]
   **重要**：完成调研后必须调用此工具保存报告！文件名用英文，内容用 Markdown 格式。

重要规则：
- 工具调用必须独占一行，以 [TOOL: 开头，] 结尾
- 收到工具返回的结果后，请直接翻译/总结给用户
- 调研完成后必须用 save_report 保存最终报告
"""

ENGINEER_TOOL_PROMPT = """
【你的工具】
你可以使用以下工具来完成开发任务。需要时，请在回复中插入工具调用：
格式：[TOOL: function_name(args)]

可用的工具：
1. write_code(filename, code) — 把代码写入 deliverables/code/ 目录
   示例：[TOOL: write_code("example.py", "print('hello')")]

2. run_code(filename) — 执行 deliverables/code/ 目录下的 Python 文件
   示例：[TOOL: run_code("example.py")]

重要规则：
- 工具调用必须独占一行，以 [TOOL: 开头，] 结尾
- 先 write_code 再 run_code 验证
- 收到 run_code 的结果后，如果报错请修复代码然后重新 write_code + run_code
"""


def get_tool_prompt(agent_name: str) -> str:
    """获取某个 Agent 的工具提示词（用于注入 system_message）。"""
    prompts = {
        "Searcher": SEARCHER_TOOL_PROMPT,
        "Engineer": ENGINEER_TOOL_PROMPT,
    }
    return prompts.get(agent_name, "")


def execute_all_tools(raw_text: str) -> tuple[str | None, list[dict]]:
    """
    检测并执行消息中所有的 [TOOL: ...] 调用，返回合并结果和创建的文件列表。

    支持一条消息中多个工具调用。

    Args:
        raw_text (str): Agent 回复的完整文本

    Returns:
        tuple[str|None, list[dict]]: (所有工具执行结果的合并文本, 创建的文件列表)
        如果没有工具调用则返回 (None, [])
        文件列表元素格式: {"path": 绝对路径, "name": 文件名, "tool": 工具名}
    """
    matches = re.findall(r'\[TOOL:\s*(\w+)\((.*?)\)\s*\]', raw_text, re.DOTALL)
    if not matches:
        return None, []

    results = []
    created_files = []
    for func_name, args_str in matches:
        result = _execute_single(func_name, args_str)
        results.append(f"[{func_name} 结果]:\n{result}")
        # 解析工具结果，提取创建的文件路径
        try:
            result_obj = json.loads(result)
            if result_obj.get("success") and result_obj.get("filepath"):
                filepath = result_obj["filepath"]
                created_files.append({
                    "path": filepath,
                    "name": os.path.basename(filepath),
                    "tool": func_name,
                })
        except (json.JSONDecodeError, TypeError):
            pass

    return "\n\n".join(results), created_files


def _execute_single(func_name: str, args_str: str) -> str:
    """执行单个工具调用。"""
    if func_name not in TOOL_MAP:
        return json.dumps({"success": False, "error": f"未知工具: {func_name}"}, ensure_ascii=False)

    func, _ = TOOL_MAP[func_name]

    try:
        if args_str.strip():
            args, kwargs = _parse_tool_args(args_str)
            result = func(*args, **kwargs)
        else:
            result = func()
        return result
    except Exception as e:
        logger.error("tool execution failed: %s → %s", func_name, e)
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


def _parse_tool_args(args_str: str):
    """
    解析工具调用参数为 (args, kwargs) 元组。

    处理多行字符串：先把引号内换行转为 \\n 转义序列，再交给 ast 解析。
    """
    import ast

    args_str = args_str.strip()
    if not args_str:
        return [], {}

    # 把引号内的字面换行转为转义序列，防止 ast 解析报错
    def _escape_newlines(m):
        return m.group(0).replace("\n", "\\n").replace("\r", "")

    escaped = re.sub(r'"[^"]*"', _escape_newlines, args_str)
    escaped = re.sub(r"'[^']*'", _escape_newlines, escaped)

    try:
        code = f"_f({escaped})"
        tree = ast.parse(code, mode='eval')
        call = tree.body

        positional = []
        for arg in call.args:
            positional.append(ast.literal_eval(arg))

        kwargs = {}
        for kw in call.keywords:
            kwargs[kw.arg] = ast.literal_eval(kw.value)

        return positional, kwargs
    except Exception as e:
        logger.warning("arg parse failed: %s → %s", args_str[:100], e)
        return [], {}
