import difflib
import json
from typing import Dict, List, Any, Union


class DiffProcessor:
    """Main class for HTML diff processing operations"""
    
    @staticmethod
    def split_html_lines(html: str) -> List[str]:
        """
        Split HTML into lines for diff computation.
        Normalize newlines and preserve line structure.
        """
        if not html:
            return []
        return html.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    @staticmethod
    def compute_html_diff(old_html: str, new_html: str) -> Dict[str, Any]:
        """
        Compute a structured diff between two HTML strings.
        Returns JSON-serializable dict with added/removed/changed segments.
        """
        old_lines = DiffProcessor.split_html_lines(old_html)
        new_lines = DiffProcessor.split_html_lines(new_html)

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
            'old_length': len(old_html),
            'new_length': len(new_html),
        }

    @staticmethod
    def apply_diff(base_html: str, diff_data: Union[Dict, str]) -> str:
        """
        Reconstruct target HTML by applying diff_data to base_html.
        Handles both dict and JSON string input.
        """
        print(f"📥 apply_diff: base_html_len={len(base_html)}, diff_data_type={type(diff_data)}")
        
        # Handle different input types
        if isinstance(diff_data, dict):
            diff_json = diff_data
        elif isinstance(diff_data, str):
            try:
                diff_json = json.loads(diff_data)
                print("⚠️  Diff data was string (parsed to dict)")
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse diff_data as JSON: {e}")
                return base_html
        else:
            print(f"❌ Unexpected diff_data type: {type(diff_data)}")
            return base_html
        
        # Validate the structure
        if not isinstance(diff_json, dict):
            print(f"❌ Invalid diff_json: expected dict, got {type(diff_json)}")
            return base_html
            
        changes = diff_json.get('changes', [])
        if not isinstance(changes, list):
            print(f"❌ Invalid changes: expected list, got {type(changes)}")
            return base_html
        
        print(f"🔄 Applying {len(changes)} changes")
        
        # Split base HTML into lines
        lines = DiffProcessor.split_html_lines(base_html)
        result = []
        cursor_old = 0
        
        # Track statistics
        applied_changes = 0
        skipped_changes = 0
        
        # Apply each change
        for i, change in enumerate(changes):
            if not isinstance(change, dict):
                print(f"⚠️  Change {i} is not a dict, skipping")
                skipped_changes += 1
                continue
                
            old_info = change.get('old', {})
            new_info = change.get('new', {})
            
            i1 = old_info.get('start', 0)
            i2 = old_info.get('end', 0)
            new_lines = new_info.get('lines', [])
            
            # Validate indices
            if i1 < 0 or i2 < i1 or i1 > len(lines) or i2 > len(lines):
                print(f"⚠️  Invalid indices in change {i}: i1={i1}, i2={i2}, total_lines={len(lines)}")
                skipped_changes += 1
                continue

            # Copy equal segment from old (lines between cursor_old and i1)
            if cursor_old < i1:
                result.extend(lines[cursor_old:i1])

            # Apply new content for this change
            if new_lines:
                result.extend(new_lines)
                
            cursor_old = i2
            applied_changes += 1

        # Append any remaining content from old that was unchanged
        if cursor_old < len(lines):
            result.extend(lines[cursor_old:])

        final_html = "\n".join(result)
        print(f"✅ apply_diff completed: applied={applied_changes}, skipped={skipped_changes}, final_len={len(final_html)}")
        return final_html


# Legacy function aliases for backward compatibility
def split_html_lines(html: str) -> List[str]:
    """Legacy function - use DiffProcessor.split_html_lines instead"""
    return DiffProcessor.split_html_lines(html)

def compute_html_diff(old_html: str, new_html: str) -> Dict[str, Any]:
    """Legacy function - use DiffProcessor.compute_html_diff instead"""
    return DiffProcessor.compute_html_diff(old_html, new_html)

def apply_diff(base_html: str, diff_data) -> str:
    """Legacy function - use DiffProcessor.apply_diff instead"""
    return DiffProcessor.apply_diff(base_html, diff_data)


# =============================================================================
# UNUSED FUNCTIONS (COMMENTED OUT FOR NOW)
# =============================================================================

"""
def reconstruct_from_checkpoint_raw(checkpoint_html, checkpoint_version, target_version, all_versions_data):
    # Advanced reconstruction using checkpoints - not currently used
    pass

def reconstruct_sequentially_raw(all_versions_data, target_version):
    # Sequential reconstruction from raw data - not currently used
    pass

def find_nearest_checkpoint(all_versions_data, target_version):
    # Find nearest checkpoint - not currently used
    pass

def reconstruct_policy_html_raw(org_policy_id, target_version, db_connection):
    # Raw SQL reconstruction - not currently used
    pass

def debug_diff_computation(old_html, new_html):
    # Debug function - not needed in production
    pass
"""
