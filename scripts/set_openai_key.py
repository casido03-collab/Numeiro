"""Interactive local setup: the key is never passed in command-line arguments."""
import getpass
import os
from pathlib import Path
import re
import tempfile

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def write_key(target: Path, key: str) -> None:
    if not key.startswith("sk-") or len(key) < 20 or any(c.isspace() for c in key):
        raise ValueError("Key format was not recognized; file was not changed.")
    original = target.read_text(encoding="utf-8-sig") if target.exists() else ""
    pattern = r"(?m)^\s*(?:export\s+)?OPENAI_API_KEY\s*=.*$"
    line = "OPENAI_API_KEY=" + key
    if re.search(pattern, original):
        updated = re.sub(pattern, lambda _: line, original)
    else:
        updated = original.rstrip("\n") + ("\n" if original else "") + line + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".env.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(updated)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    import warnings
    # Fail closed if no terminal is available: getpass must not echo the key.
    warnings.simplefilter("error", getpass.GetPassWarning)
    try:
        key = getpass.getpass("OpenAI API key (input hidden): ").strip()
        write_key(ENV_FILE, key)
        print("Saved locally. The key was not displayed or sent anywhere.")
    except (KeyboardInterrupt, EOFError):
        print("Cancelled; file unchanged.")
    except (ValueError, getpass.GetPassWarning) as exc:
        print(str(exc))
    except OSError:
        print("Could not save the file. The key was not displayed.")


if __name__ == "__main__":
    main()
