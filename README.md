<div align="center">

# 🎓 QUIZZO
### AI-Powered Educational Assessment Platform

[![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![AI Powered](https://img.shields.io/badge/AI-Powered-ff6b6b?style=for-the-badge&logo=openai&logoColor=white)](https://github.com/SHADRACK152/Quizzo)
[![License](https://img.shields.io/badge/License-MIT-4ecdc4?style=for-the-badge)](LICENSE)

**🚀 Next-generation educational assessment platform with AI-powered course generation, virtual classrooms, and intelligent proctoring.**

[✨ Live Demo](https://your-demo-url.com) • [📖 Documentation](https://docs.quizzo.com) • [🐛 Report Bug](https://github.com/SHADRACK152/Quizzo/issues) • [💡 Request Feature](https://github.com/SHADRACK152/Quizzo/issues)

</div>

---

## 🌟 **What Makes QUIZZO Special?**

<table>
<tr>
<td width="50%">

### 🧠 **AI-First Approach**
- **Smart Content Generation** with subject expertise
- **Intelligent Question Banking** with auto-difficulty scaling
- **Quality Assurance System** with 100-point scoring
- **Multi-AI Integration** (Groq, OpenAI, Cohere, HuggingFace)

</td>
<td width="50%">

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

## 🚀 **Quick Start Guide**

<details>
<summary><b>📋 Prerequisites</b></summary>

```bash
✅ Python 3.8 or higher
✅ pip package manager
✅ SQLite (included with Python)
✅ Git (for cloning)
```

</details>

### **⚡ One-Click Setup**

```bash
# 1️⃣ Clone & Navigate
git clone https://github.com/SHADRACK152/Quizzo.git && cd Quizzo

# 2️⃣ Setup Environment
python -m venv .venv && .venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# 3️⃣ Install Dependencies
pip install -r requirements.txt

# 4️⃣ Configure Environment
cp .env.example .env
# Edit .env with your API keys (optional)

# 5️⃣ Launch QUIZZO
python app.py
```

<div align="center">

🎉 **That's it!** Visit `http://localhost:5000` to access QUIZZO

</div>

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
├── 🚀 app.py                   # Core Flask application
├── 📋 requirements.txt         # Python dependencies  
├── 🔧 .env.example            # Environment template
├── 📊 instance/
│   └── quizzo.db              # SQLite database
├── 🎨 static/
│   ├── style.css              # Main stylesheet
│   ├── dashboard.js           # Frontend logic
│   └── profile_pics/          # User avatars
├── 🖼️ templates/
│   ├── base.html              # Base layout
│   ├── auth/                  # Authentication pages
│   ├── dashboard/             # User dashboards  
│   ├── exam/                  # Assessment interfaces
│   └── virtual_classroom/     # Live session pages
└── 📚 docs/
    ├── AI_SETUP_GUIDE.md      # AI integration guide
    └── QUICK_GROQ_SETUP.md    # Quick start guide
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
| **Backend** | ![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white) ![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat&logo=sqlalchemy&logoColor=white) |
| **Frontend** | ![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat&logo=html5&logoColor=white) ![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=flat&logo=css3&logoColor=white) ![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat&logo=javascript&logoColor=black) |
| **Database** | ![SQLite](https://img.shields.io/badge/SQLite-07405E?style=flat&logo=sqlite&logoColor=white) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat&logo=postgresql&logoColor=white) |
| **AI/ML** | ![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat&logo=openai&logoColor=white) ![Groq](https://img.shields.io/badge/Groq-FF6B35?style=flat&logoColor=white) ![Cohere](https://img.shields.io/badge/Cohere-39A0ED?style=flat&logoColor=white) |
| **Real-time** | ![WebRTC](https://img.shields.io/badge/WebRTC-333333?style=flat&logo=webrtc&logoColor=white) ![WebSocket](https://img.shields.io/badge/WebSocket-010101?style=flat&logoColor=white) |

</div>

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

## 🤝 **Contributing**

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