#!/bin/bash

set -e

pip install -e /openedx/requirements/app
pip install pytest-cov genbadge[coverage]

cd /openedx/requirements/app
cp /openedx/edx-platform/setup.cfg .
sed -i '/--json-report/c addopts = --nomigrations --reuse-db --durations=20 --json-report --json-report-omit keywords streams collectors log traceback tests --json-report-file=none --cov=search/ --cov-report term-missing --cov-report xml:reports/coverage/coverage.xml --cov-fail-under 0' setup.cfg

mkdir test_root
cd test_root/
ln -s /openedx/staticfiles .

cd /openedx/requirements/app

DJANGO_SETTINGS_MODULE=lms.envs.test EDXAPP_TEST_MONGO_HOST=mongodb pytest search/tests/tests.py

echo "[run]\nomit = search/migrations/*" > .coverage
genbadge coverage
