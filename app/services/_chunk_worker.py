"""子进程 worker：结果 JSON → stdout，错误 → stderr，日志 → 文件"""

import json
import logging
import sys

from app.core.logging import setup_logging


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: _chunk_worker.py <file_path>", file=sys.stderr)
        sys.exit(1)

    setup_logging()
    for h in list(logging.getLogger().handlers):
        if type(h) is logging.StreamHandler:
            logging.getLogger().removeHandler(h)

    from app.services.rag_chunk import document_chunk

    chunks = document_chunk(sys.argv[1])
    json.dump(chunks, sys.stdout, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
