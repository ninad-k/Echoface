"""Unit tests for echoface.util.gpu's HTTP-facing helpers (Ollama
reachability/model-listing/unload), with requests mocked so these run
without a live Ollama server."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from echoface.util.gpu import GpuInfo, ollama_models, ollama_reachable, unload_ollama_model


def test_gpu_info_available_property():
    assert GpuInfo(nvidia_smi_found=True, name="Fake GPU").available is True
    assert GpuInfo(nvidia_smi_found=False).available is False
    assert GpuInfo(nvidia_smi_found=True, error="boom").available is False


@patch("echoface.util.gpu.requests.get")
def test_ollama_reachable_true_on_200(mock_get):
    mock_get.return_value = MagicMock(status_code=200)
    assert ollama_reachable("http://localhost:11434") is True


@patch("echoface.util.gpu.requests.get")
def test_ollama_reachable_false_on_non_200(mock_get):
    mock_get.return_value = MagicMock(status_code=500)
    assert ollama_reachable("http://localhost:11434") is False


@patch("echoface.util.gpu.requests.get", side_effect=requests.RequestException("connection refused"))
def test_ollama_reachable_false_on_exception(mock_get):
    assert ollama_reachable("http://localhost:11434") is False


@patch("echoface.util.gpu.requests.get")
def test_ollama_models_parses_names(mock_get):
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"models": [{"name": "qwen2.5:7b"}, {"name": "llama3.2:3b"}]}
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp
    assert ollama_models("http://localhost:11434") == ["qwen2.5:7b", "llama3.2:3b"]


@patch("echoface.util.gpu.requests.get", side_effect=requests.RequestException("down"))
def test_ollama_models_empty_list_on_error(mock_get):
    assert ollama_models("http://localhost:11434") == []


@patch("echoface.util.gpu.requests.post")
def test_unload_ollama_model_true_on_200(mock_post):
    mock_post.return_value = MagicMock(status_code=200)
    assert unload_ollama_model("qwen2.5:7b") is True


@patch("echoface.util.gpu.requests.post", side_effect=requests.RequestException("down"))
def test_unload_ollama_model_false_on_exception(mock_post):
    assert unload_ollama_model("qwen2.5:7b") is False
