"""вспомогательные методы для работы с Json"""

import json
from pathlib import Path
from typing import List


def concat_json_files(source_filenames: List[str], target_filename, delete_source_files: bool = False):
    """Конкатенация содержимого набора json files."""
    result = list()
    for filename in source_filenames:
        with open(filename, 'r', encoding="utf-8") as infile:
            result.extend(json.load(infile))

    with open(target_filename, 'w', encoding="utf-8") as output_file:
        json.dump(result, output_file, indent=2, ensure_ascii=False)

    if delete_source_files:
        for filename in source_filenames:
            Path(filename).unlink(True)


          