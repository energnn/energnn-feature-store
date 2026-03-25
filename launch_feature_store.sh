cd docker
docker-compose build
docker-compose up postgresql -d
sleep 2
docker-compose up -d
