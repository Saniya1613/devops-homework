#!/bin/bash
# Issue 1: a release is rolled out with an image tag that does not exist
helm upgrade taskboard ../helm/taskboard -n s21-final --reuse-values --set backend.tag=1.0.2
