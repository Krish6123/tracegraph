import sys
from pathlib import Path

from app.parser.ast_parser import (
    extract_entities,
    parse_python_file,
)
from app.scanner.repository import find_python_files


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m app.cli <repository_path>")
        return

    repository_path = sys.argv[1]

    try:
        python_files = find_python_files(repository_path)
    except (FileNotFoundError, NotADirectoryError) as error:
        print(f"Error: {error}")
        return

    print()
    print("================================")
    print("             NEXUS")
    print("       Repository Analyzer")
    print("================================")
    print()

    print(f"Repository: {repository_path}")
    print(f"Python files found: {len(python_files)}")
    print()

    all_entities = []
    next_id = 1

    for file_path in python_files:

        try:
            tree = parse_python_file(Path(file_path))

            entities = extract_entities(
                tree,
                Path(file_path),
                starting_id=next_id,
            )

            all_entities.extend(entities)

            next_id += len(entities)

        except SyntaxError as error:
            print(f"Syntax error: {file_path}")
            print(error)

    print("Entities found:")
    print("--------------------------------")

    for entity in all_entities:
        print(
            f"[{entity.id}] "
            f"{entity.entity_type}: "
            f"{entity.name} "
            f"({entity.file_path}:{entity.line_number})"
        )

    print()
    print(f"Total entities: {len(all_entities)}")


if __name__ == "__main__":
    main()