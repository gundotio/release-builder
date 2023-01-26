import html
import json
import os
import regex
import requests
import sys

DEPLOY_STATUS = os.environ.get("DEPLOY_STATUS", "pending")
GITHUB_ACTOR = os.environ.get("GITHUB_ACTOR", "")
GITHUB_ACTOR_URL = f"https://github.com/{GITHUB_ACTOR}"
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")
GITHUB_REPOSITORY_URL = f"https://github.com/{GITHUB_REPOSITORY}"
GITHUB_RUN_ID = os.environ.get("GITHUB_RUN_ID", "")
GITHUB_RUN_STATUS_ICON = dict(
    failure=os.environ.get("RELEASE_FAILURE_ICON", "❌"),
    pending=os.environ.get("RELEASE_PENDING_ICON", "⏳"),
    success=os.environ.get("RELEASE_SUCCESS_ICON", "🚀"),
).get(DEPLOY_STATUS, os.environ.get("RELEASE_ICON", "🚀"))
GITHUB_RUN_URL = f"{GITHUB_REPOSITORY_URL}/actions/runs/{GITHUB_RUN_ID}"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
MESSAGE_TEMPLATE = os.environ.get("MESSAGE_TEMPLATE", "")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "")
PROJECT_TYPE = os.environ.get("PROJECT_TYPE", "website")
TARGET_NAME = os.environ.get("TARGET_NAME", "")
TARGET_URL = os.environ.get("TARGET_URL", "")

github = requests.Session()
github.headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
}

image_html_re = regex.compile(r'<img.*?alt="(.*?)".*?src="(.*?)".*?>')
image_md_re = regex.compile(r"!\[(.*?)\]\((.*?)\)")
pull_re = regex.compile(rf"{regex.escape(GITHUB_REPOSITORY_URL)}/pull/([0-9]+)")
release_re = regex.compile(
    r"""
    ^\#+\s
    \[(?P<version>.*?)\]\((?P<compare_url>.*?)\)\s
    \((?P<date>.*?)\)$
    """,
    regex.VERBOSE,
)


def build_message():
    user = github.get(f"https://api.github.com/users/{GITHUB_ACTOR}").json()

    actor = user.get("name", GITHUB_ACTOR)
    actor_link = f"[{actor}]({GITHUB_ACTOR_URL})"
    project = f"{PROJECT_NAME} {release['version']}".strip()
    project_link = f"[{project}]({release['compare_url']})"
    run_link = f"[{GITHUB_RUN_STATUS_ICON}]({GITHUB_RUN_URL})"
    target = TARGET_NAME
    target_link = f"[{target}]({TARGET_URL})"
    verb = "released" if PROJECT_TYPE == "package" else "deployed"

    if MESSAGE_TEMPLATE == "images":
        images = get_images(release)

        if not images:
            return

        return {
            "text": f"🚀 {actor} {verb} {project} to {target}",
            "blocks": [
                {
                    "type": "image",
                    "title": {
                        "type": "plain_text",
                        "text": text,
                    },
                    "image_url": url,
                    "alt_text": text,
                }
                for text, url in images
            ],
        }

    return {
        "username": actor,
        "icon_url": user.get("avatar_url", ""),
        "text": f"🚀 {actor} {verb} {project} to {target}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": truncate_message(
                        transform_markdown(
                            f"{run_link} {actor_link} {verb} {project_link} to {target_link}\n{release['notes']}"
                        ),
                    ),
                },
            }
        ],
        "unfurl_links": False,
        "unfurl_media": False,
    }


def find_images(text):
    return image_html_re.findall(text) + image_md_re.findall(text)


def get_images(release):
    images = []

    response = github.get(
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/pulls",
        params=dict(
            per_page=100,
            state="closed",
        ),
    )

    pulls = {pull["number"]: pull for pull in response.json()}

    for pull in release["pulls"]:
        pull = pulls.get(pull)

        if not pull:
            continue

        images.extend(
            [
                (f"{pull['title']} #{pull['number']}: {text}".strip(": "), url)
                for text, url in find_images(pull["body"] or "")
                if "badge" not in url
            ]
        )

    return images


def get_release():
    heading = None
    notes = []

    with open("CHANGELOG.md", "r") as f:
        lines = f.readlines()
        heading = lines[4]
        for line in lines[6:]:
            if line.strip():
                notes.append(line.strip())
                continue
            break

    release = release_re.match(heading).groupdict()

    pulls = [int(pr) for pr in pull_re.findall("".join(notes))]

    notes = "\n".join(notes)

    return dict(**release, notes=notes, pulls=pulls)


def transform_markdown(text):
    """Transform markdown into Slack mrkdwn"""
    text = text.replace("\r\n", "\n")
    # preserve **markdown bold**
    text = text.replace("**", "\\*\\*")
    # convert images and links into slack links
    text = regex.sub(
        r"!?(\[((?:[^\[\]]+|(?1))+)\])(\(((?:[^\(\)]+|(?3))+)\))",
        lambda m: r"<{}|{}>".format(
            m.group(4),
            html.escape(regex.sub(r"\\([\[\]])", r"\1", m.group(2)), quote=False),
        ),
        text,
    )
    # convert lists into bullets
    text = regex.sub(
        r"(?<=^) *[·•●\-\*➤]+\s*(.*)",
        r" *•*  \1",
        text,
        flags=regex.MULTILINE,
    )
    # convert headings into bold
    text = regex.sub(
        r"(?<=^)\n*[#=_]+ *(.*?) *[#=_]* *\n*$",
        r"\n*\1*\n",
        text,
        flags=regex.MULTILINE,
    )
    # convert indentation into code blocks
    text = regex.sub(r"((?:\n {4}.*)+)", r"\n```\1\n```", text)
    text = regex.sub(r"^ {4}", r"", text, flags=regex.MULTILINE)
    # restore **markdown bold** as *slack bold*
    text = text.replace("\\*\\*", "*")
    # single space after periods otherwise sentences can wrap weird
    text = regex.sub(r"\. {2,}", ". ", text)
    return text


def truncate_message(message, max_length=3000):
    message_lines = message.split("\n")
    extra_lines = []

    heading_anchor = f"{release['version']}-{release['date']}".replace(".", "")
    changelog_url = f"{GITHUB_REPOSITORY_URL}/blob/master/CHANGELOG.md#{heading_anchor}"
    more_line = ""

    while len("\n".join(message_lines)) > max_length - len(more_line):
        extra_lines.append(message_lines.pop())
        more_line = transform_markdown(f"+ [{len(extra_lines)} more]({changelog_url})")

    if more_line:
        message_lines.append(more_line)

    return "\n".join(message_lines)


if __name__ == "__main__":
    release = get_release()
    message = build_message()

    if message:
        print(json.dumps(message))
