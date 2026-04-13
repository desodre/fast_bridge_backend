import re
from typing import Optional
from pydantic import BaseModel


class FileEntry(BaseModel):
    name: str
    permissions: str
    is_dir: bool
    is_symlink: bool
    owner: str
    group: str
    size: int
    modified_at: str
    symlink_target: Optional[str] = None


class FileManagerResponse(BaseModel):
    path: str
    entries: list[FileEntry]


_LS_LINE_RE = re.compile(
    r'^([dlcbsp-][rwxstST-]{9})\s+'  # permissions
    r'\d+\s+'                          # link count
    r'(\S+)\s+'                        # owner
    r'(\S+)\s+'                        # group
    r'(\d+)\s+'                        # size
    r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+'  # date + time
    r'(.+)$'                           # name (may include " -> target")
)


def parse_ls_output(raw: str, path: str) -> FileManagerResponse:
    entries: list[FileEntry] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('total'):
            continue
        match = _LS_LINE_RE.match(line)
        if not match:
            continue
        perms, owner, group, size, modified_at, name_part = match.groups()
        symlink_target: Optional[str] = None
        if ' -> ' in name_part:
            name, symlink_target = name_part.split(' -> ', 1)
        else:
            name = name_part
        entries.append(FileEntry(
            name=name,
            permissions=perms,
            is_dir=perms[0] == 'd',
            is_symlink=perms[0] == 'l',
            owner=owner,
            group=group,
            size=int(size),
            modified_at=modified_at,
            symlink_target=symlink_target,
        ))
    return FileManagerResponse(path=path or '.', entries=entries)
