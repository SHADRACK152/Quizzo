# 🚀 QUICK GROQ SETUP - 2 MINUTE GUIDE

## Why Groq?
- ⚡ **FASTEST** free AI service (300+ tokens/second)
- 🆓 **COMPLETELY FREE** - no credit card required
- 🤖 **EXCELLENT MODELS** - LLaMA 3, Mixtral, Gemma
- 📚 **PERFECT FOR EDUCATION** - reliable and fast

## Setup Steps (2 minutes):

### Step 1: Get Your Free API Key
1. Visit: https://console.groq.com/
2. Click "Sign Up" (use your email - no credit card needed)
3. Verify your email
4. Go to "API Keys" in the dashboard
5. Click "Create API Key"
6. Copy the key (starts with `gsk_`)

### Step 2: Add to Your Project
1. Open your `.env` file in the QUIZZO folder
2. Add this line:
   ```
   GROQ_API_KEY=gsk_your_actual_key_here
   ```
3. Save the file

### Step 3: Restart QUIZZO
```bash
# Stop the current app (Ctrl+C)
# Then restart:
python app.py
```

### Step 4: Test It!
1. Go to http://localhost:5000/create_exam
2. Check the status indicator (should show Groq as available)
3. Try generating questions - they'll be AI-powered and fast!

## That's it! 🎉

You now have unlimited, lightning-fast AI question generation!

## Alternative: Hugging Face (also completely free)
If you prefer Hugging Face:
1. Go to: https://huggingface.co/settings/tokens
2. Create a token with "Read" permissions
3. Add to .env: `HUGGINGFACE_API_KEY=hf_your_token_here`

## Need Help?
- Check the full guide: FREE_AI_SETUP_GUIDE.md
- Test status: http://localhost:5000/check_ai_status