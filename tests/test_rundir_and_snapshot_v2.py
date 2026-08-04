"""P0 hardening: managed run directories and snapshot identity v2.

Run-dir side exists because `--out /path/to/anything` used to be rmtree'd.
Snapshot side exists because the v1 digest ignored mode and symlinks: chmod
+x was invisible, and symlinks were silently flattened into regular files.
"""

import os

import pytest

from causal_data_juicer.runtime.rundir import (
    MARKER,
    UnmanagedDirectoryError,
    prepare_run_dir,
)
from causal_data_juicer.store.blob import (
    BlobStore,
    digests_match,
    tree_digest,
    tree_digest_v1,
)

# -- managed run directories --------------------------------------------------


def test_fresh_dir_is_created_and_marked(tmp_path):
    out = prepare_run_dir(tmp_path / "runs" / "r1")
    assert (out / MARKER).is_file()


def test_unmanaged_existing_dir_is_refused(tmp_path):
    thesis = tmp_path / "thesis"
    thesis.mkdir()
    (thesis / "chapter1.tex").write_text("important")
    with pytest.raises(UnmanagedDirectoryError):
        prepare_run_dir(thesis)
    assert (thesis / "chapter1.tex").read_text() == "important"


def test_managed_dir_goes_to_trash_not_oblivion(tmp_path):
    out = prepare_run_dir(tmp_path / "runs" / "r1")
    (out / "units.jsonl").write_text("{}")
    prepare_run_dir(tmp_path / "runs" / "r1")  # reuse the same --out
    trash = list((tmp_path / "runs" / ".cdj-trash").iterdir())
    assert len(trash) == 1
    assert (trash[0] / "units.jsonl").read_text() == "{}"


def test_home_and_root_are_refused(tmp_path):
    with pytest.raises(UnmanagedDirectoryError):
        prepare_run_dir(os.path.expanduser("~"))


def test_symlinked_out_is_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / MARKER).write_text('{"run_id": "x"}')
    link = tmp_path / "link"
    os.symlink(real, link)
    with pytest.raises(UnmanagedDirectoryError):
        prepare_run_dir(link)


# -- snapshot identity v2 -----------------------------------------------------


@pytest.fixture()
def tree(tmp_path):
    t = tmp_path / "t"
    t.mkdir()
    (t / "a.py").write_text("x = 1\n")
    (t / "run.sh").write_text("echo hi\n")
    return t


def test_mode_change_changes_digest(tree):
    d1 = tree_digest(tree)
    os.chmod(tree / "run.sh", 0o755)
    assert tree_digest(tree) != d1
    # ...which v1 could not see — the exact bug:
    v1_before = tree_digest_v1(tree)
    os.chmod(tree / "run.sh", 0o644)
    assert tree_digest_v1(tree) == v1_before


def test_symlink_differs_from_equal_content_file(tree, tmp_path):
    (tree / "dup.txt").write_text("same")
    d_file = tree_digest(tree)
    (tree / "dup.txt").unlink()
    (tree / "orig.txt").write_text("same")
    os.symlink("orig.txt", tree / "dup.txt")
    assert tree_digest(tree) != d_file


def test_roundtrip_preserves_symlinks_and_modes(tree, tmp_path):
    os.chmod(tree / "run.sh", 0o755)
    os.symlink("a.py", tree / "alias.py")
    store = BlobStore(tmp_path / "blobs")
    digest = store.put_tree(tree)
    assert digest.startswith("v2-")
    out = store.restore_tree(digest, tmp_path / "restored")
    assert (out / "alias.py").is_symlink()
    assert os.readlink(out / "alias.py") == "a.py"
    assert (out / "run.sh").stat().st_mode & 0o777 == 0o755


def test_restore_verifies_digest(tree, tmp_path):
    store = BlobStore(tmp_path / "blobs")
    digest = store.put_tree(tree)
    (store.root / digest / "a.py").write_text("tampered = True\n")
    with pytest.raises(RuntimeError, match="digest mismatch"):
        store.restore_tree(digest, tmp_path / "restored")


def test_out_of_tree_symlink_is_stored_as_link_not_content(tree, tmp_path):
    secret = tmp_path / "host_secret.txt"
    secret.write_text("HOST-ONLY")
    os.symlink(secret, tree / "leak.txt")
    store = BlobStore(tmp_path / "blobs")
    digest = store.put_tree(tree)
    blob_leak = store.root / digest / "leak.txt"
    assert blob_leak.is_symlink()  # not flattened
    assert "HOST-ONLY" not in str(
        [
            p.read_text()
            for p in (store.root / digest).rglob("*")
            if p.is_file() and not p.is_symlink()
        ]
    )


def test_digests_match_is_schema_aware(tree):
    assert digests_match(tree_digest(tree), tree)  # v2 vs v2
    assert digests_match(tree_digest_v1(tree), tree)  # legacy recorded digest
    assert not digests_match("v2-deadbeef00000000", tree)


def test_restore_refuses_existing_destination(tree, tmp_path):
    store = BlobStore(tmp_path / "blobs")
    digest = store.put_tree(tree)
    dest = tmp_path / "existing"
    dest.mkdir()
    with pytest.raises(FileExistsError):
        store.restore_tree(digest, dest)
