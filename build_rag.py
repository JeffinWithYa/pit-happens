"""Entry point: python build_rag.py [--seasons 2024 2025] [--sessions R S]"""

from rag.build_index import main

if __name__ == "__main__":
    raise SystemExit(main())
