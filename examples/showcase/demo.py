"""Run only this isolated showcase's reviewed local source package."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from nestra_showcase.app import main  # noqa: E402 - local source path is set above

if __name__ == "__main__":
    raise SystemExit(main())
