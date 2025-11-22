"""Manual script to append QA examples to a LangSmith dataset."""

from __future__ import annotations

from datetime import datetime
from typing import List, Sequence

from langsmith import Client
from langsmith.schemas import Dataset

import dotenv

dotenv.load_dotenv()

DATASET_NAME = "finto-qa-dataset-1"
DATASET_DESCRIPTION = "QA pairs about finto chatbot."

# Update these lists freely; the script will respect whatever is defined here.
inputs: List[str] = [
    "How much profit did I make in Adani Green?",
    "What is the percentage of metal stocks in portfolio?",
]

outputs: List[str] = [
    "You have made **₹649.75** profit in Adani Green.",
    "The metal sector makes up **about 85%** of your total portfolio value.",
]


def _zip_examples(qs: Sequence[str], ans: Sequence[str]) -> tuple[list[dict], list[dict]]:
    if len(qs) != len(ans):
        raise ValueError("Inputs and outputs must be the same length.")
    return [{"question": q} for q in qs], [{"answer": a} for a in ans]


def _prompt_choice() -> str:
    print(
        "\nHow would you like to update the dataset?\n"
        "  [1] Put under the same dataset name without changing the version\n"
        "  [2] Put under the same dataset name with a new version\n"
    )
    while True:
        choice = input("Select option 1 or 2: ").strip()
        if choice in {"1", "2"}:
            return choice
        print("Invalid choice. Please enter 1 or 2.")


def _read_or_create_dataset(client: Client) -> Dataset:
    try:
        return client.read_dataset(dataset_name=DATASET_NAME)
    except Exception:
        return client.create_dataset(dataset_name=DATASET_NAME, description=DATASET_DESCRIPTION)


def _create_new_version_dataset(client: Client) -> Dataset:
    version = input("Enter a dataset version (press Enter to auto-generate): ").strip()
    if not version:
        version = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return client.create_dataset(
        dataset_name=DATASET_NAME,
        dataset_version=version,
        description=DATASET_DESCRIPTION,
    )


def main() -> None:
    client = Client()
    choice = _prompt_choice()
    dataset = (
        _read_or_create_dataset(client) if choice == "1" else _create_new_version_dataset(client)
    )

    example_inputs, example_outputs = _zip_examples(inputs, outputs)
    client.create_examples(
        inputs=example_inputs,
        outputs=example_outputs,
        dataset_id=dataset.id,
    )
    version_info = getattr(dataset, "version", None) or getattr(dataset, "dataset_version", None)
    print(
        f"Stored {len(example_inputs)} examples in dataset '{DATASET_NAME}'"
        + (f" (version: {version_info})" if version_info else "")
    )


if __name__ == "__main__":
    main()
