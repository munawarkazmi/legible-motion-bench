"""Build the anonymised supplementary zip a double-blind submission needs.

    python tools/make_submission_zip.py
    python tools/make_submission_zip.py --out /tmp/supplementary.zip

Reviewers are expected to unzip this and run the code from the README
inside it, so the zip is the artifact rather than a copy of one. Two
things it has to get right at once, and they pull against each other: it
must contain everything needed to run, and it must contain nothing that
says who wrote it. A submission is desk-rejected for the second.

So it is built rather than assembled by hand. Three rules.

Tracked files only. The file list comes from `git ls-files`, so a stray
API key, a half-finished record file or an editor backup in the working
tree cannot travel: if git does not know about it, it does not ship.

The identities are discovered, never written down here. The name, the
address and the repository to scrub come from `git config` and the
remote at run time. Hardcoding them would put them in this file, and
this file is in the zip, which is the kind of mistake that only becomes
obvious afterwards.

Nothing ships unscanned. Every byte that goes in is searched for those
identities first, and a single hit stops the build and names the file
and line. The zip is written last, so a failed run leaves no
half-anonymised artifact lying around to be submitted by accident.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The draft and its working notes carry the author block, the affiliation
# and the reading log. None of it is needed to run the benchmark and all
# of it identifies the author, so it is the one tree left out entirely.
EXCLUDED_PREFIXES = ("paper/",)

# Paper-only tooling. Both write into paper/generated/, which is not in
# the zip, so both would fail if a reviewer ran them, and a tool that
# fails on a clean checkout costs more than the two files are worth here.
EXCLUDED_FILES = ("tools/build_paper_figures.py", "tools/build_paper_results.py")

# Prepended to the README inside the zip. Everything it says is a
# consequence of anonymising, so it is said once, at the top, where a
# reviewer meets it, rather than left for them to infer from a path that
# does not resolve.
SUPPLEMENTARY_NOTE = """<!-- Added when this zip was built; not in the repository. -->
> **About this archive.** This is the supplementary code for an anonymous
> submission. It is the repository with three things taken out, all of
> them for double-blind review and all of them back at camera-ready: the
> paper draft and its working notes under `paper/`, the two tools that
> build the paper's tables and figure, and the name of the copyright
> holder in `LICENSE`, which is otherwise the MIT licence unchanged.
>
> References below to `paper/` resolve in the full repository and not in
> this archive, as does the continuous integration step that reads
> `paper/STATUS.md`. For the same reason two of the tests skip here that
> run in the repository: one checks the committed paper figure, and one
> asks git which record files are committed. `python -m pytest -q`
> reports 248 passed and 2 skipped from this archive rather than the 250
> passed quoted below, and a skip there is the archive being an archive
> rather than anything failing.
>
> Nothing needed to install, run, test or reproduce a number is missing.
> Every command below was run from a clean unpack of this archive.

