import pytest

from rhizotrace.segmentation import weights as W


def test_no_weights_points_to_source(monkeypatch):
    monkeypatch.delenv(W.ENV_VAR, raising=False)
    with pytest.raises(FileNotFoundError, match="PlantRootSeg"):
        W.resolve_weights()


def test_lfs_pointer_is_rejected(tmp_path):
    path = tmp_path / W.FILE
    path.write_text(f"version https://git-lfs.github.com/spec/v1\noid sha256:{W.SHA256}\nsize 124135667\n")
    with pytest.raises(ValueError, match="Git LFS pointer"):
        W.resolve_weights(str(path))


def test_env_var_is_used(tmp_path, monkeypatch):
    path = tmp_path / W.FILE
    path.write_bytes(b"\0" * 2048)
    monkeypatch.setenv(W.ENV_VAR, str(path))
    assert W.resolve_weights() == str(path)
