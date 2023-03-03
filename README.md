# Azure Container Apps Demo: OpenAI Tweet Generator

## Introduction

This demo shows how to deploy a simple web app that uses the [OpenAI API](https://platform.openai.com/) to generate tweets based on a given prompt. The app is built using [Flask](https://flask.palletsprojects.com/en/1.1.x/) and [Bootstrap](https://getbootstrap.com/).

Because this is mainly an Azure Container Apps demo, the app is not very sophisticated. The call to the OpenAI model could have been implemented in the Flask UI app. For demonstration purposes, a separate Container App is used to call the OpenAI API. The UI app calls the API app with the help of Dapr. Find more information about Dapr here: [https://dapr.io/](https://dapr.io/).

## Prerequisites

- Azure subscription
- [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli)
- [Docker](https://docs.docker.com/get-docker/)
- OpenAI API key or Azure OpenAI API key
- Github account to fork this repo and run the workflows

## Create container images for first deployment

Before deploying the infrastructure with Bicep, build the Docker images and push them to Docker Hub. Use the following commands from the root of this repo:

```bash
# login to Docker Hub
docker login

cd ./webui
docker build -t <dockerhub-username>/openaiui:latest .
docker push <dockerhub-username>/openaiui:latest

cd ../openai
docker build -t <dockerhub-username>/openaiapi:latest .
docker push <dockerhub-username>/openaiapi:latest
```

In `main.bicep`, find the references to the container images and replace them with the Docker Hub images. For example, for the UI, replace `${acr.properties.loginServer}/openaiui:latest` with `<dockerhub-username>/openaiui:latest`. Do the same for the API.

## Deploy Azure OpenAI

To use Azure OpenAI, you have to request access. In the portal, try to create an Azure OpenAI resource. If you don't have access, you will see a link to a page where you can request access. After you have access, create an Azure OpenAI resource.

Once you have access, deploy the `text-davinci-003` model and call it `tweeter`. Grab the value of KEY 1 and the endpoint URL from the `Keys and Endpoint` tab of the Azure OpenAI resource. You will need these values in the next steps.

In `./openai/main.py`, find the following lines:

```python
try:
    response = requests.post(
        "https://oa-geba.openai.azure.com/openai/deployments/tweeter/completions?api-version=2022-12-01",
        json=payload,
        headers={
            "api-key": azure_api_key,
            "Content-Type": "application/json"   
        })
    response = response.json()
```

Replace `oa-geba.openai.azure.com` with the endpoint URL of your Azure OpenAI resource.


You will need the key in the following section where you deploy the infrastructure. The key will be saved as a secret in Key Vault.

## Optional: Use the OpenAI API

If you cannot get access to Azure OpenAI, get an account at OpenAI and create your own API key. Use that key in the following section where you deploy the infrastructure. The key will be saved as a secret in Key Vault.

## Deploy infrastructure

Use Bicep to deploy the infrastructure. From the root of this repo, run the following commands:

```bash
RG=rg-aca-openai
LOCATION=westeurope
PREFIX=ai
AZURE_OPENAI_KEY="Your Azure OpenAI API key"
OPENAI_KEY="Your OpenAI API key"

az group create --name $RG --location $LOCATION

az deployment group create -g $RG -f ./deploy/main.bicep \
    --parameters parPrefix=$PREFIX \
    --parameters parLocation=$LOCATION \
    --parameters parAzureApiKey=$AZURE_OPENAI_KEY \
    --parameters parOpenAiApiKey=$OPENAI_KEY
```

Note that the API can use either the OpenAI API or the Azure OpenAI API. In the deployment of the API, the `TYPE` environment variable can be set to `Azure` to use Azure OpenAI. In that case you need the Azure OpenAI API key. The other key can be left empty. If you set `TYPE` to `OpenAI`, you need the OpenAI API key.

Now that the infrastructure is deployed, check the name of the `Azure Container Registry` that was deployed. It will be something like `aiacr<random-string>`. You will need this name in the next step.

## Modify the GitHub Workflows

In `.github/workflows`, there are two workflows: `build-api.yml` and `build-ui.yml`. The first one builds the API container image and pushes it to the ACR. The second one builds the UI container image and pushes it to ACR. You need to modify the workflows to use the ACR name that was deployed in the previous step.

In both yml files, find the following line:

```yaml
env:
  PREFIX: <MATCH TO YOUR PREFIX>
  RG: <MATCH TO YOUR RESOURCE GROUP>
  ACR: <MATCH TO YOUR ACR SHORT NAME.azurecr.io>
```

Now run both workflows from the GitHub Actions tab in your forked repo. They can be run manually because they use the `workflow_dispatch` trigger. The workflows will build the container images and push them to the ACR. After that, `az containerapp update` is used to update the container images in the container apps.

If you want, you can also update `main.bicep` to use the ACR that was deployed.

## Setup the GitHub Secrets

Setup the following secrets in your forked repo:
- ACR_USERNAME: the short name of the ACR
- ACR_PASSWORD: the password of the ACR
- AZURE_SUBSCRIPTION_ID: the subscription ID of the subscription where the infrastructure was deployed
- AZURE_TENANT_ID: the Azure tenant ID
- AZURE_CLIENT_ID: the Azure client ID of the app registration used for OIDC authentication

To setup GitHub for OIDC authentication to Azure, follow the instructions here: https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure?tabs=azure-portal

To retrieve the subscription ID and tenant ID, run the following commands:

```bash
az account show --query id --output tsv
az account show --query tenantId --output tsv
```

To get the name of your ACR in your resource group, run the following command:

```bash
az acr list --resource-group <resource-group-name> --query "[].name" --output tsv
```

To get the ACR password, run the following command:

```bash
az acr credential show --name <acr-name> --query passwords[0].value --output tsv
```


## Test the app

In the `ai-webui` container app (assuming your prefix is `ai`), find the Application Url. Open the URL in a browser and test the app.