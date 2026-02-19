"""Model discovery utilities for Meta Script agents.

Probes common localhost ports and endpoints for local LLM servers (phi4
style). Returns the first working endpoint and can persist the detected
API URL to `metascript_config.json` in the workspace.
"""
from __future__ import annotations

import json
import os
from typing import Optional

COMMON_HOSTS = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:7860",
    "http://127.0.0.1:7860",
]

COMMON_ENDPOINTS = ["/v1/generate", "/generate", "/v1/completions", "/health", ""]
CONFIG_FILENAME = "metascript_config.json"


def _load_json_safe(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_config() -> dict:
    """Load persistent metascript configuration (returns {} when missing)."""
    path = os.path.join(os.getcwd(), CONFIG_FILENAME)
    cfg = _load_json_safe(path)
    return cfg or {}


def save_config(cfg: dict) -> None:
    """Persist metascript configuration to the workspace."""
    path = os.path.join(os.getcwd(), CONFIG_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def probe_vllm_hosts(timeout: float = 0.8) -> Optional[str]:
    """Return a working API URL (host+endpoint) for a local vllm-like server.

    This performs best-effort HTTP probes on common ports and endpoints and
    returns the first URL that responds with JSON or HTTP 200.
    """
    try:
        import requests
    except Exception:
        return None

    for host in COMMON_HOSTS:
        for ep in COMMON_ENDPOINTS:
            url = host.rstrip("/") + ep
            try:
                if ep in ("/health", ""):
                    r = requests.get(url, timeout=timeout)
                    if r.status_code == 200:
                        return url
                else:
                    r = requests.post(url, json={"input": "ping"}, timeout=timeout)
                    if r.status_code == 200:
                        # accept anything that returns JSON-like content
                        try:
                            _ = r.json()
                            return url
                        except Exception:
                            return url
            except Exception:
                continue
    return None


# -----------------------------
# vLLM auto-start helpers
# -----------------------------
import shutil
import shlex
import subprocess
import time


def is_vllm_installed() -> bool:
    """Return True if a `vllm` executable or Python package is available."""
    if shutil.which("vllm"):
        return True
    try:
        import vllm  # type: ignore
        return True
    except Exception:
        return False


def start_vllm_server(command: str | None = None, cwd: str | None = None) -> subprocess.Popen | None:
    """Start a vllm server using the provided command (or default).

    Returns the subprocess.Popen object on success, or None on failure.
    """
    cmd = command or "vllm serve openai-community/gpt2 --model-imp transformers --host 0.0.0.0 --port 8080"
    # prefer a list for Popen
    try:
        parts = shlex.split(cmd)
        proc = subprocess.Popen(parts, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc
    except Exception:
        return None


def start_vllm_if_missing(command: str | None = None, wait_seconds: float = 10.0) -> Optional[str]:
    """Probe for a running vllm; if missing and vllm is available, start it.

    - If `command` is None, look for a persisted `start_command` in config.
    - Returns the detected API URL or None if not available/started.
    - This is a best-effort helper intended for developer convenience.
    """
    url = probe_vllm_hosts()
    if url:
        return url

    if not is_vllm_installed():
        return None

    # check persisted start command if caller didn't provide one
    if not command:
        cfg = load_config()
        command = cfg.get("start_command")

    proc = start_vllm_server(command)
    if not proc:
        return None

    # wait for the server to start responding
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        url = probe_vllm_hosts(timeout=0.5)
        if url:
            return url
        time.sleep(0.2)

    # failed to start in time
    try:
        proc.terminate()
    except Exception:
        pass
    return None


def configure_vllm(api_url: str, persist: bool = False) -> None:
    """Configure the detected vllm API URL for the current process.

    - Sets the `VLLM_API_URL` environment variable in the running process.
    - If persist=True writes `metascript_config.json` in the current
      working directory so subsequent runs pick it up.
    """
    os.environ["VLLM_API_URL"] = api_url
    if persist:
        cfg = load_config()
        cfg["VLLM_API_URL"] = api_url
        save_config(cfg)


def load_persisted_vllm_url() -> Optional[str]:
    path = os.path.join(os.getcwd(), CONFIG_FILENAME)
    cfg = _load_json_safe(path)
    if not cfg:
        return None
    return cfg.get("VLLM_API_URL")
