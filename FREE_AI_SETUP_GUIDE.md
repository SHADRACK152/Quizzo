# 🆓 FREE AI SERVICES SETUP GUIDE

This guide will help you set up **completely free** AI services for question generation in QUIZZO. These services are perfect for researchers and educators!

## 🚀 RECOMMENDED FREE AI SERVICES

### 1. 🥇 **GROQ** (BEST OPTION - Fastest & Free)
- **⚡ Lightning fast inference** (up to 300 tokens/sec)
- **🆓 Generous free tier** - No credit card required
- **🤖 Models**: LLaMA 3, Mixtral, Gemma
- **📊 Rate Limits**: Very generous for research

#### Setup Steps:
1. Visit: https://console.groq.com/
2. Sign up with your email (no credit card needed)
3. Go to "API Keys" section
4. Create a new API key
5. Copy the key and add to your `.env` file:
   ```
   GROQ_API_KEY=gsk_your_api_key_here
   ```

### 2. 🤗 **HUGGING FACE** (Completely Free Forever)
- **🆓 100% Free** - No limits for reasonable use
- **🔬 Perfect for researchers**
- **🤖 Access to thousands of models**
- **📚 Great for educational use**

#### Setup Steps:
1. Visit: https://huggingface.co/
2. Sign up for free account
3. Go to Settings → Access Tokens
4. Create a new token with "Read" permissions
5. Add to your `.env` file:
   ```
   HUGGINGFACE_API_KEY=hf_your_token_here
   ```

### 3. 🌟 **COHERE** (Generous Free Tier)
- **🎯 5 million tokens per month FREE**
- **🏆 High-quality text generation**
- **🎓 Great for educational content**
- **🔧 Easy to use API**

#### Setup Steps:
1. Visit: https://cohere.ai/
2. Sign up for free account
3. Go to Dashboard → API Keys
4. Generate a new API key
5. Add to your `.env` file:
   ```
   COHERE_API_KEY=your_api_key_here
   ```

### 4. 🤝 **TOGETHER AI** (Free Credits)
- **💰 $5 free credits monthly**
- **⚡ Fast inference**
- **🤖 Multiple open-source models**
- **📈 Good for scaling**

#### Setup Steps:
1. Visit: https://api.together.xyz/
2. Sign up for free account
3. Go to API Keys section
4. Create new API key
5. Add to your `.env` file:
   ```
   TOGETHER_API_KEY=your_api_key_here
   ```

## ⚙️ COMPLETE SETUP INSTRUCTIONS

### Step 1: Create Environment File
Create a `.env` file in your QUIZZO project root:

```bash
# Free AI Services (Add any or all of these)
GROQ_API_KEY=gsk_your_groq_key_here
HUGGINGFACE_API_KEY=hf_your_huggingface_token_here
COHERE_API_KEY=your_cohere_key_here
TOGETHER_API_KEY=your_together_key_here

# Optional: Premium services
OPENROUTER_API_KEY=your_openrouter_key_here

# Other settings
SECRET_KEY=your_secret_key_here
```

### Step 2: Install Required Dependencies
Make sure you have the required Python packages:

```bash
pip install python-dotenv requests flask
```

### Step 3: Restart the Application
After adding the API keys, restart your QUIZZO application:

```bash
python app.py
```

## 🎯 HOW IT WORKS

QUIZZO will automatically try the AI services in this order:

1. **🥇 Groq** (Fastest, most reliable)
2. **🤗 Hugging Face** (Always free backup)
3. **🌟 Cohere** (High quality)
4. **🤝 Together AI** (Good performance)
5. **💎 OpenRouter** (Premium fallback)
6. **📚 Template Library** (Final fallback)

## 🔍 TESTING YOUR SETUP

1. Open QUIZZO: http://localhost:5000
2. Login as a lecturer
3. Go to "Create Exam"
4. Try generating questions
5. Check the status indicator to see which service is being used

## 💡 TIPS FOR RESEARCHERS

### For Academic Use:
- **Hugging Face** is completely free and unlimited for research
- **Groq** offers the fastest generation for real-time applications
- **Cohere** provides high-quality outputs for academic content

### For Production:
- Set up multiple services for redundancy
- **Groq** for speed + **Cohere** for quality = perfect combo
- Always keep the template fallback as ultimate backup

### Rate Limiting Best Practices:
- Don't generate more than 20 questions at once
- Space out requests by a few seconds
- Use batch processing for large datasets

## 🆘 TROUBLESHOOTING

### "No AI services available"
- Check your `.env` file is in the correct location
- Verify API keys are correctly formatted
- Restart the Flask application
- Check the console for error messages

### "Questions generated using templates"
- This means all AI services are temporarily unavailable
- Template questions are still high-quality and usable
- Try again in a few minutes

### Rate Limiting Issues:
- Wait a few minutes before trying again
- Use fewer questions per generation
- Switch to a different free service

## 📊 SERVICE COMPARISON

| Service | Speed | Quality | Free Tier | Best For |
|---------|-------|---------|-----------|----------|
| Groq | ⚡⚡⚡⚡⚡ | ⭐⭐⭐⭐ | Very Generous | Real-time |
| Hugging Face | ⚡⚡⚡ | ⭐⭐⭐ | Unlimited | Research |
| Cohere | ⚡⚡⚡⚡ | ⭐⭐⭐⭐⭐ | 5M tokens/month | Quality |
| Together AI | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | $5/month | Scaling |

## 🎓 ACADEMIC BENEFITS

- **No Cost**: Perfect for research budgets
- **High Quality**: AI-generated questions are pedagogically sound
- **Time Saving**: Generate 10-20 questions in seconds
- **Customizable**: Adjust difficulty, type, and topic
- **Reliable**: Multiple fallback options ensure system always works

## 🔐 SECURITY NOTES

- Keep your API keys secure and never commit them to version control
- Use environment variables (`.env` file) for all sensitive data
- Regularly rotate your API keys
- Monitor usage to stay within free tier limits

## 📞 SUPPORT

If you need help setting up any of these services:

1. Check the service's official documentation
2. Look at the QUIZZO console logs for error messages
3. Test each service individually
4. The system will automatically fallback if one service fails

## 🎉 ENJOY FREE AI-POWERED QUESTION GENERATION!

With these free services set up, you'll have access to unlimited, high-quality AI question generation for your educational needs!