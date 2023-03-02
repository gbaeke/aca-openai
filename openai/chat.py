import openai

openai.api_key = "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"

response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Write a tweet about Kubernetes and make it funny"}
    ],
    temperature=0.8
)

print(response.choices[0]['message']['content'])