import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.main import validate


def main() -> None:
    folder = validate("folders", {"name": " 阅读 ", "sortOrder": "2"})
    assert folder == {"name": "阅读", "sortOrder": 2}

    folder = validate("folders", {"name": "工具", "sortOrder": "-4"})
    assert folder["sortOrder"] == 0

    folder = validate("folders", {"name": "灵感"})
    assert folder == {"name": "灵感"}


if __name__ == "__main__":
    main()
