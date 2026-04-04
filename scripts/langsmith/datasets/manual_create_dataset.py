"""Manual script to create or replace a LangSmith dataset from a JSON file.
If a dataset with the same name exists, it will be deleted and recreated."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from langsmith import Client
from langsmith.schemas import Dataset

import dotenv

dotenv.load_dotenv()


def _load_dataset_from_json(dataset_path: Path) -> dict[str, Any]:
    """Load dataset configuration and examples from JSON file."""
    with open(dataset_path, "r") as f:
        return json.load(f)


def _zip_examples(examples: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    """Convert examples from JSON format to LangSmith format."""
    example_inputs = [{"input": ex["input"]} for ex in examples]
    example_outputs = [{"output": ex["output"]} for ex in examples]
    return example_inputs, example_outputs


def _get_or_create_dataset(
    client: Client, dataset_name: str, description: str
) -> Dataset:
    """Get existing dataset or create a new one. If dataset exists, delete it first and create a new one."""
    try:
        existing_dataset = client.read_dataset(dataset_name=dataset_name)
        print(f"⚠️  Dataset '{dataset_name}' already exists. Deleting it...")
        client.delete_dataset(dataset_id=existing_dataset.id)
        print(f"✅ Deleted existing dataset '{dataset_name}'")
    except Exception:
        pass  # Dataset doesn't exist, which is fine

    # Create a new dataset
    return client.create_dataset(dataset_name=dataset_name, description=description)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or replace a LangSmith dataset from a JSON file. "
        "If a dataset with the same name exists, it will be deleted and recreated."
    )
    parser.add_argument(
        "--dataset-file",
        type=str,
        help="Path to the JSON dataset file. "
        "If not provided, defaults to finto-qa-dataset.json in the script directory.",
    )
    args = parser.parse_args()

    # Determine the dataset file path
    if args.dataset_file:
        dataset_path = Path(args.dataset_file)
        if not dataset_path.is_absolute():
            # Resolve relative paths from current working directory (project root)
            # This handles paths like "scripts/langsmith/datasets/file.json" from Makefile
            dataset_path = (Path.cwd() / dataset_path).resolve()
    else:
        # Default to finto-qa-dataset.json in the script directory
        dataset_path = Path(__file__).parent / "finto-qa-dataset.json"

    if not dataset_path.exists():
        print(f"❌ Error: Dataset file not found: {dataset_path}")
        sys.exit(1)

    # Load dataset configuration from JSON
    dataset_config = _load_dataset_from_json(dataset_path)

    # Get dataset name and description from JSON
    dataset_name = dataset_config.get("dataset_name", "unknown-dataset")
    dataset_description = dataset_config.get(
        "dataset_description", "QA pairs about finto chatbot."
    )
    examples = dataset_config.get("examples", [])

    if not examples:
        raise ValueError("No examples found in JSON file.")

    print(f"Dataset name: {dataset_name}")

    client = Client()
    dataset = _get_or_create_dataset(client, dataset_name, dataset_description)

    example_inputs, example_outputs = _zip_examples(examples)
    client.create_examples(
        inputs=example_inputs,
        outputs=example_outputs,
        dataset_id=dataset.id,
    )
    print(f"Stored {len(example_inputs)} examples in dataset '{dataset_name}'")


if __name__ == "__main__":
    main()
