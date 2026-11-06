"""Обёртка запуска: python run.py"""
import subprocess
import sys


def main():
    proc = subprocess.run([sys.executable, "bot.py"])
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
