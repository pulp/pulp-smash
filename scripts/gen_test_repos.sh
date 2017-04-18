#!/bin/bash
#
# Build the test repos to be used by Pulp Smash.
#
# This script outputs to the /test_repos/ folder. The built assets should
# never be checked into source control, so that directory is ignored
# using .gitignore.
#
# This script is primarily used by a Jenkins job which builds the assets and
# copies the contents of /test_repos/ to [0].
#
# [0]:  https://repos.fedorapeople.org/repos/pulp/pulp/test_repos
#
# NOTE: This script should be run from the repository root directory. That is,
# this script should be run from this script's parent directory.

if [ ! -f scripts/gen_test_repos.sh ]
then
    echo This script must be run in the top level directory of the pulp-smash repo
    exit 1
fi

# Remove and re-create the test_repos output directory
rm -rf test_repos
mkdir test_repos

######### Individual Repo Generated Below #########

## Make the zoo repo ##
mkdir test_repos/zoo
cp scripts/test_repo_assets/rpm/*.rpm test_repos/zoo/
createrepo -s sha256 \
           -g ../../scripts/test_repo_assets/rpm/comps.xml \
           test_repos/zoo

# Add in an updateinfo.xml file using modifyrepo
modifyrepo --mdtype=updateinfo \
           scripts/test_repo_assets/rpm/updateinfo.xml \
           test_repos/zoo/repodata/

#######################


# Compose from a subset of rpms contained in the zoo_rpms.txt file
# This example assumes one rpm on each line
#
# pushd scripts/test_repo_assets/rpm/
# xargs -a zoo_rpms.txt cp -t ../../../test_repos/zoo/
# popd
