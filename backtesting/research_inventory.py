"""List candidate searches separately from dataset/robustness audit manifests."""
import json


def search_manifests(root):
    result = []
    for path in (root/'artifacts/optimization').glob('*/manifest.json'):
        try:
            plan = json.loads(path.read_text(encoding='utf-8'))
            count = plan.get('candidate_count', len(plan.get('candidates', [])))
            if isinstance(count, int) and count > 0:
                result.append(path)
        except (ValueError, OSError):
            continue
    return sorted(result, key=lambda path: path.stat().st_mtime, reverse=True)
