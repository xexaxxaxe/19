"""Application entry point: python main.py [--db path/to/archive.db]."""
import argparse
from config import DEFAULT_DB_PATH
from database import initialize
from services import ArchiveService
from ui import ArchiveApp


def main(argv=None):
    parser = argparse.ArgumentParser(description="Настольная система археологического учёта")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Путь к файлу базы SQLite")
    args = parser.parse_args(argv)
    initialize(args.db, seed=True)
    app = ArchiveApp(ArchiveService(args.db))
    app.mainloop()


if __name__ == "__main__":
    main()