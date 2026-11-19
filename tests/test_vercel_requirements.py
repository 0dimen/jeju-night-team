"""Vercel 은 requirements.txt 의 -r 포함을 읽지 못하므로 직접 적고, 기본 의존성과 같게 유지한다."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pins(name):
    return [line.strip() for line in (ROOT / name).read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.startswith('#')]


def test_vercel_requirements_match_base():
    vercel = pins('requirements.txt')
    assert not any(line.startswith('-') for line in vercel)
    assert vercel == pins('requirements-base.txt')
    assert (ROOT / 'requirements.txt').read_text(encoding='utf-8').isascii()
