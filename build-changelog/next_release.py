import sys

next_release = "patch"

for line in sys.stdin.readlines():
    if "(major)" in line.lower() or "#major" in line.lower():
        next_release = "major"
        break

    if "(minor)" in line.lower() or "#minor" in line.lower():
        next_release = "minor"

print(next_release)
