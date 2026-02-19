CONTAINER_NAME = jovial_keldysh

test: 
	pytest -vv

# use
docker-test: 
	docker exec -it $(CONTAINER_NAME) bash -c "cd /root/atlas && source .venv/bin/activate && pytest -vv && deactivate"