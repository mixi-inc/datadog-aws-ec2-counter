PYTHON_PATH=/opt/datadog-agent/embedded/bin/

.PHONY: default test

default:
	# do nothing

test:
	PYTHONPATH=checks.d/:tests/dummy/ \
	    ${PYTHON_PATH}python -m unittest -v tests.test_aws_ec2_count

