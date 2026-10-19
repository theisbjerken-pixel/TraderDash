"""Add the TraderDash favorite to Edge's favorites bar."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

BOOKMARKS = Path.home() / "AppData/Local/Microsoft/Edge/User Data/Default/Bookmarks"
URL = "http://localhost:8501"
NAME = "TraderDash"
ROOTS = ("bookmark_bar", "other", "synced", "workspaces_v2")


def checksum(roots: dict) -> str:
    digest = hashlib.md5()

    def add_text(value: str) -> None:
        digest.update(value.encode("utf-8"))

    def add_title(value: str) -> None:
        digest.update(value.encode("utf-16-le"))

    def walk(node: dict) -> None:
        if node["type"] == "url":
            add_text(str(node["id"]))
            add_title(node["name"])
            add_text("url")
            add_text(node["url"])
        elif node["type"] == "folder":
            add_text(str(node["id"]))
            add_title(node["name"])
            add_text("folder")
            for child in node.get("children") or []:
                walk(child)

    for key in ROOTS:
        if key in roots:
            walk(roots[key])
    return digest.hexdigest()


def highest_id(node: dict) -> int:
    values = [int(node["id"])]
    for child in node.get("children") or []:
        values.append(highest_id(child))
    return max(values)


def main() -> None:
    data = json.loads(BOOKMARKS.read_text(encoding="utf-8"))
    bar = data["roots"]["bookmark_bar"]["children"]
    if any(item.get("url") == URL for item in bar):
        print("already-present")
        return

    new_id = max(highest_id(data["roots"][key]) for key in data["roots"]) + 1
    windows_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    stamp = str(int((datetime.now(timezone.utc) - windows_epoch).total_seconds() * 1_000_000))
    bar.insert(
        0,
        {
            "date_added": stamp,
            "date_last_used": "0",
            "guid": str(uuid.uuid4()),
            "id": str(new_id),
            "name": NAME,
            "show_icon": True,
            "type": "url",
            "url": URL,
        },
    )
    data["checksum"] = checksum(data["roots"])
    BOOKMARKS.write_text(json.dumps(data, ensure_ascii=False, indent=3) + "\n", encoding="utf-8")
    print("added")


if __name__ == "__main__":
    main()
