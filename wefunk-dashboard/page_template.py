#!/usr/bin/env python3

"""
Shared HTML helpers for the WEFUNK Dashboard.

This file intentionally starts very small.
For now it simply wraps complete HTML pages.

Later we'll move the shared CSS and JavaScript here as well.
"""

def page(title, body):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
</head>
<body>

{body}

</body>
</html>
"""
