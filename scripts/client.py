import openai

# Set your custom OpenAI base URL to your VLLM server
openai.api_base = "https://api.runpod.ai/v2/vllm-caiqtd1nirhws2/openai/v1"

# No API key is required, but you can set one if your server requires authentication
openai.api_key = "EMPTY"  # Set this to your actual key if required

# Fetch available models from the VLLM server
def get_available_models():
    try:
        models = openai.Model.list()
        available_model_ids = [model['id'] for model in models['data']]
        return available_model_ids
    except Exception as e:
        return f"Error fetching models: {str(e)}"

# Generate a chat completion using the specified model and message history
def get_chat_completion(messages, model_id):
    try:
        # Send the request to the VLLM server
        response = openai.ChatCompletion.create(
            model=model_id,  # Use the model ID provided
            messages=messages,
            max_tokens=100  # Adjust as needed
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"Error in generating completion: {str(e)}"

# Example usage
if __name__ == "__main__":
    # Get the list of available models
    available_models = get_available_models()
    print("Available Models:", available_models)

    if available_models and isinstance(available_models, list):
        # Use the first model from the list
        model_id = available_models[0]
        print(f"Using model: {model_id}")

        # Define the chat messages (conversation history)
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Who won the world series in 2020?"},
            {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
            {"role": "user", "content": "Where was it played?"}
        ]

        # Get the chat completion response from the VLLM server
        chat_response = get_chat_completion(messages, model_id)
        print("Chat completion response:", chat_response)
    else:
        print("No available models found.")
