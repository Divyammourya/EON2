"""
Pytest collection settings for EON.
"""

collect_ignore = [
    "docs_tree.txt",
    "src_tree.txt",
    "tests_tree.txt",
]

# These two files are Windows-only manual scratch scripts, not real
# pytest tests: they have no test functions, they run at import time,
# and they construct Windows-only objects (pywin32 .lnk shortcut
# resolution) against a hardcoded local path. They break collection on
# every non-Windows machine and CI runner, so we keep pytest from
# collecting them. If you want them back as real tests, give them test
# functions and guard the Windows-only setup behind a skip marker.
collect_ignore += [
    "tests/resource/file_launcher_test.py",
    "tests/resource/resource_launcher_test.py",
]
