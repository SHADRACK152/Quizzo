from app import app, db
import json

with app.app_context():
    # Create all new tables
    db.create_all()
    print("✅ AI Course Generation database tables created successfully!")
    
    # Add some sample AI course templates
    from app import AICourseTemplate, AIQuestionBank, AITopicTemplate
    
    # Sample Python Programming Course Template
    python_template = AICourseTemplate(
        template_name="Complete Python Programming Course",
        subject_area="Python Programming",
        difficulty_level="intermediate",
        total_estimated_hours=40,
        course_description="A comprehensive Python programming course covering fundamentals to advanced topics with practical projects and real-world applications.",
        learning_objectives=json.dumps([
            "Master Python syntax and programming fundamentals",
            "Build web applications with Flask/Django",
            "Work with databases and APIs",
            "Implement object-oriented programming concepts",
            "Create data analysis and visualization projects"
        ]),
        prerequisites=json.dumps(["Basic computer skills", "Understanding of programming concepts"]),
        course_outline=json.dumps([
            {
                "module_number": 1,
                "title": "Python Fundamentals",
                "topics": ["Variables and Data Types", "Control Structures", "Functions"]
            },
            {
                "module_number": 2,
                "title": "Object-Oriented Programming",
                "topics": ["Classes and Objects", "Inheritance", "Polymorphism"]
            }
        ]),
        ai_generated_content=json.dumps({"sample": "content"}),
        usage_count=15,
        rating=4.5
    )
    
    # Sample Data Science Template
    ds_template = AICourseTemplate(
        template_name="Data Science with Python",
        subject_area="Data Science",
        difficulty_level="advanced",
        total_estimated_hours=60,
        course_description="Advanced data science course covering machine learning, data analysis, and visualization using Python libraries.",
        learning_objectives=json.dumps([
            "Master pandas and numpy for data manipulation",
            "Create visualizations with matplotlib and seaborn", 
            "Build machine learning models with scikit-learn",
            "Perform statistical analysis and hypothesis testing",
            "Deploy ML models to production"
        ]),
        prerequisites=json.dumps(["Python programming", "Statistics basics", "Linear algebra"]),
        course_outline=json.dumps([
            {
                "module_number": 1,
                "title": "Data Analysis Fundamentals",
                "topics": ["Pandas Basics", "Data Cleaning", "Exploratory Data Analysis"]
            }
        ]),
        ai_generated_content=json.dumps({"sample": "content"}),
        usage_count=8,
        rating=4.8
    )
    
    # Sample Web Development Template
    web_template = AICourseTemplate(
        template_name="Full-Stack Web Development",
        subject_area="Web Development",
        difficulty_level="intermediate",
        total_estimated_hours=50,
        course_description="Complete web development course covering HTML, CSS, JavaScript, React, Node.js, and database integration.",
        learning_objectives=json.dumps([
            "Master HTML5, CSS3, and modern JavaScript",
            "Build responsive websites with CSS frameworks",
            "Create interactive web applications with React",
            "Develop backend APIs with Node.js and Express",
            "Integrate databases and handle authentication"
        ]),
        prerequisites=json.dumps(["Basic computer literacy", "Understanding of internet concepts"]),
        course_outline=json.dumps([
            {
                "module_number": 1,
                "title": "Frontend Fundamentals",
                "topics": ["HTML5 Structure", "CSS3 Styling", "JavaScript Basics"]
            },
            {
                "module_number": 2,
                "title": "Modern Frontend Development",
                "topics": ["React Components", "State Management", "API Integration"]
            },
            {
                "module_number": 3,
                "title": "Backend Development",
                "topics": ["Node.js Setup", "Express Framework", "Database Operations"]
            }
        ]),
        ai_generated_content=json.dumps({"sample": "content"}),
        usage_count=22,
        rating=4.6
    )
    
    # Sample Machine Learning Template
    ml_template = AICourseTemplate(
        template_name="Machine Learning Fundamentals",
        subject_area="Machine Learning",
        difficulty_level="advanced",
        total_estimated_hours=45,
        course_description="Comprehensive machine learning course covering algorithms, implementation, and real-world applications.",
        learning_objectives=json.dumps([
            "Understand core machine learning concepts and algorithms",
            "Implement ML models from scratch and using libraries",
            "Evaluate and optimize model performance",
            "Apply ML to real-world business problems",
            "Deploy ML models to production environments"
        ]),
        prerequisites=json.dumps(["Python programming", "Statistics", "Linear algebra", "Calculus basics"]),
        course_outline=json.dumps([
            {
                "module_number": 1,
                "title": "ML Fundamentals",
                "topics": ["Introduction to ML", "Types of Learning", "Data Preprocessing"]
            },
            {
                "module_number": 2,
                "title": "Supervised Learning",
                "topics": ["Linear Regression", "Classification", "Decision Trees"]
            }
        ]),
        ai_generated_content=json.dumps({"sample": "content"}),
        usage_count=12,
        rating=4.7
    )
    
    db.session.add(python_template)
    db.session.add(ds_template)
    db.session.add(web_template)
    db.session.add(ml_template)
    
    # Sample AI-generated questions
    sample_questions = [
        {
            "subject_area": "Python Programming",
            "topic_title": "Python Variables",
            "question_text": "What is the correct way to create a variable in Python?",
            "question_type": "multiple_choice",
            "options": ["var x = 5", "int x = 5", "x = 5", "declare x = 5"],
            "correct_answer": "x = 5",
            "explanation": "Python uses dynamic typing, so you simply assign a value to a variable name.",
            "difficulty_level": "beginner",
            "bloom_taxonomy_level": "remember"
        },
        {
            "subject_area": "Python Programming",
            "topic_title": "Object-Oriented Programming",
            "question_text": "True or False: In Python, multiple inheritance is supported.",
            "question_type": "true_false",
            "options": [],
            "correct_answer": "true",
            "explanation": "Python supports multiple inheritance, allowing a class to inherit from multiple parent classes.",
            "difficulty_level": "intermediate",
            "bloom_taxonomy_level": "understand"
        },
        {
            "subject_area": "Data Science",
            "topic_title": "Data Analysis",
            "question_text": "Which pandas method is used to handle missing values?",
            "question_type": "multiple_choice", 
            "options": ["dropna()", "fillna()", "isna()", "All of the above"],
            "correct_answer": "All of the above",
            "explanation": "All three methods are used for handling missing values in different ways.",
            "difficulty_level": "intermediate",
            "bloom_taxonomy_level": "apply"
        },
        {
            "subject_area": "Web Development",
            "topic_title": "JavaScript Fundamentals",
            "question_text": "What does the '===' operator do in JavaScript?",
            "question_type": "multiple_choice",
            "options": ["Assigns a value", "Compares values only", "Compares values and types", "Creates a function"],
            "correct_answer": "Compares values and types",
            "explanation": "The '===' operator performs strict equality comparison, checking both value and type.",
            "difficulty_level": "beginner",
            "bloom_taxonomy_level": "understand"
        },
        {
            "subject_area": "Machine Learning",
            "topic_title": "Supervised Learning",
            "question_text": "What is the main difference between classification and regression?",
            "question_type": "multiple_choice",
            "options": [
                "Classification predicts categories, regression predicts continuous values",
                "Classification is faster than regression",
                "Regression only works with numbers",
                "There is no difference"
            ],
            "correct_answer": "Classification predicts categories, regression predicts continuous values",
            "explanation": "Classification predicts discrete categories/classes, while regression predicts continuous numerical values.",
            "difficulty_level": "intermediate",
            "bloom_taxonomy_level": "analyze"
        },
        {
            "subject_area": "Web Development",
            "topic_title": "React Components",
            "question_text": "True or False: React components must return exactly one root element.",
            "question_type": "true_false",
            "options": [],
            "correct_answer": "false",
            "explanation": "With React 16+, components can return multiple elements using fragments or arrays.",
            "difficulty_level": "intermediate",
            "bloom_taxonomy_level": "remember"
        }
    ]
    
    for q_data in sample_questions:
        question = AIQuestionBank(
            subject_area=q_data["subject_area"],
            topic_title=q_data["topic_title"],
            question_text=q_data["question_text"],
            question_type=q_data["question_type"],
            options=json.dumps(q_data["options"]) if q_data["options"] else None,
            correct_answer=q_data["correct_answer"],
            explanation=q_data["explanation"],
            difficulty_level=q_data["difficulty_level"],
            bloom_taxonomy_level=q_data.get("bloom_taxonomy_level", "understand")
        )
        db.session.add(question)
    
    # Add some topic templates
    topic_templates = [
        {
            "subject_area": "Python Programming",
            "topic_title": "Variables and Data Types",
            "topic_description": "Learn about Python variables, data types, and type conversion",
            "difficulty_level": "beginner",
            "estimated_hours": 2,
            "learning_objectives": ["Understand variable assignment", "Know basic data types", "Perform type conversion"],
            "subtopics": ["Variables", "Strings", "Numbers", "Booleans", "Type conversion"],
            "suggested_order": 1
        },
        {
            "subject_area": "Web Development",
            "topic_title": "HTML5 Semantic Elements",
            "topic_description": "Master HTML5 semantic elements for better web structure",
            "difficulty_level": "beginner",
            "estimated_hours": 3,
            "learning_objectives": ["Use semantic HTML elements", "Structure web pages properly", "Improve accessibility"],
            "subtopics": ["header", "nav", "main", "section", "article", "aside", "footer"],
            "suggested_order": 1
        }
    ]
    
    for t_data in topic_templates:
        topic = AITopicTemplate(
            subject_area=t_data["subject_area"],
            topic_title=t_data["topic_title"],
            topic_description=t_data["topic_description"],
            difficulty_level=t_data["difficulty_level"],
            estimated_hours=t_data["estimated_hours"],
            learning_objectives=json.dumps(t_data["learning_objectives"]),
            subtopics=json.dumps(t_data["subtopics"]),
            suggested_order=t_data["suggested_order"]
        )
        db.session.add(topic)
    
    db.session.commit()
    print("✅ Sample AI course templates and questions created!")
    print(f"✅ Total course templates: {AICourseTemplate.query.count()}")
    print(f"✅ Total AI questions: {AIQuestionBank.query.count()}")
    print(f"✅ Total topic templates: {AITopicTemplate.query.count()}")
    
    # Verify table creation
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    ai_tables = [t for t in tables if 'ai_' in t.lower() or 'course_generation' in t.lower()]
    print(f"\n✅ AI-related tables created: {ai_tables}")
    
    print("\n🎉 AI Course Generation System is ready!")
    print("📝 Lecturers can now:")
    print("   • Generate complete courses with AI")
    print("   • Preview and customize course content")
    print("   • Create challenging questions automatically")
    print("   • Use popular templates")
    print("   • Build courses like GeeksforGeeks!")