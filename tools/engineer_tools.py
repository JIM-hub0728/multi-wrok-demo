"""
Engineer 的工具：write_code、run_code。
每个工具返回结构化 dict: {"success": bool, "data": ..., "error": str | None}
"""
import os
import subprocess
import json
import logging

logger = logging.getLogger(__name__)

DELIVERABLES_DIR = os.path.join("deliverables", "code")


def write_code(filename: str, code: str) -> str:
    """
    把代码写入 deliverables/code/ 目录。

    Args:
        filename (str): 文件名，如 "example.py"
        code (str): 代码内容

    Returns:
        str: JSON 字符串，格式 {"success": true, "filepath": "...", "size": 123}
    """
    try:
        os.makedirs(DELIVERABLES_DIR, exist_ok=True)
        filepath = os.path.join(DELIVERABLES_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        size = len(code.encode("utf-8"))
        logger.info("write_code: wrote %d bytes to %s", size, filepath)
        return json.dumps({"success": True, "filepath": os.path.abspath(filepath), "size": size})
    except Exception as e:
        logger.error("write_code failed: %s", e)
        return json.dumps({"success": False, "filepath": "", "error": str(e)})


def run_code(filename: str) -> str:
    """
    在子进程中执行 deliverables/code/ 下的文件，返回输出。

    按扩展名判断执行方式：
    - .py  → 用 python 解释器执行
    - .html → 提示在浏览器中打开（不可直接执行）
    - 其他 → 尝试用 python 执行，失败则返回提示

    Args:
        filename (str): 文件名，如 "example.py" 或 "page.html"

    Returns:
        str: JSON 字符串，格式 {"success": true, "output": "...", "exit_code": 0}
    """
    try:
        filepath = os.path.join(DELIVERABLES_DIR, filename)
        if not os.path.exists(filepath):
            return json.dumps({"success": False, "output": "", "error": f"文件不存在: {filepath}"})

        ext = os.path.splitext(filename)[1].lower()

        # HTML 文件：不可直接执行，提示用浏览器打开
        if ext == ".html":
            logger.info("run_code: %s is HTML, skipped execution", filename)
            return json.dumps({
                "success": True,
                "output": (
                    f"文件 {filename} 是 HTML 网页，已保存成功。"
                    f"请直接在浏览器中打开查看效果：{os.path.abspath(filepath)}"
                ),
                "exit_code": 0,
                "note": "HTML files are not executable; open in browser instead",
            })

        # 非 Python 文件给出友好提示
        if ext != ".py":
            logger.warning("run_code: %s has unknown extension '%s'", filename, ext)

        result = subprocess.run(
            ["python", filepath],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        output = output.strip() or "(无输出)"

        logger.info("run_code: %s → exit_code=%d, output=%d chars", filename, result.returncode, len(output))
        return json.dumps({
            "success": result.returncode == 0,
            "output": output[:5000],  # 最多 5000 字符
            "exit_code": result.returncode,
        })
    except subprocess.TimeoutExpired:
        logger.warning("run_code: %s timed out", filename)
        return json.dumps({"success": False, "output": "执行超时（30 秒）", "exit_code": -1})
    except Exception as e:
        logger.error("run_code failed for %s: %s", filename, e)
        return json.dumps({"success": False, "output": str(e), "exit_code": -1})
