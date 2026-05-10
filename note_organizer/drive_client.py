"""
Google Drive client for fetching field notes.

Credentials are loaded from (in priority order):
1. GOOGLE_CREDENTIALS_JSON env var (full JSON string — set this in Railway)
2. service_account.json file next to this module (local dev only)
"""

import io
import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

SUPPORTED_MIME_TYPES = {
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.google-apps.document",
}


def _build_credentials():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        info = json.loads(creds_json)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

    local_path = os.path.join(os.path.dirname(__file__), "service_account.json")
    if os.path.exists(local_path):
        return service_account.Credentials.from_service_account_file(local_path, scopes=SCOPES)

    raise RuntimeError(
        "No Google credentials found. "
        "Set the GOOGLE_CREDENTIALS_JSON environment variable or place "
        "service_account.json in the note_organizer directory."
    )


class DriveClient:
    def __init__(self):
        creds = _build_credentials()
        self.service = build("drive", "v3", credentials=creds)

    def list_files_recursive(self, folder_id: str) -> list[dict]:
        """Return a flat list of all supported files under folder_id."""
        out: list[dict] = []
        self._recurse(folder_id, "", out)
        return out

    def _recurse(self, folder_id: str, path_prefix: str, out: list) -> None:
        page_token = None
        while True:
            resp = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=1000,
                pageToken=page_token,
            ).execute()

            for item in resp.get("files", []):
                name = item["name"]
                mime = item["mimeType"]
                drive_path = f"{path_prefix}/{name}" if path_prefix else name

                if mime == "application/vnd.google-apps.folder":
                    self._recurse(item["id"], drive_path, out)
                elif mime in SUPPORTED_MIME_TYPES:
                    out.append({
                        "id": item["id"],
                        "name": name,
                        "mime_type": mime,
                        "drive_path": drive_path,
                    })

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    def download_bytes(self, file_id: str, mime_type: str) -> bytes:
        """Download file content. Google Docs are exported as .docx."""
        if mime_type == "application/vnd.google-apps.document":
            request = self.service.files().export_media(
                fileId=file_id,
                mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        else:
            request = self.service.files().get_media(fileId=file_id)

        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()
