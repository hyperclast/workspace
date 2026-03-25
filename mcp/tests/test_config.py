"""Tests for config module."""

import os

import pytest

from hyperclast_mcp.config import get_base_url, get_token


class TestGetToken:
    def test_returns_token_from_env(self, monkeypatch):
        monkeypatch.setenv("HYPERCLAST_TOKEN", "tok_abc123")
        assert get_token() == "tok_abc123"

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("HYPERCLAST_TOKEN", "  tok_abc123  \n")
        assert get_token() == "tok_abc123"

    def test_exits_when_missing(self, monkeypatch):
        monkeypatch.delenv("HYPERCLAST_TOKEN", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            get_token()
        assert exc_info.value.code == 1

    def test_exits_when_empty(self, monkeypatch):
        monkeypatch.setenv("HYPERCLAST_TOKEN", "")
        with pytest.raises(SystemExit):
            get_token()

    def test_exits_when_whitespace_only(self, monkeypatch):
        monkeypatch.setenv("HYPERCLAST_TOKEN", "   ")
        with pytest.raises(SystemExit):
            get_token()


class TestGetBaseUrl:
    def test_default_url(self, monkeypatch):
        monkeypatch.delenv("HYPERCLAST_URL", raising=False)
        assert get_base_url() == "https://hyperclast.com"

    def test_custom_url(self, monkeypatch):
        monkeypatch.setenv("HYPERCLAST_URL", "http://localhost:9800")
        assert get_base_url() == "http://localhost:9800"

    def test_strips_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("HYPERCLAST_URL", "http://localhost:9800/")
        assert get_base_url() == "http://localhost:9800"

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("HYPERCLAST_URL", "  http://localhost:9800  ")
        assert get_base_url() == "http://localhost:9800"
