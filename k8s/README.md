# Kubernetes Deployment for OpenAI demo

Requires an existing Kubernetes cluster. I deployed AKS with version 1.25.x with 1-3 nodes of 2 CPUs/8GB.

Requires Azure CLI, helm and kubectl, the Kubernetes CLI.

Run `az aks get-credentials -n clustername -g resourcegroup` to get credentials.

## Install Dapr

This requires Dapr on your local machine. See https://dapr.io for more information

Run `dapr init -k` to install Dapr on the cluster via the command line.

Run `dapr dashboard -k` to check the installation on the cluster.

## Install an Ingress Controller

Install a basic configuration of Nginx Ingress controller:

```bash
NAMESPACE=ingress-basic

helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  --create-namespace \
  --namespace $NAMESPACE \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/azure-load-balancer-health-probe-request-path"=/healthz
```

Get the Niginx Ingress service and note the IP address:

`k get service ingress-nginx-controller -n ingress-basic -o jsonpath='{.status.loadBalancer.ingress[0].ip}'`

We will use the IP address together with the nip.io service to create a hostname for our web UI. E.g., ui-20.31.75.31.nip.io

## Install the UI

In `k8s/webui` there are manifests you can use with kustomize. From that folder, run the following command:

```bash
kubectl apply -k .
```

The above command will do the following:
- create the `openai` namespace
- create a deployment, service and ingress in that namespace

⚠️ **Note**: the ingress contains a hostname that should use the IP address of the ingress controller; adjust as needed

## Enable workload identity

Enable the OIDC Issuer on the cluster and create the managed identity:

```bash
CLUSTER=kub-tweet
RG=rg-aks
LOCATION=westeurope
IDENTITY=id-tweet

# this will take a few minutes
az aks update -g $RG -n $CLUSTER --enable-oidc-issuer

export AKS_OIDC_ISSUER="$(az aks show -n $CLUSTER -g $RG --query "oidcIssuerProfile.issuerUrl" -otsv)"
echo Issuer URL: $AKS_OIDC_ISSUER

export SUBSCRIPTION_ID="$(az account show --query "id" -otsv)"
echo Subscription ID: $SUBSCRIPTION_ID

# run this command and check the identity in the portal
az identity create --name $IDENTITY --resource-group $RG \
  --location $LOCATION --subscription $SUBSCRIPTION_ID

# set this client id in the env of the api deployment
export USER_ASSIGNED_CLIENT_ID="$(az identity show -n $IDENTITY -g $RG --query "clientId" -otsv)"
echo Client ID: $USER_ASSIGNED_CLIENT_ID

# kubernetes service account in the openai namespace used in the manifests
SANAME=sa-tweet

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  annotations:
    azure.workload.identity/client-id: ${USER_ASSIGNED_CLIENT_ID}
  labels:
    azure.workload.identity/use: "true"
  name: $SANAME
  namespace: openai
EOF

# create the federated  credentials
az identity federated-credential create --name fc-sademo --identity-name $IDENTITY \
  --resource-group $RG --issuer ${AKS_OIDC_ISSUER} \
  --subject system:serviceaccount:openai:$SANAME

```

## Deploy the API

In deployment.yaml in `./k8s/api` ensure you have the following:
- AZURE_KEY_VAULT_URL: set to a Key Vault URL that contains a secret called `openai-api-key` with a valid OpenAI API key
- MANAGED_IDENTITY_CLIENT_ID: set to the client id of the managed identity created in the above procedure
- spec:serviceAccount set to the same service account name created above (sa-tweet) and that the service account is created in the openai namespace

Assign the managed identity the role to read secrets from the Key Vault referenced by AZURE_KEY_VAULT_URL

Now deploy the API with Kustomize from the `./k8s/api` folder:

```bash
kubectl apply -k .
```





