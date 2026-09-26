from pathlib import Path

import pytest

from curtamap.s3_sync import parse_s3_uri, plan_sync, sync, sync_from_env


class FakeS3:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects
        self.downloads: list[str] = []

    def get_paginator(self, name: str):
        assert name == "list_objects_v2"
        return self

    def paginate(self, Bucket: str, Prefix: str):  # noqa: N803 - assinatura do boto3
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        yield {"Contents": [{"Key": k, "Size": len(self.objects[k])} for k in keys[:1]]}
        yield {"Contents": [{"Key": k, "Size": len(self.objects[k])} for k in keys[1:]]}
        yield {}

    def download_file(self, Bucket: str, Key: str, Filename: str) -> None:  # noqa: N803
        self.downloads.append(Key)
        Path(Filename).write_bytes(self.objects[Key])


@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        ("s3://bucket/raw/", ("bucket", "raw/")),
        ("s3://bucket/raw", ("bucket", "raw/")),
        ("s3://bucket", ("bucket", "")),
        ("s3://bucket/", ("bucket", "")),
    ],
)
def test_parse_s3_uri(uri: str, expected: tuple[str, str]) -> None:
    assert parse_s3_uri(uri) == expected


@pytest.mark.parametrize("uri", ["https://bucket/raw", "s3://", "bucket/raw", ""])
def test_parse_rejects_invalid_uris(uri: str) -> None:
    with pytest.raises(ValueError, match="URI S3"):
        parse_s3_uri(uri)


def test_plan_skips_folders_and_files_of_the_same_size(tmp_path: Path) -> None:
    (tmp_path / "igual.parquet").write_bytes(b"123")
    objects = [("raw/", 0), ("raw/igual.parquet", 3), ("raw/novo.parquet", 5), ("raw/a/b.bin", 1)]

    plan = plan_sync(objects, "raw/", tmp_path)

    assert plan == [
        ("raw/novo.parquet", tmp_path / "novo.parquet"),
        ("raw/a/b.bin", tmp_path / "a" / "b.bin"),
    ]


def test_plan_redownloads_a_file_with_another_size(tmp_path: Path) -> None:
    (tmp_path / "x.parquet").write_bytes(b"1")

    assert plan_sync([("raw/x.parquet", 3)], "raw/", tmp_path) == [
        ("raw/x.parquet", tmp_path / "x.parquet")
    ]


def test_plan_rejects_keys_that_escape_the_destination(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="inseguro"):
        plan_sync([("raw/../../etc/passwd", 1)], "raw/", tmp_path)


def test_sync_downloads_across_pages(tmp_path: Path) -> None:
    client = FakeS3({"raw/a.parquet": b"aa", "raw/b.parquet": b"bbb", "outro/c": b"c"})

    written = sync("s3://bucket/raw/", tmp_path, client=client)

    assert sorted(p.name for p in written) == ["a.parquet", "b.parquet"]
    assert (tmp_path / "b.parquet").read_bytes() == b"bbb"
    assert sync("s3://bucket/raw/", tmp_path, client=client) == []
    assert client.downloads == ["raw/a.parquet", "raw/b.parquet"]


def test_sync_from_env_is_a_no_op_without_uris(tmp_path: Path) -> None:
    assert sync_from_env({}, data_dir=tmp_path, model_dir=tmp_path, client=None) == []


def test_sync_from_env_places_data_and_models(tmp_path: Path) -> None:
    client = FakeS3({"dados/raw/x.parquet": b"x", "modelos/previsao/m.joblib": b"m"})
    env = {
        "CURTAMAP_DATA_S3_URI": "s3://b/dados/raw/",
        "CURTAMAP_MODEL_S3_URI": "s3://b/modelos/previsao/",
    }

    sync_from_env(env, data_dir=tmp_path / "data", model_dir=tmp_path / "models", client=client)

    assert (tmp_path / "data" / "raw" / "x.parquet").exists()
    assert (tmp_path / "models" / "previsao" / "m.joblib").exists()
