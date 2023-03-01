import openai
from flask import Flask, request, jsonify
import os, requests
import logging

# set up logging
logging.basicConfig(level=logging.DEBUG)

# check environment for TYPE and exit if it doesn't exist
if 'TYPE' not in os.environ:
    print('Please set the TYPE environment variable')
    exit(1)

# Set type from environment: type should be OpenAI or Azure
type = os.environ['TYPE']

# check for OpenAI API key in environment and exit if it doesn't exist
if type == 'OpenAI' and 'OPENAI_API_KEY' not in os.environ:
    logging.error('Please set the OPENAI_API_KEY environment variable')
    exit(1)

# check for Azure API key in environment and exit if it doesn't exist
if type == 'Azure' and 'AZURE_API_KEY' not in os.environ:
    logging.error('Please set the AZURE_API_KEY environment variable')
    exit(1)


# Set OpenAI API key from environment
if type == 'OpenAI':
    openai.api_key = os.environ['OPENAI_API_KEY']
    logging.info("Using OpenAI")

# Set Azure API key from environment
if type == 'Azure':
    azure_api_key = os.environ['AZURE_API_KEY']
    logging.info("Using Azure")


# Set up Flask app to run on port 5001
app = Flask(__name__)

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

    # Return generated tweet as JSON response
    return tweet

def generate_azure(text, sentiment):
    # Define Azure prompt
    prompt = f"Write a tweet about {text} and make it {sentiment}"

    payload = {
        "prompt": prompt,
        "max_tokens": 50,
        "temperature": 0.8
    }

    # Call Azure REST API
    # You can use the OpenAI SDK for Python with base, type and version set
    # see https://learn.microsoft.com/en-us/azure/cognitive-services/openai/quickstart?pivots=programming-language-python
    try:
        response = requests.post(
            "https://oa-geba.openai.azure.com/openai/deployments/tweeter/completions?api-version=2022-12-01",
            json=payload,
            headers={
                "api-key": azure_api_key,
                "Content-Type": "application/json"   
            })
        response = response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Response status: {e}")
        return e
        
    logging.debug(f"Response: {response}")

    # Extract tweet
    tweet = response['choices'][0]['text'].strip()

    # Return generated tweet as JSON response
    return tweet

# Run Flask app
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001, debug=True)