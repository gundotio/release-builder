import os
import re
import sys

GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")

repo_url = f"https://github.com/{GITHUB_REPOSITORY}"

lines = []

for line in sys.stdin.readlines():
    match = re.match(rf"^- (.*) #([0-9]+)$", line)

    if match is None:
        lines.append((line.lstrip("- "), []))
        continue

    title = re.sub(r"\s+#?[\(\[]?(major|minor|patch)[\]\)]?", "", match.group(1))
    number = match.group(2)

    if lines and title == lines[-1][0]:
        lines[-1][1].append(number)
        continue

    lines.append((title, [number]))


def render_line(title, prs):
    return f"- {title} {' '.join(render_link(number) for number in prs)}"


def render_link(number):
    return f"[#{number}]({repo_url}/pull/{number})"


print("\n".join(render_line(title, prs) for title, prs in lines))
