"""Object storage for the raw page archive (STORE-10).

Bytes are sealed to the environment's public key before they leave the
process, so the archive is ciphertext at rest and only worker roles can read
it. The bucket carries a 7-day lifecycle rule.
"""

import asyncio
import io
from typing import Protocol

from minio import Minio
from minio.commonconfig import ENABLED, Filter
from minio.error import S3Error
from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule


class BlobStore(Protocol):
    async def put(self, key: str, data: bytes) -> None: ...

    async def get(self, key: str) -> bytes | None: ...

    async def delete_prefix(self, prefix: str) -> int: ...


class MemoryBlobStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def delete_prefix(self, prefix: str) -> int:
        keys = [k for k in self.objects if k.startswith(prefix)]
        for k in keys:
            del self.objects[k]
        return len(keys)


class S3BlobStore:
    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str,
        retention_days: int = 7,
    ) -> None:
        secure = endpoint.startswith("https://")
        host = endpoint.split("://", 1)[-1].rstrip("/")
        self._client = Minio(
            host, access_key=access_key, secret_key=secret_key, secure=secure, region=region
        )
        self._bucket = bucket
        self._retention_days = retention_days
        self._ready = False
        self._lock = asyncio.Lock()

    def _ensure_sync(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
        self._client.set_bucket_lifecycle(
            self._bucket,
            LifecycleConfig(
                [
                    Rule(
                        ENABLED,
                        rule_filter=Filter(prefix=""),
                        rule_id="raw-pages-retention",
                        expiration=Expiration(days=self._retention_days),
                    ),
                ]
            ),
        )

    async def ensure(self) -> None:
        if self._ready:
            return
        async with self._lock:
            if not self._ready:
                await asyncio.to_thread(self._ensure_sync)
                self._ready = True

    async def put(self, key: str, data: bytes) -> None:
        await self.ensure()
        await asyncio.to_thread(
            self._client.put_object,
            self._bucket,
            key,
            io.BytesIO(data),
            len(data),
            content_type="application/octet-stream",
        )

    async def get(self, key: str) -> bytes | None:
        await self.ensure()

        def _get() -> bytes | None:
            try:
                resp = self._client.get_object(self._bucket, key)
            except S3Error as exc:
                if exc.code in ("NoSuchKey", "NoSuchObject"):
                    return None
                raise
            try:
                return bytes(resp.read())
            finally:
                resp.close()
                resp.release_conn()

        return await asyncio.to_thread(_get)

    async def delete_prefix(self, prefix: str) -> int:
        await self.ensure()

        def _delete() -> int:
            n = 0
            for obj in self._client.list_objects(self._bucket, prefix=prefix, recursive=True):
                if obj.object_name:
                    self._client.remove_object(self._bucket, obj.object_name)
                    n += 1
            return n

        return await asyncio.to_thread(_delete)
