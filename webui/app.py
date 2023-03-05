from flask import Flask, render_template, request
import requests
import os
import logging

# set up logging
logging.basicConfig(level=logging.DEBUG)

# retrieve INVOKE_URL from environment and exit if not set
if 'INVOKE_URL' not in os.environ:
    logging.error('Please set the INVOKE_URL environment variable')
    exit(1)

# set INVOKE_URL from environment
invoke_url = os.environ['INVOKE_URL']



app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    response_status = None
    tweet = None
    text_field = None
    sentiment = None

    # check front door id
    frontdoor_id = request.headers.get('X-Azure-FDID')
    if frontdoor_id:
        logging.info(f"FrontDoor ID: {frontdoor_id}")
    else:
        return render_template('fd.html')

    if request.method == 'POST':
        text_field = request.form['text']
        sentiment = request.form['dropdown']
        payload = {'text': text_field, 'sentiment': sentiment}
        try:
            response = requests.post(invoke_url, json=payload)
            response_status = response.status_code
            # retrieve tweet from response
            tweet = response.json()['tweet']
            logging.info(f"Response status: {response_status}")
        except requests.exceptions.RequestException as e:
            response_status = e
            logging.error(f"Response status: {response_status}")
    return render_template('index.html', response_status=response_status, tweet=tweet, prompt_text=text_field, sentiment=sentiment)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
