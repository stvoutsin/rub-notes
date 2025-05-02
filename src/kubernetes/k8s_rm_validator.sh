#!/bin/bash
NAMESPACE=$1

echo "Checking for resources related to namespace: $NAMESPACE"

# Check if namespace still exists
if kubectl get namespace $NAMESPACE &>/dev/null; then
  echo "Namespace $NAMESPACE still exists"
  exit 1
fi


echo "Checking ClusterRoles..."
kubectl get clusterroles -o json | jq -r ".items[] | select(.metadata.name | contains(\"$NAMESPACE\")) | .metadata.name"

echo "Checking ClusterRoleBindings..."
kubectl get clusterrolebindings -o json | jq -r ".items[] | select(.metadata.name | contains(\"$NAMESPACE\")) | .metadata.name"

echo "Checking PersistentVolumes..."
kubectl get pv -o json | jq -r ".items[] | select(.spec.claimRef.namespace == \"$NAMESPACE\") | .metadata.name"

echo "Checking CustomResourceDefinitions..."
kubectl get crd -o json | jq -r ".items[] | select(.metadata.name | contains(\"$NAMESPACE\")) | .metadata.name"

echo "Checking ValidatingWebhookConfigurations..."
kubectl get validatingwebhookconfigurations -o json | jq -r ".items[] | select(.metadata.name | contains(\"$NAMESPACE\")) | .metadata.name"

echo "Checking MutatingWebhookConfigurations..."
kubectl get mutatingwebhookconfigurations -o json | jq -r ".items[] | select(.metadata.name | contains(\"$NAMESPACE\")) | .metadata.name"


echo "Checking Secrets..."
kubectl get secrets --all-namespaces -o json | jq -r ".items[] | select(.metadata.annotations != null and .metadata.annotations | to_entries | map(select(.key | contains(\"$NAMESPACE\"))) | length > 0) | .metadata.name"

echo "Check complete!"
