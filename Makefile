test: pytest -vv

docker-test: docker exec -it jovial_keldysh bash -c "cd /root/atlas && source .venv/bin/activate && pytest -vv && deactivate"