from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ProxyModel(BaseModel):
    """Model representing the proxy settings for the request."""

    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    type: str


class ActionType(Enum):
    """Enum representing the types of browser actions available."""

    SCREENSHOT = "screenshot"
    PDF = "pdf"


class Action(BaseModel):
    """Model representing a browser action to be performed."""

    type: ActionType


class CrawlRequest(BaseModel):
    """Model representing the URL and associated parameters for the request."""

    url: str
    block_media: bool = False
    accept_cookies_selector: Optional[str] = None
    wait_after_load: int = 0
    timeout: int = 15000
    user_agent: Optional[str] = None
    locale: Optional[str] = None
    extra_headers: Optional[Dict[str, str]] = None
    proxy: Optional[ProxyModel] = None
    actions: List[Action] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str


class AttachmentType(str, Enum):
    PDF = "pdf"
    SCREENSHOT = "screenshot"


class Attachment(BaseModel):
    type: AttachmentType
    content: str


class CrawlResponse(BaseModel):
    url: str
    html: str
    status_code: int
    error: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    attachments: List[Attachment] = Field(default_factory=list)
