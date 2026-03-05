#!/bin/bash
# Quick backend status check script

echo "=== Backend Pod Status ==="
kubectl get pods -l app=orbitalviz-backend

echo -e "\n=== Latest Backend Pod ==="
POD=$(kubectl get pods -l app=orbitalviz-backend --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$POD" ]; then
    echo "No running backend pod found"
    echo -e "\nChecking all pods:"
    kubectl get pods -l app=orbitalviz-backend -o wide
else
    echo "Pod: $POD"
    
    echo -e "\n=== Recent Logs ==="
    kubectl logs $POD --tail=20
    
    echo -e "\n=== Testing Backend Endpoint ==="
    kubectl run curl-test-$RANDOM --image=curlimages/curl:latest --rm -i --restart=Never --timeout=10s -- curl -s http://orbitalviz-backend:8000/ --max-time 3
fi
