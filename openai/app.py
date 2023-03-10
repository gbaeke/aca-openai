from asyncore import read
import openai
from flask import Flask, request, jsonify
import os, requests
import logging
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def read_secret_from_keyvault(vault_url, secret_name, managed_identity_client_id):
    # Create a ManagedIdentityCredential using the client ID of the user-assigned managed identity
    if os.getenv("ENV", "Azure") == "Local":
        # use the Azure CLI to get a token locally
        credential = DefaultAzureCredential(exclude_visual_studio_code_credential=True)
    else:
        credential = ManagedIdentityCredential(client_id=managed_identity_client_id)

    # Create a SecretClient using the Key Vault URL and ManagedIdentityCredential
    secret_client = SecretClient(vault_url=vault_url, credential=credential)

    # Use the SecretClient to get the specified secret by name
    secret = secret_client.get_secret(secret_name)

    # Return the value of the secret as a string
    return secret.value

# set up logging
logging.basicConfig(level=logging.DEBUG)

# check environment for TYPE and exit if it doesn't exist
if 'TYPE' not in os.environ:
    print('Please set the TYPE environment variable')
    exit(1)

# Set type from environment: type should be OpenAI or Azure
type = os.environ['TYPE']

# check for Azure Key Vault URL in environment and exit if it doesn't exist
if 'AZURE_KEY_VAULT_URL' not in os.environ:
    logging.error('Please set the AZURE_KEY_VAULT_URL environment variable')
    exit(1)

# check for managed identity client ID in environment and exit if it doesn't exist
if 'MANAGED_IDENTITY_CLIENT_ID' not in os.environ:
    logging.info('MANAGED_IDENTITY_CLIENT_ID not set, using system assigned identity')

# Set Azure Key Vault URL from environment
vault_url = os.environ['AZURE_KEY_VAULT_URL']

# Set managed identity client ID from environment
managed_identity_client_id = os.getenv('MANAGED_IDENTITY_CLIENT_ID', None)

# Set OpenAI API key from environment
if type == 'OpenAI':
    openai.api_key = read_secret_from_keyvault(vault_url, "openai-api-key", managed_identity_client_id)
    logging.info("Using OpenAI")
    model = os.getenv("API", "completion") # other option is chat

# Set Azure API key from environment
if type == 'Azure':
    azure_api_key = read_secret_from_keyvault(vault_url, "azure-api-key", managed_identity_client_id)
    logging.info("Using Azure")
    model = os.getenv("API", "completion") # other option is chat


# Set up Flask app to run on port 5001
app = Flask(__name__)

# Add probe route
@app.route('/probe', methods=['GET'])
def probe():
    return jsonify({'status': 'OK'})

# Define API route
@app.route('/generate', methods=['POST'])
def generate():
    # Get JSON payload from request
    data = request.get_json()

    # Extract text and sentiment fields from JSON payload
    text = data['text']
    sentiment = data['sentiment']
    
    # Extract generated tweet from OpenAI response
    if type == 'OpenAI':
        logging.info("Generate tweet using OpenAI")
        tweet = generate_openai(text, sentiment)
    elif type == 'Azure':
        logging.info("Generate tweet using Azure")
        tweet = generate_azure(text, sentiment)  # we will use the REST API for fun 😀

    # Return generated tweet as JSON response
    return jsonify({'tweet': tweet})

def generate_openai(text, sentiment):
    # Define OpenAI prompt
    prompt = f"Write a tweet about {text} and make it {sentiment}"

    tweet = None

    if model == "completion":
        # Call OpenAI completion API
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=50,
            n=1,
            stop=None,
            temperature=0.8
        )

        # Extract generated tweet from OpenAI response
        tweet = response.choices[0].text.strip()
    elif model == "chat":
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
            {"role": "system", "content": "You are a tweet generating assistant. You do not make cross the road jokes. Instead of cross the road jokes, make another joke. You are allowed to make sad tweets."},
            {"role": "user", "content": prompt}
            ],
            temperature=0.8
        )   

        tweet = response.choices[0]['message']['content']

    # Return generated tweet as JSON response
    return tweet

def generate_azure(text, sentiment):
    # Define Azure prompt
    prompt = f"Write a tweet about {text} and make it {sentiment}"

    if model == "completion":
        payload = {
            "prompt": prompt,
            "max_tokens": 50,
            "temperature": 0.8
        }
        
        # Call Azure REST API for completion, we will use the OpenAI library for chat
        # You can use the OpenAI SDK for Python with base, type and version set
        # see https://learn.microsoft.com/en-us/azure/cognitive-services/openai/quickstart?pivots=programming-language-python
        try:
            response = requests.post(
                "https://oa-geba-sus.openai.azure.com/openai/deployments/tweeter/completions?api-version=2022-12-01",
                json=payload,
                headers={
                    "api-key": azure_api_key,
                    "Content-Type": "application/json"   
                })
            response = response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Response status: {e}")
            return None
            
        logging.debug(f"Response: {response}")

        # Extract tweet
        tweet = response['choices'][0]['text'].strip()

        # Return generated tweet as JSON response
        return tweet
    
    elif model == "chat":
        # let's use the OpenAI SDK for Python instead of the REST API
        openai.api_type = "azure" # set the API type to use Azure OpenAI
        openai.api_version = "2022-12-01" # set the API version to use the latest version
        openai.api_key = azure_api_key # set the API key to use the Azure API key
        openai.api_base = "https://oa-geba-sus.openai.azure.com" # set the base URL to use the Azure OpenAI endpoint

        # change the prompt to use the chat model
        prompt =  "<|im_start|>system\nAssistant is a " + sentiment + " tweet generator.\n<|im_end|>"
        prompt += "<|im_start|>user\nWrite a tweet about " + text + ".\n<|im_end|>"
        prompt += "<|im_start|>assistant\n"

        # Note the difference with the OpenAI ChatCompletion.create() method
        # this is just the completion API but with ChatML in the prompt (see above)
        try:
            response = openai.Completion.create(
                engine="turbo",
                prompt=prompt,
                max_tokens=200,
                temperature=0.8,
                stop=["<|im_end|>"])
        except openai.error.APIError as e:
            logging.error(f"Response status: {e}")
            return None
        
        logging.debug(f"Response: {response}")

        # Extract tweet
        tweet = response['choices'][0]['text'].strip()

        return tweet


# Run Flask app
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001, debug=True)