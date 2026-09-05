from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol


class ObjectStore(Protocol):
    def read_json(self, key: str) -> dict[str, Any] | None:
        ...

    def write_json(self, key: str, payload: dict[str, Any]) -> None:
        ...

    def exists(self, key: str) -> bool:
        ...

    def download_to(self, key: str, dest: Path) -> None:
        ...

    def upload_from(self, key: str, src: Path) -> None:
        ...


class OssObjectStore:
    def __init__(self, bucket_name: str, endpoint: str | None = None) -> None:
        import oss2

        region = os.environ.get("ALIYUN_REGION", "cn-hangzhou")
        raw = (
            endpoint
            or os.environ.get("ST_MCU_OSS_ENDPOINT")
            or f"https://oss-{region}.aliyuncs.com"
        )
        if not raw.startswith("http"):
            raw = "https://" + raw
        access_key = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID") or os.environ.get(
            "OSS_ACCESS_KEY_ID"
        )
        secret = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET") or os.environ.get(
            "OSS_ACCESS_KEY_SECRET"
        )
        if access_key and secret:
            auth = oss2.Auth(access_key, secret)
        else:
            auth = oss2.ProviderAuth(oss2.credentials.EnvironmentVariableCredentialsProvider())
        self._bucket = oss2.Bucket(auth, raw, bucket_name)

    def read_json(self, key: str) -> dict[str, Any] | None:
        if not self.exists(key):
            return None
        return json.loads(self._bucket.get_object(key).read())

    def write_json(self, key: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        self._bucket.put_object(key, body, headers={"Content-Type": "application/json"})

    def exists(self, key: str) -> bool:
        return bool(self._bucket.object_exists(key))

    def download_to(self, key: str, dest: Path) -> None:
        if not self.exists(key):
            raise FileNotFoundError(f"OSS object missing: {key}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._bucket.get_object_to_file(key, str(dest))

    def upload_from(self, key: str, src: Path) -> None:
        self._bucket.put_object_from_file(key, str(src))


class GcsObjectStore:
    def __init__(self, bucket_name: str) -> None:
        from google.cloud import storage

        self._bucket = storage.Client().bucket(bucket_name)

    def read_json(self, key: str) -> dict[str, Any] | None:
        blob = self._bucket.blob(key)
        if not blob.exists():
            return None
        return json.loads(blob.download_as_text())

    def write_json(self, key: str, payload: dict[str, Any]) -> None:
        self._bucket.blob(key).upload_from_string(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            content_type="application/json",
        )

    def exists(self, key: str) -> bool:
        return bool(self._bucket.blob(key).exists())

    def download_to(self, key: str, dest: Path) -> None:
        blob = self._bucket.blob(key)
        if not blob.exists():
            raise FileNotFoundError(f"GCS object missing: {key}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(dest))

    def upload_from(self, key: str, src: Path) -> None:
        self._bucket.blob(key).upload_from_filename(str(src))
