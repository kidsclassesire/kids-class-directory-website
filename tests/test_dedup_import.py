import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.dedup_import import discover_source_files


def test_discover_source_files_skips_known_outputs_and_non_sources():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / 'candidate_a.csv').write_text('name\nTest\n', encoding='utf-8')
        (root / 'candidate_b.json').write_text('[]', encoding='utf-8')
        (root / 'classes_in_database.json').write_text('[]', encoding='utf-8')
        (root / 'all_normalized_candidates.csv').write_text('name\nIgnore\n', encoding='utf-8')
        (root / 'notes.txt').write_text('ignore me', encoding='utf-8')

        discovered = discover_source_files(root)

        assert [p.name for p in discovered] == ['candidate_a.csv', 'candidate_b.json']
