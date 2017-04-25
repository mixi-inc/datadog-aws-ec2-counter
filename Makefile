PYTHON_PATH=/opt/datadog-agent/embedded/bin/

.PHONY: default test codingrule

default:
	# do nothing

test:
	PYTHONPATH=checks.d/:tests/dummy/ \
	    ${PYTHON_PATH}python -m unittest -v tests.test_aws_ec2_count

codingrule:
	find ./ -name "*.py" | ${PYTHON_PATH}flake8 --config ./.config/flake8

