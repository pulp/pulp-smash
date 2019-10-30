Release Process
===============

Location: :doc:`/index` → :doc:`/release`

The two goals of the release process are to create a tagged commit which
bumps the version file and describes changes since the last release, and to
generate packages which can be uploaded to PyPI.

There are other ways to create a *release* this one is just an example.

Assumptions
-----------

This release process was created assuming that your **fork** is named **origin**,
and the **upstream** is repository is named **upstream**.

Steps
-----

1. Assume that your master branch is up to date.

.. code-block:: sh

    git checkout master
    git fetch --all
    git merge upstream/master
    git status

2. Clean any unnecessary files. Mainly the ones in **dist** dir.

.. code-block:: sh

    make dist-lean

3. From the root of Pulp Smash dir verify the current version.

.. code-block:: sh

    cat VERSION 

4. From the root of Pulp Smash dir run the script to create a new release.

.. code-block:: sh

    git status
    ./scripts/release.sh 'string_new_version'

5. Sanity check the dist dir.

.. code-block:: sh

    ls dist/

6. A new commit was added by the script, and VERSION file should be updated.
Verify that **HEAD** is pointing to the right commit.

.. code-block:: sh

    cat VERSION 
    git show HEAD


7. Push to Github. Verify that files were updated and a new TAG was created.

.. code-block:: sh

    git push origin master --tags && git push upstream master --tags

8. Upload to PyPI. Assure that your have the twine package in your Python
env.

.. code-block:: sh

    twine upload dist/*

9. Go to PyPI and verify that files were uploaded properly.
