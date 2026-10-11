import re
from urllib.parse import urlparse

from fastapi import HTTPException


GITHUB_REPOSITORY = re.compile(r"^/[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*/?$")


def validate_github_url(value: str) -> tuple[str, str, str]:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path.endswith("/")
        or not GITHUB_REPOSITORY.fullmatch(parsed.path.removesuffix(".git"))
    ):
        raise HTTPException(status_code=422, detail="Only public GitHub HTTPS repository URLs are supported")
    path = parsed.path.strip("/").removesuffix(".git")
    owner, name = path.split("/")
    return f"https://github.com/{owner}/{name}.git", owner, name


def safe_child(root: Path, child: Path) -> Path:
    root = root.resolve()
    child = child.resolve()
    if child != root and root not in child.parents:
        raise ValueError("workspace path escapes configured root")
    return child
