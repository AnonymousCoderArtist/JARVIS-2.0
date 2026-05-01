"""Tool result models for TUI."""

from pydantic import BaseModel
from typing import Optional


class BashResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class GrepResult(BaseModel):
    matches: str = ""


class ReadFileResult(BaseModel):
    path: str
    content: str = ""


class SearchReplaceResult(BaseModel):
    content: str = ""


class TodoResult(BaseModel):
    todos: list = []


class WriteFileResult(BaseModel):
    path: str
    bytes_written: int = 0
    content: str = ""