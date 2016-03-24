#!/bin/bash
set -euo pipefail

# Make sure local fork is updated
git fetch -p --all
git checkout master
git merge --ff-only upstream/master

NEW_VERSION="$(date +%Y.%m.%d)"
OLD_VERSION="$(git tag --list | tail -n 1)"

if [ "${NEW_VERSION}" = "${OLD_VERSION}" ]; then
    echo "Nothing to release"
    exit 0
fi

# Bump version number
echo "${NEW_VERSION}" > VERSION

# Generate the package
make package-clean package

# Sanity check Pulp Smash packages on both Python 2 and Python 3
for python in python{2,3}; do
    venv="$(mktemp --directory)"
    virtualenv -p "${python}" "${venv}"
    set +u
    source "${venv}/bin/activate"
    set -u
    for dist in dist/*; do
        pip install --quiet "${dist}"
        python -m pulp_smash 1>/dev/null
        pip uninstall --quiet --yes pulp_smash
    done
    deactivate
    rm -rf "${venv}"
done

# Get the changes from last release and commit
git add VERSION
git commit -m "Release version ${NEW_VERSION}" \
    -m "Shortlog of commits since last release:" \
    -m "$(git shortlog ${OLD_VERSION}.. | sed 's/^./    &/')"

# Tag with the new version
git tag "${NEW_VERSION}"

fmt <<EOF

This script has made only local changes: it has updated the VERSION file,
generated a new commit, tagged the new commit, and performed a few checks along
the way. If you are confident in these changes, you can publish them with
commands like the following:
EOF

cat <<EOF

    git push --tags origin master && git push --tags upstream master
    make publish

EOF
