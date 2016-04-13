#!/usr/bin/env bash
#
# For each file found by `find`, generate a reStructuredText document in
# `docs/api/`.
#
set -euo pipefail

find pulp_smash/ tests/ -type f -name '*.py' | while read file_name; do
    # Transform file names to python module names. For example:
    #
    #     tests/__init__.py → tests
    #     tests/test_api.py → tests.test_api
    #
    # Note that file_name has no leading "./", as we omit it in find, above.
    module_name="${file_name%.py}"
    module_name="${module_name%/__init__}"
    module_name="${module_name//\//.}"

    # Generate stub *.rst file. (Tip: ${#foo} returns the length of foo.)
    cat >"docs/api/${module_name}.rst" <<EOF
\`${module_name}\`
$(printf %${#module_name}s | tr ' ' =)==

Location: :doc:\`/index\` → :doc:\`/api\` → :doc:\`/api/${module_name}\`

.. automodule:: ${module_name}
EOF
done
