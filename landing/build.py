"""Wrap landing.html (the published fragment) into a standalone index.html for any static host."""
from pathlib import Path

here = Path(__file__).resolve().parent
body = (here / "landing.html").read_text(encoding="utf8")
head_end = body.index("</style>") + len("</style>")
page = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        + body[:head_end] + "\n</head>\n<body>\n" + body[head_end:] + "\n</body>\n</html>\n")
(here / "index.html").write_text(page, encoding="utf8")
print("wrote", here / "index.html")