"""

# Anonymous copyright holder for the licence. The call asks for a clear
# open-source licence, so the licence stays; only the holder is masked,
# and it goes back at camera-ready.
ANONYMOUS_HOLDER = "Anonymous Author(s)"

# Text files worth reading for identities. A binary is checked too, as
# bytes, because PDF metadata and GIF comments both carry names.
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".cfg", ".yml",
    ".yaml", ".bib", ".tex", ".ins", ".dtx", ".bst", "",
}


def git(*args) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def identities() -> list[str]:
    """Who to scrub, taken from the repository rather than from this file."""
    found = []
    for key in ("user.name", "user.email"):
        value = git("config", key).strip()
        if value:
            found.append(value)
            if key == "user.email":
                found.append(value.split("@")[0])
    remote = git("remote", "get-url", "origin").strip()
    match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?$", remote)
    if match:
        owner = match.group(1)
        found.append(owner)
        found.append(f"{owner}/{match.group(2)}")
    # Longest first, so a report names the most specific hit it can.
    return sorted({f for f in found if len(f) > 3}, key=len, reverse=True)


def included_files() -> list[str]:
    names = [n for n in git("ls-files").split("\n") if n]
    return [
        n
        for n in names
        if not n.startswith(EXCLUDED_PREFIXES) and n not in EXCLUDED_FILES
    ]


def anonymised(name: str, data: bytes, holder: str) -> bytes:
    """The licence keeps its terms and loses its holder; the README gains
    a note saying what was taken out and why."""
    if name == "LICENSE":
        text = data.decode("utf-8")
        return re.sub(
            r"(Copyright \(c\) \d{4} ).*", rf"\1{holder}", text, count=1
        ).encode("utf-8")
    if name == "README.md":
        return SUPPLEMENTARY_NOTE.encode("utf-8") + data
    return data


def scan(name: str, data: bytes, patterns: list[str]) -> list[str]:
    hits = []
    suffix = Path(name).suffix.lower()
    if suffix in TEXT_SUFFIXES:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        if text is not None:
            for number, line in enumerate(text.splitlines(), start=1):
                for pattern in patterns:
                    if pattern.lower() in line.lower():
                        hits.append(f"{name}:{number}: {pattern}")
            return hits
    lowered = data.lower()
    for pattern in patterns:
        if pattern.lower().encode("utf-8") in lowered:
            hits.append(f"{name}: {pattern} (in the bytes)")
    return hits


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="supplementary.zip")
    parser.add_argument(
        "--also",
        default="",
        help="extra comma-separated strings to refuse, for anything the "
        "repository's own git metadata does not know about, such as a "
        "personal site or a funder",
    )
    args = parser.parse_args(argv)

    patterns = identities()
    patterns += [p.strip() for p in args.also.split(",") if p.strip()]
    if not patterns:
        raise SystemExit(
            "no identities found to scrub, which means the scan would pass "
            "on anything. Set git config user.name and user.email, or pass "
            "--also, rather than shipping an unchecked zip."
        )
    print("refusing any of:")
    for pattern in patterns:
        print(f"  {pattern}")

    names = included_files()
    dirty = [n for n in git("status", "--porcelain").split("\n") if n.strip()]
    if dirty:
        print(f"\nnote: {len(dirty)} file(s) differ from the last commit;")
        print("      the zip is built from the working tree, not from HEAD.")

    payload, hits = [], []
    for name in names:
        data = (ROOT / name).read_bytes()
        data = anonymised(name, data, ANONYMOUS_HOLDER)
        hits += scan(name, data, patterns)
        payload.append((name, data))

    if hits:
        print(f"\n{len(hits)} identifying hit(s); nothing was written:")
        for hit in hits:
            print(f"  {hit}")
        return 1

    # Referenced but absent, which is not fatal and is worth knowing: a
    # reviewer following a path that is not in the zip reads it as sloppy.
    dangling = set()
    for name, data in payload:
        if Path(name).suffix.lower() not in {".md", ".py", ".toml", ".yml"}:
            continue
        # This file names the excluded prefixes because excluding them is
        # its job. Reporting its own comments as dangling references is
        # noise, and noise in a report is how the real entries stop being
        # read.
        if Path(name).name == Path(__file__).name:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for prefix in EXCLUDED_PREFIXES:
            for match in re.finditer(rf"`?{re.escape(prefix)}[\w./-]*`?", text):
                dangling.add(f"{name}: {match.group(0).strip('`')}")

    out = Path(args.out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in payload:
            # A fixed timestamp, so two builds of the same commit are the
            # same bytes and the zip can be checked rather than trusted.
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"\n{len(payload)} files, {out.stat().st_size:,} bytes -> {out}")
    print(f"sha256 {digest}")
    if dangling:
        print(f"\n{len(dangling)} reference(s) to excluded paths:")
        for item in sorted(dangling):
            print(f"  {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
