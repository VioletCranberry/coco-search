#!/bin/bash
set -euo pipefail

echo "Deploying application to production..."

docker build -t myapp:latest .
docker push registry.example.com/myapp:latest

kubectl apply -f k8s/deployment.yaml
kubectl rollout status deployment/myapp
