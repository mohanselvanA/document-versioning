import difflib
import json
from typing import Dict, List, Any, Union


class DiffProcessor:
    """Main class for HTML diff processing operations"""

    @staticmethod
    def split_html_lines(html: str) -> List[str]:
        """
        Split HTML into normalized lines for consistent diff computation.
        Ensures consistent line endings and no trailing newlines.
        """
        if not html:
            return []
        return html.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    @staticmethod
    def compute_html_diff(old_html: str, new_html: str) -> Dict[str, Any]:
        """
        Compute a structured diff between two HTML strings.
        Returns JSON-safe dict with the list of change operations.
        """
        old_lines = DiffProcessor.split_html_lines(old_html)
        new_lines = DiffProcessor.split_html_lines(new_html)

        matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
        changes: List[Dict[str, Any]] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            changes.append({
                "op": tag,  # 'replace' | 'delete' | 'insert'
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
        """
        Reconstruct target HTML by applying a diff to base_html.
        Works for both JSON strings and Python dicts.
        """
        print(f"[apply_diff] base_html length={len(base_html)}, diff_data type={type(diff_data)}")

        # Parse diff data if string
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

        # Validate diff structure
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

            # Validate and clamp indices
            total_old = len(old_lines)
            i1 = max(0, min(i1, total_old))
            i2 = max(0, min(i2, total_old))

            # Add unchanged lines before current change
            if cursor < i1:
                result.extend(old_lines[cursor:i1])

            # Apply operation
            if op_type in ("replace", "insert"):
                result.extend(new_lines)
            elif op_type == "delete":
                # Nothing added for delete
                pass
            else:
                print(f"[apply_diff] Unknown operation type: {op_type}")

            cursor = i2

        # Add remaining lines (after last diff)
        if cursor < len(old_lines):
            result.extend(old_lines[cursor:])

        final_html = "\n".join(result)
        print(f"[apply_diff] Completed — final length: {len(final_html)}")
        return final_html


# Legacy aliases (for backward compatibility)
def split_html_lines(html: str) -> List[str]:
    """Legacy alias for DiffProcessor.split_html_lines"""
    return DiffProcessor.split_html_lines(html)


def compute_html_diff(old_html: str, new_html: str) -> Dict[str, Any]:
    """Legacy alias for DiffProcessor.compute_html_diff"""
    return DiffProcessor.compute_html_diff(old_html, new_html)


def apply_diff(base_html: str, diff_data) -> str:
    """Legacy alias for DiffProcessor.apply_diff"""
    return DiffProcessor.apply_diff(base_html, diff_data)


# =============================================================================
# OPTIONAL DEBUG / EXPERIMENTAL UTILITIES (COMMENTED OUT)
# =============================================================================

"""
def visualize_diff_html(old_html: str, new_html: str) -> str:
    '''Return a colored HTML visualization of changes for debugging'''
    import difflib
    diff = difflib.HtmlDiff()
    return diff.make_file(
        old_html.splitlines(),
        new_html.splitlines(),
        fromdesc='Old HTML',
        todesc='New HTML'
    )
"""
