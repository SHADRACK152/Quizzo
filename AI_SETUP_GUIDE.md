# QUIZZO AI Configuration Guide

## Setting up OpenRouter API for AI Question Generation

### Option 1: Get OpenRouter API Key (Recommended)

1. **Visit OpenRouter**: Go to https://openrouter.ai/
2. **Create Account**: Sign up for a free account
3. **Get API Key**: Go to Settings → API Keys and create a new key
4. **Add Credits**: Visit Settings → Credits and purchase credits (starts from $5)
5. **Set Environment Variable**: 
   - Windows: `set OPENROUTER_API_KEY=your_api_key_here`
   - Or create a `.env` file in the QUIZZO folder with: `OPENROUTER_API_KEY=your_api_key_here`

### Option 2: Use Built-in Fallback Questions

If you don't want to use AI, the system will automatically use built-in question templates for:
- Medicine/Biology
- Mathematics  
- Science
- History
- And more topics

### Current Status

✅ **Fallback System Active**: The system is currently using built-in question templates
⚠️ **AI Unavailable**: OpenRouter API key not configured or insufficient credits

### Features Available Without API:
- ✅ Question generation using templates
- ✅ Multiple choice, True/False, and Text questions
- ✅ Topic-based question selection
- ✅ Difficulty levels
- ✅ All exam creation features
- ✅ Student assessment functionality

### Features Available With API:
- 🤖 AI-generated custom questions
- 🧠 Intelligent topic analysis
- 📚 Context-aware question creation
- 🎯 Advanced difficulty calibration
- 💡 Educational explanations
- 🔄 Unlimited question variety

### Test the System

Try creating an exam now! The system will:
1. Use built-in questions if no API key is configured
2. Show a message about using templates
3. Still provide high-quality educational content

## Troubleshooting

### Common Issues:
1. **"Insufficient credits"** → Add credits to your OpenRouter account
2. **"API key not found"** → Set the OPENROUTER_API_KEY environment variable
3. **"Request timeout"** → Check your internet connection

### Environment Variable Setup:

**Windows (Command Prompt):**
```cmd
set OPENROUTER_API_KEY=or-v1-your-key-here
python app.py
```

**Windows (PowerShell):**
```powershell
$env:OPENROUTER_API_KEY="or-v1-your-key-here"
python app.py
```

**Create .env file:**
Create a file named `.env` in the QUIZZO folder:
```
OPENROUTER_API_KEY=or-v1-your-key-here
SECRET_KEY=your-secret-key-here
```

### Restart Required
After setting the environment variable, restart the application:
```cmd
python app.py
```

## Need Help?

The system works perfectly with or without the API. The fallback questions are professionally crafted and suitable for educational use.