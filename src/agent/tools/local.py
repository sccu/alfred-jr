"""Tools for the local profile — MacBook control."""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool, tool

_SENSITIVE_DIRS = (
    ".ssh",
    ".gnupg",
    ".aws",
    ".kube",
    ".config/gcloud",
    ".docker",
)

_SENSITIVE_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx"})
_SENSITIVE_NAMES = frozenset({"id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"})
_MAX_BYTES = 50 * 1024  # 50 KB
_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"})


def _is_sensitive(path: Path) -> bool:
    home = Path.home()
    for d in _SENSITIVE_DIRS:
        try:
            path.relative_to(home / d)
            return True
        except ValueError:
            pass
    if path.suffix in _SENSITIVE_SUFFIXES:
        return True
    if path.name in _SENSITIVE_NAMES:
        return True
    if path.name.startswith(".env"):
        return True
    return False


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"[페이지 {i + 1}]\n{text}")
    if not pages:
        return "텍스트를 추출할 수 없습니다 (스캔 이미지 PDF일 수 있습니다)."
    full = "\n\n".join(pages)
    if len(full.encode()) > _MAX_BYTES:
        return full.encode()[:_MAX_BYTES].decode(errors="replace") + "\n\n[50KB 초과 — 앞부분만 반환]"
    return full


@tool
def read_file(path: str) -> str:
    """로컬 파일을 읽어 내용을 반환한다. PDF와 텍스트 파일을 지원하며 50KB 초과 시 앞부분만 반환한다."""
    try:
        p = Path(path).expanduser().resolve()
        if _is_sensitive(p):
            return f"접근 거부: 민감한 경로입니다 — {path}"
        if not p.exists():
            return f"파일 없음: {path}"
        if not p.is_file():
            return f"파일이 아님: {path}"
        if p.suffix.lower() == ".pdf":
            return _read_pdf(p)
        raw = p.read_bytes()
        text = raw[:_MAX_BYTES].decode("utf-8", errors="replace")
        if len(raw) > _MAX_BYTES:
            text += "\n\n[50KB 초과 — 앞부분만 반환]"
        return text
    except Exception as e:
        return f"읽기 실패: {e}"


@tool
def list_directory(path: str) -> str:
    """로컬 디렉토리의 파일·폴더 목록을 반환한다. ~ 를 홈 디렉토리로 사용할 수 있다."""
    try:
        p = Path(path).expanduser().resolve()
        if _is_sensitive(p):
            return f"접근 거부: 민감한 경로입니다 — {path}"
        if not p.exists():
            return f"경로 없음: {path}"
        if not p.is_dir():
            return f"디렉토리가 아님: {path}"
        entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        if not entries:
            return "비어 있는 디렉토리입니다."
        lines = [f"{'[폴더]' if e.is_dir() else '[파일]'} {e.name}" for e in entries]
        return "\n".join(lines)
    except PermissionError:
        return f"접근 거부: OS 권한이 없습니다 — {path}"
    except Exception as e:
        return f"목록 조회 실패: {e}"


LOCAL_TOOLS: list[BaseTool] = [read_file, list_directory]
