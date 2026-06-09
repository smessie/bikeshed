from __future__ import annotations

import dataclasses
import hashlib
import os
from datetime import datetime, timezone

import kdl

from .. import messages as m
from .. import t

if t.TYPE_CHECKING:
    ManifestRelPath: t.TypeAlias = str
    ManifestFileHash: t.TypeAlias = str | None


@dataclasses.dataclass
class Manifest:
    dt: datetime = dataclasses.field(default_factory=lambda:dtNow())
    entries: dict[ManifestRelPath, ManifestFileHash] = dataclasses.field(default_factory=dict)
    # Bump this version manually whenever you update the datafiles
    version: int = 1

    @staticmethod
    def fromString(text: str) -> Manifest | None:
        try:
            doc = kdl.parse(text)
        except kdl.errors.ParseError:
            return Manifest.legacyFromString(text)
        manifest = doc["manifest"]
        entries = {file.props["path"]: file.props["hash"] for file in manifest.getAll("file")}
        return Manifest(dt=manifest.props["updated"], version=manifest.props["version"], entries=entries)

    @staticmethod
    def legacyFromString(text: str) -> Manifest | None:
        lines = text.split("\n")
        if len(lines) < 10:
            # Something's definitely borked
            m.warn(
                f"Error when parsing manifest: manifest is {len(lines)} long, which is too short to possibly be valid. Please report this!\nEntire manifest:\n{text}",
            )
            return None
        dt = parseDt(lines[0].strip())
        if dt is None:
            return None
        try:
            version = int(lines[1].strip())
            entryLines = lines[2:]
        except ValueError:
            version = 0
            entryLines = lines[1:]
        entries: dict[str, str | None] = {}
        for line in entryLines:
            line = line.strip()
            if line == "":
                continue
            hash, _, path = line.strip().partition(" ")
            if hash.startswith("error"):
                entries[path.strip()] = None
            else:
                entries[path.strip()] = hash

        return Manifest(dt, entries, version)

    @staticmethod
    def fromPath(
        path: str,
        allowedFiles: t.Container[str] | None = None,
        allowedFolders: t.Container[str] | None = None,
    ) -> Manifest:
        manifest = Manifest()
        for absPath, relPath in getDatafilePaths(path):
            if allowedFiles is None and allowedFolders is None:
                # No filter
                pass
                # Otherwise you have to pass at least one filter
            elif allowedFiles and relPath in allowedFiles:
                pass
            elif allowedFolders and relPath.partition("/")[0] in allowedFolders:
                pass
            else:
                continue
            with open(absPath, encoding="utf-8") as fh:
                manifest.entries[relPath] = hashFile(fh)
        return manifest

    def __str__(self) -> str:
        doc = kdl.Document(
            nodes=[
                kdl.Node(
                    "manifest",
                    None,
                    props={"updated": self.dt, "version": self.version},
                ),
            ],
        )
        manifestNode = doc["manifest"]
        for p, h in sorted(self.entries.items(), key=keyManifest):
            node = kdl.Node("file", None, props={"hash": h, "path": p})
            if h is None:
                node.props["error"] = True
            manifestNode.nodes.append(node)
        return doc.print()

    def daysOld(self) -> int:
        return (dtNow() - self.dt).days

    def save(self, path: str) -> None:
        with open(os.path.join(path, "manifest.txt"), "w", encoding="utf-8") as fh:
            fh.write(str(self))

    def hasError(self) -> bool:
        return self.dt == dtZero() or any(x is None for x in self.entries.values())


def keyManifest(entry: tuple[str, t.Any]) -> tuple[int, int | str, str]:
    name = entry[0]
    if "/" in name:
        dir, _, file = name.partition("/")
        return 1, dir, file
    else:
        return 0, len(name), name


def hashFile(fh: t.TextIO) -> str:
    return hashlib.md5(fh.read().encode("ascii", "xmlcharrefreplace")).hexdigest()


def getDatafilePaths(basePath: str) -> t.Generator[tuple[str, str], None, None]:
    for root, dirs, files in os.walk(basePath, topdown=True):
        if "readonly" in dirs:
            dirs.remove("readonly")
        for filename in files:
            if filename == "":
                continue
            filePath = os.path.join(root, filename)
            yield filePath, os.path.relpath(filePath, basePath)


def parseDt(s: str) -> datetime | None:
    dt = trystrptime(s, "%Y-%m-%d %H:%M:%S.%f")
    if dt:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def trystrptime(s: str, format: str) -> datetime | None:
    try:
        return datetime.strptime(s, format)
    except:  # pylint: disable=bare-except
        return None


def dtNow() -> datetime:
    return datetime.now(timezone.utc)


def dtZero() -> datetime:
    return datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
