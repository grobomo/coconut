#!/usr/bin/env bash
# T013: RONE poller health check — verify K8s pod is running, show logs
set -euo pipefail

NAMESPACE="${RONE_NAMESPACE:-hackathon-teams-poller}"
KUBECONFIG_PATH="${KUBECONFIG:-$(ls ~/Downloads/*.kubeconfig 2>/dev/null | head -1)}"

if [[ -z "$KUBECONFIG_PATH" ]]; then
    echo "ERROR: No kubeconfig found. Set KUBECONFIG or download from RONE portal."
    exit 1
fi

export KUBECONFIG="$KUBECONFIG_PATH"

echo "=== Cluster Info ==="
kubectl cluster-info 2>&1 || { echo "FAIL: Cannot reach cluster"; exit 1; }

echo ""
echo "=== Pods in $NAMESPACE ==="
kubectl get pods -n "$NAMESPACE" -o wide 2>&1

echo ""
echo "=== Pod Status ==="
kubectl get pods -n "$NAMESPACE" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\t"}{.status.containerStatuses[0].restartCount}{" restarts\n"}{end}' 2>&1

echo ""
echo "=== Recent Logs (last 50 lines) ==="
POD=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [[ -n "$POD" ]]; then
    kubectl logs "$POD" -n "$NAMESPACE" --tail=50 2>&1
else
    echo "No pods found in namespace $NAMESPACE"
fi
