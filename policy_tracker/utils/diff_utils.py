# import difflib
# from typing import Dict, List, Tuple


# def split_html_lines(html: str) -> List[str]:
#     # Keep line-based diffs; normalize newlines
#     return (html or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")


# def compute_html_diff(old_html: str, new_html: str) -> Dict:
#     """
#     Compute a structured diff between two HTML strings.
#     Returns JSON-serializable dict with added/removed/changed segments.
#     """
#     old_lines = split_html_lines(old_html)
#     new_lines = split_html_lines(new_html)

#     diff = difflib.SequenceMatcher(a=old_lines, b=new_lines)

#     changes: List[Dict] = []
#     for tag, i1, i2, j1, j2 in diff.get_opcodes():
#         if tag == 'equal':
#             continue
#         changes.append({
#             'op': tag,  # 'replace' | 'delete' | 'insert'
#             'old': {
#                 'start': i1,
#                 'end': i2,
#                 'lines': old_lines[i1:i2],
#             },
#             'new': {
#                 'start': j1,
#                 'end': j2,
#                 'lines': new_lines[j1:j2],
#             }
#         })

#     return {
#         'changes': changes,
#         'old_num_lines': len(old_lines),
#         'new_num_lines': len(new_lines),
#     }


# def apply_diff(base_html: str, diff_json: Dict) -> str:
#     """
#     Reconstruct target HTML by applying diff_json to base_html.
#     Only supports diffs produced by compute_html_diff.
#     """
#     lines = split_html_lines(base_html)

#     # We will rebuild using the diff's new slices
#     # Strategy: walk through changes in order, constructing the new list
#     # by copying 'equal' segments implicitly and using 'new' slices for ops.
#     result: List[str] = []
#     cursor_old = 0
#     for change in diff_json.get('changes', []):
#         i1 = change['old']['start']
#         i2 = change['old']['end']
#         j1 = change['new']['start']
#         j2 = change['new']['end']

#         # Copy equal segment from old
#         if cursor_old < i1:
#             result.extend(lines[cursor_old:i1])

#         # Apply new content for this change
#         result.extend(change['new']['lines'])

#         cursor_old = i2

#     # Append any remaining tail from old that was equal
#     if cursor_old < len(lines):
#         result.extend(lines[cursor_old:])

#     return "\n".join(result)

import difflib
from typing import Dict, List
from ..models import PolicyVersion

def split_html_lines(html: str) -> List[str]:
    # Keep line-based diffs; normalize newlines
    return (html or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")

def compute_html_diff(old_html: str, new_html: str) -> Dict:
    """
    Compute a structured diff between two HTML strings.
    Returns JSON-serializable dict with added/removed/changed segments.
    """
    old_lines = split_html_lines(old_html)
    new_lines = split_html_lines(new_html)

    diff = difflib.SequenceMatcher(a=old_lines, b=new_lines)

    changes: List[Dict] = []
    for tag, i1, i2, j1, j2 in diff.get_opcodes():
        if tag == 'equal':
            continue
        changes.append({
            'op': tag,  # 'replace' | 'delete' | 'insert'
            'old': {
                'start': i1,
                'end': i2,
                'lines': old_lines[i1:i2],
            },
            'new': {
                'start': j1,
                'end': j2,
                'lines': new_lines[j1:j2],
            }
        })

    return {
        'changes': changes,
        'old_num_lines': len(old_lines),
        'new_num_lines': len(new_lines),
    }

def apply_diff(base_html: str, diff_json: Dict) -> str:
    """
    Reconstruct target HTML by applying diff_json to base_html.
    Only supports diffs produced by compute_html_diff.
    """
    lines = split_html_lines(base_html)

    # We will rebuild using the diff's new slices
    # Strategy: walk through changes in order, constructing the new list
    # by copying 'equal' segments implicitly and using 'new' slices for ops.
    result: List[str] = []
    cursor_old = 0
    for change in diff_json.get('changes', []):
        i1 = change['old']['start']
        i2 = change['old']['end']
        j1 = change['new']['start']
        j2 = change['new']['end']

        # Copy equal segment from old
        if cursor_old < i1:
            result.extend(lines[cursor_old:i1])

        # Apply new content for this change
        result.extend(change['new']['lines'])

        cursor_old = i2

    # Append any remaining tail from old that was equal
    if cursor_old < len(lines):
        result.extend(lines[cursor_old:])

    return "\n".join(result)

def reconstruct_from_checkpoint(checkpoint_version, target_version):
    """
    Reconstruct target version by applying diffs from checkpoint to target.
    """
    current_html = checkpoint_version.checkpoint  # Start from checkpoint HTML
    
    # Get all versions between checkpoint and target (inclusive)
    versions_between = PolicyVersion.objects.filter(
        org_policy=checkpoint_version.org_policy,
        version__gte=checkpoint_version.version,
        version__lte=target_version.version
    ).order_by('version')
    
    # Apply each diff sequentially
    for version in versions_between:
        if version.version != checkpoint_version.version:  # Skip checkpoint itself
            current_html = apply_diff(current_html, version.diff_data)
    
    return current_html