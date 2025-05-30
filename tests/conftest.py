"""
Common pytest fixtures for testing.
"""
import os
import pathlib
import shutil
from unittest.mock import patch
import logging

import pytest
import numpy as np
from sentence_transformers import SentenceTransformer


@pytest.fixture
def fixture_path():
    """Return the path to the fixtures directory."""
    return pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_tasks_path(fixture_path):
    """Return the path to the sample TASKS.yaml file."""
    return fixture_path / "sample_tasks.yaml"


@pytest.fixture
def sample_preferences_path(fixture_path):
    """Return the path to the sample PREFERENCES.yaml file."""
    return fixture_path / "sample_preferences.yaml"


@pytest.fixture
def sample_memory_toml_path(fixture_path):
    """Return the path to the sample memory.toml file."""
    return fixture_path / "sample_memory.toml"


@pytest.fixture
def empty_tasks_path(fixture_path):
    """Return the path to the empty TASKS.yaml file."""
    return fixture_path / "empty_tasks.yaml"


@pytest.fixture
def malformed_tasks_path(fixture_path):
    """Return the path to the malformed TASKS.yaml file."""
    return fixture_path / "malformed_tasks.yaml"


@pytest.fixture
def comments_only_tasks_path(fixture_path):
    """Return the path to the TASKS.yaml file with only comments."""
    return fixture_path / "comments_only_tasks.yaml"


@pytest.fixture
def mock_sentence_transformer():
    """Mock the SentenceTransformer class where it is used in memory_utils."""
    # Target where SentenceTransformer is looked up in memory_utils.py
    with patch("scripts.memory_utils.SentenceTransformer") as mock_st_class:
        mock_instance = mock_st_class.return_value
        # Configure the mock instance, e.g., encode, get_sentence_embedding_dimension
        mock_instance.encode.return_value = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        mock_instance.get_sentence_embedding_dimension.return_value = 4 # Consistent small dimension for tests
        yield mock_st_class # Yield the mock class itself


@pytest.fixture
def temp_task_file(tmp_path):
    """Create a temporary TASKS.yaml file."""
    task_file = tmp_path / "TASKS.yaml"
    yield task_file
    # Cleanup if needed
    if task_file.exists():
        task_file.unlink()


@pytest.fixture
def temp_vector_store(tmp_path):
    """Create a temporary directory for the vector store."""
    vec_dir = tmp_path / ".cursor" / "vecstore"
    vec_dir.mkdir(parents=True, exist_ok=True)
    yield vec_dir
    # Cleanup
    if vec_dir.exists():
        shutil.rmtree(vec_dir)


@pytest.fixture
def temp_memory_toml(tmp_path, sample_memory_toml_path):
    """Create a temporary memory.toml file."""
    memory_toml = tmp_path / "memory.toml"
    # Copy sample memory.toml to temporary file
    shutil.copy(sample_memory_toml_path, memory_toml)
    yield memory_toml
    # Cleanup
    if memory_toml.exists():
        memory_toml.unlink()


@pytest.fixture(autouse=True)
def configure_logging():
    """Configure logging to ensure caplog fixtures work correctly."""
    # Configure root logger to use a basic format and INFO level
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s  %(name)s:%(module)s.py:%(lineno)d %(message)s',
        force=True  # Override any existing configuration
    )
    # This ensures logs will be captured by caplog fixture
    yield
    # Reset logging configuration after test if needed 