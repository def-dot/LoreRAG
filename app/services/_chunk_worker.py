"""子进程 worker：运行 document_chunk，结果 JSON → stdout，错误 → stderr"""

import json
import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: _chunk_worker.py <file_path>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    try:
        from app.services.rag_chunk import document_chunk

        chunks = document_chunk(file_path)
        json.dump(chunks, sys.stdout, ensure_ascii=False, default=str)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
