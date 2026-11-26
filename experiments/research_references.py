"""Resolve read-only research inputs while keeping historical seals in logical paths."""
from hashlib import sha256

REFERENCE = 'runtime/research_reference'


def source(root, relative):
    """Prefer curated copies for old runtime inputs. Current outputs keep their paths."""
    path = root / relative
    parts = path.relative_to(root).parts
    if len(parts) > 2 and parts[0] == 'runtime' and parts[1] != 'research_reference':
        candidate = root / REFERENCE / '/'.join(parts[1:])
        if candidate.is_file():
            return candidate
    return path


def logical(root, path):
    """Return the original path spelling used in the research manifest."""
    parts = path.relative_to(root).parts
    if parts[:2] == ('runtime', 'research_reference'):
        return '/'.join(('runtime', *parts[2:]))
    return path.relative_to(root).as_posix()


def sealed(root, relative, expected):
    """Verify a historical source, including exact code preserved before relocation."""
    path = source(root, relative)
    if path.is_file() and sha256(path.read_bytes()).hexdigest() == expected:
        return path
    original = root / REFERENCE / 'frozen_code' / relative
    if original.is_file() and sha256(original.read_bytes()).hexdigest() == expected:
        return original
    raise ValueError(f'Sealed source missing or changed: {relative}')
