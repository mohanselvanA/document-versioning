import difflib
import json
from typing import Dict, List, Any, Union


class DiffProcessor:
    @staticmethod
    def split_html_lines(html: str) -> List[str]:
        if not html:
            return []
        return html.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    @staticmethod
    def compute_html_diff(old_html: str, new_html: str) -> Dict[str, Any]:
        old_lines = DiffProcessor.split_html_lines(old_html)
        new_lines = DiffProcessor.split_html_lines(new_html)
        matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
        changes: List[Dict[str, Any]] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            changes.append({
                "op": tag,
                "old": {
                    "start": i1,
                    "end": i2,
                    "lines": old_lines[i1:i2],
                },
                "new": {
                    "start": j1,
                    "end": j2,
                    "lines": new_lines[j1:j2],
                },
            })
        diff_data = {
            "changes": changes,
            "old_line_count": len(old_lines),
            "new_line_count": len(new_lines),
            "old_length": len(old_html),
            "new_length": len(new_html),
        }
        return diff_data

    @staticmethod
    def apply_diff(base_html: str, diff_data: Union[Dict, str]) -> str:
        print(f"[apply_diff] base_html length={len(base_html)}, diff_data type={type(diff_data)}")
        if isinstance(diff_data, str):
            try:
                diff_json = json.loads(diff_data)
                print("[apply_diff] Parsed diff_data from JSON string")
            except json.JSONDecodeError:
                print("[apply_diff] Failed to parse diff_data string — returning base_html")
                return base_html
        elif isinstance(diff_data, dict):
            diff_json = diff_data
        else:
            print(f"[apply_diff] Unsupported diff_data type: {type(diff_data)}")
            return base_html
        changes = diff_json.get("changes")
        if not isinstance(changes, list):
            print("[apply_diff] Invalid diff_data structure: missing 'changes' list")
            return base_html
        old_lines = DiffProcessor.split_html_lines(base_html)
        result: List[str] = []
        cursor = 0
        print(f"[apply_diff] Applying {len(changes)} changes...")
        for idx, change in enumerate(changes):
            if not isinstance(change, dict):
                print(f"[apply_diff] Skipping invalid change at index {idx}")
                continue
            old_info = change.get("old", {})
            new_info = change.get("new", {})
            op_type = change.get("op", "replace")
            i1 = old_info.get("start", 0)
            i2 = old_info.get("end", 0)
            new_lines = new_info.get("lines", [])
            total_old = len(old_lines)
            i1 = max(0, min(i1, total_old))
            i2 = max(0, min(i2, total_old))
            if cursor < i1:
                result.extend(old_lines[cursor:i1])
            if op_type in ("replace", "insert"):
                result.extend(new_lines)
            elif op_type == "delete":
                pass
            else:
                print(f"[apply_diff] Unknown operation type: {op_type}")
            cursor = i2
        if cursor < len(old_lines):
            result.extend(old_lines[cursor:])
        final_html = "\n".join(result)
        print(f"[apply_diff] Completed — final length: {len(final_html)}")
        return final_html


def split_html_lines(html: str) -> List[str]:
    return DiffProcessor.split_html_lines(html)


def compute_html_diff(old_html: str, new_html: str) -> Dict[str, Any]:
    return DiffProcessor.compute_html_diff(old_html, new_html)


def apply_diff(base_html: str, diff_data) -> str:
    return DiffProcessor.apply_diff(base_html, diff_data)
