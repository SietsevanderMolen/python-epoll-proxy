connect:
	ncat 127.0.0.1 8080

run_tests:
	py.test

run_proxy:
	pypy3 relay.py

run_destination:
	ncat -k -l 8081

clean:
	find . -name "*.pyc" -delete
