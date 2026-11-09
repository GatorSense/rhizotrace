"""Locating the P-EnDe weights: an explicit path or RHIZOTRACE_WEIGHTS.

The weights are not distributed with rhizotrace. They come from the PlantRootSeg
repository.
"""

import hashlib
import os

SOURCE = "https://github.com/GatorSense/PlantRootSeg/tree/master/Models"
FILE = "P-EnDe-model.pth"
SHA256 = "0ad6298eb63508c09a6c3aa14fc0a715627425f992bf4ae552b03941ba4c5aaf"
ENV_VAR = "RHIZOTRACE_WEIGHTS"


def sha256_of(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _is_lfs_pointer(path):
    """A clone without Git LFS leaves a small text pointer in place of the weights."""
    if os.path.getsize(path) > 1024:
        return False
    with open(path, "rb") as f:
        return f.read(40).startswith(b"version https://git-lfs")


def resolve_weights(path=None):
    """The weights file from path, else from RHIZOTRACE_WEIGHTS."""
    path = path or os.environ.get(ENV_VAR)
    if not path:
        raise FileNotFoundError(f"no P-EnDe weights given. Download {FILE} from {SOURCE}, then pass "
                                f"weights= (--weights on the command line) or set {ENV_VAR}.")
    if not os.path.exists(path):
        raise FileNotFoundError(f"weights file not found: {path}")
    if _is_lfs_pointer(path):
        raise ValueError(f"{path} is a Git LFS pointer, not the weights. Download {FILE} itself from "
                         f"{SOURCE}, or clone PlantRootSeg with Git LFS installed.")
    return path
