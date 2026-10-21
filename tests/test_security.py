"""Security and robustness: hostile hostnames, ports and file trees must be handled safely."""

import os

import pytest

from qday.safety import InputError, parse_hosts, validate_host, validate_port
from qday.scanner import code as scanner

VALID = [
    ("example.com", "example.com"),
    ("EXAMPLE.com", "example.com"),
    ("example.com.", "example.com"),
    ("  example.com  ", "example.com"),
    ("sub.domain.example.co.in", "sub.domain.example.co.in"),
    ("xn--bcher-kva.example", "xn--bcher-kva.example"),
    ("a-b.c-d.org", "a-b.c-d.org"),
    ("https://example.com", "example.com"),
    ("https://example.com/path?q=1", "example.com"),
    ("http://example.com:8443/x", "example.com"),
    ("127.0.0.1", "127.0.0.1"),
    ("10.0.0.255", "10.0.0.255"),
    ("::1", "::1"),
    ("[::1]", "::1"),
    ("2001:db8::1", "2001:db8::1"),
    ("localhost", "localhost"),
    ("a" * 63 + ".com", "a" * 63 + ".com"),
]

INVALID = [
    "", "   ", "-proxy evil:8080", "-connect", "--help", "a b.com", "host;id", "host|cat",
    "host&&ls", "$(whoami).com", "`id`.com", "host\nother", "host\x00.com", "exa_mple.com",
    "-example.com", "example-.com", "a" * 64 + ".com", "x." * 130 + "com", "ftp://example.com",
    "file:///etc/passwd", "javascript:alert(1)", "http://", "https:///path", "..", ".", "example..com",
    "256.1.1.1", "1.2.3", "ex ample.com", "example.com/path",
]


@pytest.mark.parametrize("raw,expected", VALID)
def test_valid_hosts(raw, expected):
    assert validate_host(raw) == expected


@pytest.mark.parametrize("raw", INVALID)
def test_invalid_hosts(raw):
    with pytest.raises(InputError):
        validate_host(raw)


@pytest.mark.parametrize("raw", [None, 123, b"example.com", ["example.com"]])
def test_non_string_hosts(raw):
    with pytest.raises(InputError):
        validate_host(raw)


@pytest.mark.parametrize("port,expected", [(1, 1), (443, 443), ("8443", 8443), (65535, 65535)])
def test_valid_ports(port, expected):
    assert validate_port(port) == expected


@pytest.mark.parametrize("port", [0, -1, 65536, 10**9, "https", "", None, 3.5j, "443; rm"])
def test_invalid_ports(port):
    with pytest.raises(InputError):
        validate_port(port)


def test_parse_hosts_dedupes_and_reports():
    hosts, errors = parse_hosts("a.com\nA.com, https://a.com\n-x\n\nb.org")
    assert hosts == ["a.com", "b.org"]
    assert len(errors) == 1 and errors[0].startswith("-x")


@pytest.mark.parametrize("separator", ["\n", ",", " ", "\t", ",\n", "\r\n"])
def test_parse_hosts_separators(separator):
    hosts, errors = parse_hosts(separator.join(["a.com", "b.com", "c.com"]))
    assert hosts == ["a.com", "b.com", "c.com"] and not errors


# ---------------------------------------------------------------- scanner robustness
def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf8")


def found(tmp_path):
    return [a["algorithm"] for a in scanner.scan_code(str(tmp_path))["assets"]]


def test_missing_folder_raises(tmp_path):
    with pytest.raises(InputError):
        scanner.scan_code(str(tmp_path / "missing"))


def test_file_instead_of_folder_raises(tmp_path):
    write(tmp_path / "a.py", "x = 1")
    with pytest.raises(InputError):
        scanner.scan_code(str(tmp_path / "a.py"))


def test_binary_file_is_skipped(tmp_path):
    write(tmp_path / "blob.py", b"\x00\x01rsa.generate_private_key(key_size=2048)\x00")
    assert found(tmp_path) == []


def test_oversized_file_is_skipped(tmp_path):
    write(tmp_path / "big.py", "hashlib.md5(x)\n" + "#" * (scanner.MAX_FILE_BYTES + 10))
    assert found(tmp_path) == []


def test_non_utf8_file_does_not_crash(tmp_path):
    write(tmp_path / "latin.py", "h = hashlib.md5(b'caf\xe9')\n".encode("latin-1"))
    assert "MD5" in found(tmp_path)


@pytest.mark.parametrize("vendored", sorted(scanner.SKIP_DIRS))
def test_vendored_dirs_are_skipped(tmp_path, vendored):
    write(tmp_path / vendored / "lib.py", "hashlib.md5(x)\n")
    write(tmp_path / "app.py", "hashlib.sha1(x)\n")
    assert found(tmp_path) == ["SHA-1"]


def test_very_long_lines_are_skipped(tmp_path):
    write(tmp_path / "min.js", "var a='" + "x" * 600 + "';crypto.createHash('md5')\n")
    assert found(tmp_path) == []


def test_findings_are_capped(tmp_path):
    write(tmp_path / "many.py", "hashlib.md5(x)\n" * 50)
    res = scanner.scan_code(str(tmp_path), max_findings=10)
    assert res["truncated"] and len(res["assets"]) == 10


def test_env_example_is_scanned(tmp_path):
    write(tmp_path / ".env.example", "JWT_ALG=RS256\n")
    assert "RSA-2048" in found(tmp_path)


def test_symlink_loop_does_not_hang(tmp_path):
    write(tmp_path / "a.py", "hashlib.md5(x)\n")
    try:
        os.symlink(tmp_path, tmp_path / "loop", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks need extra privileges on this OS")
    assert found(tmp_path) == ["MD5"]


def test_symlinked_file_outside_tree_is_not_followed(tmp_path):
    outside = tmp_path / "outside"
    inside = tmp_path / "inside"
    write(outside / "secret.py", "hashlib.md5(x)\n")
    inside.mkdir()
    try:
        os.symlink(outside / "secret.py", inside / "link.py")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks need extra privileges on this OS")
    assert scanner.scan_code(str(inside))["assets"] == []


def test_deep_nesting(tmp_path):
    deep = tmp_path
    for i in range(40):
        deep = deep / f"d{i}"
    write(deep / "x.py", "hashlib.sha1(x)\n")
    assert found(tmp_path) == ["SHA-1"]


def test_empty_folder(tmp_path):
    res = scanner.scan_code(str(tmp_path))
    assert res["assets"] == [] and res["files_scanned"] == 0
