# Provider Model Lists

This directory contains static model lists for providers, matching the Aether project's format.

## File Format

Each JSON file follows the Aether-style format:

```json
{
  "displayName": "Provider Name",
  "baseUrl": "https://api.example.com",
  "apiKeyTemplate": "your_api_key_template",
  "models": [
    {
      "id": "model-id",
      "name": "Model Name",
      "tooltip": "Model description",
      "maxInputTokens": 128000,
      "maxOutputTokens": 4096,
      "sdkMode": "openai",
      "baseUrl": "https://api.example.com",
      "capabilities": {
        "toolCalling": true,
        "imageInput": false
      }
    }
  ]
}
```

## Background Model Fetching

The system implements background model fetching similar to Aether:

1. **Static Models**: JSON files in this directory serve as fallback model lists
2. **Dynamic Fetching**: Providers with `fetch_models=True` attempt to fetch models from their API
3. **Caching**: Fetched models are cached for 6 hours to avoid redundant API calls
4. **Fallback Chain**: Cache → Static File → API Fetch → Config Models

## Usage

To add models for a provider:

1. Create a JSON file named `<provider_id>.json` in this directory
2. The system automatically loads it when the provider is used
3. No configuration changes needed in `known_providers.py`

## Example Files

- `puter.json` - Puter AI models
- `zhipu.json` - Zhipu AI models  
- `deepseek.json` - DeepSeek models
- `moonshot.json` - Moonshot AI models
