import hashlib
import secrets
import string
from typing import Optional

import html2text


def generate_random_string(length: Optional[int] = 10) -> str:
    """Generates a random alphanumeric string with `length` chars."""
    char_set = string.ascii_letters + string.digits
    return "".join([secrets.choice(char_set) for i in range(length)])


def hashify(data: str, length: Optional[int] = None) -> str:
    hash_obj = hashlib.sha256(data.encode("utf-8"))
    full_hash = hash_obj.hexdigest()
    return full_hash[:length] if length is not None else full_hash


def generate_external_id(length: Optional[int] = 10, data: Optional[str] = None) -> str:
    if data is not None:
        return hashify(data, length)
    return generate_random_string(length)


def to_markdown(html: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = False
    md = h.handle(html)

    return md.strip()
