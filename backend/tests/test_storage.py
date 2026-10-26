from __future__ import annotations

import asyncio
import io

from starlette.datastructures import Headers, UploadFile

from app.core.config import settings
from app.services import storage

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


class FakeS3:
    def __init__(self) -> None:
        self.puts: list[dict[str, object]] = []
        self.deletes: list[dict[str, object]] = []

    def put_object(self, **kwargs: object) -> None:
        self.puts.append(kwargs)

    def delete_object(self, **kwargs: object) -> None:
        self.deletes.append(kwargs)

    def get_object(self, **kwargs: object) -> dict[str, object]:
        assert kwargs["Key"]
        return {"Body": io.BytesIO(PDF)}


def test_object_storage_round_trip_uses_neon_bucket(monkeypatch) -> None:
    fake = FakeS3()
    monkeypatch.setattr(storage, "_s3_client", lambda: fake)
    monkeypatch.setattr(settings, "BODY_ANALYSIS_BUCKET", "gym")
    monkeypatch.setattr(settings, "AWS_ENDPOINT_URL_S3", "http://storage.local")

    upload = UploadFile(
        file=io.BytesIO(PDF),
        filename="scan.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )
    original_name, stored_name, size = asyncio.run(
        storage.save_body_analysis_upload(upload)
    )

    assert original_name == "scan.pdf"
    assert stored_name.endswith(".pdf")
    assert size == len(PDF)
    assert fake.puts == [
        {
            "Bucket": "gym",
            "Key": f"body-analysis/{stored_name}",
            "Body": PDF,
            "ContentType": "application/pdf",
        }
    ]

    assert storage.read_stored_file(stored_name) == PDF

    storage.delete_stored_file(stored_name)
    assert fake.deletes == [
        {"Bucket": "gym", "Key": f"body-analysis/{stored_name}"}
    ]
