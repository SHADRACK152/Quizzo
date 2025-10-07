#!/usr/bin/env python3
"""
Migration script to add study materials and self-paced courses features
Run this to update your database with the new tables
"""

from app import app, db
from sqlalchemy import text

def migrate_database():
    """Add new tables for study materials and self-paced courses"""
    
    with app.app_context():
        try:
            print("🚀 Starting database migration for study features...")
            
            # Create all new tables
            db.create_all()
            
            print("✅ Database migration completed successfully!")
            print("📚 Added Study Materials features:")
            print("   - StudyMaterial table")
            print("   - MaterialBookmark table") 
            print("   - MaterialRating table")
            
            print("🎓 Added Self-Paced Courses features:")
            print("   - Course table")
            print("   - Lesson table")
            print("   - CourseEnrollment table")
            print("   - LessonProgress table")
            print("   - CourseReview table")
            
            # Add some sample study materials
            print("📖 Adding sample study materials...")
            add_sample_study_materials()
            
            # Add sample courses
            print("📝 Adding sample courses...")
            add_sample_courses()
            
            print("🎉 Migration completed! Your QUIZZO platform now has:")
            print("   ✓ Study materials search and bookmarking")
            print("   ✓ Self-paced courses with progress tracking")
            print("   ✓ Course reviews and ratings")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.session.rollback()

def add_sample_study_materials():
    """Add some sample study materials"""
    from app import StudyMaterial
    
    try:
        sample_materials = [
            {
                'title': 'Khan Academy Biology',
                'description': 'Comprehensive biology course covering cells, genetics, evolution and more',
                'url': 'https://www.khanacademy.org/science/biology',
                'category': 'biology',
                'material_type': 'interactive',
                'difficulty_level': 'intermediate',
                'source': 'Khan Academy',
                'rating': 4.8,
                'added_by': 1,
                'tags': 'biology,cells,genetics,evolution,free'
            },
            {
                'title': 'Coursera Chemistry Course',
                'description': 'Introduction to general chemistry principles and lab techniques',
                'url': 'https://www.coursera.org/learn/general-chemistry',
                'category': 'chemistry',
                'material_type': 'video',
                'difficulty_level': 'beginner',
                'source': 'Coursera',
                'rating': 4.6,
                'added_by': 1,
                'tags': 'chemistry,general,lab,principles'
            },
            {
                'title': 'MIT Physics Lectures',
                'description': 'Advanced physics lectures from MIT OpenCourseWare',
                'url': 'https://ocw.mit.edu/courses/physics/',
                'category': 'physics',
                'material_type': 'video',
                'difficulty_level': 'advanced',
                'source': 'MIT OCW',
                'rating': 4.9,
                'added_by': 1,
                'tags': 'physics,MIT,advanced,mechanics,quantum'
            },
            {
                'title': 'Python Programming for Beginners',
                'description': 'Learn Python programming from scratch with practical examples',
                'url': 'https://www.python.org/about/gettingstarted/',
                'category': 'programming',
                'material_type': 'article',
                'difficulty_level': 'beginner',
                'source': 'Python.org',
                'rating': 4.5,
                'added_by': 1,
                'tags': 'python,programming,beginner,coding'
            },
            {
                'title': 'Calculus Made Easy',
                'description': 'Step-by-step calculus tutorials with visual explanations',
                'url': 'https://www.paulsOnlineMathNotes.com/calculus/',
                'category': 'mathematics',
                'material_type': 'article',
                'difficulty_level': 'intermediate',
                'source': 'Paul\'s Online Math Notes',
                'rating': 4.7,
                'added_by': 1,
                'tags': 'calculus,mathematics,tutorial,visual'
            }
        ]
        
        for material_data in sample_materials:
            # Check if material already exists
            existing = StudyMaterial.query.filter_by(url=material_data['url']).first()
            if not existing:
                material = StudyMaterial(**material_data)
                db.session.add(material)
        
        db.session.commit()
        print(f"   ✓ Added {len(sample_materials)} sample study materials")
        
    except Exception as e:
        print(f"   ❌ Error adding sample materials: {str(e)}")
        db.session.rollback()

def add_sample_courses():
    """Add some sample self-paced courses"""
    from app import Course, Lesson
    
    try:
        # Sample course
        course_data = {
            'title': 'Introduction to Data Science',
            'description': 'Learn the fundamentals of data science including Python, statistics, and machine learning',
            'instructor_id': 1,
            'category': 'data_science',
            'difficulty_level': 'beginner',
            'estimated_duration_hours': 20,
            'is_published': True,
            'prerequisites': 'Basic computer skills',
            'learning_objectives': 'Understand data analysis, learn Python basics, create visualizations'
        }
        
        # Check if course already exists
        existing_course = Course.query.filter_by(title=course_data['title']).first()
        if not existing_course:
            course = Course(**course_data)
            db.session.add(course)
            db.session.flush()  # Get the course ID
            
            # Add sample lessons
            lessons = [
                {
                    'course_id': course.id,
                    'title': 'Introduction to Data Science',
                    'content': '<h2>Welcome to Data Science!</h2><p>In this lesson, you\'ll learn what data science is and why it\'s important...</p>',
                    'lesson_type': 'text',
                    'duration_minutes': 30,
                    'order_index': 1,
                    'is_published': True
                },
                {
                    'course_id': course.id,
                    'title': 'Python Basics for Data Science',
                    'content': '<h2>Python Fundamentals</h2><p>Let\'s start with Python programming basics...</p>',
                    'lesson_type': 'text',
                    'duration_minutes': 45,
                    'order_index': 2,
                    'is_published': True
                },
                {
                    'course_id': course.id,
                    'title': 'Working with Data',
                    'content': '<h2>Data Manipulation</h2><p>Learn how to clean and manipulate data...</p>',
                    'lesson_type': 'text',
                    'duration_minutes': 60,
                    'order_index': 3,
                    'is_published': True
                }
            ]
            
            for lesson_data in lessons:
                lesson = Lesson(**lesson_data)
                db.session.add(lesson)
            
            db.session.commit()
            print(f"   ✓ Added sample course: {course.title} with {len(lessons)} lessons")
        
    except Exception as e:
        print(f"   ❌ Error adding sample courses: {str(e)}")
        db.session.rollback()

if __name__ == '__main__':
    migrate_database()