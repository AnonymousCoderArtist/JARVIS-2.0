"""Tool result models for TUI."""

from pydantic import BaseModel
from typing import Optional


class BashResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class GrepMatch(BaseModel):
    file: str
    line: int
    content: str


class GrepResult(BaseModel):
    matches: list[GrepMatch] = []


class ReadFileResult(BaseModel):
    path: str
    content: str = ""


class TodoResult(BaseModel):
    todos: list = []


class WriteFileResult(BaseModel):
    path: str
    bytes_written: int = 0
    content: str = ""


class SearchReplaceResult(BaseModel):
    path: str = ""
    old_str: str = ""
    new_str: str = ""
    replacements: int = 0
    content: str = ""


class LSResult(BaseModel):
    items: list[str] = []