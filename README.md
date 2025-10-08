<div align="center">

# 🎓 QUIZZO
### AI-Powered Educational Assessment Platform with Mobile-Responsive Chatbot

[![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![AI Powered](https://img.shields.io/badge/AI-Powered-ff6b6b?style=for-the-badge&logo=openai&logoColor=white)](https://github.com/SHADRACK152/Quizzo)
[![Mobile Ready](https://img.shields.io/badge/Mobile-Ready-4ecdc4?style=for-the-badge&logo=mobile&logoColor=white)](https://github.com/SHADRACK152/Quizzo)
[![Live Demo](https://img.shields.io/badge/Live-Demo-success?style=for-the-badge&logo=render&logoColor=white)](https://quizzo-9ryy.onrender.com/)

**🚀 Next-generation educational assessment platform with AI-powered course generation, virtual classrooms, intelligent proctoring, and ChatGPT-like mobile chatbot.**

[✨ Live Demo](https://quizzo-9ryy.onrender.com/) • [🤖 AI Chatbot](https://quizzo-9ryy.onrender.com/dashboard) • [🐛 Report Bug](https://github.com/SHADRACK152/Quizzo/issues) • [💡 Request Feature](https://github.com/SHADRACK152/Quizzo/issues)

</div>

---

## 🌟 **What Makes QUIZZO Special?**

<table>
<tr>
<td width="50%">

### � **ChatGPT-Like AI Chatbot**
- **Mobile-Responsive Design** optimized for phones & tablets
- **Touch-Friendly Interface** with prominent send button
- **Swipe Navigation** for seamless mobile experience
- **Real-time AI Assistance** for learning support

### �🧠 **AI-First Approach**
- **Smart Content Generation** with subject expertise
- **Intelligent Question Banking** with auto-difficulty scaling
- **Quality Assurance System** with 100-point scoring
- **Multi-AI Integration** (Groq, OpenAI, Cohere, HuggingFace)

</td>
<td width="50%">

### 📱 **Mobile-First Experience**
- **Responsive Design** works perfectly on all devices
- **Progressive Web App** capabilities
- **Touch Optimized** with 44px+ touch targets
- **Cross-Platform Compatibility** (iOS, Android, Desktop)

### 🏫 **Virtual Learning Hub**
- **Real-time Video Conferencing** with WebRTC
- **Interactive Collaboration Tools** and live chat
- **Screen Sharing & Recording** capabilities
- **Session Analytics** and engagement tracking

</td>
</tr>
<tr>
<td width="50%">

### 🛡️ **Smart Proctoring**
- **AI-Powered Monitoring** with behavior analysis
- **Anti-Cheating Detection** (tab switching, face recognition)
- **Real-time Alerts** and violation tracking
- **Automated Reporting** with detailed insights

</td>
<td width="50%">

### 🎯 **Personalized Experience**
- **Adaptive Learning Paths** based on performance
- **Gamification System** with achievements & leaderboards
- **Progress Analytics** with detailed insights
- **Multi-Role Support** (Students, Lecturers, Admins)

</td>
</tr>
</table>

---

## 📱 **Mobile Chatbot Features**

<div align="center">

| Feature | Mobile | Desktop | Description |
|---------|--------|---------|-------------|
| 🎨 **Responsive Layout** | ✅ | ✅ | Adapts perfectly to any screen size |
| 👆 **Touch-Friendly** | ✅ | ✅ | Large buttons (44px+) for easy tapping |
| 🎭 **Swipe Gestures** | ✅ | ❌ | Swipe to open/close sidebar |
| 📤 **Prominent Send Button** | ✅ | ✅ | Color-coded, animated send button |
| 🎪 **ChatGPT-Like Interface** | ✅ | ✅ | Familiar, intuitive design |
| 💬 **Real-time AI Chat** | ✅ | ✅ | Instant responses with typing indicators |

</div>

---

## 🚀 **Quick Start Guide**

### 🌐 **Try the Live Demo**

<div align="center">

**🎉 QUIZZO is now live and fully deployed!**

[![Live Demo](https://img.shields.io/badge/🚀_Live_Demo-Visit_Now-success?style=for-the-badge&logo=render)](https://quizzo-9ryy.onrender.com/)

**📱 Test the Mobile Chatbot:** [quizzo-9ryy.onrender.com/dashboard](https://quizzo-9ryy.onrender.com/dashboard)

</div>

### 🎯 **Demo Accounts**
```
👨‍🎓 Student: student@demo.com / password123
👨‍🏫 Lecturer: lecturer@demo.com / password123  
👨‍💼 Admin: admin@demo.com / password123
```

---

## 🛠️ **Local Development Setup**

<details>
<summary><b>📋 Prerequisites</b></summary>

```bash
✅ Python 3.12 or higher
✅ pip package manager
✅ SQLite (included with Python)
✅ Git (for cloning)
```

</details>

### **⚡ One-Click Local Setup**

```bash
# 1️⃣ Clone & Navigate
git clone https://github.com/SHADRACK152/Quizzo.git && cd Quizzo

# 2️⃣ Setup Environment
python -m venv .venv && .venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# 3️⃣ Install Dependencies
pip install -r requirements.txt

# 4️⃣ Configure Environment (Optional)
cp .env.example .env
# Edit .env with your AI API keys for enhanced features

# 5️⃣ Launch QUIZZO Locally
python app.py
```

<div align="center">

🎉 **Local Development:** Visit `http://localhost:5000`  
📱 **Mobile Testing:** Use browser dev tools to test mobile interface

</div>

---

## 🚀 **Deployment**

<div align="center">

### **Production Deployment on Render.com**

✅ **Automatic Deployment** from GitHub  
✅ **PostgreSQL Database** with Neon integration  
✅ **Python 3.12 Runtime** for optimal performance  
✅ **Mobile-Optimized Configuration**  
✅ **Health Checks & Auto-scaling**  

</div>

### 🔧 **Deployment Features**
- **Zero-Downtime Deploys** with health checks
- **Automatic SSL** certificates  
- **Global CDN** for fast mobile access
- **Database Connection Pooling** for reliability
- **Environment Variable Management**

---

## ⚙️ **Configuration**

<details>
<summary><b>🔧 Environment Variables</b></summary>

Create a `.env` file in your project root:

```env
# 🔑 Security
SECRET_KEY=your-super-secret-key-here
FLASK_ENV=development

# 🤖 AI Services (Optional - Fallback content available)
GROQ_API_KEY=gsk_your_groq_key_here
OPENAI_API_KEY=sk-your_openai_key_here
COHERE_API_KEY=your_cohere_key_here
HUGGINGFACE_API_KEY=hf_your_huggingface_key_here

# 💾 Database
DATABASE_URL=sqlite:///quizzo.db
```

</details>

<details>
<summary><b>🔗 AI Services Setup</b></summary>

| Service | Tier | Speed | Setup Link |
|---------|------|-------|------------|
| **Groq** ⭐ | Free | Ultra Fast | [Get API Key](https://console.groq.com/) |
| **Cohere** | 5M tokens/month | Fast | [Get API Key](https://dashboard.cohere.ai/) |
| **Hugging Face** | Unlimited | Medium | [Get API Key](https://huggingface.co/settings/tokens) |
| **OpenAI** | Premium | Fast | [Get API Key](https://platform.openai.com/) |

> 💡 **Pro Tip**: AI services are optional! QUIZZO includes comprehensive fallback content for all subjects.

</details>

---

## 📁 **Project Architecture**

<details>
<summary><b>🏗️ Folder Structure</b></summary>

```
Quizzo/
├── 🚀 app.py                   # Core Flask application with mobile optimization
├── � render.yaml             # Production deployment configuration
├── 🐍 .python-version         # Python 3.12 runtime specification
├── �📋 requirements.txt         # Python dependencies (PostgreSQL compatible)
├── 🔧 .env.example            # Environment template
├── 📊 instance/
│   └── quizzo.db              # SQLite database (local development)
├── 🎨 static/
│   ├── style.css              # Main stylesheet with mobile CSS
│   ├── dashboard.js           # Frontend logic
│   └── profile_pics/          # User avatars
├── 🖼️ templates/
│   ├── base.html              # Responsive base layout
│   ├── quizzo_bot.html        # Mobile-responsive chatbot interface
│   ├── auth/                  # Authentication pages
│   ├── dashboard/             # User dashboards  
│   ├── exam/                  # Assessment interfaces
│   └── virtual_classroom/     # Live session pages
└── 📚 docs/
    ├── AI_SETUP_GUIDE.md      # AI integration guide
    ├── QUICK_GROQ_SETUP.md    # Quick start guide
    └── MOBILE_FEATURES.md     # Mobile optimization documentation
```

</details>

---

## 🎮 **User Journeys**

<div align="center">

### 👨‍🎓 **For Students**
🔐 **Login** → 📚 **Browse Courses** → ✅ **Enroll** → 📝 **Take Exams** → 🏫 **Join Virtual Classes** → 📈 **Track Progress**

### 👨‍🏫 **For Lecturers** 
🔐 **Login** → 🤖 **Generate AI Courses** → 📝 **Create Exams** → 🎥 **Host Live Sessions** → 📊 **Monitor Analytics** → 📋 **Review Performance**

### 👨‍💼 **For Administrators**
🔐 **Login** → 👥 **Manage Users** → 🔍 **System Overview** → 📊 **Platform Analytics** → 🛡️ **Content Moderation**

</div>

---

## 🛠️ **Tech Stack**

<div align="center">

| **Category** | **Technologies** |
|-------------|------------------|
| **Backend** | ![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=flat&logo=python&logoColor=white) ![Flask](https://img.shields.io/badge/Flask_2.3-000000?style=flat&logo=flask&logoColor=white) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy_1.4-D71F00?style=flat&logo=sqlalchemy&logoColor=white) |
| **Frontend** | ![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat&logo=html5&logoColor=white) ![CSS3](https://img.shields.io/badge/CSS3_Mobile-1572B6?style=flat&logo=css3&logoColor=white) ![JavaScript](https://img.shields.io/badge/JavaScript_ES6-F7DF1E?style=flat&logo=javascript&logoColor=black) |
| **Database** | ![PostgreSQL](https://img.shields.io/badge/PostgreSQL_Neon-316192?style=flat&logo=postgresql&logoColor=white) ![SQLite](https://img.shields.io/badge/SQLite_Dev-07405E?style=flat&logo=sqlite&logoColor=white) |
| **AI/ML** | ![OpenAI](https://img.shields.io/badge/OpenAI_GPT-412991?style=flat&logo=openai&logoColor=white) ![Groq](https://img.shields.io/badge/Groq_Llama-FF6B35?style=flat&logoColor=white) ![Cohere](https://img.shields.io/badge/Cohere-39A0ED?style=flat&logoColor=white) |
| **Deployment** | ![Render](https://img.shields.io/badge/Render_Cloud-46E3B7?style=flat&logo=render&logoColor=white) ![GitHub](https://img.shields.io/badge/GitHub_Actions-181717?style=flat&logo=github&logoColor=white) |
| **Mobile** | ![PWA](https://img.shields.io/badge/PWA_Ready-5A0FC8?style=flat&logo=pwa&logoColor=white) ![Responsive](https://img.shields.io/badge/Mobile_First-FF6B35?style=flat&logo=mobile&logoColor=white) |

</div>

### 📱 **Mobile Optimization Features**
- ✅ **Responsive Design** with CSS Grid & Flexbox
- ✅ **Touch-Friendly UI** with 44px+ touch targets
- ✅ **Swipe Gestures** for navigation
- ✅ **Progressive Web App** capabilities
- ✅ **Viewport Optimization** for all screen sizes
- ✅ **Performance Optimized** for mobile networks

---

## 🏗️ **System Architecture**

<details>
<summary><b>📊 Database Models</b></summary>

### **Core Models**
- 👤 **User**: Multi-role authentication (Students, Lecturers, Admins)
- 📚 **Course**: Self-paced learning modules with AI generation
- 📝 **Exam**: Multi-format assessments with intelligent grading
- ❓ **Question**: Dynamic question bank with difficulty scaling
- 🎯 **Session**: Exam attempts and virtual classroom tracking

### **Advanced Features**
- 🤖 **AI Templates**: Smart course generation with quality scoring
- 🎮 **Gamification**: Achievement system with points and leaderboards  
- 🛡️ **Monitoring**: Real-time proctoring with behavior analytics
- 💬 **Communication**: Integrated chat and support systems

</details>

<details>
<summary><b>🔒 Security Framework</b></summary>

| **Layer** | **Implementation** |
|-----------|-------------------|
| **Authentication** | 🔐 Werkzeug password hashing + Flask sessions |
| **Input Validation** | 🛡️ SQL injection prevention + sanitization |
| **File Security** | 📁 Secure uploads with filename validation |
| **AI Proctoring** | 👁️ Webcam monitoring + behavior analysis |
| **Anti-Cheating** | 🚫 Tab switching detection + face recognition |

</details>

---

## � **Mobile Chatbot Experience**

<div align="center">

### **Experience the ChatGPT-like AI Assistant**

![Mobile Chatbot Demo](https://img.shields.io/badge/Try_Mobile_Chatbot-Live_Demo-success?style=for-the-badge&logo=mobile)

</div>

### 📱 **Mobile Features**
```javascript
// Swipe right from edge to open sidebar
👆 Swipe Right → 📂 Open Chat History

// Tap anywhere outside to close
👆 Tap Outside → ❌ Close Sidebar  

// Large, prominent send button
👆 Tap Send → 🚀 Instant Response

// Touch-friendly interface
👆 44px+ Touch Targets → ✅ Easy Tapping
```

### 🎨 **Interface Highlights**
- **🎭 Collapsible Sidebar** - Chat history slides in smoothly
- **🎨 Gradient Send Button** - Changes color when enabled
- **💬 Real-time Typing** - See AI thinking with animated dots
- **📱 Mobile-First Design** - Optimized for thumb navigation
- **🌈 Smooth Animations** - Polished, professional feel

### 🧠 **AI Capabilities**
- 📚 **Educational Support** - Homework help & study tips
- 🎯 **Platform Guidance** - QUIZZO features & navigation
- 💡 **Quick Suggestions** - Pre-built common questions
- 🔄 **Context Awareness** - Remembers conversation history
- ⚡ **Instant Responses** - Powered by Groq's ultra-fast LLMs

---

## �🤝 **Contributing**

<div align="center">

**We ❤️ contributions! Join our growing community of developers.**

[![Contributors](https://img.shields.io/github/contributors/SHADRACK152/Quizzo?style=for-the-badge)](https://github.com/SHADRACK152/Quizzo/graphs/contributors)
[![Forks](https://img.shields.io/github/forks/SHADRACK152/Quizzo?style=for-the-badge)](https://github.com/SHADRACK152/Quizzo/network/members)
[![Stars](https://img.shields.io/github/stars/SHADRACK152/Quizzo?style=for-the-badge)](https://github.com/SHADRACK152/Quizzo/stargazers)
[![Issues](https://img.shields.io/github/issues/SHADRACK152/Quizzo?style=for-the-badge)](https://github.com/SHADRACK152/Quizzo/issues)

</div>

### **🚀 Quick Contribution Guide**

```bash
# 1️⃣ Fork the repo
gh repo fork SHADRACK152/Quizzo

# 2️⃣ Create feature branch  
git checkout -b feature/amazing-new-feature

# 3️⃣ Make your changes
# ... code magic happens ...

# 4️⃣ Commit with style
git commit -m "✨ Add amazing new feature"

# 5️⃣ Push & create PR
git push origin feature/amazing-new-feature
```

<details>
<summary><b>📋 Development Guidelines</b></summary>

- ✅ Follow **PEP 8** Python style guide
- ✅ Add **comprehensive tests** for new features  
- ✅ Update **documentation** as needed
- ✅ Ensure **all tests pass** before submitting
- ✅ Use **conventional commits** for better tracking

</details>

## 📈 Roadmap

- [ ] **Mobile App**: React Native mobile application
- [ ] **Advanced Analytics**: Machine learning insights
- [ ] **Integration APIs**: LMS integration capabilities
- [ ] **Multi-language Support**: Internationalization
- [ ] **Advanced Proctoring**: Enhanced AI monitoring
- [ ] **Cloud Deployment**: Docker containerization

## 🐛 Known Issues

- Rate limiting on free AI services during peak usage
- Virtual classroom requires HTTPS for production WebRTC
- Large file uploads may timeout on slow connections

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **AI Services**: Groq, OpenAI, Cohere, Hugging Face
- **Open Source Libraries**: Flask, SQLAlchemy, WebRTC
- **Educational Resources**: Inspired by modern learning platforms

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/SHADRACK152/Quizzo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/SHADRACK152/Quizzo/discussions)
- **Documentation**: Check the `/docs` folder for detailed guides

---

<div align="center">
  <strong>Built with ❤️ for education</strong><br>
  <em>Empowering learning through AI-powered assessment</em>
</div>