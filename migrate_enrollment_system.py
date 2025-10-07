from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # Add new columns to CourseEnrollment table
        print("Updating CourseEnrollment table...")
        
        # Check if columns already exist before adding
        result = db.session.execute(text("PRAGMA table_info(course_enrollment)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'enrollment_number' not in columns:
            db.session.execute(text("ALTER TABLE course_enrollment ADD COLUMN enrollment_number VARCHAR(20)"))
            print("✅ Added enrollment_number column")
            
        if 'student_name' not in columns:
            db.session.execute(text("ALTER TABLE course_enrollment ADD COLUMN student_name VARCHAR(200)"))
            print("✅ Added student_name column")
            
        if 'student_email' not in columns:
            db.session.execute(text("ALTER TABLE course_enrollment ADD COLUMN student_email VARCHAR(200)"))
            print("✅ Added student_email column")
            
        if 'enrollment_status' not in columns:
            db.session.execute(text("ALTER TABLE course_enrollment ADD COLUMN enrollment_status VARCHAR(20) DEFAULT 'active'"))
            print("✅ Added enrollment_status column")
            
        if 'certificate_issued' not in columns:
            db.session.execute(text("ALTER TABLE course_enrollment ADD COLUMN certificate_issued BOOLEAN DEFAULT 0"))
            print("✅ Added certificate_issued column")
            
        if 'final_grade' not in columns:
            db.session.execute(text("ALTER TABLE course_enrollment ADD COLUMN final_grade VARCHAR(5)"))
            print("✅ Added final_grade column")
        
        db.session.commit()
        
        # Update existing enrollments with missing data
        from app import CourseEnrollment, User, generate_enrollment_number
        
        enrollments_to_update = CourseEnrollment.query.filter(
            CourseEnrollment.enrollment_number == None
        ).all()
        
        print(f"Updating {len(enrollments_to_update)} existing enrollments...")
        
        for enrollment in enrollments_to_update:
            # Generate enrollment number
            enrollment.enrollment_number = generate_enrollment_number(enrollment.course_id)
            
            # Get user data
            user = db.session.get(User, enrollment.user_id)
            if user:
                enrollment.student_name = user.username
                enrollment.student_email = user.email
            
            enrollment.enrollment_status = 'active'
            enrollment.certificate_issued = False
        
        db.session.commit()
        
        print("✅ Student course enrollment system updated successfully!")
        print("📝 New features:")
        print("   • Automatic enrollment number generation")
        print("   • Student profile data integration")
        print("   • Enrollment status tracking")
        print("   • Course progress management")
        print("   • Certificate system preparation")
        
        # Verify the update
        total_enrollments = CourseEnrollment.query.count()
        enrollments_with_numbers = CourseEnrollment.query.filter(
            CourseEnrollment.enrollment_number != None
        ).count()
        
        print(f"\n📊 Enrollment Statistics:")
        print(f"   Total enrollments: {total_enrollments}")
        print(f"   With enrollment numbers: {enrollments_with_numbers}")
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        db.session.rollback()
        raise