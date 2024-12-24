#!/bin/bash

set -e

pip install --src /openedx/venv/src -e /openedx/requirements/app

cd /openedx/requirements/app
cp /openedx/edx-platform/setup.cfg .

mkdir test_root
cd test_root/
ln -s /openedx/staticfiles .

cd /openedx/requirements/app

DJANGO_SETTINGS_MODULE=lms.envs.test EDXAPP_TEST_MONGO_HOST=mongodb pytest search/tests/test.py \
  && \
  rm -rf test_root
