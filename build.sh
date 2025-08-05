docker build -f Dockerfile -t mysql-processor .
docker tag mysql-processor izerui/mysql-processor
docker push izerui/mysql-processor
