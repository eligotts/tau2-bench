from typing import Optional

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class WebsiteStatus(BaseModelNoExtra):
    url: str
    loads_successfully: bool
    response_time_ms: int
    error_code: Optional[str] = None  # "502", "503", "500", "ssl_error", "dns_error"
    ssl_warning: bool = False
    page_content_correct: bool = True


class HostingUserDB(DB):
    website: WebsiteStatus
    email_working: bool = True
    dns_resolves: bool = True
    browser_cache_stale: bool = False
    local_dns_stale: bool = False
    user_verified_working: bool = True
    needs_email_verification: bool = False
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    account_id: Optional[str] = None
