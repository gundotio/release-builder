import semver
import sys

current_version = semver.VersionInfo.parse(sys.argv[1].lstrip("v"))
next_release = len(sys.argv) > 2 and sys.argv[2] or "patch"

print(getattr(current_version, f"bump_{next_release}")())
