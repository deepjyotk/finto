from collections import Counter


def get_errors_frequency(file_path: str) -> Counter:

    counter  = Counter[str]()

    with open(file_path, 'r') as file:

        for line in file:
            line = line.strip()

            if not line:
                continue

            if ":" in line:
                level, error_type = line.split(":",1)

                counter[error_type] += 1


    return counter



print(get_errors_frequency("logs.txt"))



