"""Acceptance artefacts are a migration boundary, not disposable golden output."""
import hashlib
import json
from pathlib import Path

import pytest


def test_hube_frozen_acceptance_artifacts_preserved():
    commons = Path(__file__).resolve().parents[1]
    hube = commons.parent / 'game_hube'
    if not hube.exists():
        pytest.skip('The Hube source checkout is needed to verify the M0 freeze')
    baseline = json.loads((commons / 'docs/M0_BASELINE.json').read_text())
    for name, expected in baseline['frozen_artifacts'].items():
        actual = hashlib.sha256((hube / name).read_bytes()).hexdigest()
        assert actual == expected, (
            f'{name} changed: document and approve the semantic migration before '
            'updating the M0 acceptance baseline'
        )
